import { create } from 'zustand';
import { listPatterns, deletePattern, toggleCuration as apiToggleCuration } from '../api/patterns';
import type { PatternCursor, PatternFilters, PatternItem } from '../api/types';
import { toast } from '../lib/toast';

interface PatternLibraryState {
  items: PatternItem[];
  cursor: PatternCursor | null;
  hasMore: boolean;
  loading: boolean;
  error: string | null;

  loadMore: (filters: PatternFilters) => Promise<void>;
  removePattern: (id: string) => Promise<void>;
  toggleCuration: (arrangementId: string, nextState: boolean) => Promise<void>;
  reset: () => void;
}

const INITIAL: Omit<PatternLibraryState, 'loadMore' | 'removePattern' | 'toggleCuration' | 'reset'> = {
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

  toggleCuration: async (arrangementId, nextState) => {
    const prevItems = get().items;
    // Optimistic fan-out: flip every item with matching source_candidate_id.
    set({
      items: prevItems.map((p) =>
        p.source_candidate_id === arrangementId
          ? { ...p, is_curated: nextState, curated_at: nextState ? new Date().toISOString() : null }
          : p,
      ),
    });
    try {
      const resp = await apiToggleCuration(arrangementId, nextState);
      // Reconcile timestamps from the server.
      set((state) => ({
        items: state.items.map((p) =>
          resp.affected_pattern_ids.includes(p.id)
            ? { ...p, is_curated: resp.is_curated, curated_at: resp.curated_at }
            : p,
        ),
      }));
      toast.success(nextState ? 'Curated' : 'Removed from curated');
    } catch (err) {
      set({ items: prevItems });
      toast.error('Failed to update curation');
      throw err;
    }
  },

  reset: () => set({ ...INITIAL }),
}));
