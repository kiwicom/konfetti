.. _-konfetti-:

🎊 konfetti 🎊
==============

|codecov| |Build| |Version| |Python versions| |License|

Description
-----------

``konfetti`` is a Python configuration management system with an intuitive
API, lazy evaluation and (a)sync Vault support.

The interface design and features are heavily inspired by `decouple`_, `Django`_, `envparse`_ and `dynaconf`_.

**Key features**:

-  Lazy evaluation;
-  Built-in environment variables support;
-  Built-in async Vault access support;
-  Helpers for tests;
-  Django integration.

**Benefits of lazy evaluation**:

-  Faster & simpler test runs; No need for evaluation the the whole
   project config if it is not used
-  Avoid network calls during imports until necessary;

Quickstart
----------

To use ``konfetti`` you need to define:

-  configuration variables in a module or a class;
-  an access point;

Settings module
^^^^^^^^^^^^^^^

.. code:: python

   # app_name/settings/production.py
   from konfetti import env, vault

   VAULT_ADDR = env("VAULT_ADDR")
   VAULT_TOKEN = env("VAULT_TOKEN")

   DEBUG = env("DEBUG", default=False)
   DATABASE_URI = vault("path/to/db")

The naming convention for variables names is upper case, other variables
will be ignored. To work with Vault it is required to specify
``VAULT_ADDR`` and ``VAULT_TOKEN`` in the settings module.

Access point
^^^^^^^^^^^^

.. code:: python

   # app_name/settings/__init__.py
   from konfetti import Konfig, AsyncVaultBackend

   config = Konfig(vault_backend=AsyncVaultBackend("/secret/team"))

``konfetti`` relies on ``KONFETTI_SETTINGS`` environment variable to
discover your settings module, in the case above:

``export KONFETTI_SETTINGS=app_name.settings.production``

Alternatively the access point could be initiated from an object, importable string, mapping or a JSON file.

.. code:: python

   class TestSettings:
       VALUE = "secret"
   config = Konfig.from_object(TestSettings, ...)

.. code:: python

   config = Konfig.from_object("path.to.settings", ...)

   # If the config is in the same module
   SECRET = vault("/path/to")["secret"]
   config = Konfig.from_object(__name__, ...)

.. code:: python

   config = Konfig.from_mapping({"SECRET": 42}, ...)

.. code:: python

   config = Konfig.from_json("/path/to.json")

Usage
^^^^^

The settings module/class with configuration options shouldn't be
accessed directly, because the aforementioned features are implemented
in the access point level.

.. code:: python

   from app_name.settings import config

   async def something():
       await config.DATABASE_URI  # asynchronously taken from Vault
       debug = config.DEBUG  # Usual sync access

Documentation
-------------

For full documentation, please see https://konfetti.readthedocs.io/en/latest/

Or you can look at the ``docs/`` directory in the repository.

Python support
--------------

Konfetti supports Python 2.7, 3.5, 3.6, 3.7 and 3.8

License
-------

The code in this project is licensed under `MIT license`_. By contributing to `konfetti`, you agree that your contributions will be licensed under its MIT license.

.. |codecov| image:: https://codecov.io/gh/kiwicom/konfetti/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/kiwicom/konfetti
.. |Build| image:: https://travis-ci.org/kiwicom/konfetti.svg?branch=master
   :target: https://travis-ci.org/kiwicom/konfetti
.. |Version| image:: https://img.shields.io/pypi/v/konfetti.svg
   :target: https://pypi.org/project/konfetti/
.. |Python versions| image:: https://img.shields.io/pypi/pyversions/konfetti.svg
   :target: https://pypi.org/project/konfetti/
.. |License| image:: https://img.shields.io/pypi/l/konfetti.svg
   :target: https://opensource.org/licenses/MIT

.. _Django: https://github.com/django/django
.. _decouple: https://github.com/henriquebastos/python-decouple
.. _envparse: https://github.com/rconradharris/envparse
.. _dynaconf: https://github.com/rochacbruno/dynaconf

.. _MIT license: https://opensource.org/licenses/MIT
