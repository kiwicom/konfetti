"""Support for configuration based on `os.environ`."""
import os

# Ignore PyImportSortBear, PyUnusedCodeBear
from typing import Any, Callable, Union  # pylint: disable=unused-import

import attr

from .mixins import CastableMixin, validate_cast, DefaultMixin, CONTAINER_TYPES
from .utils import NOT_SET


@attr.s(slots=True)
class EnvVariable(DefaultMixin, CastableMixin):
    """Environment variable holder."""

    name = attr.ib(type=str, validator=attr.validators.instance_of(str))
    default = attr.ib(default=NOT_SET)
    cast = attr.ib(default=NOT_SET, validator=validate_cast)
    subcast = attr.ib(default=NOT_SET, validator=validate_cast)

    @name.validator
    def check_name(self, attribute, value):
        if not value:
            raise ValueError("Environment variable name should not be an empty string")
        if "\x00" in value:
            raise ValueError("Environment variable name contains null bytes - '\\x00'")

    @subcast.validator
    def check_subcast(self, attribute, value):
        if value is not NOT_SET and self.cast not in CONTAINER_TYPES:
            allowed_type_names = [option.__name__ for option in CONTAINER_TYPES]
            raise ValueError(
                "`subcast` is only available when `cast` is one of these options: {}".format(allowed_type_names)
            )

    @classmethod
    def env(
        cls,
        name,  # type: str
        default=NOT_SET,  # type: Any
        cast=NOT_SET,  # type: Union[object, Callable]
        subcast=NOT_SET,  # type: Union[object, Callable]
    ):
        # type: (...) -> EnvVariable
        """Define a config option that will look for it's value in `os.environ`."""
        return cls(name=name, default=default, cast=cast, subcast=subcast)

    def __str__(self):
        """Evaluating the option could be helpful if some other options depend on this one.

        >>> DATABASE_ROLE = env("DATABASE_ROLE", default="user")
        >>> DATABASE_URI = vault(f"path/to/app_{DATABASE_ROLE}_rw")
        """
        return str(self.evaluate())

    def evaluate(self):
        # type: () -> Any
        """Get the environ variable value and process it."""
        value = os.getenv(self.name)
        if value is None:
            return self._get_default()
        return self._cast(value)
