"""Required to avoid SyntaxError on Python 2."""
import asyncio
from functools import wraps
from typing import Any

from .utils import iscoroutine, rebuild_dict


def wrap_coro(context_manager, coro):
    """Wrap a coro with the given context manager."""

    @wraps(coro)
    async def inner(*args, **kwargs):
        # type: (*Any, **Any) -> Any
        with context_manager:
            return await coro(*args, **kwargs)

    return inner


def make_async_callback(coro, callback):
    """Wrap calling of the callback on the coro result in a coro.

    Needed to provide an awaitable response to the Konfig users.
    """

    async def inner():
        data = await coro
        return callback(data)

    return inner()


def make_simple_coro(value):
    """Help to emulate async interfaces."""

    async def inner():
        return value

    return inner()


async def async_process_dict(data, callback):
    """The given dictionary could contain coros as leaves.

    Return a copy of the given dictionaries with all coroutines evaluated.

    NOTE. Only dictionaries are supported as nested values.
    """
    coros = []

    # Re-create dict only once?

    # Collect all coroutines and convert to Task instances to await them via `asyncio.gather`
    def collect_coros(value):
        value = callback(value)
        if iscoroutine(value):
            value = asyncio.ensure_future(value)
            coros.append(value)
        return value

    tasks = rebuild_dict(data, collect_coros)

    # No need to run `gather` since there are no coros in the original dictionary
    if not coros:
        return tasks

    await asyncio.gather(*coros, return_exceptions=True)

    # Extract results from stored `Task` instances

    def get_task_result(value):
        if isinstance(value, asyncio.Task):
            value = value.result()
        return value

    return rebuild_dict(tasks, get_task_result)
