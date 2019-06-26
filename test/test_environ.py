import pytest

from kwonfig import env
from kwonfig.exceptions import MissingError
from kwonfig.mixins import _cast_boolean

pytestmark = [pytest.mark.usefixtures("settings", "env")]


def test_env_var_access(config, monkeypatch):
    """Env variables are accessed via `config.env`."""
    monkeypatch.setenv("DEBUG", "False")
    assert config.DEBUG is False


def test_env_var_invalid_boolean(config, monkeypatch):
    """If boolean value is not valid, it should rise an error."""
    monkeypatch.setenv("DEBUG", "ABC")
    with pytest.raises(ValueError, match="Not a boolean: `ABC`"):
        config.DEBUG


def test_env_var_default(config):
    """`default` should be used when env variable is not present in the environment."""
    assert config.DEBUG is True


def test_env_missing_without_default(config, monkeypatch):
    """If `default` is not specified and the variable is missing it should rise an error."""
    monkeypatch.delenv("REQUIRED")
    with pytest.raises(MissingError, match="Variable `REQUIRED` is not found and has no `default` specified"):
        config.REQUIRED


def test_env_var_int_cast(config, monkeypatch):
    """`cast` callable should be applied if specified."""
    monkeypatch.setenv("INTEGER", "56")
    assert config.INTEGER == 56


def test_env_var_as_string(monkeypatch):
    """Instance of EnvVariable is evaluated on `str` call."""
    monkeypatch.setenv("KEY", "value")
    assert str(env("KEY")) == "value"


@pytest.mark.parametrize("value, expected", (("true", True), ("TRUE", True), ("no", False)))
def test_cast_boolean_valid(value, expected):
    assert _cast_boolean(value) is expected


def test_cast_boolean_invalid():
    with pytest.raises(ValueError, match="Not a boolean: `ABC`"):
        _cast_boolean("ABC")


def test_cast_not_callable():
    with pytest.raises(TypeError, match="'cast' must be callable"):
        env("TEST", cast=1)


@pytest.mark.parametrize(
    "name, exc_type, message",
    (
        (1, TypeError, "'name' must be <class 'str'>"),
        ("", ValueError, "Environment variable name should not be an empty string"),
        ("\x00bla", ValueError, "Environment variable name contains null bytes"),
    ),
)
def test_name_not_string(name, exc_type, message):
    with pytest.raises(exc_type, match=message):
        env(name)
