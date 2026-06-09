/**
 * Shared SSE streaming helper for the generation / realization / mutation flows.
 *
 * All three flows open an SSE POST stream and drain it with `reader.read()`.
 * A stream that opens then hangs with zero bytes would block that loop forever,
 * leaving the calling flow stuck in its in-flight state (the `finally` that
 * resets `loading`/`inFlight` never runs). To bound that, every stream is wrapped
 * in an AbortController with a hard timeout: `reader.read()` rejects on abort, so
 * a true hang can't block forever and server-side work is cancelled.
 *
 * The timer is cleared on ALL exit paths (success, parse handler throw, error,
 * abort) so it can never fire late against an unrelated round.
 */

/** Hard cap on a single SSE round, including a stream that hangs with no bytes. */
export const SSE_TIMEOUT_MS = 600_000;

export class SSETimeoutError extends Error {
  constructor(message = `Stream timed out after ${SSE_TIMEOUT_MS / 60_000} minutes.`) {
    super(message);
    this.name = 'SSETimeoutError';
  }
}

export interface SSEEvent {
  event: string;
  data: Record<string, unknown>;
}

export interface StreamSSEOptions {
  /** Opens the SSE response. Must forward `signal` to its `fetch` so abort works. */
  open: (signal: AbortSignal) => Promise<Response>;
  /** Called once per parsed SSE event. Throw `STOP_STREAM` to end early. */
  onEvent: (e: SSEEvent) => void;
  /** Thrown when the response is not ok / has no body. Defaults to a generic message. */
  notOkMessage?: (status: number) => string;
  /** Timeout override (ms). Defaults to {@link SSE_TIMEOUT_MS}. */
  timeoutMs?: number;
}

/** Sentinel an `onEvent` handler can throw to stop draining the stream cleanly. */
export const STOP_STREAM = Symbol('STOP_STREAM');

/**
 * Drives an SSE stream to completion (or early stop / timeout / error).
 *
 * Resolves normally once the stream ends or `onEvent` throws `STOP_STREAM`.
 * Rejects with {@link SSETimeoutError} on the timeout, or with the underlying
 * error otherwise. The abort timer is always cleared before returning.
 */
export async function streamSSE(options: StreamSSEOptions): Promise<void> {
  const { open, onEvent, notOkMessage, timeoutMs = SSE_TIMEOUT_MS } = options;

  const controller = new AbortController();
  let timedOut = false;
  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  try {
    const response = await open(controller.signal);
    if (!response.ok || !response.body) {
      throw new Error(
        notOkMessage ? notOkMessage(response.status) : `Stream failed: ${response.status}`,
      );
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split(/\r?\n\r?\n/);
        buffer = parts.pop() ?? '';

        for (const part of parts) {
          if (!part.trim()) continue;
          let eventType = '';
          let dataStr = '';
          for (const line of part.split(/\r?\n/)) {
            if (line.startsWith('event: ')) eventType = line.slice(7).trim();
            else if (line.startsWith('data: ')) dataStr = line.slice(6).trim();
          }
          if (!eventType || !dataStr) continue;

          let data: Record<string, unknown>;
          try {
            data = JSON.parse(dataStr);
          } catch {
            continue;
          }

          try {
            onEvent({ event: eventType, data });
          } catch (stop) {
            if (stop === STOP_STREAM) return;
            throw stop;
          }
        }

        await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
      }
    } finally {
      reader.releaseLock();
    }
  } catch (err) {
    if (timedOut) throw new SSETimeoutError();
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}
