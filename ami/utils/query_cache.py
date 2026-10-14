import contextlib

from cachalot.api import cachalot_disabled


@contextlib.contextmanager
def no_query_cache():
    """Turn off the cachalot query cache for a block, and turn it back on even when the block raises.

    Use this instead of ``cachalot.api.cachalot_disabled()``, which only re-enables the cache on a
    clean exit: one exception leaves the cache off for the rest of the thread, so a Celery worker
    stays uncached until restart and later query-count tests in the same process fail.
    Works as a decorator too, re-entered on every call.
    """
    context = cachalot_disabled()
    context.__enter__()
    try:
        yield
    finally:
        context.__exit__(None, None, None)
