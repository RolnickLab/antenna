import contextlib

from cachalot.api import cachalot_disabled


@contextlib.contextmanager
def no_query_cache():
    """Stop reads in a block from using the cachalot query cache, and restore the previous state even when it raises.

    Writes still invalidate cached tables inside the block; only reads bypass the cache.
    Use this instead of ``cachalot.api.cachalot_disabled()``, which only restores the state on a clean
    exit: one exception leaves the cache off for the rest of the thread, so a Celery worker stays
    uncached until its process is recycled and later query-count tests in the same process fail.
    Works as a decorator too, re-entered on every call.
    """
    context = cachalot_disabled()
    context.__enter__()
    try:
        yield
    finally:
        context.__exit__(None, None, None)
