import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import TokenUsagePanel from '../TokenUsagePanel';
import { useCandidateStore } from '../../stores/candidateStore';
import type { TokenUsage } from '../../services/sse';

const sample: TokenUsage = {
  round: 1,
  total_input: 1000,
  total_output: 400,
  total_cached: 0,
  total_tokens: 1400,
  by_model: { pro: { input: 1000, output: 400, cached: 0, calls: 1 } },
  by_phase: { generate: { input: 1000, output: 400, calls: 1, model: 'pro' } },
  estimated_cost_usd: 0.005,
  is_estimate: true,
  is_synthetic: false,
};

describe('TokenUsagePanel', () => {
  beforeEach(() => useCandidateStore.getState().reset());

  it('renders nothing when there is no usage', () => {
    const { container } = render(<TokenUsagePanel />);
    expect(container.firstChild).toBeNull();
  });

  it('shows the round total tokens and an estimated cost', () => {
    useCandidateStore.getState().setLiveUsage(sample);
    render(<TokenUsagePanel />);
    expect(screen.getByTestId('token-usage-panel')).toBeInTheDocument();
    // Round headline and session footer both show 1,400 when there is a single round.
    expect(screen.getAllByText(/1,400/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/est\./).length).toBeGreaterThan(0);
  });

  it('lists the per-phase breakdown', () => {
    useCandidateStore.getState().setLiveUsage(sample);
    render(<TokenUsagePanel />);
    expect(screen.getByText(/generate/)).toBeInTheDocument();
  });
});
