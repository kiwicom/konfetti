.. _contributing:

Contributing
------------

Code formatting
~~~~~~~~~~~~~~~

In order to maintain code formatting consistency we use
`black <https://github.com/ambv/black/>`__ to format the python files. A
pre-commit hook that formats the code is provided but it needs to be
installed on your local git repo, so...

In order to install the pre-commit framework run
``pip install pre-commit`` or if you prefer homebrew
``brew install pre-commit``

Once you have installed pre-commit just run ``pre-commit install`` on
your repo folder

If you want to exclude some files from Black (e.g. automatically
generated database migrations or test
`snapshots <https://github.com/syrusakbary/snapshottest>`__) please
follow instructions for
`pyproject.toml <https://github.com/ambv/black#pyprojecttoml>`__

Testing
~~~~~~~

To run all tests:

.. code:: bash

   docker run -p 8200:8200 -d --cap-add=IPC_LOCK -e 'VAULT_DEV_ROOT_TOKEN_ID=test_root_token' vault:0.9.6
   tox -p all

Note that tox doesn't know when you change the ``requirements.txt`` and
won't automatically install new dependencies for test runs. Run
``pip install tox-battery`` to install a plugin which fixes this
silliness.

It also possible to run tests via docker-compose that will start up all
required environment:

.. code:: bash

   $ make docker-test

or alternatively:

.. code:: bash

   $ docker-compose -f docker-compose-tests.yml run konfetti
