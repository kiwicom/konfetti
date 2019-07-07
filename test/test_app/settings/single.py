from konfetti import env, Konfig

KEY = "value"
DEBUG = env("DEBUG", default=True, cast=bool)

config = Konfig.from_object(__name__)
