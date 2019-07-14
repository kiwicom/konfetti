from __future__ import absolute_import

import importlib
import inspect
import pkgutil
import sys

import attr
from django import conf

from ..core import Konfig


def install(path, **kwargs):
    config = Konfig.from_object(path, strict_override=False, **kwargs)
    proxy = KonfigProxy(conf.settings, config)

    @attr.s(slots=True, hash=True)
    class Wrapper(object):
        def __getattribute__(self, name):
            if name == "settings":
                return proxy
            return getattr(conf, name)

    load_submodules()
    sys.modules["django.conf"] = Wrapper()  # type: ignore

    _patch_settings(proxy)
    return config


def load_submodules():
    """django.conf contains subpackages, that should be loaded upfront to access them via __getattribute__."""
    for _, name, _ in pkgutil.walk_packages(conf.__path__):
        importlib.import_module("django.conf." + name)


@attr.s(slots=True)
class KonfigProxy(object):
    django_settings = attr.ib()
    konfig = attr.ib(type=Konfig)

    def __getattr__(self, item):
        """Check through Konfig first and then fallback to the Django's one."""
        if self.is_overridden(item):
            return getattr(self.django_settings, item)
        try:
            return getattr(self.konfig, item)
        except AttributeError:
            return getattr(self.django_settings, item)

    def is_overridden(self, item):
        """Only for cases when Django's `override_settings` is used."""
        return isinstance(self.django_settings, conf.UserSettingsHolder) and self.django_settings.is_overridden(item)


def _patch_settings(config):
    """Look for already imported settings and patch them with the Konfig instance."""
    frame_infos = inspect.stack()
    for frame_info in reversed(frame_infos):
        f_globals = frame_info[0].f_globals
        if isinstance(f_globals.get("settings"), conf.LazySettings):
            f_globals["settings"] = config
