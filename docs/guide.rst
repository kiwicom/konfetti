Configuration 101
-----------------

There are a couple of principles that will help you to avoid problems
when you specify or use your configuration.

Do not access configuration on the module level
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Do this:

.. code:: python

   from app_name.settings import config

   def get_redis_client():
       return StrictRedis.from_url(config.REDIS_URL)

Instead of this:

.. code:: python

   from redis import StrictRedis
   from app_name.settings import config

   cache_redis = StrictRedis.from_url(config.REDIS_URL)

In this case on each usage the redis client will be re-evaluated, which
might be not good for performance reasons.

As an alternative you could have a global Redis instance by using
``python-lazy-object-proxy``:

.. code:: bash

   pip install lazy-object-proxy

.. code:: python

   import lazy_object_proxy

   ...

   cache_redis = lazy_object_proxy.Proxy(get_redis_client)

**NOTE**. Do not forget to clean up shared resources when it is needed,
usually on the application / testcase teardown.

Why?
^^^^

Accessing configuration on the module level leads to side-effects on
imports, this fact could produce unrelated errors when you run your test
suite:

-  Simple unit tests will fail due to lack of configuration options or
   Vault unavailability;
-  Slow tests due to config initialization and long network calls (they
   could time out as well);

Having your config access lazy will prevent many for those cases because
that code branches won't be executed on imports and will not affect your
test suite.