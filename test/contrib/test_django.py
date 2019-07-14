from contextlib import closing, contextmanager
import os
import signal
import socket
from subprocess import Popen
import time

import django
from django.conf import settings
from django.test import override_settings
import pytest
import requests

pytestmark = [pytest.mark.usefixtures("env", "vault_data", "django_setup")]

PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("", 0))
    with closing(sock):
        return str(sock.getsockname()[1])


@pytest.fixture(scope="session")
def django_setup(vault_prefix):
    os.environ["VAULT_PREFIX"] = vault_prefix
    os.environ["DJANGO_SETTINGS_MODULE"] = "django_app.settings"
    django.setup()
    yield
    os.environ.pop("DJANGO_SETTINGS_MODULE", None)


def test_config():
    # via konfetti
    assert settings.DEBUG
    # Django's important option
    assert settings.SECRET_KEY == "foo"
    # Vault
    assert settings.SECRET == "value"
    # From extension
    assert settings.KEY == 42
    # From Django's global settings
    assert settings.ALLOWED_HOSTS == []


def test_access_methods():
    """Default settings methods are accessible."""
    with pytest.raises(RuntimeError, match="already configured"):
        settings.configure()


def test_settings_access():
    """When `setting` are accessed in this way after patching."""
    # Explicit import to check how custom __getattribute__ is working
    from django.conf import settings

    assert settings.SECRET == "value"


@override_settings(ALLOWED_HOSTS=["localhost"])
def test_override_global():
    # Overriding an option defined in Django's global settings
    assert settings.ALLOWED_HOSTS == ["localhost"]


@override_settings(SECRET_KEY="bar")
def test_override_local():
    # Defined on the project level
    assert settings.SECRET_KEY == "bar"


def test_override_vault():
    """Django tests utils."""
    assert settings.SECRET == "value"
    with override_settings(SECRET="bar", ALLOWED_HOSTS=["not-local"]):
        assert settings.SECRET == "bar"
        assert settings.ALLOWED_HOSTS == ["not-local"]
    assert settings.SECRET == "value"


def test_konfetti_override():
    """Konfetti override."""
    assert settings.SECRET == "value"
    with settings.override(SECRET="bar", ALLOWED_HOSTS=["not-local"]):
        assert settings.SECRET == "bar"
        assert settings.ALLOWED_HOSTS == ["not-local"]
    assert settings.SECRET == "value"


@pytest.fixture
def django_server(monkeypatch, vault_data, vault_prefix):
    monkeypatch.setenv("PYTHONPATH", PATH)
    port = get_free_port()
    with run(("django-admin", "runserver", port, "-v3"), lambda: wait_until(port)):
        yield port


@contextmanager
def run(args, preparation):
    popen = Popen(args, env=os.environ, close_fds=True, preexec_fn=os.setsid)
    preparation()
    yield
    try:
        # Process group is required for Python 2.7
        os.killpg(os.getpgid(popen.pid), signal.SIGTERM)
    except OSError:
        pass


def wait_until(port, max_timeout=5):
    start = time.time()
    while time.time() - start <= max_timeout:
        try:
            requests.get("http://127.0.0.1:{}/ping".format(port))
            return True
        except requests.exceptions.ConnectionError:
            pass
    raise RuntimeError


def test_django_runserver(django_server, vault_addr, vault_token):
    response = requests.get("http://127.0.0.1:{}/".format(django_server))
    assert response.json() == {
        "DEBUG": True,
        "KEY": 42,
        "REQUIRED": "important",
        "ROOT_URLCONF": "django_app.views",
        "SECRET": "value",
        "SECRET_KEY": "foo",
        "VAULT_ADDR": vault_addr,
        "VAULT_TOKEN": vault_token,
    }
