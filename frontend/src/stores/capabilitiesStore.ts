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
  // Whether a given feature is available. Defaults to `true` until
  // capabilities load, so feature surfaces don't flicker-hidden on first
  // paint; once loaded, returns the backend's reported flag.
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

  can: (feature) => {
    const caps = get().capabilities;
    if (caps === null) return true; // optimistic until loaded
    return caps.features[feature] ?? false;
  },
}));
