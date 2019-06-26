from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
import sys

import pytest

import kwonfig
from kwonfig import KWonfig
from kwonfig.exceptions import InvalidSecretOverrideError, MissingError, SecretKeyMissing, VaultBackendMissing
from kwonfig.utils import NOT_SET
from kwonfig.vault import VaultBackend
from kwonfig.vault.core import VaultVariable

pytestmark = [pytest.mark.usefixtures("env", "vault_data")]


@pytest.mark.parametrize(
    "option, expected",
    (
        ("SECRET", "value"),
        ("WHOLE_SECRET", {"SECRET": "value", "IS_SECRET": True, "DECIMAL": "1.3"}),
        ("NESTED_SECRET", "what?"),
        ("DECIMAL", Decimal("1.3")),
    ),
)
def test_vault_access(config, option, expected):
    assert getattr(config, option) == expected


def test_missing_key(config):
    """The given key could be absent in vault data."""
    with pytest.raises(
        SecretKeyMissing, match="Path `path/to` exists in Vault but does not contain given key path - `ANOTHER_SECRET`"
    ):
        assert config.ANOTHER_SECRET == "value"


def test_missing_variable(config, vault_prefix):
    with pytest.raises(
        MissingError, match="Option `{}/something/missing` is not present in Vault".format(vault_prefix)
    ):
        config.NOT_IN_VAULT


def test_missing_vault_backend():
    config = KWonfig()
    with pytest.raises(
        VaultBackendMissing,
        match="Vault backend is not configured. "
        "Please specify `vault_backend` option in your `KWonfig` initialization",
    ):
        config.SECRET


@pytest.mark.parametrize("path", ("/path/to/", "/path/to", "path/to/", "path/to"))
def test_get_secret(path, config):
    assert config.get_secret(path) == {"SECRET": "value", "IS_SECRET": True, "DECIMAL": "1.3"}


@pytest.mark.parametrize(
    "transform",
    (
        lambda x: x.center(len(x) + 2, "/"),  # /path/
        lambda x: x.rjust(len(x) + 1, "/"),  # /path
        lambda x: x.ljust(len(x) + 1, "/"),  # path/
    ),
)
def test_get_secret_with_prefix(vault_prefix, transform):
    """Trailing and leading slashes don't matter."""
    config = KWonfig(vault_backend=VaultBackend(transform(vault_prefix), try_env_first=False))
    assert config.get_secret("/path/to") == {"SECRET": "value", "IS_SECRET": True, "DECIMAL": "1.3"}


@pytest.mark.parametrize("action", (lambda c: c.get_secret("path/to"), lambda c: c.SECRET))
def test_disable_secrets(config, monkeypatch, action):
    monkeypatch.setenv("KIWI_CONFIG_DISABLE_SECRETS", "1")
    with pytest.raises(
        RuntimeError,
        match="Access to vault is disabled. Unset `KIWI_CONFIG_DISABLE_SECRETS` environment variable to enable it.",
    ):
        action(config)


def test_get_secret_without_vault_credentials(config, monkeypatch):
    monkeypatch.delenv("VAULT_ADDR")
    monkeypatch.delenv("VAULT_TOKEN")
    with pytest.raises(MissingError, match="""Can't access secret `/path/to` due"""):
        config.get_secret("/path/to")


@pytest.mark.parametrize("path, keys, expected", (("/path/to/", ["SECRET"], "PATH__TO"), ("path/to", [], "PATH__TO")))
def test_override_variable_name(path, keys, expected):
    variable = VaultVariable(path)
    for key in keys:
        variable = variable[key]
    assert variable.override_variable_name == expected


def test_path_not_string():
    if sys.version_info[0] == 2:
        message = "'path' must be <type 'str'>"
    else:
        message = "'path' must be <class 'str'>"
    with pytest.raises(TypeError, match=message):
        kwonfig.vault(1)


@pytest.mark.parametrize(
    "prefix, path, expected", ((NOT_SET, "path/to", "path/to"), ("secret/team", "path/to", "secret/team/path/to"))
)
def test_prefixes(prefix, path, expected):
    backend = VaultBackend(prefix)
    assert backend._get_full_path(path) == expected


def test_get_secret_file(config):
    file = config.SECRET_FILE
    assert isinstance(file, BytesIO)
    assert file.read() == b"content\nanother_line"


