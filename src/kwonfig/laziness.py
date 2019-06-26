# Ignore PyImportSortBear, PyUnusedCodeBear
from typing import Any, Callable, Union  # pylint: disable=unused-import

import attr

from . import exceptions
from .mixins import CastableMixin, DefaultMixin, validate_cast
from .utils import NOT_SET


@attr.s(slots=True)
class LazyVariable(DefaultMixin, CastableMixin):
    name = attr.ib(default=NOT_SET)
    func = attr.ib(default=NOT_SET)
    default = attr.ib(default=NOT_SET)
    cast = attr.ib(default=NOT_SET, validator=validate_cast)

    @classmethod
    def lazy(
        cls,
        name_or_function,  # type: Union[str, object, Callable]
        default=NOT_SET,  # type: Any
        cast=NOT_SET,  # type: Union[object, Callable]
    ):
        """If some configuration option should be evaluated in runtime (e.g. depends on the others).

        >>> @lazy("VARIABLE_NAME")
            def function(config):
                return "NOT_" + config.SECRET
        """
        if callable(name_or_function):
            return cls(func=name_or_function, default=default, cast=cast)
        return cls(name=name_or_function, default=default, cast=cast)

    def __call__(self, func):
        if self.func is not NOT_SET:
            raise RuntimeError("LazyVariable already has a callable assigned")
        self.func = func
        name = func.__module__.rsplit(".", 1)[1]
        module = __import__(func.__module__, fromlist=[name])
        setattr(module, self.name, self)
        return self

    def evaluate(self, config):
        try:
            result = self.func(config)
            return self._cast(result)
        except exceptions.MissingError:
            return self._get_default()
