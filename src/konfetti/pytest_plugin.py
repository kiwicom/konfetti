from inspect import getmodule
import sys

import attr
import pytest


@attr.s
class ConfigWrapper(object):
    """For proxying `__setattr__` calls as `_configure` to `Konfig` instances."""

    config = attr.ib()

    def __setattr__(self, key, value):
        if key == "config":
            self.__dict__[key] = value
        else:
            config_key = "{}-{}-{}".format(id(self), key, value)
            self.config._configure(config_key, **{key: value})

    def __getattr__(self, item):
        return getattr(self.config, item)


def get_caller_module(depth=2):
    """Get the module of the caller."""
    frame = sys._getframe(depth)
    module = getmodule(frame)
    # Happens when there's no __init__.py in the folder
    if module is None:
        return get_caller_module(depth=depth)
    return module


def make_fixture(config, name="settings"):
    """Create a fixture that will clean-up config overrides automatically."""

    @pytest.fixture(name=name)
    def fixture():
        wrapper = ConfigWrapper(config=config)
        yield wrapper
        config._unconfigure_all()

    module = get_caller_module(2)
    if hasattr(module, name):
        raise RuntimeError(
            "Module `{}` already has a member with name `{}`. Use another name for this fixture".format(
                module.__name__, name
            )
        )
    fixture.__module__ = module.__name__
    setattr(module, name, fixture)
    return fixture