def test_override_secret(config, monkeypatch):
    monkeypatch.setenv("PATH__TO", '{"foo": "bar"}')
    assert config.get_secret("path/to") == {"foo": "bar"}
    assert config.get_secret("path/to")["foo"] == "bar"


def test_override_config_secret(config, monkeypatch):
    monkeypatch.setenv("PATH__TO", '{"SECRET": "bar"}')
    assert config.WHOLE_SECRET == {"SECRET": "bar"}
    assert config.SECRET == "bar"


@pytest.mark.parametrize("data", ("[1, 2]", "[invalid]"))
@pytest.mark.parametrize("action", (lambda config: config.get_secret("path/to"), lambda config: config.SECRET))
def test_override_invalid(config, monkeypatch, data, action):
    monkeypatch.setenv("PATH__TO", data)
    with pytest.raises(InvalidSecretOverrideError, match="`PATH__TO` variable should be a JSON-encoded dictionary"):
        action(config)


def test_default_config(config):
    assert config.DEFAULT == "default"


def test_override_with_default(config, monkeypatch):
    monkeypatch.setenv("PATH__TO", '{"DEFAULT": "non-default"}')
    assert config.DEFAULT == "non-default"


def test_disable_defaults(config, monkeypatch):
    monkeypatch.setenv("VAULT_DISABLE_DEFAULTS", "True")
    with pytest.raises(SecretKeyMissing):
        config.DEFAULT


@pytest.fixture
def config_with_cached_vault(vault_prefix):
    return KWonfig(vault_backend=VaultBackend(vault_prefix, cache_ttl=1))


SECRET_DATA = {"DECIMAL": "1.3", "IS_SECRET": True, "SECRET": "value"}


def test_cold_cache(config_with_cached_vault, vault_prefix):
    # Cache is empty, data is taken from vault
    assert not config_with_cached_vault.vault_backend.cache._data
    assert config_with_cached_vault.get_secret("/path/to") == SECRET_DATA
    # Response is cached
    data = config_with_cached_vault.vault_backend.cache._data
    # Straight comparison for dicts fails on Python 2.7 :(
    assert list(data) == [vault_prefix + "/path/to"]
    assert data[vault_prefix + "/path/to"]["data"] == SECRET_DATA


def test_warm_cache(config_with_cached_vault, vault_prefix, mocker):
    test_cold_cache(config_with_cached_vault, vault_prefix)
    vault = mocker.patch("hvac.Client.read")
    # Cache is warmed and contains the secret
    assert config_with_cached_vault.get_secret("/path/to") == SECRET_DATA
    assert config_with_cached_vault.vault_backend.cache[vault_prefix + "/path/to"] == SECRET_DATA

    assert not vault.called


@pytest.mark.freeze_time
def test_no_recaching(config_with_cached_vault, mocker, freezer):
    assert config_with_cached_vault.get_secret("/path/to") == SECRET_DATA
    freezer.tick(0.5)
    vault = mocker.patch("hvac.Client.read")
    assert config_with_cached_vault.get_secret("/path/to") == SECRET_DATA
    assert not vault.called
    freezer.tick(0.6)
    assert config_with_cached_vault.get_secret("/path/to")
    assert vault.called


def skip_if_python(version):
    return pytest.mark.skipif(sys.version_info[0] == version, reason="Doesnt work on Python {}".format(version))


@pytest.mark.parametrize(
    "ttl, exc_type, message",
    (
        pytest.param(10 ** 20, ValueError, r"'cache_ttl' should be in range \(0, 999999999\]", marks=skip_if_python(2)),
        pytest.param(10 ** 20, TypeError, r".*must be.*", marks=skip_if_python(3)),
        ('"', TypeError, r".*must be.*"),
    ),
)
def test_ttl(ttl, exc_type, message):
    with pytest.raises(exc_type, match=message):
        VaultBackend("path/to", cache_ttl=ttl)


def test_cast_decimal_warning(config):
    with pytest.warns(RuntimeWarning, match="Float to Decimal conversion detected, please use string or integer."):
        config.FLOAT_DECIMAL


def test_cast_date(config):
    assert config.DATE == date(year=2019, month=1, day=25)


def test_cast_datetime(config):
    assert config.DATETIME == datetime(year=2019, month=1, day=25, hour=14, minute=35, second=5)
