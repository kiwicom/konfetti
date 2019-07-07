import os
import sys
from types import ModuleType
import uuid

import hvac
import pytest

from konfetti.core import Konfig
from konfetti.vault import VaultBackend

pytest_plugins = ["pytester"]

VAULT_ADDR = os.getenv("TEST_VAULT_ADDR", "http://localhost:8200")
VAULT_TOKEN = os.getenv("VAULT_DEV_ROOT_TOKEN_ID", "test_root_token")

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(scope="session")
def vault_prefix():
    """Random prefix is needed to avoid clashes in parallel runs and reuse the same Vault instance."""
    return "secret/team/" + str(uuid.uuid4().hex)


@pytest.fixture
def config(request, vault_prefix):
    marker = request.node.get_closest_marker("async_vault")
    if marker:
        from konfetti.vault import AsyncVaultBackend as vault_backend
    else:
        vault_backend = VaultBackend
    yield Konfig(vault_backend=vault_backend(vault_prefix))
    sys.modules.pop("settings.production", None)


@pytest.fixture()
def vault_addr():
    return VAULT_ADDR


@pytest.fixture()
def vault_token():
    return VAULT_TOKEN


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("KONFETTI_SETTINGS", "test_app.settings.production")
    monkeypatch.setenv("VAULT_ADDR", VAULT_ADDR)
    monkeypatch.setenv("VAULT_TOKEN", VAULT_TOKEN)
    monkeypatch.setenv("REQUIRED", "important")


@pytest.fixture
def settings(testdir, env, vault_prefix):
    """Setting module to test."""
    settings = testdir.mkdir("settings")
    settings.ensure("__init__.py").write(
        """
from konfetti import Konfig
from konfetti.vault import VaultBackend

config = Konfig(vault_backend=VaultBackend("{}"))
""".format(
            vault_prefix
        )
    )
    with open(os.path.join(CURRENT_DIR, "test_app/settings/production.py")) as fd:
        settings.ensure("production.py").write(fd.read())
    return settings


@pytest.fixture(autouse=True, scope="session")
def vault_data(vault_prefix):
    # works with dev vault docker image
    # docker run -p 8200:8200 -d --cap-add=IPC_LOCK -e 'VAULT_DEV_ROOT_TOKEN_ID=test_root_token' vault:0.9.6

    vault = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)
    data = {
        vault_prefix + "/path/to": {"SECRET": "value", "IS_SECRET": True, "DECIMAL": "1.3"},
        vault_prefix + "/path/to/cast": {"DECIMAL": 1.3, "DATE": "2019-01-25", "DATETIME": "2019-01-25T14:35:05"},
        vault_prefix + "/path/to/nested": {"NESTED_SECRET": {"nested": "what?"}},
        vault_prefix + "/path/to/file": {"SECRET_FILE": "content\nanother_line"},
    }
    for key, values in data.items():
        vault.write(key, **values)
    yield
    for key in data:
        vault.delete(key)


@pytest.fixture
def mocked_import_config_module(mocker):
    module = ModuleType("fake")
    module.EXAMPLE = "test"
    module.SOMETHING = "else"
    return mocker.patch("konfetti.loaders.import_config_module", return_value=module)
