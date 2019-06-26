from kwonfig import env, vault

KEY = "value"
DEBUG = env("DEBUG", default=True, cast=bool)
SECRET = vault("path/to")["SECRET"]
WHOLE_SECRET = vault("path/to")
NESTED_SECRET = vault("path/to/nested")["NESTED_SECRET"]["nested"]
VAULT_ADDR = env("VAULT_ADDR")
VAULT_TOKEN = env("VAULT_TOKEN")

not_a_config_option = 1

DICTIONARY = {"static": 1, "vault": vault("path/to")["SECRET"], "env": env("DEBUG", default=True, cast=bool)}
