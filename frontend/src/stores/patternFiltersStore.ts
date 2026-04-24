import { create } from 'zustand';
import type { PatternFilters } from '../api/types';

interface PatternFiltersState {
  filters: PatternFilters;
  setFilter: (patch: PatternFilters) => void;
  setCuratedOnly: (value: boolean) => void;
}

export const usePatternFiltersStore = create<PatternFiltersState>((set) => ({
  filters: {},
  setFilter: (patch) => set((state) => ({ filters: { ...state.filters, ...patch } })),
  setCuratedOnly: (value) =>
    set((state) => {
      const next = { ...state.filters };
      if (value) {
        next.curated_only = true;
      } else {
        delete next.curated_only;
      }
      return { filters: next };
    }),
}));
