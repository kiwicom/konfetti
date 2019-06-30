import pytest

from konfetti.utils import flatten_dict, rebuild_dict


@pytest.mark.parametrize("value, expected", (({}, []), ({"A": 1}, [(["A"], 1)]), ({"A": {"B": 1}}, [(["A", "B"], 1)])))
def test_flatten_dict(value, expected):
    assert list(flatten_dict(value)) == expected


def callback(value):
    return value + 1


@pytest.mark.parametrize("value, expected", (({}, {}), ({"A": 1}, {"A": 2}), ({"A": {"B": 1}}, {"A": {"B": 2}})))
def test_rebuild_dict(value, expected):
    assert rebuild_dict(value, callback) == expected
