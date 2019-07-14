from flask import Flask
import pytest

from konfetti import Konfig, VaultBackend
from konfetti.contrib.flask import FlaskKonfig

pytestmark = [pytest.mark.usefixtures("settings", "env", "vault_data")]


@pytest.fixture
def app():
    return Flask("testing")


CUSTOM_KWARGS = {"SOMETHING": 1, "SERVER_NAME": "test"}


def test_init_app(app):
    # The same API is available after the extension init
    assert not app.config["TESTING"]
    config = FlaskKonfig()
    config.init_app(app, **CUSTOM_KWARGS)
    assert_config(app.config)
    # All methods are available
    app.config.from_envvar
    assert not app.config["TESTING"]


def test_init(app):
    FlaskKonfig(app, **CUSTOM_KWARGS)
    assert_config(app.config)


def test_config_instance(app, vault_prefix):
    config = Konfig(vault_backend=VaultBackend(vault_prefix), strict_override=False)
    FlaskKonfig(app, konfig=config, **CUSTOM_KWARGS)
    assert_config(app.config)
    assert app.config.SECRET == "value"


def assert_config(config):
    # All options are available via __getitem__ like in Flask.config and via __getattr__ as in konfetti
    # Settings module
    assert config.KEY == "value"
    assert config["KEY"] == "value"
    # Flask config
    assert config.SESSION_COOKIE_NAME == "session"
    assert config["SESSION_COOKIE_NAME"] == "session"
    # Directly specified
    assert config.SOMETHING == 1
    assert config["SOMETHING"] == 1
    # Overridden via explicit kwarg
    assert config.SERVER_NAME == "test"
    assert config["SERVER_NAME"] == "test"
