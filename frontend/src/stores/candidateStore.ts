import { create } from 'zustand';
import type { CandidateSummary } from '../services/api';

interface CandidateState {
  candidates: CandidateSummary[];
  loading: boolean;
  progress: string | null;
  error: string | null;
  setCandidates: (candidates: CandidateSummary[]) => void;
  setLoading: (loading: boolean) => void;
  setProgress: (progress: string | null) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useCandidateStore = create<CandidateState>((set) => ({
  candidates: [],
  loading: false,
  progress: null,
  error: null,
  setCandidates: (candidates) => set({ candidates }),
  setLoading: (loading) => set({ loading }),
  setProgress: (progress) => set({ progress }),
  setError: (error) => set({ error }),
  reset: () => set({ candidates: [], loading: false, progress: null, error: null }),
}));
