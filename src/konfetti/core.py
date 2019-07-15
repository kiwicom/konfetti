import json
import sys
from collections import OrderedDict
from functools import wraps

# Ignore PyImportSortBear, PyUnusedCodeBear
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, Set

import attr
from dotenv import load_dotenv

from .exceptions import MissingError
from .vault.base import BaseVaultBackend
from .laziness import LazyVariable
from .log import core_logger
from . import exceptions, loaders
from ._compat import class_types
from .environ import EnvVariable
from .utils import iscoroutinefunction, rebuild_dict, NOT_SET
from .vault import VaultVariable


def get_config_option_names(module):
    # type: (ConfigHolder) -> List[str]
    """Get all configuration option names defined in the given module."""
    return [attr_name for attr_name in dir(module) if attr_name.isupper()]


@attr.s(slots=True)
class ConfigHolder(object):
    konfig = attr.ib()
    sources = attr.ib(type=List, factory=list)

    def __iter__(self):
        # newer config sources have higher precedence
        for source in reversed(self.sources):
            yield source.get(self.konfig)

    def __dir__(self):
        output = set()  # type: Set[Any]
        for source in self:
            output |= set(dir(source))
        return list(output)

    def __getattr__(self, item):
        for source in self:
            try:
                return getattr(source, item)
            except AttributeError:
                pass
        raise AttributeError

    def append(self, item):
        self.sources.append(Lazy(item))


@attr.s(slots=True)
class Lazy(object):
    closure = attr.ib()
    value = attr.ib(init=False, default=NOT_SET)

    def get(self, *args, **kwargs):
        if self.value is NOT_SET:
            self.value = self.closure(*args, **kwargs)
            core_logger.info("Configuration loaded")
        return self.value


