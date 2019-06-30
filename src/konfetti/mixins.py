from datetime import date, datetime
from decimal import Decimal
from typing import Any
import warnings

from . import exceptions
from .utils import NOT_SET

_BOOLEANS = {
    "1": True,
    "yes": True,
    "true": True,
    "on": True,
    "0": False,
    "no": False,
    "false": False,
    "off": False,
    "": False,
}


def _cast_boolean(value):
    # type: (str) -> bool
    """Special case for boolean casting.

    Everything in `os.environ` is of type `str`. Calling `bool` on non-empty strings will result in True.
    """
    try:
        return _BOOLEANS[str(value).lower()]
    except KeyError:
        raise ValueError("Not a boolean: `{}`".format(value))


def validate_cast(self, attribute, value):
    if value is not NOT_SET and not callable(value):
        raise TypeError("'cast' must be callable")


class CastableMixin(object):
    def _cast(self, value):
        # type: (Any) -> Any
        """Cast value to specified type if needed."""
        if self.cast is NOT_SET:  # type: ignore
            return value
        if self.cast is bool:  # type: ignore
            return _cast_boolean(value)
        if self.cast is datetime:  # type: ignore
            return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
        if self.cast is date:  # type: ignore
            return datetime.strptime(value, "%Y-%m-%d").date()
        if self.cast is Decimal and isinstance(value, float):  # type: ignore
            warnings.warn("Float to Decimal conversion detected, please use string or integer.", RuntimeWarning)
            return Decimal(str(value))
        return self.cast(value)  # type: ignore


class DefaultMixin(object):
    def _get_default(self):
        # type: () -> Any
        """Return default if it is specified."""
        if self.default is NOT_SET:  # type: ignore
            raise exceptions.MissingError(
                "Variable `{}` is not found and has no `default` specified".format(self.name)  # type: ignore
            )
        if callable(self.default):  # type: ignore
            return self.default()  # type: ignore
        return self.default  # type: ignore
