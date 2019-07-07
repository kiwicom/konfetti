"""Utilities to load different configuration types."""
from typing import Mapping

from ._compat import string_types
from .utils import import_config_module, import_string


def default_loader_factory():
    def loader(konfig):
        return import_config_module(konfig.config_variable_name)

    return loader


def json_loader_factory(path, loads):
    def loader(konfig):
        with open(path) as fd:
            mapping = loads(fd.read())
        return type("Config", (), mapping)

    return loader


def noop_loader_factory(obj):
    def loader(konfig):
        return obj

    return loader


def mapping_loader_factory(obj):
    def loader(konfig):
        return type("Config", (), obj)

    return loader


def import_loader_factory(obj):
    def loader(konfig):
        return import_string(obj)

    return loader


def get_loader_factory(obj):
    if isinstance(obj, string_types):
        return import_loader_factory(obj)
    if isinstance(obj, Mapping):
        return mapping_loader_factory(obj)
    return noop_loader_factory(obj)
