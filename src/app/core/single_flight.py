"""Single-flight jobs (api-and-integration): at most one run per key at a time.

A caller that asks for a job already running joins it and receives its result, instead of
starting a second run. Holly uses it so a manual refresh during the hourly notification cycle,
or two analysts evaluating the same notification at once, cost one run, not two.
"""

import asyncio
from collections.abc import Awaitable, Callable


class SingleFlight[T]:
    def __init__(self) -> None:
        self._running: dict[str, asyncio.Future[T]] = {}

    async def run(self, key: str, job: Callable[[], Awaitable[T]]) -> T:
        running = self._running.get(key)
        if running is not None:
            return await asyncio.shield(running)
        future: asyncio.Future[T] = asyncio.get_running_loop().create_future()
        self._running[key] = future
        try:
            result = await job()
        except asyncio.CancelledError:
            future.cancel()
            raise
        except Exception as exc:
            future.set_exception(exc)
            # Mark the exception as retrieved, so a run nobody joined does not log a warning.
            future.exception()
            raise
        else:
            future.set_result(result)
            return result
        finally:
            del self._running[key]
