from functools import wraps
from typing import Any, Dict, Optional  # ignore: PyUnusedCodeBear

import attr

from .. import exceptions
from ..cache import EMPTY
from ..log import vault_logger
from ..utils import NOT_SET
from .base import BaseVaultBackend


def cached_call(method):
    @wraps(method)
    def inner(self, path, url, token, username, password):  # pylint: disable=too-many-arguments

        value = self._get_from_cache(path)
        if value is EMPTY:
            value = method(self, path, url, token, username, password)
            self._set_to_cache(path, value)
        return value

    return inner


@attr.s
class VaultBackend(BaseVaultBackend):
    is_async = False

    def load(self, path, url, token, username, password):  # pylint: disable=too-many-arguments
        # type: (str, str, Optional[str], Optional[str], Optional[str]) -> Dict[str, Any]

        from requests.exceptions import RequestException
        from tenacity import Retrying

        retry = self._get_retry(Retrying, RequestException)
        full_path = self._get_full_path(path)
        return retry.call(self._call, full_path, url, token, username, password)

    @cached_call
    def _call(self, path, url, token, username, password):  # pylint: disable=too-many-arguments
        # type: (str, str, Optional[str], Optional[str], Optional[str]) -> Any
        vault_logger.debug('Access "%s" in Vault', path)
        import hvac

        vault = hvac.Client(url=url, token=token)
        if not token and (username and password):
            if self._token is not NOT_SET:
                vault.auth.adapter.token = self._token
            else:
                vault_logger.debug("Retrieving a new token")
                vault.auth_userpass(username, password)
                self._token = vault.auth.adapter.token

        try:
            response = self.read_path(path, vault)
        except hvac.exceptions.Forbidden as exc:
            if username and password:
                vault_logger.debug("Token is invalid. Retrieving a new token")
                vault.auth_userpass(username, password)
                self._token = vault.auth.adapter.token
                response = self.read_path(path, vault)
            else:
                raise exc

        return response["data"]

    def read_path(self, path, vault):
        response = vault.read(path)
        if response is None:
            raise exceptions.MissingError("Option `{}` is not present in Vault ({})".format(path, self.prefix))
        return response
