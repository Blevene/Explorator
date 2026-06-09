"""Client-disconnect cancellation for the SSE round endpoints.

The generation/realization/mutation routes launch the round work detached via
``asyncio.create_task``. sse-starlette only cancels the streaming generator when
the client disconnects — not the detached task — so ``graph.ainvoke`` (and its
real Gemini spend) would otherwise run to completion against a stream nobody is
reading. ``cancel_on_disconnect`` wraps the stream and cancels the task when the
stream closes (disconnect OR normal end).

These tests exercise the shared helper directly with a real ``asyncio.Task``
running a stubbed graph that awaits a controllable Event, so cancellation is
deterministic and doesn't depend on sse-starlette internals.
"""
import asyncio

import pytest

from explorator.api.sse import SSEChannel, cancel_on_disconnect


def _start_round(channel: SSEChannel, started: asyncio.Event, release: asyncio.Event):
    """Build a detached round task mimicking the routes' ``run_and_close``.

    The "graph" emits one event, signals it has started, then blocks on
    ``release`` (an Event the test controls) — standing in for a long-running
    ``graph.ainvoke``. The ``finally`` closes the channel, exactly as the routes do.
    """

    async def run_and_close() -> None:
        try:
            await channel.send("round_started", {"round_id": "r1"})
            started.set()
            await release.wait()  # blocks until the test releases it
            await channel.send("round_completed", {"round_id": "r1"})
        finally:
            await channel.close()

    return asyncio.create_task(run_and_close())


@pytest.mark.asyncio
async def test_early_disconnect_cancels_background_task() -> None:
    """Closing the stream early cancels the still-running round task."""
    channel = SSEChannel()
    release = asyncio.Event()  # never set → the round would block forever
    started = asyncio.Event()
    task = _start_round(channel, started, release)

    stream = cancel_on_disconnect(channel, task)

    # Consume the first event, then disconnect by closing the generator early —
    # this is what sse-starlette does to the wrapper on client disconnect.
    first = await stream.__anext__()
    assert first["event"] == "round_started"
    await started.wait()
    assert not task.done()  # the round is still blocked on `release`

    await stream.aclose()  # triggers the helper's finally → cancels the task

    assert task.cancelled()
    assert not release.is_set()  # the round never reached completion


@pytest.mark.asyncio
async def test_normal_completion_does_not_cancel() -> None:
    """A round that finishes normally drains fully and is not cancelled."""
    channel = SSEChannel()
    release = asyncio.Event()
    started = asyncio.Event()
    task = _start_round(channel, started, release)

    events = []
    stream = cancel_on_disconnect(channel, task)

    first = await stream.__anext__()
    events.append(first["event"])
    await started.wait()

    release.set()  # let the round run to completion

    async for event in stream:  # drains round_completed + the close sentinel
        events.append(event["event"])

    await task  # already finished; must not raise
    assert not task.cancelled()
    assert events == ["round_started", "round_completed"]


@pytest.mark.asyncio
async def test_close_is_idempotent() -> None:
    """SSEChannel.close() can be called twice without enqueuing two sentinels.

    Both the task's ``finally`` and a teardown path may close the channel; a
    second sentinel would either leak or, for a drained queue, hang a reader.
    """
    channel = SSEChannel()
    await channel.send("x", {})
    await channel.close()
    await channel.close()  # no-op

    seen = [e["event"] async for e in channel.stream()]
    assert seen == ["x"]  # exactly one event, single sentinel terminated the stream
