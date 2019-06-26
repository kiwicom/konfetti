from datetime import datetime, timedelta
from typing import Dict, Optional, Union

import attr

from .log import cache_logger

EMPTY = object()


def to_timedelta(value):
    # type: (Optional[Union[int, float]]) -> Optional[timedelta]
    if value is None or isinstance(value, timedelta):
        return value
    return timedelta(seconds=value)


def check_ttl(self, attribute, value):
    """Time-to-live could be a `timedelta` instance, `int` or `float`."""
    if isinstance(value, timedelta):
        return
    attr.validators.optional(attr.validators.instance_of((int, float)))(  # type: ignore
        self, attribute, value
    )
    if value is not None and not 0 < value <= 999999999:
        raise ValueError("'cache_ttl' should be in range (0, 999999999]")


@attr.s(slots=True)
class InMemoryCache(object):
    """Simple in-memory cache.

    The cache uses a built-in `dict` which gives thread-safety for basic operations because of the GIL
    https://docs.python.org/3/glossary.html#term-global-interpreter-lock

    However, there is one (at least visible now) case when it is possible to have a data race - removing data from
    the cache, which takes multiple steps and `del self._data[key]` could fail because of concurrent access.
    """

    ttl = attr.ib(
        type=Optional[Union[int, float, timedelta]], default=None, validator=check_ttl, converter=to_timedelta
    )
    _data = attr.ib(init=False, type=Dict[str, Dict], factory=dict)

    def _is_expired(self, inserted):
        """If ttl is defined, then check if the given value passed due or not."""
        return self.ttl is not None and inserted + self.ttl < datetime.utcnow()

    def _delete_if_expired(self, key, inserted):
        # type: (str, datetime) -> bool
        """Delete the item if it is expired.

        Return if the item was deleted.
        """
        if self._is_expired(inserted):
            cache_logger.debug('Delete expired "%s" cache entry', key)
            try:
                del self._data[key]
            except KeyError:
                # Could be deleted from another thread
                # Hard to reproduce with `slots=True` since mocking doesn't work
                pass
            return True
        return False

    def __getitem__(self, item):
        data = self._data[item]
        if self._delete_if_expired(item, data["inserted"]):
            raise KeyError
        return data["data"]

    def __setitem__(self, key, value):
        """If ttl is not defined, then cache the value forever."""
        if self.ttl is not None:
            inserted = datetime.utcnow()  # type: Optional[datetime]
            cache_logger.debug('Add "%s" to cache for %s', key, self.ttl)
        else:
            inserted = None
            cache_logger.debug('Add "%s" to cache forever', key)
        self._data[key] = {"data": value, "inserted": inserted}

    def __contains__(self, item):
        try:
            data = self._data[item]
            # item wasn't deleted -> still valid and exists in the cache
            return not self._delete_if_expired(item, data["inserted"])
        except KeyError:
            return False

    def get(self, key):
        data = self._data.get(key, EMPTY)
        if data is EMPTY:
            return data
        if self._delete_if_expired(key, data["inserted"]):
            return EMPTY
        return data["data"]

    def set(self, key, value):
        self[key] = value

    def clear(self):
        """Re-create cache storage."""
        self._data = {}
