import { create } from 'zustand';
import type { CandidateSummary, FinalSelection } from '../services/api';
import type { TokenUsage } from '../services/sse';

interface CandidateState {
  candidates: CandidateSummary[];
  finalSelection: FinalSelection | null;
  loading: boolean;
  progress: string | null;
  error: string | null;
  selectedForComparison: string[];
  usages: TokenUsage[];
  live: TokenUsage | null;
  setLiveUsage: (u: TokenUsage) => void;
  commitLiveUsage: () => void;
  clearUsage: () => void;
  setCandidates: (candidates: CandidateSummary[]) => void;
  setFinalSelection: (fs: FinalSelection | null) => void;
  setLoading: (loading: boolean) => void;
  setProgress: (progress: string | null) => void;
  setError: (error: string | null) => void;
  toggleComparison: (candidateId: string) => void;
  clearComparison: () => void;
  reset: () => void;
}

const MAX_COMPARISON = 3;

export const useCandidateStore = create<CandidateState>((set) => ({
  candidates: [],
  finalSelection: null,
  loading: false,
  progress: null,
  error: null,
  selectedForComparison: [],
  usages: [],
  live: null,
  setLiveUsage: (live) => set({ live }),
  commitLiveUsage: () =>
    set((state) => (state.live ? { usages: [...state.usages, state.live], live: null } : {})),
  clearUsage: () => set({ usages: [], live: null }),
  setCandidates: (candidates) => set({ candidates }),
  setFinalSelection: (finalSelection) => set({ finalSelection }),
  setLoading: (loading) => set({ loading }),
  setProgress: (progress) => set({ progress }),
  setError: (error) => set({ error }),
  toggleComparison: (candidateId) =>
    set((state) => {
      const current = state.selectedForComparison;
      if (current.includes(candidateId)) {
        return { selectedForComparison: current.filter((id) => id !== candidateId) };
      }
      const next = current.length >= MAX_COMPARISON ? current.slice(1) : current;
      return { selectedForComparison: [...next, candidateId] };
    }),
  clearComparison: () => set({ selectedForComparison: [] }),
  reset: () =>
    set({
      candidates: [],
      finalSelection: null,
      loading: false,
      progress: null,
      error: null,
      selectedForComparison: [],
      usages: [],
      live: null,
    }),
}));

export function sessionTokenTotals(state: CandidateState): { tokens: number; cost: number } {
  const committed = state.usages;
  const all = state.live ? [...committed, state.live] : committed;
  return {
    tokens: all.reduce((sum, u) => sum + u.total_tokens, 0),
    cost: all.reduce((sum, u) => sum + u.estimated_cost_usd, 0),
  };
}
