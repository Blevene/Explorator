import { describe, it, expect, beforeEach } from 'vitest';
import { usePatternFiltersStore } from '../patternFiltersStore';

describe('patternFiltersStore', () => {
  beforeEach(() => {
    usePatternFiltersStore.setState({ filters: {} });
  });

  it('setFilter merges a patch into filters', () => {
    usePatternFiltersStore.getState().setFilter({ genre: 'jazz' });
    expect(usePatternFiltersStore.getState().filters).toEqual({ genre: 'jazz' });

    usePatternFiltersStore.getState().setFilter({ pattern_type: 'voicing' });
    expect(usePatternFiltersStore.getState().filters).toEqual({
      genre: 'jazz',
      pattern_type: 'voicing',
    });
  });

  it('setFilter with undefined clears a key', () => {
    usePatternFiltersStore.setState({ filters: { genre: 'jazz' } });
    usePatternFiltersStore.getState().setFilter({ genre: undefined });
    expect(usePatternFiltersStore.getState().filters).toEqual({ genre: undefined });
  });
});
