import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useGenerationFlow } from '../useGenerationFlow';
import { useCandidateStore } from '../../stores/candidateStore';

vi.mock('../../services/api', () => ({
  listCandidates: vi.fn(() => Promise.resolve({ items: [] })),
}));

function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  let i = 0;
  const body = new ReadableStream<Uint8Array>({
    pull(controller) {
      if (i < chunks.length) controller.enqueue(encoder.encode(chunks[i++]));
      else controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
}

describe('useGenerationFlow — failed round still commits spend', () => {
  beforeEach(() => {
    useCandidateStore.getState().reset();
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve(
        sseResponse([
          'event: token_usage\ndata: {"round":1,"total_input":500,"total_output":100,"total_cached":0,"total_tokens":600,"by_model":{"flash":{"input":500,"output":100,"cached":0,"calls":1}},"by_phase":{"generate":{"input":500,"output":100,"calls":1,"model":"flash"}},"estimated_cost_usd":0.001,"is_estimate":true,"is_synthetic":false}\n\n',
          'event: round_error\ndata: {"error":"boom"}\n\n',
        ]),
      ),
    ));
  });
  afterEach(() => vi.unstubAllGlobals());

  it('commits the live usage to history even when the round errors', async () => {
    const { result } = renderHook(() => useGenerationFlow('session-1'));
    await act(async () => {
      await result.current.generate('x');
    });
    expect(result.current.error).toBeTruthy();           // round_error surfaced
    expect(useCandidateStore.getState().usages).toHaveLength(1);  // spend still recorded
    expect(useCandidateStore.getState().usages[0].total_tokens).toBe(600);
  });
});
