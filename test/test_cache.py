from datetime import timedelta

import pytest

from konfetti.cache import EMPTY, InMemoryCache


@pytest.fixture
def cache():
    return InMemoryCache()


@pytest.fixture
def ttl_cache():
    return InMemoryCache(ttl=0.001)


@pytest.mark.parametrize(
    "value, expected",
    ((1, timedelta(seconds=1)), (5.3, timedelta(seconds=5.3)), (timedelta(seconds=5), timedelta(seconds=5))),
)
def test_ttl_value(value, expected):
    assert InMemoryCache(ttl=value).ttl == expected


def test_getitem(cache):
    with pytest.raises(KeyError):
        cache["key"]


def test_get(cache):
    assert cache.get("key") is EMPTY


def test_setitem(cache):
    cache["key"] = "value"
    assert cache["key"] == "value"


def test_set(cache):
    cache.set("key", "value")
    assert cache["key"] == "value"


def test_contains(cache):
    cache["key"] = "value"
    assert "key" in cache


def test_not_contains(cache):
    assert "random" not in cache


@pytest.mark.parametrize("action", (lambda c: c.get("key") is EMPTY, lambda c: "key" not in c), ids=["get", "contains"])
@pytest.mark.freeze_time
def test_ttl_cache(ttl_cache, freezer, action):
    ttl_cache["key"] = "value"
    assert "key" in ttl_cache
    assert ttl_cache.get("key") == "value"
    freezer.tick(5)
    assert action(ttl_cache)
    assert not ttl_cache._data


@pytest.mark.freeze_time
def test_ttl_cache_getitem(ttl_cache, freezer):
    ttl_cache["key"] = "value"
    assert "key" in ttl_cache
    assert ttl_cache["key"] == "value"
    freezer.tick(5)
    with pytest.raises(KeyError):
        ttl_cache["key"]
    assert not ttl_cache._data


def test_clear_cache(cache):
    cache["key"] = "value"
    assert cache["key"] == "value"
    cache.clear()
    assert "key" not in cache
