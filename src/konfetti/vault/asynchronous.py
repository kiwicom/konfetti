from functools import wraps
from urllib.parse import urljoin

import attr

from .. import exceptions
from ..cache import EMPTY
from ..log import vault_logger
from .base import BaseVaultBackend


def _get_full_url(url, full_path):
    # type: (str, str) -> str
    """Join the Vault server URL with the endpoint path."""
    return urljoin(url + "/v1/", full_path)


def cached_call(method):
    @wraps(method)
    async def inner(self, path, url, token):

        value = self._get_from_cache(path)
        if value is EMPTY:
            value = await method(self, path, url, token)
            self._set_to_cache(path, value)
        return value

    return inner


@attr.s
class AsyncVaultBackend(BaseVaultBackend):
    is_async = True

    async def load(self, path, url, token):
        full_path = self._get_full_path(path)
        return await self._call(full_path, url, token)

    def __attrs_post_init__(self):
        from aiohttp import ClientConnectionError
        from tenacity import retry_if_exception_type, stop_after_attempt, stop_after_delay, wait_exponential, \
            AsyncRetrying

        r = AsyncRetrying(
            retry=retry_if_exception_type(ClientConnectionError),
            reraise=True,
            stop=stop_after_attempt(3),
            # stop=(stop_after_attempt(3) | stop_after_delay(10)),
            # wait=wait_exponential(multiplier=1, min=4, max=10),
        )
        self.load = await r.wraps(self.load)

    @cached_call
    async def _call(self, path, url, token):
        """A call to the Vault server."""
        vault_logger.debug('Access "%s" in Vault', path)
        import aiohttp

        url = _get_full_url(url, path)
        headers = {"X-Vault-Token": token}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, allow_redirects=False) as response:
                content = await response.json()
        if "data" not in content:
            raise exceptions.MissingError("Option `{}` is not present in Vault ({})".format(path, self.prefix))
        return content["data"]
