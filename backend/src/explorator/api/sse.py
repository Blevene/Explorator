"""Server-Sent Events helpers for round progress."""

import asyncio
import contextlib
import json
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any


class SSEChannel:
    """A channel that collects SSE events during a round."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self._queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._closed = False

    async def send(self, event_type: str, data: dict[str, Any]) -> None:
        """Push an event to the channel."""
        event = {"event": event_type, "data": data}
        self.events.append(event)
        await self._queue.put(event)

    async def close(self) -> None:
        """Signal end of stream.

        Idempotent: the sentinel is enqueued at most once. The background task's
        ``finally`` and the stream wrapper's cancel path may both call this, so a
        second call must be a harmless no-op (otherwise two sentinels could be
        enqueued, or — for callers awaiting drain — deadlock).
        """
        if self._closed:
            return
        self._closed = True
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


async def cancel_on_disconnect(
    channel: SSEChannel,
    task: "asyncio.Task[Any]",
) -> AsyncIterator[dict[str, str]]:
    """Stream a channel, cancelling ``task`` when the stream closes.

    The round work is launched detached via ``asyncio.create_task``. When the
    client disconnects (navigation / the frontend's AbortController), sse-starlette
    cancels only this generator — not the detached task. Wrapping the stream lets
    us propagate that cancellation: on disconnect OR normal end we cancel the task
    so ``graph.ainvoke`` (and its real LLM spend) stops instead of running to
    completion.

    Cancelling mid-round is safe here: in-memory mode is ephemeral, and Neo4j
    persistence writes nodes per-item under their own try/except, so a partial
    round leaves at most some already-committed candidates rather than a corrupt
    state. The ``if not task.done()`` guard skips cancelling a task that already
    finished (the normal-completion path), and ``SSEChannel.close()`` is idempotent
    so the task's ``finally`` close and this teardown can't double-enqueue or
    deadlock.
    """
    try:
        async for event in channel.stream():
            yield event
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
