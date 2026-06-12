import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useGenerationFlow } from '../useGenerationFlow';
import { useCandidateStore } from '../../stores/candidateStore';

// Hoisted: stub the post-stream candidate reload so it doesn't hit the network.
vi.mock('../../services/api', () => ({
  listCandidates: vi.fn(() => Promise.resolve({ items: [] })),
}));

// A real fetch-style Response whose body streams one SSE token_usage event,
// then a round_completed, then closes.
function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  let i = 0;
  const body = new ReadableStream<Uint8Array>({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(encoder.encode(chunks[i++]));
      } else {
        controller.close();
      }
    },
  });
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
}

describe('useGenerationFlow — token_usage', () => {
  beforeEach(() => {
    useCandidateStore.getState().reset();
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve(
        sseResponse([
          'event: token_usage\ndata: {"round":1,"total_input":1000,"total_output":400,"total_cached":0,"total_tokens":1400,"by_model":{"pro":{"input":1000,"output":400,"cached":0,"calls":1}},"by_phase":{"generate":{"input":1000,"output":400,"calls":1,"model":"pro"}},"estimated_cost_usd":0.005,"is_estimate":true}\n\n',
          'event: round_completed\ndata: {"round":1}\n\n',
        ]),
      ),
    ));
  });
  afterEach(() => vi.unstubAllGlobals());

  it('stores live usage from a token_usage event and commits on completion', async () => {
    const { result } = renderHook(() => useGenerationFlow('session-1'));
    await act(async () => {
      await result.current.generate('a dreamy progression');
    });
    // After a successful round, the live snapshot is committed into history.
    expect(useCandidateStore.getState().usages).toHaveLength(1);
    expect(useCandidateStore.getState().usages[0].total_tokens).toBe(1400);
  });
});
