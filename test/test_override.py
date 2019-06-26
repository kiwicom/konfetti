import sys

import pytest

from kwonfig import KiwiConfig
from kwonfig.exceptions import ForbiddenOverrideError

pytestmark = [pytest.mark.usefixtures("settings")]


skip_if_py2 = pytest.mark.skipif(sys.version_info[0] == 2, reason="Async syntax is not supported on Python 2.")


def test_override_function(testdir):
    """`override` decorator allows users to set custom config values per test function."""
    testdir.makepyfile(
        """
    from settings import config
    import pytest

    @pytest.fixture
    def example():
        return "test"

    @config.override(INTEGER=123)
    def test_override_function():
        assert config.INTEGER == 123

    @config.override(INTEGER=123)
    def test_override_function_with_fixture(example):
        assert config.INTEGER == 123
        assert example == "test"

    @config.override(INTEGER=123)
    @pytest.mark.parametrize("x", [1, 2])
    def test_override_function_with_parametrize(example, x):
        assert config.INTEGER == 123
        assert example == "test"
        assert isinstance(x, int)

    @pytest.mark.parametrize("x", [1, 2])
    @config.override(INTEGER=123)
    def test_override_function_with_parametrize_first(example, x):
        assert config.INTEGER == 123
        assert example == "test"
        assert isinstance(x, int)

    def test_disable():
        assert config.INTEGER == 1
    """
    )
    result = testdir.runpytest("-s")
    result.assert_outcomes(passed=7)


def test_override_vault_secret(testdir):
    """Vault vault should be overridden correctly."""
    testdir.makepyfile(
        """
    from settings import config

    @config.override(SECRET="not secret")
    def test_override_function():
        assert config.SECRET == "not secret"

    def test_disable():
        assert config.INTEGER == 1
    """
    )
    result = testdir.runpytest()
    result.assert_outcomes(passed=2)


def test_override_method(testdir):
    """`override` decorator also works for class methods."""
    testdir.makepyfile(
        """
    from settings import config
    import pytest

    @pytest.fixture
    def example():
        return "test"

    class TestOverride:

        @config.override(INTEGER=123)
        def test_override(self):
            assert config.INTEGER == 123

        @config.override(INTEGER=123)
        def test_override_with_fixture(self, example):
            assert config.INTEGER == 123
            assert example == "test"

        def test_disable_on_method(self):
            assert config.INTEGER == 1

    def test_disable_on_function():
        assert config.INTEGER == 1
    """
    )
    result = testdir.runpytest()
    result.assert_outcomes(passed=4)


def test_override_class(testdir):
    """`override` decorator also works for classes."""
    testdir.makepyfile(
        """
    from settings import config
    import pytest

    @pytest.fixture
    def example():
        return "test"

    @config.override(INTEGER=123)
    class TestOverride:

        def test_override(self):
            assert config.INTEGER == 123

        def test_override_with_fixture(self, example):
            assert config.INTEGER == 123
            assert example == "test"

        @config.override(INTEGER=456)
        def test_another_override(self, example):
            assert config.INTEGER == 456
            assert example == "test"

    def test_disable_on_function():
        assert config.INTEGER == 1
    """
    )
    result = testdir.runpytest()
    result.assert_outcomes(passed=4)


def test_override_class_with_setup(testdir):
    """`override` decorator also works for classes that have custom `setup_class` and `teardown_class` methods."""
    testdir.makepyfile(
        """
    from settings import config

    @config.override(INTEGER=123)
    class TestOverride:

        @classmethod
        def setup_class(cls):
            cls.attr = 42

        def test_override(self):
            assert self.attr == 42
            assert config.INTEGER == 123

        def test_another_override(self):
            assert self.attr == 42
            assert config.INTEGER == 123

        @classmethod
        def teardown_class(cls):
            print("TearDown call")

    def test_disable_on_function():
        assert config.INTEGER == 1
    """
    )
    result = testdir.runpytest("-s")
    result.assert_outcomes(passed=3)
    result.stdout.fnmatch_lines(["*TearDown call*"])


def test_override_unittest_class(testdir):
    """`override` decorator also works for unittest-style classes."""
    testdir.makepyfile(
        """
    import unittest
    from settings import config

    @config.override(INTEGER=123)
    class TestOverride(unittest.TestCase):

        def test_override(self):
            assert config.INTEGER == 123

        def test_another_override(self):
            assert config.INTEGER == 123

    def test_disable_on_function():
        assert config.INTEGER == 1
    """
    )
    result = testdir.runpytest()
    result.assert_outcomes(passed=3)


