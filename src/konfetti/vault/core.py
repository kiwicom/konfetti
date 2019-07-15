from inspect import isgenerator
from io import BytesIO
import json
from typing import Any, Callable, Dict, List, Tuple, Union  # ignore: PyUnusedCodeBear

import attr

from .. import exceptions
from ..environ import EnvVariable
from ..mixins import CastableMixin, validate_cast
from ..utils import iscoroutine, NOT_SET
from .synchronous import VaultBackend

SEPARATOR = "__"
SECRETS_DISABLED_VARIABLE = "KONFETTI_DISABLE_SECRETS"


def are_defaults_disabled():
    return EnvVariable("VAULT_DISABLE_DEFAULTS", default=False, cast=bool).evaluate()


@attr.s(slots=True)
class VaultVariable(CastableMixin):
    """Vault variable holder."""

    # Path to the Vault secret
    path = attr.ib(type=str, validator=attr.validators.instance_of(str))
    cast = attr.ib(default=NOT_SET, validator=validate_cast)
    default = attr.ib(default=NOT_SET)
    # Optional sequence of keys in the loaded data
    # E.g. data["first"]["second"] will be stored as ["first", "second"]
    keys = attr.ib(init=False, factory=list, type=List[str])

    @classmethod
    def vault(cls, path, cast=NOT_SET, default=NOT_SET):
        # type: (str, Union[object, Callable], Any) -> VaultVariable
        """A secret value from Vault."""
        return cls(path=path, cast=cast, default=default)

    @classmethod
    def vault_file(cls, path):
        """Wrap a value from Vault in a file-like object."""
        return cls(path=path, cast=lambda value: BytesIO(value.encode("utf8")))

    def evaluate(self, backend, closure):
        # type: (VaultBackend, Callable) -> Any
        if backend.try_env_first:
            try:
                return self._try_load_from_env(backend)
            except exceptions.MissingError:
                pass
        self.validate_allowance_to_access_secrets()
        url, token, username, password = self._load_credentials(closure)
        data = backend.load(self.path, url, token, username, password)
        if iscoroutine(data) or isgenerator(data):
            # To avoid syntax errors on Python 2.7
            from .._async import make_async_callback

            return make_async_callback(data, self._extract_value)
        return self._extract_value(data)

    def _try_load_from_env(self, backend):
        # type: (VaultBackend) -> Any
        value = EnvVariable(self.override_variable_name, cast=self.cast).evaluate()
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            pass
        if not isinstance(value, dict):
            raise exceptions.InvalidSecretOverrideError(
                "`{}` variable should be a JSON-encoded dictionary, got: `{}`".format(
                    self.override_variable_name, value
                )
            )
        for key in self.keys:
            value = value[key]

        if backend.is_async:
            from .._async import make_simple_coro

            value = make_simple_coro(value)
        return value

    def _load_credentials(self, closure):
        # type: (Callable) -> Tuple[str, str, str, str]
        try:
            return closure()
        except exceptions.MissingError:
            raise exceptions.MissingError(
                "Can't access secret `{}` due to failing to load Vault config".format(self.path)
            )

    def _extract_value(self, data):
        # type: (Dict[str, Any]) -> Any
        """Extract value from given Vault data."""
        for key in self.keys:
            try:
                data = data[key]
            except KeyError:
                if not are_defaults_disabled() and self.default is not NOT_SET:
                    return self.default
                key_path = ".".join(self.keys)
                raise exceptions.SecretKeyMissing(
                    "Path `{}` exists in Vault but does not contain given key path - `{}`".format(self.path, key_path)
                )
        return self._cast(data)

    def __getitem__(self, item):
        # type: (str) -> VaultVariable
        """Store all [key1][key2] path inside `self.keys`."""
        self.keys.append(item)
        return self

    def validate_allowance_to_access_secrets(self):
        # type: () -> None
        if self.disabled:
            raise RuntimeError(
                "Access to vault is disabled. Unset `{}` environment variable to enable it.".format(
                    SECRETS_DISABLED_VARIABLE
                )
            )

    @property
    def disabled(self):
        # type: () -> bool
        """If secrets access is globally disabled."""
        # Move to some global config or we need to modify in runtime?
        return EnvVariable(SECRETS_DISABLED_VARIABLE, default=False, cast=bool).evaluate()

    @property
    def override_variable_name(self):
        # type: () -> str
        """Convert path to a name of environment variable that will be checked for overriding.

        If some key in that secret is going to be overridden then its name is concatenated
        via double underscore as well.

        Example:
            config.vault("path/to") -> "PATH__TO"
        """
        return self.path.strip("/").replace("/", SEPARATOR).upper()

    @property
    def override_example(self):
        """Provide an example for overriding the variable via environment."""
        if self.keys:
            # Add example value
            example = {}  # type: Dict[str, Dict[str, Any]]
            current_level = example  # type: Any
            for key in self.keys[:-1]:
                current_level[key] = {}
                current_level = current_level[key]
            current_level[self.keys[-1]] = "example_value"
            value = json.dumps(example)
        else:
            value = "{}"
        return {self.override_variable_name: value}
