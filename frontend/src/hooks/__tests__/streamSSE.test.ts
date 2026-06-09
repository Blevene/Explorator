import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { streamSSE, STOP_STREAM, SSETimeoutError, type SSEEvent } from '../streamSSE';

/**
 * Build a Response whose body is a ReadableStream that yields the given byte
 * chunks (each chunk an already-encoded Uint8Array), one per `read()`.
 * `hang` keeps the stream open forever after the chunks (never closes), to
 * exercise the timeout path.
 */
function streamResponse(chunks: Uint8Array[], opts: { hang?: boolean; signal?: AbortSignal } = {}): Response {
  let i = 0;
  const body = new ReadableStream<Uint8Array>({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(chunks[i++]);
        return;
      }
      if (opts.hang) {
        // Simulate a stream that opens then hangs: the pending read() never
        // resolves on its own. A real fetch body rejects the read when its
        // request signal aborts, so mirror that here off the composed signal.
        return new Promise<void>((_resolve, reject) => {
          opts.signal?.addEventListener('abort', () =>
            reject(new DOMException('aborted', 'AbortError')),
          );
        });
      }
      controller.close();
    },
  });
  return new Response(body, { status: 200 });
}

const enc = (s: string) => new TextEncoder().encode(s);

describe('streamSSE', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('parses CRLF-framed SSE events and reassembles a partial buffer split across reads', async () => {
    // Event 1 arrives whole; event 2 is split mid-frame across two reads, with
    // the trailing \r\n\r\n delimiter only arriving in the third chunk.
    const chunks = [
      enc('event: node_started\r\ndata: {"node":"a"}\r\n\r\n'),
      enc('event: node_started\r\ndata: {"nod'),
      enc('e":"b"}\r\n\r\n'),
    ];
    const events: SSEEvent[] = [];
    const promise = streamSSE({
      open: () => Promise.resolve(streamResponse(chunks)),
      onEvent: (e) => events.push(e),
    });
    await vi.runAllTimersAsync();
    await promise;

    expect(events).toEqual([
      { event: 'node_started', data: { node: 'a' } },
      { event: 'node_started', data: { node: 'b' } },
    ]);
  });

  it('terminates cleanly when onEvent throws STOP_STREAM (resolves, no throw, later events ignored)', async () => {
    const chunks = [
      enc('event: round_error\r\ndata: {"error":"boom"}\r\n\r\n'),
      enc('event: node_started\r\ndata: {"node":"late"}\r\n\r\n'),
    ];
    const seen: string[] = [];
    const promise = streamSSE({
      open: () => Promise.resolve(streamResponse(chunks)),
      onEvent: (e) => {
        seen.push(e.event);
        if (e.event === 'round_error') throw STOP_STREAM;
      },
    });
    await vi.runAllTimersAsync();
    await expect(promise).resolves.toBeUndefined();
    // Stopped at the first event; the "late" event after STOP is never delivered.
    expect(seen).toEqual(['round_error']);
  });

  it('rejects with SSETimeoutError when the stream hangs past the timeout', async () => {
    const promise = streamSSE({
      open: (signal) => Promise.resolve(streamResponse([], { hang: true, signal })),
      onEvent: () => {},
      timeoutMs: 1000,
    });
    const assertion = expect(promise).rejects.toBeInstanceOf(SSETimeoutError);
    await vi.advanceTimersByTimeAsync(1000);
    await assertion;
  });

  it('clears the timeout timer on success so no late abort fires', async () => {
    const clearSpy = vi.spyOn(globalThis, 'clearTimeout');
    const chunks = [enc('event: node_started\r\ndata: {"node":"a"}\r\n\r\n')];
    const promise = streamSSE({
      open: () => Promise.resolve(streamResponse(chunks)),
      onEvent: () => {},
      timeoutMs: 1000,
    });
    await vi.runAllTimersAsync();
    await promise;

    expect(clearSpy).toHaveBeenCalled();

    // Advancing well past the timeout must not produce any late SSETimeoutError:
    // the timer was cleared, so nothing fires against an already-finished round.
    await vi.advanceTimersByTimeAsync(5000);
    await expect(promise).resolves.toBeUndefined();
    clearSpy.mockRestore();
  });

  it('rejects with the underlying error (not a timeout) when onEvent throws a non-STOP error', async () => {
    const chunks = [enc('event: realization_error\r\ndata: {"error":"nope"}\r\n\r\n')];
    const promise = streamSSE({
      open: () => Promise.resolve(streamResponse(chunks)),
      onEvent: () => {
        throw new Error('nope');
      },
    });
    const assertion = expect(promise).rejects.toThrowError('nope');
    await vi.runAllTimersAsync();
    await assertion;
  });

  it('aborts via an external signal without being mislabeled as a timeout', async () => {
    const controller = new AbortController();
    const promise = streamSSE({
      open: (signal) => {
        // Reject the fetch when the (composed) signal aborts, like a real fetch.
        return new Promise<Response>((_resolve, reject) => {
          signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
        });
      },
      onEvent: () => {},
      signal: controller.signal,
    });
    const assertion = expect(promise).rejects.not.toBeInstanceOf(SSETimeoutError);
    controller.abort();
    await vi.runAllTimersAsync();
    await assertion;
  });
});
