import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useCapabilitiesStore } from '../capabilitiesStore';
import * as api from '../../services/api';

const NEO4J_CAPS: api.Capabilities = {
  persistence_mode: 'neo4j',
  features: {
    durable_persistence: true,
    pattern_library: true,
    feedback_learning: true,
    session_history: true,
    lineage: true,
    genre_research: true,
    curation: true,
  },
};

const MEMORY_CAPS: api.Capabilities = {
  persistence_mode: 'memory',
  features: {
    durable_persistence: false,
    pattern_library: false,
    feedback_learning: false,
    session_history: false,
    lineage: false,
    genre_research: false,
    curation: false,
  },
};

describe('capabilitiesStore', () => {
  beforeEach(() => {
    useCapabilitiesStore.setState({ capabilities: null, loading: false, error: null });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('defaults: not memory mode and can() optimistic-true before load', () => {
    const s = useCapabilitiesStore.getState();
    expect(s.isMemoryMode()).toBe(false);
    expect(s.can('pattern_library')).toBe(true);
    expect(s.can('curation')).toBe(true);
  });

  it('populates capabilities on fetch (neo4j mode)', async () => {
    vi.spyOn(api, 'getCapabilities').mockResolvedValue(NEO4J_CAPS);
    await useCapabilitiesStore.getState().fetch();
    const s = useCapabilitiesStore.getState();
    expect(s.capabilities).toEqual(NEO4J_CAPS);
    expect(s.isMemoryMode()).toBe(false);
    expect(s.can('pattern_library')).toBe(true);
  });

  it('reflects memory mode and disables features after fetch', async () => {
    vi.spyOn(api, 'getCapabilities').mockResolvedValue(MEMORY_CAPS);
    await useCapabilitiesStore.getState().fetch();
    const s = useCapabilitiesStore.getState();
    expect(s.isMemoryMode()).toBe(true);
    expect(s.can('pattern_library')).toBe(false);
    expect(s.can('session_history')).toBe(false);
    expect(s.can('lineage')).toBe(false);
    expect(s.can('curation')).toBe(false);
    expect(s.can('genre_research')).toBe(false);
  });

  it('can() returns false for unknown features once loaded', async () => {
    vi.spyOn(api, 'getCapabilities').mockResolvedValue(MEMORY_CAPS);
    await useCapabilitiesStore.getState().fetch();
    expect(useCapabilitiesStore.getState().can('nonexistent_feature')).toBe(false);
  });

  it('records error on fetch failure', async () => {
    vi.spyOn(api, 'getCapabilities').mockRejectedValue(new Error('boom'));
    await useCapabilitiesStore.getState().fetch();
    const s = useCapabilitiesStore.getState();
    expect(s.error).toBe('boom');
    expect(s.loading).toBe(false);
    expect(s.capabilities).toBeNull();
  });
});
