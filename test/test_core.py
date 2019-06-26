import os
import sys

from dotenv import load_dotenv
import pytest

from kwonfig.core import import_config_module, KWonfig
from kwonfig.exceptions import MissingError, SettingsNotLoadable, SettingsNotSpecified
from kwonfig.vault import VaultBackend

pytestmark = [pytest.mark.usefixtures("settings")]


def test_simple_var_access(config):
    """Global instance should provide access to actual module attributes."""
    assert "settings.production" not in sys.modules
    assert config.KEY == "value"


def test_forbid_setattr(config):
    """`setattr` is forbidden for options in KWonfig."""
    with pytest.raises(AttributeError):
        config.KEY = "value"


def test_missing_variable(config):
    """If the accessed option is missing it should rise an error."""
    with pytest.raises(MissingError, match="Option `MISSING` is not present in "):
        config.MISSING


def test_no_reinitialization(mocked_import_config_module):
    """When config instance is accessed second time, the underlying module is not re-imported."""
    config = KWonfig()
    for _ in (1, 2):
        assert config.EXAMPLE == "test"
        # Py2.7, Py3.5: replace with `assert_called_once` when 2.7/3.5 support will be dropped.
        assert mocked_import_config_module.called is True
        assert mocked_import_config_module.call_count == 1


def test_config_module_not_exists(config, monkeypatch):
    """If there is no settings module found on init, an error should occur."""
    monkeypatch.setenv(config.config_variable_name, "not.exist")
    with pytest.raises(SettingsNotLoadable, match=r"Unable to load configuration file `not.exist`"):
        config.MISSING


def test_config_var_not_specified(config, monkeypatch):
    """If config is not specified, an error should occur."""
    monkeypatch.delenv(config.config_variable_name)
    with pytest.raises(SettingsNotSpecified, match="The environment variable `KWONFIG` is not set"):
        config.MISSING


def test_exception_in_config_module(config, monkeypatch):
    """If an exception occurred during loading of the config module, a proper exception should be propagated."""
    monkeypatch.setenv(config.config_variable_name, "test_app.settings.invalid")
    with pytest.raises(ZeroDivisionError):
        config.MISSING


def test_import_single_string_module(config, monkeypatch):
    # A case without "." in the module path
    monkeypatch.setenv(config.config_variable_name, "sys")
    assert import_config_module(config.config_variable_name) is sys


def test_custom_config_variable_name(monkeypatch):
    # Config variable name is customizable
    config = KWonfig(config_variable_name="APP_CONFIG")
    monkeypatch.setenv("APP_CONFIG", "test_app.settings.production")
    assert config.KEY == "value"


@pytest.mark.usefixtures("mocked_import_config_module")
def test_require():
    """Validate config and raise proper exception if required variables are missing."""
    config = KWonfig()
    with pytest.raises(MissingError, match=r"Options \['MISSING', 'YET_ANOTHER_MISSING'\] are required"):
        config.require("MISSING", "YET_ANOTHER_MISSING")


@pytest.mark.usefixtures("mocked_import_config_module")
def test_require_ok():
    config = KWonfig()
    assert config.require("EXAMPLE") is None


@pytest.mark.usefixtures("mocked_import_config_module")
def test_require_nothing():
    """Given keys should contain at least one element."""
    config = KWonfig()
    with pytest.raises(RuntimeError, match="You need to specify at least one key"):
        config.require()


def test_dotenv(testdir):
    settings = testdir.tmpdir.ensure_dir("settings")
    settings.ensure(".env").write("FROM_DOTENV=loaded")
    config = KWonfig(dotenv=os.path.join(str(settings), ".env"))
    assert config.FROM_DOTENV == "loaded"


@pytest.mark.parametrize("override, expected_value", ((True, "loaded"), (False, "loaded_from_env")))
def test_dotenv_override(testdir, monkeypatch, override, expected_value):
    # If something is already present in env we can decide should it be overridden from .env or not
    settings = testdir.tmpdir.ensure_dir("settings")
    settings.ensure(".env").write("FROM_DOTENV=loaded")
    monkeypatch.setenv("FROM_DOTENV", "loaded_from_env")
    config = KWonfig(dotenv=os.path.join(str(settings), ".env"), dotenv_override=override)
    assert config.FROM_DOTENV == expected_value


def test_dotenv_reloading(testdir, mocker):
    """The dotenv file shouldn't be reloaded after first time."""
    settings = testdir.tmpdir.ensure_dir("settings")
    settings.ensure(".env").write("FROM_DOTENV=loaded")
    config = KWonfig(dotenv=os.path.join(str(settings), ".env"), dotenv_override=True)
    load_env = mocker.patch("kwonfig.core.load_dotenv", wraps=load_dotenv)
    assert config.FROM_DOTENV == "loaded"
    assert load_env.called

    load_env.reset_mock()
    assert config.FROM_DOTENV == "loaded"
    assert not load_env.called


@pytest.mark.parametrize("key, result", (("SECRET", True), ("MISSING", False)))
def test_contains(config, key, result):
    assert (key in config) is result


def test_contains_invalid(config):
    # Only strings are allowed
    with pytest.raises(TypeError, match="Config options names are strings, got: `int`"):
        1 in config


def test_contains_override():
    config = KWonfig(strict_override=False)
    with config.override(MISSING="awesome"):
        with config.override():
            assert "MISSING" in config


def test_asdict(monkeypatch, vault_prefix, vault_addr, vault_token):
    monkeypatch.setenv("KWONFIG", "test_app.settings.subset")
    config = KWonfig(vault_backend=VaultBackend(vault_prefix))
    assert config.asdict() == {
        "DEBUG": True,
        "SECRET": "value",
        "KEY": "value",
        "VAULT_ADDR": vault_addr,
        "VAULT_TOKEN": vault_token,
        "NESTED_SECRET": "what?",
        "WHOLE_SECRET": {"DECIMAL": "1.3", "IS_SECRET": True, "SECRET": "value"},
        "DICTIONARY": {"static": 1, "env": True, "vault": "value"},
    }


def test_vault_override_variables(monkeypatch, vault_prefix):
    monkeypatch.setenv("KWONFIG", "test_app.settings.subset")
    config = KWonfig(vault_backend=VaultBackend(vault_prefix))
    assert config.vault.get_override_examples() == {
        "NESTED_SECRET": {"PATH__TO__NESTED": '{"NESTED_SECRET": {"nested": "example_value"}}'},
        "SECRET": {"PATH__TO": '{"SECRET": "example_value"}'},
        "WHOLE_SECRET": {"PATH__TO": "{}"},
    }


def test_vault_override_variables_cache(monkeypatch, vault_prefix):
    monkeypatch.setenv("KWONFIG", "test_app.settings.subset")
    config = KWonfig(vault_backend=VaultBackend(vault_prefix))
    assert config.vault is config.vault
    assert config.vault.get_override_examples() is config.vault.get_override_examples()