@attr.s(slots=True)
class Konfig(object):
    """Configuration holder."""

    vault_backend = attr.ib(
        default=None, validator=attr.validators.optional(attr.validators.instance_of(BaseVaultBackend))
    )
    dotenv = attr.ib(default=None)
    dotenv_override = attr.ib(default=False, type=bool)
    # Forbids overriding with options that are not defined in the config module
    strict_override = attr.ib(default=True, type=bool)
    config_variable_name = attr.ib(default="KONFETTI_SETTINGS", type=str)
    loader = attr.ib(factory=loaders.default_loader_factory)
    _dotenv_loaded = attr.ib(type=bool, init=False, default=False)
    _conf = attr.ib(init=False)
    _vault = attr.ib(init=False, default=None)
    _config_overrides = attr.ib(init=False, type="OrderedDict[str, Dict]", factory=OrderedDict)

    def __attrs_post_init__(self):
        self._conf = ConfigHolder(self)
        self._conf.append(self.loader)

    @classmethod
    def from_object(cls, obj, **kwargs):
        """Create a config from the given object, mapping or an importable string."""
        factory = loaders.get_loader_factory(obj)
        return cls(loader=factory, **kwargs)

    @classmethod
    def from_json(cls, path, loads=json.loads, **kwargs):
        """Create a config from the given path to JSON file."""
        return cls(loader=loaders.json_loader_factory(path, loads), **kwargs)

    def extend_with_json(self, path, loads=json.loads):
        """Extend the config with data from the JSON file."""
        self._conf.append(loaders.json_loader_factory(path, loads))

    def extend_with_object(self, obj):
        """Extend the config with the given mapping."""
        factory = loaders.get_loader_factory(obj)
        self._conf.append(factory)

    def _load_dotenv(self):
        # type: () -> None
        """Load environment from `.env` file.

        No-op if .env is already loaded.
        """
        if self._dotenv_loaded:
            return
        load_dotenv(dotenv_path=self.dotenv, override=self.dotenv_override)
        self._dotenv_loaded = True
        core_logger.info(".env is loaded")

    def _configure(self, override_id, **kwargs):
        # type: (str, **Any) -> None
        """Custom settings for overriding."""
        core_logger.debug("Start overriding with %s", kwargs)
        if self.strict_override:
            self._validate_override(kwargs)
        # check for intersecting keys? maybe forbid merging if keys are intersecting
        self._config_overrides[override_id] = kwargs

    def _validate_override(self, kwargs):
        # type: (Dict[str, int]) -> None
        """Prevent setting config options that are not defined in the config module / class.

        This helps to keep all overrides up-to-date if some options are removed from the config.
        """
        config_option_names = get_config_option_names(self._conf)
        for key in kwargs:
            if key not in config_option_names:
                raise exceptions.ForbiddenOverrideError(
                    "Can't override `{}` config option, because it is not defined in the config module".format(key)
                )

    def _unconfigure(self, override_id):
        # type: (str) -> None
        """Remove the given override."""
        core_logger.debug("Stop overriding with %s", self._config_overrides[override_id])
        del self._config_overrides[override_id]

    def _unconfigure_all(self):
        # type: () -> None
        """Remove all overrides."""
        core_logger.debug("Stop overriding")
        self._config_overrides = OrderedDict()

    def override(self, **kwargs):
        # type: (**Any) -> OverrideContextManager
        """Override the config with provided keyword arguments."""
        return OverrideContextManager(self, **kwargs)

    def require(self, *keys):
        # type: (*str) -> None
        """Check if the given keys are present in the config."""
        if not keys:
            raise RuntimeError("You need to specify at least one key")
        missing_keys = []
        for key in keys:
            try:
                getattr(self, key)
            except (exceptions.MissingError, exceptions.SecretKeyMissing):
                missing_keys.append(key)
        if missing_keys:
            raise exceptions.MissingError("Options {keys} are required".format(keys=missing_keys))

    def __getattr__(self, item):
        # type: (str) -> Any
        """A core place for config options access. Provides `config.SECRET` API."""
        if item.startswith("_"):
            raise AttributeError
        core_logger.debug('Accessing "%s" option', item)
        value = self._get_from_override(item)
        if value is not None:
            return value
        return self._get_from_config(item)

    def _get_from_override(self, item):
        # type: (str) -> Any
        """Look up in override levels from top to bottom."""
        if self._config_overrides:
            # are values ordered as well?
            for key in reversed(self._config_overrides):
                try:
                    return self._config_overrides[key][item]
                except KeyError:
                    continue
        return None

    def _get_from_config(self, item):
        # type: (str) -> Any
        """Get given option from actual config."""
        try:
            obj = getattr(self._conf, item)
        except AttributeError:
            raise exceptions.MissingError("Option `{}` is not present in `{}`".format(item, self._conf.__name__))
        return self._evaluate(obj)

    def _evaluate(self, obj):
        """Evaluate given config option."""
        if isinstance(obj, EnvVariable):
            self._load_dotenv()
            return obj.evaluate()
        if isinstance(obj, VaultVariable):
            self._load_dotenv()
            return self._get_secret(obj)
        if isinstance(obj, LazyVariable):
            self._load_dotenv()
            return obj.evaluate(self)
        if isinstance(obj, dict):
            return self._evaluate_dict(obj)
        return obj

    def __contains__(self, item):
        # type: (str) -> bool
        """If given config option name exists in the config."""
        if not isinstance(item, str):
            raise TypeError("Config options names are strings, got: `{}`".format(type(item).__name__))
        value = self._get_from_override(item)
        if value is not None:
            return True
        return bool(getattr(self._conf, item, False))

    def get_secret(self, path):
        # type: (str) -> Any
        """Access a value via secret backend."""
        core_logger.info('Access secret "%s"', path)
        variable = VaultVariable(path)
        return self._get_secret(variable)

    def _get_secret(self, obj):
        # type: (VaultVariable) -> Any
        if self.vault_backend is None:
            raise exceptions.VaultBackendMissing(
                "Vault backend is not configured. "
                "Please specify `vault_backend` option in "
                "your `Konfig` initialization"
            )

        # A closure is needed to avoid a need to evaluate VAULT_{ADDR,TOKEN} variables
        # before environment overriding was checked
        def closure():
            # type: () -> Tuple[str, Optional[str], Optional[str], Optional[str]]
            address = self.VAULT_ADDR

            # Try to load token/credentials but raise exception only if both of them are missing
            token = get_option("VAULT_TOKEN")
            username = get_option("VAULT_USERNAME")
            password = get_option("VAULT_PASSWORD")

            if token is None and (username is None or password is None):
                raise MissingError

            return address, token, username, password

        def get_option(name):
            try:
                return getattr(self, name)
            except MissingError:
                pass

        return obj.evaluate(self.vault_backend, closure)  # type: ignore

    def asdict(self):
        """Convert the config to a dictionary.

        Depending on the Vault backend could return an awaitable object.
        """
        keys = get_config_option_names(self._conf)
        result = {key: getattr(self, key) for key in keys}
        return self._evaluate_dict(result)

    def _evaluate_dict(self, obj):
        # Configuration dict could be multilevel and contain config variables, that should be evaluated
        # The basic strategy is to create a copy of the given dict with all options evaluated (+ coros awaited)
        # Why copy?
        # Because of call-by-reference for dicts - otherwise the original dictionary in the config module / class
        # will be modified
        def evaluate_option(value):
            if isinstance(value, (VaultVariable, EnvVariable, LazyVariable)):
                value = self._evaluate(value)
            return value

        if self.vault_backend and self.vault_backend.is_async:
            from ._async import async_process_dict

            return async_process_dict(obj, evaluate_option)
        return rebuild_dict(obj, evaluate_option)

    @property
    def vault(self):
        """A namespace for Vault-related actions."""
        if not self._vault:
            self._vault = _Vault(self)
        return self._vault


