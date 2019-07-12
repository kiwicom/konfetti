"""These tests are executed in subprocess, otherwise pytest segfaults for some reason."""
from decimal import Decimal
from typing import Coroutine

import aiohttp
import pytest
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt

from konfetti import env, Konfig
from konfetti._async import make_async_callback, make_simple_coro
from konfetti.exceptions import KonfettiError, MissingError, SecretKeyMissing
from konfetti.utils import NOT_SET
from konfetti.vault import AsyncVaultBackend

pytestmark = [pytest.mark.asyncio, pytest.mark.async_vault, pytest.mark.usefixtures("env", "vault_data")]

# Parametrize tests somehow? Async vs sync


@pytest.mark.parametrize(
    "option, expected",
    (
        ("SECRET", "value"),
        ("WHOLE_SECRET", {"SECRET": "value", "IS_SECRET": True, "DECIMAL": "1.3"}),
        ("NESTED_SECRET", "what?"),
        ("DECIMAL", Decimal("1.3")),
    ),
)
async def test_async_vault_access(config, option, expected):
    # All config options are coros on access and should be awaited
    variable = getattr(config, option)
    assert isinstance(variable, Coroutine)
    assert await variable == expected


async def test_missing_key(config):
    """The given key could be absent in vault data."""
    with pytest.raises(
        SecretKeyMissing, match="Path `path/to` exists in Vault but does not contain given key path - `ANOTHER_SECRET`"
    ):
        await config.ANOTHER_SECRET


async def test_missing_variable(config, vault_prefix):
    with pytest.raises(
        MissingError, match="Option `{}/something/missing` is not present in Vault".format(vault_prefix)
    ):
        await config.NOT_IN_VAULT


async def test_get_secret(config):
    assert await config.get_secret("path/to") == {"SECRET": "value", "IS_SECRET": True, "DECIMAL": "1.3"}


@pytest.mark.parametrize("action", (lambda c: c.get_secret("path/to"), lambda c: c.SECRET))
async def test_disable_secrets(config, monkeypatch, action):
    # This option completely disables Vault access
    monkeypatch.setenv("KONFETTI_DISABLE_SECRETS", "1")
    with pytest.raises(
        RuntimeError,
        match="Access to vault is disabled. Unset `KONFETTI_DISABLE_SECRETS` environment variable to enable it.",
    ):
        await action(config)


async def test_override_with_default(config, monkeypatch):
    # Override has higher priority than default
    monkeypatch.setenv("PATH__TO", '{"DEFAULT": "non-default"}')
    assert await config.DEFAULT == "non-default"


@pytest.mark.parametrize("url", ("http://localhost:8200", "http://localhost:8200/"))
async def test_get_full_url(url):
    # Slashes don't matter
    from konfetti.vault.asynchronous import _get_full_url

    assert _get_full_url(url, "path/to") == "http://localhost:8200/v1/path/to"


async def test_make_async_callback():
    async def coro():
        return 1

    def callback(value):
        return value + 1

    assert await make_async_callback(coro(), callback) == 2


async def test_make_simple_coro():
    coro = make_simple_coro(1)
    assert isinstance(coro, Coroutine)
    assert await coro == 1


@pytest.fixture
def config_with_cached_vault(vault_prefix):
    return Konfig(vault_backend=AsyncVaultBackend(vault_prefix, cache_ttl=1))


SECRET_DATA = {"DECIMAL": "1.3", "IS_SECRET": True, "SECRET": "value"}


async def test_cold_cache(config_with_cached_vault, vault_prefix, mocker):
    # Cache is empty, data is taken from vault
    assert await config_with_cached_vault.get_secret("/path/to") == SECRET_DATA
    # Response is cached
    assert config_with_cached_vault.vault_backend.cache._data == {
        vault_prefix + "/path/to": {"data": SECRET_DATA, "inserted": mocker.ANY}
    }


async def test_warm_cache(config_with_cached_vault, vault_prefix, mocker):
    await test_cold_cache(config_with_cached_vault, vault_prefix, mocker)
    vault = mocker.patch("aiohttp.ClientSession.get")
    # Cache is warmed and contains the secret
    assert await config_with_cached_vault.get_secret("/path/to") == SECRET_DATA
    assert config_with_cached_vault.vault_backend.cache[vault_prefix + "/path/to"] == SECRET_DATA

    assert not vault.called


@pytest.mark.freeze_time
async def test_no_recaching(config_with_cached_vault, mocker, freezer, vault_token):
    # Regression. Options were re-cached after taken from cache
    assert await config_with_cached_vault.get_secret("/path/to") == SECRET_DATA
    freezer.tick(0.5)
    async with aiohttp.ClientSession(headers={"X-Vault-Token": vault_token}) as session:
        vault = mocker.patch("aiohttp.ClientSession.get", wraps=session.get)
        assert await config_with_cached_vault.get_secret("/path/to") == SECRET_DATA
        assert not vault.called
        freezer.tick(0.6)
        assert await config_with_cached_vault.get_secret("/path/to")
        assert vault.called


