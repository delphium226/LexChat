"""Small helpers shared by the tool executors."""

import asyncio
from typing import Callable, Optional


async def _emit(on_chunk: Optional[Callable], data: dict):
    """Helper to emit events if callback is provided."""
    if on_chunk:
        res = on_chunk(data)
        if asyncio.iscoroutine(res):
            await res
