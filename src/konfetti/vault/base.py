from typing import Optional, Union  # ignore: PyUnusedCodeBear

import attr

from ..cache import check_ttl, EMPTY, InMemoryCache
from ..utils import NOT_SET


@attr.s(slots=True)
class BaseVaultBackend(object):
    prefix = attr.ib(type=Union[str, object], default=NOT_SET)
    cache_ttl = attr.ib(type=Optional[Union[int, float]], validator=check_ttl, default=None)
    cache = attr.ib(init=False, default=NOT_SET)
    try_env_first = attr.ib(type=bool, default=True, validator=attr.validators.instance_of(bool))
    max_retries = attr.ib(type=int, default=3, validator=attr.validators.instance_of(int))
    max_retry_time = attr.ib(type=int, default=15, validator=attr.validators.instance_of(int))
    retry = attr.ib(default=None)
    _token = attr.ib(init=False, type=Union[str, object], default=NOT_SET)

    is_async = None  # type: Optional[bool]

    def __attrs_post_init__(self):
        if self.cache_ttl is not None:
            self.cache = InMemoryCache(ttl=self.cache_ttl)

    @prefix.validator
    def check_name(self, attribute, value):
        if value is not NOT_SET:
            attr.validators.instance_of(str)(self, attribute, value)

    def _get_full_path(self, path):
        # type: (str) -> str
        """Get full path to the secret.

        Join prefix with the given path and cleanup leading & trailing slashes.
        """
        if self.prefix is NOT_SET:
            return path.strip("/")
        return self.prefix.strip("/") + "/" + path.strip("/")  # type: ignore

    def _get_from_cache(self, path):
        if self.cache is not NOT_SET:
            return self.cache.get(path)
        return EMPTY

    def _set_to_cache(self, path, value):
        if self.cache is not NOT_SET:
            self.cache.set(path, value)

    def _get_retry(self, cls, exception):
        retry = self.retry
        if not retry:
            from tenacity import retry_if_exception_type, stop_after_attempt, stop_after_delay

            retry = cls(
                retry=retry_if_exception_type(exception),
                reraise=True,
                stop=(stop_after_attempt(self.max_retries) | stop_after_delay(self.max_retry_time)),
            )
        return retry
