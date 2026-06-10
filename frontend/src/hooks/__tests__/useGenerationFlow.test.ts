import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useGenerationFlow } from '../useGenerationFlow';

// Wrap React.useState so the test can observe every state-setter the hook owns
// and detect any dispatch that fires after the component unmounts. This is the
// precise regression #1 fixes: the flow's `finally` (setLoading/setCurrentNode)
// must be gated behind a mountedRef so it never runs on an unmounted (dead)
// fiber. ESM namespaces can't be spied in place, so re-export through a mock.
const setterCallsAfterUnmount: unknown[][] = [];
const unmountFlag = { value: false };
vi.mock('react', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useState: (initial: unknown) => {
      const [value, setter] = actual.useState(initial as never);
      const tracked = (...args: unknown[]) => {
        if (unmountFlag.value) setterCallsAfterUnmount.push(args);
        return (setter as (...a: unknown[]) => void)(...args);
      };
      return [value, tracked as typeof setter];
    },
  };
});

/**
 * Build a Response whose body hangs forever: the pending read() never resolves
 * on its own, but a real fetch body rejects the read when its request signal
 * aborts, so mirror that off `signal` here. This lets us start a stream that
 * stays in-flight until the hook's unmount cleanup aborts it — the exact
 * condition that runs the flow's `finally` against an unmounted fiber.
 */
function hangingResponse(signal?: AbortSignal): Response {
  const body = new ReadableStream<Uint8Array>({
    pull() {
      return new Promise<void>((_resolve, reject) => {
        signal?.addEventListener('abort', () =>
          reject(new DOMException('aborted', 'AbortError')),
        );
      });
    },
  });
  return new Response(body, { status: 200 });
}

describe('useGenerationFlow — no state update after unmount', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    setterCallsAfterUnmount.length = 0;
    unmountFlag.value = false;
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('does NOT invoke any setState in finally after unmount mid-stream', async () => {
    // fetch returns a hanging stream that only rejects once its request signal
    // aborts (i.e. on unmount). streamSSE forwards the composed signal here.
    const fetchMock = vi.fn((_url: string, init?: RequestInit) =>
      Promise.resolve(hangingResponse(init?.signal ?? undefined)),
    );
    vi.stubGlobal('fetch', fetchMock);

    const { result, unmount } = renderHook(() => useGenerationFlow('session-1'));

    // Kick off a round (don't await: it hangs until unmount).
    let generatePromise!: Promise<void>;
    act(() => {
      generatePromise = result.current.generate('a dreamy pad progression');
    });

    // Let the fetch resolve and the reader start draining (the hang begins).
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(result.current.loading).toBe(true);
    expect(fetchMock).toHaveBeenCalled();

    // Unmount mid-stream. The cleanup aborts the controller, which rejects the
    // hanging read → the hook's catch early-returns (caller abort) and `finally`
    // runs. With the mountedRef gate, `finally` must NOT call any setState.
    unmountFlag.value = true;
    unmount();

    await act(async () => {
      await vi.runAllTimersAsync();
      // Drain the aborted generate() promise so its finally fully executes.
      await generatePromise.catch(() => {});
    });

    // The gated `finally` performed ZERO state updates on the unmounted fiber.
    expect(setterCallsAfterUnmount).toEqual([]);
  });
});
