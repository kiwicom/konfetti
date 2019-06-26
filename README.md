# kwonfig

## Description

NOTE: The documentation is in progress

`kwonfig` provides a framework-independent way for configuration of applications or libraries written in Python.

Key features:

- Lazy evaluation; 
- Built-in environment variables support;
- Built-in Vault support;
- Helpers for tests.

The primary motivation for building this library is to unify all configuration in different projects and make it as lazy as possible. In this case, we could get these benefits:

- No need to full app configuration when running a subset of tests that don't need a full config;
- Avoid network calls during imports until necessary; 

The interface design and features are heavily inspired by `Django` & `decouple`.

**Supported Python versions**: 2.7 & 3.5 - 3.8

## Quickstart

To use `kwonfig` you need to define:

- configuration variables in a module or a class;
- an access point;

### Settings module

```python
# app_name/settings/production.py
from kwonfig import env, vault

VAULT_ADDR = env("VAULT_ADDR")
VAULT_TOKEN = env("VAULT_TOKEN")

DEBUG = env("DEBUG", default=False)
DATABASE_URI = vault("path/to/db")
```

**NOTE**: The naming convention for variables names is to use upper case, other variables will be ignored.

### Access point

```python
# app_name/settings/__init__.py
from kwonfig import KiwiConfig, VaultBackend

config = KiwiConfig(vault_backend=VaultBackend("/secret/team"))
```

`kwonfig` relies on `KIWI_CONFIG` environment variable to discover your settings module, in the case above:

`export KIWI_CONFIG=app_name.settings.production`

### Usage

The settings module/class with configuration options shouldn't be accessed directly, because the aforementioned 
features are implemented in the access point level.

```python
from app_name.settings import config

def something():
    config.DATABASE_URI
```

## API

**Table of contents**:

