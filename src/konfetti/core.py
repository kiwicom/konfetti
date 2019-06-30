import sys
from collections import OrderedDict
from functools import wraps
import os
from types import ModuleType

# Ignore PyImportSortBear, PyUnusedCodeBear
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import attr
from dotenv import load_dotenv

from .vault.base import BaseVaultBackend
from .laziness import LazyVariable
from .log import core_logger
from . import exceptions
from ._compat import class_types
from .environ import EnvVariable
from .utils import import_string, iscoroutinefunction, rebuild_dict
from .vault import VaultVariable


def import_config_module(config_variable_name):
    # type: (str) -> ModuleType
    """Import the given module."""
    path = os.getenv(config_variable_name)
    if not path:
        raise exceptions.SettingsNotSpecified(
            "The environment variable `{}` is not set or empty "
            "and as such configuration could not be "
            "loaded. Set this variable and make it "
            "point to a configuration file".format(config_variable_name)
        )
    try:
        return import_string(path)
    except (ImportError, ValueError):
        # ValueError happens when import string ends with a dot
        raise exceptions.SettingsNotLoadable("Unable to load configuration file `{}`".format(path))


def get_config_option_names(module):
    # type: (ModuleType) -> List[str]
    """Get all configuration option names defined in the given module."""
    return [attr_name for attr_name in dir(module) if attr_name.isupper()]


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
    _initialized = attr.ib(type=bool, init=False, default=False)
    _dotenv_loaded = attr.ib(type=bool, init=False, default=False)
    _conf = attr.ib(init=False, default=None)
    _vault = attr.ib(init=False, default=None)
    _config_overrides = attr.ib(init=False, type="OrderedDict[str, Dict]", factory=OrderedDict)

    def _setup(self):
        # type: () -> None
        """Load configuration module.

        No-op if the module is already loaded.
        """
        if self._initialized:
            return
        self._conf = import_config_module(self.config_variable_name)
        self._initialized = True
        core_logger.info("Configuration loaded")

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
            self._setup()
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
        self._setup()
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
        return obj

    def __contains__(self, item):
        # type: (str) -> bool
        """If given config option name exists in the config."""
        if not isinstance(item, str):
            raise TypeError("Config options names are strings, got: `{}`".format(type(item).__name__))
        value = self._get_from_override(item)
        if value is not None:
            return True
        self._setup()
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
            # type: () -> Tuple[str, str]
            return self.VAULT_ADDR, self.VAULT_TOKEN

        return obj.evaluate(self.vault_backend, closure)  # type: ignore

    def asdict(self):
        """Convert the config to a dictionary.

        Depending on the Vault backend could return an awaitable object.
        """
        self._setup()
        keys = get_config_option_names(self._conf)
        result = {key: getattr(self, key) for key in keys}

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

            return async_process_dict(result, evaluate_option)
        return rebuild_dict(result, evaluate_option)

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
            self._config._setup()
            vault_variables = {}  # type: Dict[str, Dict[str, Any]]
            # Traverse via config content
            for attr_name in vars(self._config._conf):
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
