import os

from konfetti import env, vault, VaultBackend
from konfetti.contrib.django import install

SECRET_KEY = "foo"

ROOT_URLCONF = "django_app.views"

DEBUG = env("DEBUG", default=True, cast=bool)
REQUIRED = env("REQUIRED")

VAULT_ADDR = env("VAULT_ADDR")
VAULT_TOKEN = env("VAULT_TOKEN")

SECRET = vault("path/to")["SECRET"]

config = install(__name__, vault_backend=VaultBackend(os.getenv("VAULT_PREFIX")))
config.extend_with_object({"KEY": 42})
