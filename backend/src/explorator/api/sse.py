"""Server-Sent Events helpers for round progress."""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any


class SSEChannel:
    """A channel that collects SSE events during a round."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self._queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    async def send(self, event_type: str, data: dict[str, Any]) -> None:
        """Push an event to the channel."""
        event = {"event": event_type, "data": data}
        self.events.append(event)
        await self._queue.put(event)

    async def close(self) -> None:
        """Signal end of stream."""
        await self._queue.put(None)

    async def stream(self) -> AsyncGenerator[dict[str, str], None]:
        """Yield dicts formatted for sse-starlette's EventSourceResponse.

        EventSourceResponse expects dicts with 'event' and 'data' keys.
        It handles the SSE wire format (event: / data: / newlines) itself.
        """
        while True:
            event = await self._queue.get()
            if event is None:
                break
            yield {
                "event": event["event"],
                "data": json.dumps(event["data"]),
            }
