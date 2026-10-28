import contextlib

from cachalot.api import cachalot_disabled


@contextlib.contextmanager
def no_query_cache():
    """``cachalot_disabled()`` that is restored even when the block raises, so one failing test stays one.

    Use it around query-count assertions, which the query cache would otherwise hide.
    """
    context = cachalot_disabled()
    context.__enter__()
    try:
        yield
    finally:
        context.__exit__(None, None, None)
