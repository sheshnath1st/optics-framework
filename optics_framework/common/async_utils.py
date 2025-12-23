import asyncio
from typing import Any, Coroutine
from optics_framework.common.logging_config import internal_logger


def run_async(coro: Coroutine[Any, Any, Any]):
    """
    Run async coroutine safely from sync code.
    Handles nested event loops (pytest, Jupyter, asyncio frameworks).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None:
        internal_logger.debug("[AsyncUtils] No running loop → asyncio.run()")
        return asyncio.run(coro)

    internal_logger.debug("[AsyncUtils] Running loop detected → thread-safe execution")
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()
