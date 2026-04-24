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

  it('setCuratedOnly(true) sets curated_only filter', () => {
    usePatternFiltersStore.getState().setCuratedOnly(true);
    expect(usePatternFiltersStore.getState().filters.curated_only).toBe(true);
  });

  it('setCuratedOnly(false) clears curated_only from filters', () => {
    usePatternFiltersStore.setState({ filters: { curated_only: true } });
    usePatternFiltersStore.getState().setCuratedOnly(false);
    expect(usePatternFiltersStore.getState().filters.curated_only).toBeUndefined();
  });

  it('setCuratedOnly does not disturb other filters', () => {
    usePatternFiltersStore.setState({ filters: { genre: 'jazz', pattern_type: 'progression' } });
    usePatternFiltersStore.getState().setCuratedOnly(true);
    const { filters } = usePatternFiltersStore.getState();
    expect(filters.genre).toBe('jazz');
    expect(filters.pattern_type).toBe('progression');
    expect(filters.curated_only).toBe(true);
  });
});
