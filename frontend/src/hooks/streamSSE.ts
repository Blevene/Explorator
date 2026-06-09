/**
 * Shared SSE streaming helper for the generation / realization / mutation flows.
 *
 * All three flows open an SSE POST stream and drain it with `reader.read()`.
 * A stream that opens then hangs with zero bytes would block that loop forever,
 * leaving the calling flow stuck in its in-flight state (the `finally` that
 * resets `loading`/`inFlight` never runs). To bound that, every stream is wrapped
 * in an AbortController with a hard timeout: `reader.read()` rejects on abort, so
 * a true hang can't block forever. Aborting the fetch only cancels the in-flight
 * request and (best-effort) signals the server to stop the underlying work — it
 * happens on the timeout or when a caller-supplied signal aborts (e.g. unmount),
 * not on a normal stream end.
 *
 * Callers may pass an external `AbortSignal` (composed with the internal timeout
 * controller) so they can abort the request on unmount / when the session changes,
 * instead of leaking the request + server work until the timeout fires.
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

/** Reason passed to `controller.abort()` when a caller aborts via the external signal. */
export const USER_ABORT = Symbol('USER_ABORT');

export interface StreamSSEOptions {
  /** Opens the SSE response. Must forward `signal` to its `fetch` so abort works. */
  open: (signal: AbortSignal) => Promise<Response>;
  /** Called once per parsed SSE event. Throw `STOP_STREAM` to end early. */
  onEvent: (e: SSEEvent) => void;
  /** Thrown when the response is not ok / has no body. Defaults to a generic message. */
  notOkMessage?: (status: number) => string;
  /** Timeout override (ms). Defaults to {@link SSE_TIMEOUT_MS}. */
  timeoutMs?: number;
  /**
   * Optional caller-owned signal, composed with the internal timeout controller.
   * Aborting it (e.g. in a React unmount cleanup) cancels the request without
   * being mislabeled as a timeout.
   */
  signal?: AbortSignal;
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
  const { open, onEvent, notOkMessage, timeoutMs = SSE_TIMEOUT_MS, signal: externalSignal } = options;

  const controller = new AbortController();
  let timedOut = false;
  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  // Compose the caller's signal with our timeout controller. A caller abort
  // forwards to the internal controller WITHOUT setting `timedOut`, so a
  // navigation/unmount abort is never mislabeled as a timeout.
  const onExternalAbort = () => controller.abort(externalSignal?.reason ?? USER_ABORT);
  if (externalSignal) {
    if (externalSignal.aborted) onExternalAbort();
    else externalSignal.addEventListener('abort', onExternalAbort, { once: true });
  }

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

        // Yield to the event loop between reads. Use setTimeout(0) rather than
        // requestAnimationFrame: rAF is throttled/suspended in a backgrounded
        // tab, which would stall a long round running in the background.
        await new Promise<void>((resolve) => setTimeout(resolve, 0));
      }
    } finally {
      reader.releaseLock();
    }
  } catch (err) {
    // Only a real timeout maps to SSETimeoutError. A caller abort sets the
    // signal but not `timedOut`, so it surfaces as the underlying abort error.
    if (timedOut) throw new SSETimeoutError();
    throw err;
  } finally {
    clearTimeout(timeoutId);
    externalSignal?.removeEventListener('abort', onExternalAbort);
  }
}
