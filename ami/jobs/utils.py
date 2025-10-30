import asyncio
import logging
import typing

logger = logging.getLogger(__name__)


def _run_in_async_loop(func: typing.Callable, error_msg: str) -> typing.Any:
    # helper to use new_event_loop() to ensure we're not mixing with Django's async context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(func())
    except Exception as e:
        logger.error(f"Error in async loop - {error_msg}: {e}")
        return None
    finally:
        loop.close()
