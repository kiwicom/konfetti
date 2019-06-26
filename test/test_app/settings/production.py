from datetime import date, datetime
from decimal import Decimal

from kwonfig import env, lazy, vault, vault_file

KEY = "value"
DEBUG = env("DEBUG", default=True, cast=bool)
REQUIRED = env("REQUIRED")
INTEGER = env("INTEGER", default=1, cast=int)
FROM_DOTENV = env("FROM_DOTENV", default="not_loaded")

SECRET = vault("path/to")["SECRET"]
ANOTHER_SECRET = vault("path/to")["ANOTHER_SECRET"]
WHOLE_SECRET = vault("path/to")
NESTED_SECRET = vault("path/to/nested")["NESTED_SECRET"]["nested"]
SECRET_FILE = vault_file("path/to/file")["SECRET_FILE"]
DEFAULT = vault("path/to", default="default")["DEFAULT"]

IS_SECRET = vault("path/to", cast=bool)["IS_SECRET"]
DECIMAL = vault("path/to", cast=Decimal)["DECIMAL"]
FLOAT_DECIMAL = vault("path/to/cast", cast=Decimal)["DECIMAL"]
DATE = vault("path/to/cast", cast=date)["DATE"]
DATETIME = vault("path/to/cast", cast=datetime)["DATETIME"]

NOT_IN_VAULT = vault("something/missing")

LAZY_LAMBDA = lazy(lambda config: config.KEY + "/" + config.SECRET + "/" + config.REQUIRED)


@lazy("LAZY_PROPERTY")
def lazy_property(config):
    return config.KEY + "/" + config.SECRET + "/" + config.REQUIRED


VAULT_ADDR = env("VAULT_ADDR")
VAULT_TOKEN = env("VAULT_TOKEN")
