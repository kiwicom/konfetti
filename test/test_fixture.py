import pytest

pytestmark = [pytest.mark.usefixtures("settings", "vault_data")]


def test_fixtures(testdir):
    testdir.makepyfile(
        """
    import pytest
    from settings import config
    from konfetti.pytest_plugin import make_fixture

    make_fixture(config)

    @pytest.fixture
    def global_settings(settings):
        settings.INTEGER = 456
        settings.SECRET = "NOOO"

    @pytest.fixture
    def global_settings2(settings):
        settings.INTEGER = 43

    @pytest.fixture
    def inherited_settings(global_settings, settings):
        settings.SECRET = "rewritten"

    @pytest.fixture
    def not_used_settings(settings):
        pass

    @pytest.mark.usefixtures("global_settings")
    def test_pytest_fixture(settings):
        # set from `global_settings`
        assert settings.INTEGER == 456
        assert config.INTEGER == 456

        # fixture overriding
        settings.INTEGER = 123
        assert settings.INTEGER == 123
        assert config.INTEGER == 123

        # context manager should work as well
        with settings.override(KEY="overridden1", INTEGER=7):
            with settings.override(KEY="overridden"):
                assert settings.INTEGER == 7
                assert config.INTEGER == 7
                assert settings.KEY == "overridden"
                assert config.KEY == "overridden"
            assert settings.KEY == "overridden1"
            assert config.KEY == "overridden1"

        # should be restored to the state before the context manager
        assert settings.INTEGER == 123
        assert config.INTEGER == 123
        assert settings.KEY == "value"
        assert config.KEY == "value"

    @pytest.mark.usefixtures("global_settings2")
    def test_another_pytest_fixture(settings):
        # Should use only overrides from `global_settings2`
        # `global_settings` should be already rolled back
        assert config.INTEGER == 43
        assert settings.INTEGER == 43
        assert config.SECRET == "value"
        assert settings.SECRET == "value"

    @pytest.mark.usefixtures("inherited_settings")
    def test_multi_fixture(settings):
        assert config.SECRET == "rewritten"
        assert settings.SECRET == "rewritten"

    @pytest.mark.usefixtures("not_used_settings")
    def test_not_used_settings(settings):
        assert config.INTEGER == 1
        assert settings.INTEGER == 1

    def test_disable(settings):
        assert config.INTEGER == 1
        assert settings.INTEGER == 1
    """
    )
    result = testdir.runpytest()
    result.assert_outcomes(passed=5)


def test_invalid_name(testdir):
    testdir.makepyfile(
        """
    import pytest
    from settings import config
    from konfetti.pytest_plugin import make_fixture

    make_fixture(config, name="config")
    """
    )
    result = testdir.runpytest()
    result.assert_outcomes(error=1)
    result.stdout.fnmatch_lines(
        [
            "*RuntimeError: Module `test_invalid_name` already has a member with name `config`. "
            "Use another name for this fixture*"
        ]
    )