async def test_asdict(monkeypatch, vault_prefix, vault_addr, vault_token):
    # All options, including dicts should be evaluated
    monkeypatch.setenv("KONFETTI_SETTINGS", "test_app.settings.subset")
    config = Konfig(vault_backend=AsyncVaultBackend(vault_prefix))
    assert await config.asdict() == {
        "DEBUG": True,
        "SECRET": "value",
        "KEY": "value",
        "VAULT_ADDR": vault_addr,
        "VAULT_TOKEN": vault_token,
        "NESTED_SECRET": "what?",
        "WHOLE_SECRET": {"DECIMAL": "1.3", "IS_SECRET": True, "SECRET": "value"},
        "DICTIONARY": {"env": True, "static": 1, "vault": "value"},
    }


async def test_asdict_shortcut(vault_prefix, vault_addr, vault_token):
    # If there are no coroutines - nothing should be awaited

    class TestSettings:
        SECRET = 1
        VAULT_ADDR = env("VAULT_ADDR")
        VAULT_TOKEN = env("VAULT_TOKEN")

    config = Konfig.from_object(TestSettings, vault_backend=AsyncVaultBackend(vault_prefix))
    assert await config.asdict() == {"SECRET": 1, "VAULT_ADDR": vault_addr, "VAULT_TOKEN": vault_token}


async def test_retry(config, mocker):
    mocker.patch("aiohttp.ClientSession._request", side_effect=aiohttp.ClientConnectionError)
    m = mocker.patch.object(config.vault_backend, "_call", wraps=config.vault_backend._call)
    with pytest.raises(aiohttp.ClientConnectionError):
        await config.SECRET
    assert m.called is True
    assert m.call_count == 3


async def test_retry_object(vault_prefix, mocker):
    config = Konfig(
        vault_backend=AsyncVaultBackend(
            vault_prefix,
            retry=AsyncRetrying(retry=retry_if_exception_type(KonfettiError), reraise=True, stop=stop_after_attempt(2)),
        )
    )
    mocker.patch("aiohttp.ClientSession._request", side_effect=KonfettiError)
    m = mocker.patch.object(config.vault_backend, "_call", wraps=config.vault_backend._call)
    with pytest.raises(KonfettiError):
        await config.SECRET
    assert m.called is True
    assert m.call_count == 2


@pytest.mark.parametrize("token", ("token_removed", "token_expired"))
async def test_userpass(config, monkeypatch, token):
    if token == "token_removed":
        monkeypatch.delenv("VAULT_TOKEN")
    else:
        monkeypatch.setenv("VAULT_TOKEN", token)
    monkeypatch.setenv("VAULT_USERNAME", "test_user")
    monkeypatch.setenv("VAULT_PASSWORD", "test_password")
    assert await config.SECRET == "value"


async def test_invalid_token(config, monkeypatch):
    monkeypatch.setenv("VAULT_TOKEN", "invalid")
    with pytest.raises(aiohttp.client_exceptions.ClientResponseError):
        await config.SECRET


async def test_userpass_cache(config_with_cached_vault, vault_prefix, mocker, monkeypatch):
    monkeypatch.delenv("VAULT_TOKEN")
    monkeypatch.setenv("VAULT_USERNAME", "test_user")
    monkeypatch.setenv("VAULT_PASSWORD", "test_password")
    await test_cold_cache(config_with_cached_vault, vault_prefix, mocker)
    vault = mocker.patch("aiohttp.ClientSession.get")
    # Cache is warmed and contains the secret
    assert await config_with_cached_vault.get_secret("/path/to") == SECRET_DATA
    assert config_with_cached_vault.vault_backend.cache[vault_prefix + "/path/to"] == SECRET_DATA

    assert not vault.called


async def test_userpass_token_cache(config, monkeypatch, mocker):
    monkeypatch.delenv("VAULT_TOKEN")
    monkeypatch.setenv("VAULT_USERNAME", "test_user")
    monkeypatch.setenv("VAULT_PASSWORD", "test_password")
    # First time access / auth
    auth = mocker.patch("konfetti.AsyncVaultBackend._auth_userpass", wraps=config.vault_backend._auth_userpass)
    assert config.vault_backend._token is NOT_SET
    assert await config.SECRET == "value"
    assert auth.called is True
    assert auth.call_count == 1
    assert config.vault_backend._token is not NOT_SET
    # Second time access / no auth
    auth = mocker.patch("konfetti.AsyncVaultBackend._auth_userpass", wraps=config.vault_backend._auth_userpass)
    first_token = config.vault_backend._token
    assert await config.IS_SECRET is True
    assert auth.called is False
    assert config.vault_backend._token == first_token
