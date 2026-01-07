import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Coroutine
from optics_framework.common.logging_config import internal_logger

_persistent_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: threading.Thread | None = None
_loop_lock = threading.Lock()

# Shared executor to avoid thread churn
_executor = ThreadPoolExecutor(max_workers=1)


def _start_loop(loop: asyncio.AbstractEventLoop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


def _get_or_create_persistent_loop() -> asyncio.AbstractEventLoop:
    global _persistent_loop, _loop_thread

    with _loop_lock:
        if _persistent_loop is None or _persistent_loop.is_closed():
            internal_logger.info("[AsyncUtils] Creating persistent event loop")

            _persistent_loop = asyncio.new_event_loop()
            _loop_thread = threading.Thread(
                target=_start_loop,
                args=(_persistent_loop,),
                daemon=True,
                name="optics-async-loop"
            )
            _loop_thread.start()

    return _persistent_loop


def run_async(coro: Coroutine[Any, Any, Any]):
    """
    Safely run async coroutine from sync code.
    - Works with pytest / nested loops
    - Avoids deadlocks
    - Stable for Playwright
    """

    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    # 🔹 Case 1: No running loop → use persistent background loop
    if running_loop is None:
        loop = _get_or_create_persistent_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=30)

    # 🔹 Case 2: Running loop exists → avoid deadlock
    internal_logger.debug(
        "[AsyncUtils] Running loop detected → offloading to executor"
    )

    def _submit():
        future = asyncio.run_coroutine_threadsafe(coro, running_loop)
        return future.result(timeout=30)

    return _executor.submit(_submit).result(timeout=30)
