from functools import wraps
from typing import Any, Dict  # ignore: PyUnusedCodeBear

import attr

from .. import exceptions
from ..cache import EMPTY
from ..log import vault_logger
from .base import BaseVaultBackend


def cached_call(method):
    @wraps(method)
    def inner(self, path, url, token):

        value = self._get_from_cache(path)
        if value is EMPTY:
            value = method(self, path, url, token)
            self._set_to_cache(path, value)
        return value

    return inner


@attr.s
class VaultBackend(BaseVaultBackend):
    is_async = False

    def load(self, path, url, token):
        # type: (str, str, str) -> Dict[str, Any]

        from requests.exceptions import RequestException
        from tenacity import Retrying

        retry = self._get_retry(Retrying, RequestException)
        full_path = self._get_full_path(path)
        return retry.call(self._call, full_path, url, token)

    @cached_call
    def _call(self, path, url, token):
        vault_logger.debug('Access "%s" in Vault', path)
        import hvac

        vault = hvac.Client(url=url, token=token)
        response = vault.read(path)
        if response is None:
            raise exceptions.MissingError("Option `{}` is not present in Vault ({})".format(path, self.prefix))

        return response["data"]
