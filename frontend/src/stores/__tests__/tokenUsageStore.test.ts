import { describe, it, expect, beforeEach } from 'vitest';
import { useCandidateStore, sessionTokenTotals } from '../candidateStore';
import type { TokenUsage } from '../../services/sse';

function usage(round: number, total: number): TokenUsage {
  return {
    round,
    total_input: total,
    total_output: 0,
    total_cached: 0,
    total_tokens: total,
    by_model: { pro: { input: total, output: 0, cached: 0, calls: 1 } },
    by_phase: { generate: { input: total, output: 0, calls: 1, model: 'pro' } },
    estimated_cost_usd: total / 1000,
    is_estimate: true,
  };
}

describe('candidateStore token usage', () => {
  beforeEach(() => useCandidateStore.getState().reset());

  it('setLiveUsage exposes the in-flight running total', () => {
    useCandidateStore.getState().setLiveUsage(usage(1, 500));
    expect(useCandidateStore.getState().live?.total_tokens).toBe(500);
  });

  it('commitLiveUsage moves live into history and clears live', () => {
    const s = useCandidateStore.getState();
    s.setLiveUsage(usage(1, 500));
    s.commitLiveUsage();
    expect(useCandidateStore.getState().live).toBeNull();
    expect(useCandidateStore.getState().usages).toHaveLength(1);
  });

  it('sessionTokenTotals sums history plus any in-flight live (no double count)', () => {
    const s = useCandidateStore.getState();
    s.setLiveUsage(usage(1, 500));
    s.commitLiveUsage();                       // history: [500]
    s.setLiveUsage(usage(1, 300));             // live: 300, not yet committed
    const totals = sessionTokenTotals(useCandidateStore.getState());
    expect(totals.tokens).toBe(800);
    expect(totals.cost).toBeCloseTo(0.8, 5);
  });

  it('reset clears usage state', () => {
    const s = useCandidateStore.getState();
    s.setLiveUsage(usage(1, 500));
    s.commitLiveUsage();
    s.reset();
    expect(useCandidateStore.getState().usages).toHaveLength(0);
    expect(useCandidateStore.getState().live).toBeNull();
  });
});
