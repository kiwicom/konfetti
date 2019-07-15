from functools import wraps
from typing import Any, Optional
from urllib.parse import urljoin

import attr

from .. import exceptions
from ..cache import EMPTY
from ..log import vault_logger
from ..utils import NOT_SET
from .base import BaseVaultBackend


def _get_full_url(url, full_path):
    # type: (str, str) -> str
    """Join the Vault server URL with the endpoint path."""
    return urljoin(url + "/v1/", full_path)


def cached_call(method):
    @wraps(method)
    async def inner(self, path, url, token, username, password):  # pylint: disable=too-many-arguments

        value = self._get_from_cache(path)
        if value is EMPTY:
            value = await method(self, path, url, token, username, password)
            self._set_to_cache(path, value)
        return value

    return inner


@attr.s
class AsyncVaultBackend(BaseVaultBackend):
    is_async = True

    async def load(self, path, url, token, username, password):  # pylint: disable=too-many-arguments
        # type: (str, str, Optional[str], Optional[str], Optional[str]) -> Any
        from aiohttp import ClientConnectionError
        from tenacity import AsyncRetrying

        retry = self._get_retry(AsyncRetrying, ClientConnectionError)
        full_path = self._get_full_path(path)
        return await retry.call(self._call, full_path, url, token, username, password)

    @cached_call
    async def _call(self, path, url, token, username, password):  # pylint: disable=too-many-arguments
        # type: (str, str, Optional[str], Optional[str], Optional[str]) -> Any
        """A call to the Vault server."""
        vault_logger.debug('Access "%s" in Vault', path)
        import aiohttp

        if not token and (username and password):
            if self._token is not NOT_SET:
                token = self._token  # type: ignore
            else:
                vault_logger.debug("Retrieving a new token")
                token = await self._auth_userpass(url, username, password)
                self._token = token

        try:
            content = await self._read_path(path, url, token)  # type: ignore
        except aiohttp.client_exceptions.ClientResponseError as exc:
            if exc.status == 403 and (username and password):
                vault_logger.debug("Token is invalid. Retrieving a new token")
                token = await self._auth_userpass(url, username, password)
                self._token = token
                content = await self._read_path(path, url, token)
            else:
                raise exc

        return content["data"]

    async def _read_path(self, path, url, token):
        # type: (str, str, str) -> Any
        import aiohttp

        url = _get_full_url(url, path)
        headers = {"X-Vault-Token": token}

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, allow_redirects=False) as response:
                content = await response.json()
                try:
                    response.raise_for_status()
                except aiohttp.client_exceptions.ClientResponseError as exc:
                    if exc.status != 404:
                        raise exc

        if "data" not in content:
            raise exceptions.MissingError("Option `{}` is not present in Vault ({})".format(path, self.prefix))
        return content

    @staticmethod
    async def _auth_userpass(url, username, password):
        # type: (str, str, str) -> str
        import aiohttp

        params = {"password": password}
        auth_url = _get_full_url(url, "auth/userpass/login/{}".format(username))
        async with aiohttp.ClientSession() as session:
            async with session.post(auth_url, json=params, allow_redirects=False) as response:
                content = await response.json()
                response.raise_for_status()
                return content["auth"]["client_token"]
