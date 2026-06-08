import { create } from 'zustand';
import { getCapabilities, type Capabilities } from '../services/api';

interface CapabilitiesState {
  capabilities: Capabilities | null;
  loading: boolean;
  error: string | null;

  fetch: () => Promise<void>;
  // Whether the backend is running without a durable graph backend.
  // Returns false until capabilities load, so the limited-mode banner
  // never flickers in before we actually know the mode.
  isMemoryMode: () => boolean;
  // Whether a given feature is available. FAILS CLOSED: returns `false`
  // while capabilities are pending OR if the fetch failed, so DB-only
  // surfaces are never shown/enabled without confirmation from the backend.
  // Once loaded, returns the backend's reported flag.
  can: (feature: string) => boolean;
}

export const useCapabilitiesStore = create<CapabilitiesState>((set, get) => ({
  capabilities: null,
  loading: false,
  error: null,

  fetch: async () => {
    if (get().loading) return;
    set({ loading: true, error: null });
    try {
      const capabilities = await getCapabilities();
      set({ capabilities, loading: false });
    } catch (err) {
      set({ loading: false, error: err instanceof Error ? err.message : String(err) });
    }
  },

  isMemoryMode: () => get().capabilities?.persistence_mode === 'memory',

  // Fail closed: false while pending or on fetch error.
  can: (feature) => get().capabilities?.features[feature] ?? false,
}));

// Reactive selector hooks for React components. These subscribe to the
// `capabilities` VALUE (not the stable `can`/`isMemoryMode` function refs),
// so consumers re-render when capabilities load. Same fail-closed semantics:
// false while pending / on error, true only once the backend confirms.
//
// Non-hook callers (and tests) should keep using the `can`/`isMemoryMode`
// methods via `useCapabilitiesStore.getState()`.
export const useCan = (feature: string): boolean =>
  useCapabilitiesStore((s) => s.capabilities?.features[feature] ?? false);

export const useIsMemoryMode = (): boolean =>
  useCapabilitiesStore((s) => s.capabilities?.persistence_mode === 'memory');
