"""Sleep helpers.

Sleep is centralized to make tests easier and to keep executors simple.
"""

from __future__ import annotations

import asyncio
import time


def sleep(seconds: float) -> None:
    """Sleep synchronously for the given number of seconds."""
    time.sleep(seconds)


async def async_sleep(seconds: float) -> None:
    """Sleep asynchronously for the given number of seconds."""
    await asyncio.sleep(seconds)
