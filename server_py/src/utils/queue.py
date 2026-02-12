import asyncio
import logging
import uuid
from typing import Callable, Optional

logger = logging.getLogger("app")


class RequestQueue:
    """Async concurrency limiter for AI requests.

    Mirrors the Node.js RequestQueue from server/src/utils/queue.js.
    Uses an asyncio.Semaphore for concurrency control and a list
    for tracking queued tasks and notifying them of position.
    """

    def __init__(self, concurrency: int = 5):
        self.concurrency = concurrency
        self._semaphore = asyncio.Semaphore(concurrency)
        self._active = 0
        self._queue: list[dict] = []
        self._lock = asyncio.Lock()

    async def enqueue(
        self,
        task_factory: Callable,
        on_waiting: Optional[Callable] = None,
    ):
        """Queue an async task for execution.

        Args:
            task_factory: Async callable that returns the result.
            on_waiting: Optional callback(position) called when queued.

        Returns:
            The result of task_factory().
        """
        task_id = str(uuid.uuid4())

        # If semaphore is locked, notify the caller of their position
        if self._semaphore.locked() and on_waiting:
            logger.info(f"[Queue] Semaphore locked! Enqueuing task {task_id}")
            async with self._lock:
                position = len(self._queue) + 1
                self._queue.append({"id": task_id, "on_waiting": on_waiting})
            on_waiting(position)
            # Notify all queued tasks of updated positions
            await self._notify_positions()

        async with self._semaphore:
            # Remove from queue if present
            async with self._lock:
                self._queue = [t for t in self._queue if t["id"] != task_id]
                self._active += 1

            await self._notify_positions()

            try:
                logger.info(f"[Queue] Starting task {task_id}. Active: {self._active}")
                result = await task_factory()
                return result
            except Exception as e:
                logger.error(f"[Queue] Task {task_id} failed: {e}")
                raise
            finally:
                async with self._lock:
                    self._active -= 1
                logger.info(f"[Queue] Task {task_id} finished. Active: {self._active}")

    async def _notify_positions(self):
        """Notify all waiting tasks of their current position."""
        async with self._lock:
            for i, task in enumerate(self._queue):
                if task.get("on_waiting"):
                    try:
                        task["on_waiting"](i + 1)
                    except Exception:
                        pass

    def get_stats(self) -> dict:
        return {
            "active": self._active,
            "queued": len(self._queue),
            "concurrency": self.concurrency,
        }
