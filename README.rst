.. _-konfetti-:

🎊 konfetti 🎊
==============

|codecov| |Build| |Version| |Python versions| |License|

Description
-----------

``konfetti`` is a Python configuration management library that simplifies the process of setting up your application to run on your company’s infrastructure.

This library will help you to retrieve secrets from Vault, manages the access to settings required by our monitoring services, such as Datadog and Sentry, and set up tests for evaluating your app's behavior.

Konfetti manages your app's configuration settings through lazy evaluation: It only calls and configures what your app needs and when it needs it.

Key benefits:
^^^^^^^^^^^^^

**Configurable lazy evaluation** - You can choose the moment when Konfetti will evaluate your the configuration of your app.

**Faster & simpler test runs** - No need for evaluating the configuration of the whole project if it's not used.

**Faster and flexible testing** - Isolating small parts of your application no longer requires you to perform a complete setup for each test.

**Integration with popular Web Application Frameworks** - Konfetti can seamlessly work with Django, Flask, and Celery.


The interface design and features are heavily inspired by `decouple`_, `Django`_, `envparse`_ and `dynaconf`_.


Quickstart
----------

Before Konfetti can perform its tasks, you'll need to create a settings module and then tell Konfetti the location of this module.

1. Creating the Settings Module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Please find the application settings, for your production, local, or other environments, using the following path:
``app_name/settings/production.py``

Next, please review the below code block and copy the relevant parts in your settings file.


> :warning: **Variables need to be named with all uppercase letters, other variables will be ignored**

> :warning: **If your app requires Vault access, then you'll need to specify `VAULT_ADDR` and `VAULT_TOKEN` in the settings module**


.. code:: python

   # app_name/settings/production.py
   from konfetti import env, vault

   VAULT_ADDR = env("VAULT_ADDR")
   VAULT_TOKEN = env("VAULT_TOKEN")

   DEBUG = env("DEBUG", default=False)
   DATABASE_URI = vault("path/to/db")

Apart from the import statement ``from konfetti import env, vault``, you can remove the settings for the features that you don't use.

If, for instance, you don’t use a database, then you can remove the `DATABASE_URI` variable. Depending on your settings, it might also be called `DB_URI`, or similar.

Furthermore, you can remove `VAULT_ADDR` and `VAULT_TOKEN` if your app doesn’t require secrets.

2. Configuring the Access Point
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: python

   # app_name/settings/__init__.py
   from konfetti import Konfig, AsyncVaultBackend

   config = Konfig(vault_backend=AsyncVaultBackend("/secret/team"))

In your app's environment variables, please add the KONFETTI_SETTINGS variable with the path to your settings module.  In the case of the code block above, it would be:

``export KONFETTI_SETTINGS=app_name.settings.production``

Alternatively the access point could be initiated from an object, importable string, mapping or a JSON file:

**Object**

.. code:: python

   class TestSettings:
       VALUE = "secret"
   config = Konfig.from_object(TestSettings, ...)

**Importable string**

.. code:: python

   config = Konfig.from_object("path.to.settings", ...)

   # If the config is in the same module
   SECRET = vault("/path/to")["secret"]
   config = Konfig.from_object(__name__, ...)

**Mapping**

.. code:: python

   config = Konfig.from_mapping({"SECRET": 42}, ...)

**JSON**

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
