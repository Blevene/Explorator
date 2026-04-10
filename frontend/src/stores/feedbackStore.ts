import { create } from 'zustand';

export interface FeedbackEntry {
  id: string;
  content: string;
  interpreted_adjustments: Record<string, unknown>;
  adjusted_weights: Record<string, number>;
  satisfaction: string;
  timestamp: string;
}

interface FeedbackState {
  entries: FeedbackEntry[];
  currentWeights: Record<string, number> | null;
  submitting: boolean;
  error: string | null;
  addEntry: (entry: FeedbackEntry) => void;
  setCurrentWeights: (weights: Record<string, number>) => void;
  setSubmitting: (submitting: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useFeedbackStore = create<FeedbackState>((set) => ({
  entries: [],
  currentWeights: null,
  submitting: false,
  error: null,
  addEntry: (entry) =>
    set((state) => ({
      entries: [...state.entries, entry],
      currentWeights: entry.adjusted_weights,
    })),
  setCurrentWeights: (weights) => set({ currentWeights: weights }),
  setSubmitting: (submitting) => set({ submitting }),
  setError: (error) => set({ error }),
  reset: () => set({ entries: [], currentWeights: null, submitting: false, error: null }),
}));