def test_override_unittest_class_custom_setup(testdir):
    """If unittest-style class has custom `setUp` and `tearDown` then `override` should work as well."""
    testdir.makepyfile(
        """
    import unittest
    from settings import config

    @config.override(INTEGER=123)
    class TestOverride(unittest.TestCase):

        def setUp(self):
            self.func = 1

        @classmethod
        def setUpClass(cls):
            cls.cls = 2

        def test_override(self):
            assert self.func == 1
            assert self.cls == 2
            assert config.INTEGER == 123

        def test_another_override(self):
            assert self.func == 1
            assert self.cls == 2
            assert config.INTEGER == 123

        def tearDown(self):
            print("TearDown call")

        @classmethod
        def tearDownClass(cls):
            print("TearDownClass call")

    def test_disable_on_function():
        assert config.INTEGER == 1
    """
    )
    result = testdir.runpytest("-s")
    result.assert_outcomes(passed=3)
    result.stdout.fnmatch_lines(["*TearDownClass call*"])
    result.stdout.fnmatch_lines(["*TearDown call*"])


def test_override_custom_setup_error(testdir):
    """When an error occurs in a custom setup method config should be unconfigured."""
    testdir.makepyfile(
        """
    from settings import config

    @config.override(INTEGER=123)
    class TestOverride:

        @classmethod
        def setup_class(cls):
            1 / 0

        def test_override(self):
            print("NOT EXECUTED")

        @classmethod
        def teardown_class(cls):
            1 / 0

    def test_disabled():
        assert config.INTEGER == 1
    """
    )
    result = testdir.runpytest("-s")
    result.assert_outcomes(passed=1, error=1)
    assert "NOT EXECUTED" not in result.stdout._log_text


@skip_if_py2
def test_async_test(testdir):
    """`override` decorator works for async tests."""
    testdir.makepyfile(
        """
    import pytest
    from settings import config

    pytestmark = pytest.mark.asyncio

    @config.override(INTEGER=123)
    async def test_override_per_test():
        assert config.INTEGER == 123

    async def test_disable():
        assert config.INTEGER == 1
    """
    )
    result = testdir.runpytest()
    result.assert_outcomes(passed=2)


def test_override_unknown_type(config):
    """`override` can't decorate arbitrary types."""
    with pytest.raises(TypeError, match="Don't know how to use `override` for `int`"):
        config.override(INTEGER=123)(123)


def test_override_unknown_option():
    """If an option passed to `override` doesn't exist in the config module an error should be risen.

    Active only with `strict_override` config option.
    """
    config = KiwiConfig(strict_override=True)
    with pytest.raises(
        ForbiddenOverrideError,
        match="Can't override `NOT_EXIST` config option, because it is not defined in the config module",
    ):
        with config.override(NOT_EXIST=123):
            pass


def test_strict_override_valid():
    config = KiwiConfig(strict_override=True)
    with config.override(INTEGER=123):
        assert config.INTEGER == 123


def test_override_context_manager(config):
    """It is possible to use it as a context manager."""
    with config.override(INTEGER=123):
        assert config.INTEGER == 123
    assert config.INTEGER == 1


def test_override_context_manager_nested(testdir):
    """Multiple levels of overriding are nested."""
    testdir.makepyfile(
        """
    from settings import config

    def test_context_manager():
        with config.override(INTEGER=123):
            with config.override(KEY="overridden"):
                assert config.INTEGER == 123
                assert config.KEY == "overridden"
            assert config.KEY == "value"
            assert config.INTEGER == 123
        assert config.INTEGER == 1
        assert config.KEY == "value"

    @config.override(KEY="foo")
    def test_context_manager_with_decorator():
        assert config.KEY == "foo"
        with config.override(INTEGER=123):
            with config.override(KEY="overridden"):
                assert config.INTEGER == 123
                assert config.KEY == "overridden"
            assert config.KEY == "foo"
            assert config.INTEGER == 123
        assert config.INTEGER == 1
        assert config.KEY == "foo"

    def test_disable():
        assert config.INTEGER == 1
    """
    )
    result = testdir.runpytest()
    result.assert_outcomes(passed=3)


def test_no_setup_on_override(mocked_import_config_module):
    """If overridden option is accessed, then config is not loaded."""
    config = KiwiConfig(strict_override=False)
    with config.override(EXAMPLE="awesome"):
        assert config.EXAMPLE == "awesome"
    mocked_import_config_module.assert_not_called()


def test_setup_on_override(mocked_import_config_module):
    """If non-overridden option is accessed, then config should be loaded."""
    config = KiwiConfig()
    with config.override(SOMETHING="awesome"):
        assert config.EXAMPLE == "test"
    # Py2.7, Py3.5: replace with `assert_called` when 2.7/3.5 support will be dropped.
    assert mocked_import_config_module.called is True
    assert mocked_import_config_module.call_count >= 1