@attr.s(slots=True)
class _Vault(object):
    """A namespace holder to provide `config.vault.get_override_examples()` API."""

    _config = attr.ib(type=Konfig)
    _overrides = attr.ib(init=False, default=None, type=Dict[str, Dict[str, str]])

    def get_override_examples(self):
        # type: () -> Dict[str, Dict[str, Any]]
        """To simplify overriding process it could be helpful to look at examples."""
        if not self._overrides:
            vault_variables = {}  # type: Dict[str, Dict[str, Any]]
            # Traverse via config content
            for attr_name in dir(self._config._conf):
                value = getattr(self._config._conf, attr_name)
                # Filter vault variables
                if not attr_name.startswith("_") and isinstance(value, VaultVariable):
                    # Fetch override_variable_name
                    vault_variables[attr_name] = value.override_example
            self._overrides = vault_variables
        return self._overrides


class OverrideContextManager:
    """Apply temporal changes to certain config module."""

    __slots__ = ("config", "kwargs")

    def __init__(self, config, **kwargs):
        # type: (Konfig, **Any) -> None
        self.config = config
        self.kwargs = kwargs

    def __enter__(self):
        # type: () -> None
        self.enable()

    def __exit__(self, exc_type, exc_val, exc_tb):
        # type: (Optional[Any], Optional[Any], Optional[Any]) -> None
        self.disable()

    def enable(self):
        # type: () -> None
        # Changes should be atomic?
        # Rollback on error
        self.config._configure(str(id(self)), **self.kwargs)

    def disable(self):
        # type: () -> None
        self.config._unconfigure(str(id(self)))

    def __call__(self, decorated):
        # type: (Union[Callable, type]) -> Union[Callable, type]
        """Wrap an object with config-overriding logic.

        Supported object types:
          - coroutines;
          - callables;
          - classes including unittest.TestCase subclasses;
        """
        if isinstance(decorated, class_types):
            return self.wrap_class(decorated)
        if iscoroutinefunction(decorated):
            return self.wrap_coro(decorated)
        if callable(decorated):
            return self.wrap_callable(decorated)
        raise TypeError("Don't know how to use `override` for `{}`".format(type(decorated).__name__))

    def wrap_class(self, cls):
        # type: (type) -> type
        """Apply config overriding for given class."""
        decorated_set_up = getattr(cls, "setup_class", lambda: None)
        decorated_tear_down = getattr(cls, "teardown_class", lambda: None)

        @classmethod  # type: ignore
        def setup_class(_):
            # type: (type) -> None
            self.enable()
            try:
                decorated_set_up()
            except Exception:
                self.disable()
                raise

        @classmethod  # type: ignore
        def teardown_class(_):
            # type: (type) -> None
            try:
                decorated_tear_down()
            finally:
                self.disable()

        cls.setup_class = setup_class  # type: ignore
        cls.teardown_class = teardown_class  # type: ignore
        return cls

    def wrap_callable(self, func):
        # type: (Callable) -> Callable
        """Apply config override to sync test functions."""

        if sys.version_info[0] == 2:
            return self._wrap_callable_py2(func)
        return self._wrap_callable_py3(func)

    def _wrap_callable_py2(self, func):
        """On Python 2.7 having functools.wraps is not enough for pytest fixture injecting.

        To avoid extra dependency on `wrapt` it is specified only for Python 2 dependencies and
        done differently here. Maybe it will be better to just use
        """
        import wrapt

        @wrapt.decorator
        def wrapper(func, instance, args, kwargs):
            with self:
                return func(*args, **kwargs)

        return wrapper(func)

    def _wrap_callable_py3(self, func):
        @wraps(func)
        def inner(*args, **kwargs):
            # type: (*Any, **Any) -> Any
            with self:
                return func(*args, **kwargs)

        return inner

    def wrap_coro(self, coro):
        # type: (Callable) -> Callable
        """Apply config override to async test functions."""
        from ._async import wrap_coro

        return wrap_coro(self, coro)
