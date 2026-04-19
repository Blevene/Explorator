import { create } from 'zustand';
import { listPatterns, deletePattern } from '../api/patterns';
import type { PatternCursor, PatternFilters, PatternItem } from '../api/types';

interface PatternLibraryState {
  items: PatternItem[];
  cursor: PatternCursor | null;
  hasMore: boolean;
  loading: boolean;
  error: string | null;

  loadMore: (filters: PatternFilters) => Promise<void>;
  removePattern: (id: string) => Promise<void>;
  reset: () => void;
}

const INITIAL: Omit<PatternLibraryState, 'loadMore' | 'removePattern' | 'reset'> = {
  items: [],
  cursor: null,
  hasMore: true,
  loading: false,
  error: null,
};

export const usePatternLibraryStore = create<PatternLibraryState>((set, get) => ({
  ...INITIAL,

  loadMore: async (filters) => {
    if (!get().hasMore || get().loading) return;
    set({ loading: true, error: null });
    try {
      const response = await listPatterns(filters, get().cursor ?? undefined);
      set((state) => ({
        items: [...state.items, ...response.items],
        cursor: response.next_cursor,
        hasMore: response.next_cursor !== null,
        loading: false,
      }));
    } catch (err) {
      set({ loading: false, error: err instanceof Error ? err.message : String(err) });
    }
  },

  removePattern: async (id) => {
    const prevItems = get().items;
    set({ items: prevItems.filter((p) => p.id !== id) });
    try {
      await deletePattern(id);
    } catch (err) {
      set({ items: prevItems, error: err instanceof Error ? err.message : String(err) });
      throw err;
    }
  },

  reset: () => set({ ...INITIAL }),
}));
