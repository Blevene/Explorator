import { create } from 'zustand';
import type { CandidateSummary, FinalSelection } from '../services/api';

interface CandidateState {
  candidates: CandidateSummary[];
  finalSelection: FinalSelection | null;
  loading: boolean;
  progress: string | null;
  error: string | null;
  setCandidates: (candidates: CandidateSummary[]) => void;
  setFinalSelection: (fs: FinalSelection | null) => void;
  setLoading: (loading: boolean) => void;
  setProgress: (progress: string | null) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useCandidateStore = create<CandidateState>((set) => ({
  candidates: [],
  finalSelection: null,
  loading: false,
  progress: null,
  error: null,
  setCandidates: (candidates) => set({ candidates }),
  setFinalSelection: (finalSelection) => set({ finalSelection }),
  setLoading: (loading) => set({ loading }),
  setProgress: (progress) => set({ progress }),
  setError: (error) => set({ error }),
  reset: () => set({ candidates: [], finalSelection: null, loading: false, progress: null, error: null }),
}));
