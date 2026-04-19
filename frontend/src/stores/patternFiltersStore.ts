import { create } from 'zustand';
import type { PatternFilters } from '../api/types';

interface PatternFiltersState {
  filters: PatternFilters;
  setFilter: (patch: PatternFilters) => void;
}

export const usePatternFiltersStore = create<PatternFiltersState>((set) => ({
  filters: {},
  setFilter: (patch) => set((state) => ({ filters: { ...state.filters, ...patch } })),
}));
