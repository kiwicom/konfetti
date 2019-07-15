import os
import sys

from dotenv import load_dotenv
import pytest

from konfetti import env, vault
from konfetti.core import get_config_option_names, Konfig
from konfetti.exceptions import MissingError, SettingsNotLoadable, SettingsNotSpecified
from konfetti.utils import import_config_module
from konfetti.vault import VaultBackend

pytestmark = [pytest.mark.usefixtures("settings")]

HERE = os.path.dirname(os.path.abspath(__file__))


def test_simple_var_access(config):
    """Global instance should provide access to actual module attributes."""
    assert "settings.production" not in sys.modules
    assert config.KEY == "value"


def test_forbid_setattr(config):
    """`setattr` is forbidden for options in Konfig."""
    with pytest.raises(AttributeError):
        config.KEY = "value"


def test_missing_variable(config):
    """If the accessed option is missing it should rise an error."""
    with pytest.raises(MissingError, match="Option `MISSING` is not present in "):
        config.MISSING


def test_no_reinitialization(mocked_import_config_module):
    """When config instance is accessed second time, the underlying module is not re-imported."""
    config = Konfig()
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
    with pytest.raises(SettingsNotSpecified, match="The environment variable `KONFETTI_SETTINGS` is not set"):
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
    config = Konfig(config_variable_name="APP_CONFIG")
    monkeypatch.setenv("APP_CONFIG", "test_app.settings.production")
    assert config.KEY == "value"


@pytest.mark.usefixtures("mocked_import_config_module")
def test_require():
    """Validate config and raise proper exception if required variables are missing."""
    config = Konfig()
    with pytest.raises(MissingError, match=r"Options \['MISSING', 'YET_ANOTHER_MISSING'\] are required"):
        config.require("MISSING", "YET_ANOTHER_MISSING")


@pytest.mark.usefixtures("mocked_import_config_module")
def test_require_ok():
    config = Konfig()
    assert config.require("EXAMPLE") is None


@pytest.mark.usefixtures("mocked_import_config_module")
def test_require_nothing():
    """Given keys should contain at least one element."""
    config = Konfig()
    with pytest.raises(RuntimeError, match="You need to specify at least one key"):
        config.require()


def test_dotenv(testdir):
    settings = testdir.tmpdir.ensure_dir("settings")
    settings.ensure(".env").write("FROM_DOTENV=loaded")
    config = Konfig(dotenv=os.path.join(str(settings), ".env"))
    assert config.FROM_DOTENV == "loaded"


@pytest.mark.parametrize("override, expected_value", ((True, "loaded"), (False, "loaded_from_env")))
def test_dotenv_override(testdir, monkeypatch, override, expected_value):
    # If something is already present in env we can decide should it be overridden from .env or not
    settings = testdir.tmpdir.ensure_dir("settings")
    settings.ensure(".env").write("FROM_DOTENV=loaded")
    monkeypatch.setenv("FROM_DOTENV", "loaded_from_env")
    config = Konfig(dotenv=os.path.join(str(settings), ".env"), dotenv_override=override)
    assert config.FROM_DOTENV == expected_value


def test_dotenv_reloading(testdir, mocker):
    """The dotenv file shouldn't be reloaded after first time."""
    settings = testdir.tmpdir.ensure_dir("settings")
    settings.ensure(".env").write("FROM_DOTENV=loaded")
    config = Konfig(dotenv=os.path.join(str(settings), ".env"), dotenv_override=True)
    load_env = mocker.patch("konfetti.core.load_dotenv", wraps=load_dotenv)
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
    config = Konfig(strict_override=False)
    with config.override(MISSING="awesome"):
        with config.override():
            assert "MISSING" in config


def test_asdict(monkeypatch, vault_prefix, vault_addr, vault_token):
    monkeypatch.setenv("KONFETTI_SETTINGS", "test_app.settings.subset")
    config = Konfig(vault_backend=VaultBackend(vault_prefix))
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


def test_dictionary_access(monkeypatch, vault_prefix):
    monkeypatch.setenv("KONFETTI_SETTINGS", "test_app.settings.subset")
    config = Konfig(vault_backend=VaultBackend(vault_prefix))
    assert config.DICTIONARY == {"static": 1, "env": True, "vault": "value"}


def test_from_object(vault_prefix, vault_addr, vault_token):
    class Test:
        VALUE = 42
        VAULT_ADDR = env("VAULT_ADDR")
        VAULT_TOKEN = env("VAULT_TOKEN")
        SECRET = vault("path/to")["SECRET"]

    config = Konfig.from_object(Test, vault_backend=VaultBackend(vault_prefix))
    assert config.asdict() == {"VALUE": 42, "SECRET": "value", "VAULT_ADDR": vault_addr, "VAULT_TOKEN": vault_token}


def test_from_mapping():
    config = Konfig.from_object({"VALUE": 42})
    assert config.asdict() == {"VALUE": 42}


def test_from_string(vault_prefix, vault_addr, vault_token):
    config = Konfig.from_object("test_app.settings.subset", vault_backend=VaultBackend(vault_prefix))
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


def test_from_json(vault_prefix):
    path = os.path.join(HERE, "test_app/settings/config.json")
    config = Konfig.from_json(path, vault_backend=VaultBackend(vault_prefix))
    assert config.asdict() == {"VALUE": "from json", "SECRET": 42}


def test_extend():
    from test_app.settings.single import config

    path = os.path.join(HERE, "test_app/settings/config.json")
    config.extend_with_json(path)
    assert config.asdict() == {"DEBUG": True, "KEY": "value", "VALUE": "from json", "SECRET": 42}


def test_extend_with_object():
    from test_app.settings.single import config

    config.extend_with_object({"FOO": "bar"})
    assert config.asdict() == {"DEBUG": True, "KEY": "value", "FOO": "bar"}


def test_config_options_uniqueness(config):
    """Config option names should not e duplicated from different configs."""
    config.extend_with_object({"NEW": 1})
    config.extend_with_object({"NEW": 2})
    config_options = get_config_option_names(config._conf)
    assert len(set(config_options)) == len(config_options)


def test_single_file():
    """Config object is defined in the same settings module."""
    from test_app.settings.single import config

    assert config.asdict() == {"DEBUG": True, "KEY": "value"}


def test_vault_override_variables(monkeypatch, vault_prefix):
    monkeypatch.setenv("KONFETTI_SETTINGS", "test_app.settings.subset")
    config = Konfig(vault_backend=VaultBackend(vault_prefix))
    assert config.vault.get_override_examples() == {
        "NESTED_SECRET": {"PATH__TO__NESTED": '{"NESTED_SECRET": {"nested": "example_value"}}'},
        "SECRET": {"PATH__TO": '{"SECRET": "example_value"}'},
        "WHOLE_SECRET": {"PATH__TO": "{}"},
    }


def test_vault_override_variables_cache(monkeypatch, vault_prefix):
    monkeypatch.setenv("KONFETTI_SETTINGS", "test_app.settings.subset")
    config = Konfig(vault_backend=VaultBackend(vault_prefix))
    assert config.vault is config.vault
    assert config.vault.get_override_examples() is config.vault.get_override_examples()


def test_callable_default(config):
    assert config.CALLABLE_DEFAULT == 42