- [Lazy evaluation](https://github.com/kiwicom/kwonfig#lazy-evaluation)
- [Environment](https://github.com/kiwicom/kwonfig#environment)
- [Vault](https://github.com/kiwicom/kwonfig#vault)
- [Testing](https://github.com/kiwicom/kwonfig#testing)

### Lazy evaluation

Until a config option is accessed it is not evaluated - it is lazy. To avoid side effects on imports accessing
configuration should be avoided on a module level.

This concept allows you to choose when you actually evaluate the config. Why?

- Testing. If you need to test a small piece of code that doesn't require any configuration - you don't have to setup it;
- Faster application startup; Use only what you need at the moment

It is still possible to evaluate the config eagerly on the app startup - access the needed variables in the entry points.
It could be done either with direct accessing needed variables or with `config.require(...)` / `config.asdict()` calls. 

### Environment

```python
from kwonfig import env

VARIABLE = env("VARIABLE_NAME", default="foo") 
```

Since environment variables are strings, there is a `cast` option to convert 
given variable from a string to the desired type:

```python
from kwonfig import env

VARIABLE = env("VARIABLE_NAME", default=42, cast=int)
```

You can pass any callable as `cast`.
If there is a need to use the environment variable immediately, it could be 
evaluated via `str` call (other ways could be added on demand):

```python
from kwonfig import env, vault

DATABASE_ROLE = env("DATABASE_ROLE", default="booking")

DATABASE_URI = vault(f"db/{DATABASE_ROLE}")
```

If `cast` is specified, then it will be applied before evaluation as well.

#### `.env` support

It is possible to specify a path to the `.env` file and it will be used as a source
of data for environment variables.

`dotenv_override` parameter specifies whether the `.env` value should be used if
both the environment variable and the `.env` record exists, `False` by default. 

```python
# app_name/settings/__init__.py
from kwonfig import KiwiConfig

config = KiwiConfig(dotenv="path/to/.env", dotenv_override=False)
```

### Vault

#### Backend configuration

To use Vault as a secrets storage you need to configure the access point:

```python
# app_name/settings/__init__.py
from kwonfig import KiwiConfig, VaultBackend

config = KiwiConfig(vault_backend=VaultBackend("your/prefix"))
```

There are two Vault backends available:

- `kwonfig.VaultBackend`
- `kwonfig.AsyncVaultBackend`

The main difference is that the latter requires using `await` to access 
the secret value (the call will be handled asynchronously under the hood), otherwise the interfaces and capabilities are the same.

Each backend requires a `prefix` to be specified, the trailing / leading slashes don't matter,
 `"your/prefix"` will work the same as `"/your/prefix/"`.

#### Usage

Every Vault secret needs a `path` to be used as a lookup (leading and trailing slashes don't matter as well):

```python
# app_name/settings/production.py
from kwonfig import vault

WHOLE_SECRET = vault("path/to")
```

In this case all key/value pairs will be loaded on evaluation:

```python
>>> from app_name.settings import config
>>> config.WHOLE_SECRET
{'key': 'value', 'foo': 'bar'}
```

You can specify a specific key to be returned for a config option with `[]` syntax:

```python
# app_name/settings/production.py
from kwonfig import vault

KEY = vault("path/to")["key"]
```

```python
>>> from app_name.settings import config
>>> config.KEY
value
```

Using square brackets will not trigger evaluation - you could specify as many levels as you want:

```python
# app_name/settings/production.py
from kwonfig import vault

DEEP = vault("path/to")["deeply"]["nested"]["key"]
```

Casting could be specified as well:

```python
# app_name/settings/production.py
from decimal import Decimal
from kwonfig import vault

DECIMAL = vault("path/to", cast=Decimal)["fee_amount"]  # stored as string
```

```python
>>> from app_name.settings import config
>>> config.DECIMAL
Decimal("0.15")
```

Sometimes you need to access to some secrets dynamically. `KiwiConfig` provides a way to do it:

```python
>>> from app_name.settings import config
>>> config.get_secret("path/to")["key"]
value
```

##### Secret files

It is possible to get a file-like interface for vault secret.

```python
# app_name/settings/production.py
from kwonfig import vault_file

KEY = vault_file("path/to/file")["key"]
```

```python
>>> from app_name.settings import config
>>> config.KEY.readlines()
[b'value']
```

##### Defaults

It is possible to specify the default value for vault variable. Value could be
any type for a key in a secret and a `dict` for the whole secret.

```python
DEFAULT = vault("path/to", default="default")["DEFAULT"]
DEFAULT_SECRET = vault("path/to", default={"DEFAULT_SECRET": "default_secret"})

>>> from app_name.settings import config
>>> config.DEFAULT
"default"
>>> config.DEFAULT_SECRET
{"DEFAULT_SECRET": "default_secret"}
```

Defaults could be disabled entirely if `VAULT_DISABLE_DEFAULTS` is set

```bash
$ export VAULT_DISABLE_DEFAULTS="true"
```

##### Overriding Vault secrets

In some cases, secrets need to be overridden in runtime on the application level. You can define some custom values
for tests or you just want to run the app with some different configuration without changing data in Vault.

There is a way to do it using environment variables or `.env` records
To redefine certain config option you need to redefine the whole secret with a JSON encoded string.

Example:

```python
# app_name/settings/production.py
from kwonfig import vault

KEY = vault("path/to")["key"]
```

```python
>>> from app_name.settings import config
>>> config.KEY
value
>>> import os
>>> os.environ["PATH__TO"] = '{"key": "overridden"}'
>>> config.KEY
overridden
```

To check how to override certain option there is a `config.vault.get_override_examples()` helper:

```python
>>> config.vault.get_override_examples()
{
    "NESTED_SECRET": {
        "PATH__TO__NESTED": '{"NESTED_SECRET": {"nested": "example_value"}}'
    },
    "SECRET": {
        "PATH__TO": '{"SECRET": "example_value"}'
    },
    "WHOLE_SECRET": {
        "PATH__TO": "{}"
    },
}
```

By default, when the evaluation will happen on a Vault secret, the environment will be checked first. 
If you don't need this behavior, it could be turned off with `try_env_first=False` option to the chosen backend:

```python
# app_name/settings/__init__.py
from kwonfig import KiwiConfig, VaultBackend

config = KiwiConfig(vault_backend=VaultBackend("your/prefix", try_env_first=False))
```

##### Disabling access to secrets

If you want to forbid any access to Vault (e.g. in your tests) you can set `KIWI_CONFIG_DISABLE_SECRETS` environment
variable with `1` / `on` / `true` / `yes`.

```python
>>> import os
>>> from app_name.settings import config
>>> os.environ["KIWI_CONFIG_DISABLE_SECRETS"] = "1"
>>> config.get_secret("path/to")["key"]
...
RuntimeError: Access to secrets is disabled. Unset KIWI_CONFIG_DISABLE_SECRETS variable to enable it. 
```

##### Caching

Vault values could be cached in memory:

```python
config = KiwiConfig(vault_backend=VaultBackend("your/prefix", cache_ttl=60))
```

By default, caching is disabled.

#### Lazy options

If there is a need to calculate config options dynamically (e.g., if it depends on values of other options) `kwonfig`
provides `lazy`:

```python
from kwonfig import lazy

LAZY_LAMBDA = lazy(lambda config: config.KEY + "/" + config.SECRET + "/" + config.REQUIRED)


@lazy("LAZY_PROPERTY")
def lazy_property(config):
    return config.KEY + "/" + config.SECRET + "/" + config.REQUIRED
```

### Testing

It is usually a good idea to use a slightly different configuration for tests (disabled tracing, sentry, etc.).

```
export KIWI_CONFIG=app_name.settings.tests
```

It is very useful to override some config options in tests. `KiwiConfig.override` will override config options defined
in the settings module. It works as a context manager or a decorator to provide explicit setup & clean up for overridden options.

```python
from app_name.settings import config

# DEBUG will be `True` for `test_everything`
@config.override(DEBUG=True)
def test_everything():
    # DEBUG will be `False` again for this block 
    with config.override(DEBUG=False):
        ...
```

Overrides could be nested, and deeper level has precedence over all levels above:

```python
from app_name.settings import config

@config.override(FOO=1, BAR=2)
def test_many_things():
    with config.override(BAR=3):
        assert config.FOO == 1
        assert config.BAR == 3
    # As it was before
    assert config.BAR == 2
```

Also, override works for classes (including inherited from `unittest.TestCase`):

```python
@config.override(INTEGER=123)
class TestOverride:

    def test_override(self):
        assert config.INTEGER == 123

    @config.override(INTEGER=456)
    def test_another_override(self):
        assert config.INTEGER == 456

def test_not_affected():
    assert config.INTEGER == 1
```

NOTE. `setup_class/setUp` and `teardown_class/tearDown` methods will work with `override`.

`kwonfig` includes a pytest integration that gives you a fixture, that allows you to override given config without
using a context manager/decorator approach and automatically rollbacks changes made:

```python
import pytest
from app_name.settings import config
from kwonfig.pytest_plugin import make_fixture

# create a fixture. the default name is "settings",
# but could be specified via `name` option
make_fixture(config)

@pytest.fixture
def global_settings(settings):
    settings.INTEGER = 456


@pytest.mark.usefixtures("global_settings")
def test_something(settings):
    assert settings.INTEGER == 456
    assert config.INTEGER == 456

    # fixture overriding
    settings.INTEGER = 123
    assert settings.INTEGER == 123
    assert config.INTEGER == 123

    # context manager should work as well
    with settings.override(INTEGER=7):
        assert settings.INTEGER == 7
        assert config.INTEGER == 7
    
    # Context manager changes are rolled back
    assert settings.INTEGER == 123
    assert config.INTEGER == 123


# This test is not affected by the fixture
def test_disable(settings):
    assert config.INTEGER == 1
    assert settings.INTEGER == 1
```

NOTE. It is forbidden to create two fixtures from the same config instances.

### Extras

The environment variable name could be customized via `config_variable_name` option:

```python
config = KiwiConfig(config_variable_name="APP_CONFIG")
```

Alternatively, it is possible to specify class-based settings:

```python
from kwonfig import env, vault


class ProductionSettings:
    VAULT_ADDR = env("VAULT_ADDR")
    VAULT_TOKEN = env("VAULT_TOKEN")
    
    DEBUG = env("DEBUG", default=False)
    DATABASE_URI = vault("path/to/db")
```

It possible to load the whole config and get its content as a dict:

```python
>>> config.asdict()
{
    "ENV": "env value",
    "KEY": "static value",
    "SECRET": "secret_value",
}
```

If you need to validate that certain variables are present in the config, there is `require`:

```python
>>> config.require("SECRET")
...
MissingError: Options ['SECRET'] are required
```

Or to check that they are defined:

```python
>>> "SECRET" in config
True
```

## Configuration 101

There are a couple of principles that will help you to avoid problems when you specify or use your configuration.

### Do not access configuration on the module level

Do this:

```python
from app_name.settings import config

def get_redis_client():
    return StrictRedis.from_url(config.REDIS_URL)
```

Instead of this:

```python
from redis import StrictRedis
from app_name.settings import config

cache_redis = StrictRedis.from_url(config.REDIS_URL)
```

However, if you want to have a global Redis instance, consider using `python-lazy-object-proxy`:

```bash
pip install lazy-object-proxy
```

```python
import lazy_object_proxy

...

cache_redis = lazy_object_proxy.Proxy(get_redis_client)
```

#### Why?

Accessing configuration on the module level leads to side-effects on imports, this fact could produce unrelated
errors when you run your test suite:

- Simple unit tests will fail due to lack of configuration options or Vault unavailability;
- Slow tests due to config initialization and long network calls (they could time out as well);

Having your config access lazy will prevent many for those cases because that code branches won't be executed on 
imports and will not affect your test suite.

## Code formatting

In order to maintain code formatting consistency we use [black](https://github.com/ambv/black/)
to format the python files. A pre-commit hook that formats the code is provided but it needs to be
installed on your local git repo, so...

In order to install the pre-commit framework run `pip install pre-commit`
or if you prefer homebrew `brew install pre-commit`

Once you have installed pre-commit just run `pre-commit install` on your repo folder

If you want to exclude some files from Black (e.g. automatically generated
database migrations or test [snapshots](https://github.com/syrusakbary/snapshottest))
please follow instructions for [pyproject.toml](https://github.com/ambv/black#pyprojecttoml)

## Testing

To run all tests:

```bash
docker run -p 8200:8200 -d --cap-add=IPC_LOCK -e 'VAULT_DEV_ROOT_TOKEN_ID=test_root_token' vault:0.9.6
tox -p all
```

Note that tox doesn't know when you change the `requirements.txt`
and won't automatically install new dependencies for test runs.
Run `pip install tox-battery` to install a plugin which fixes this silliness.

It also possible to run tests via docker-compose that will start up all
required environment:

```bash
$ make docker-test
```

or alternatively:

```bash
$ docker-compose -f docker-compose-tests.yml run kwonfig
```

## Contributing

TODO
