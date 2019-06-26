import pytest

from kwonfig import lazy

pytestmark = [pytest.mark.usefixtures("settings")]


def test_decorator(config):
    assert config.LAZY_PROPERTY == "value/value/important"


def test_lambda(config):
    assert config.LAZY_LAMBDA == "value/value/important"


def test_lambda_forbid_to_call():
    with pytest.raises(RuntimeError, match="LazyVariable already has a callable assigned"):

        @lazy(lambda config: 1)
        def anything(config):
            pass


def test_cast(config):
    assert lazy(lambda c: 1, cast=str).evaluate(config) == "1"


def test_default(config):
    assert lazy(lambda c: c.UNKNOWN, default="TEST").evaluate(config) == "TEST"
