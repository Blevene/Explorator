import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { usePatternLibraryStore } from '../patternLibraryStore';
import * as api from '../../api/patterns';
import type { PatternItem, PatternListResponse } from '../../api/types';

const makeItem = (id: string, score: number): PatternItem => ({
  id, pattern_type: 'progression', genre: 'dream_pop', tags: [],
  source_candidate_id: `cand_${id}`, abstracted_pattern: {},
  success_metrics: { weighted_total: score }, notes: '',
  created_at: '2026-04-19T00:00:00Z',
});

describe('patternLibraryStore', () => {
  beforeEach(() => {
    usePatternLibraryStore.getState().reset();
    vi.restoreAllMocks();
  });

  afterEach(() => vi.restoreAllMocks());

  it('loadMore appends items and updates cursor', async () => {
    const response: PatternListResponse = {
      items: [makeItem('p1', 0.8), makeItem('p2', 0.7)],
      next_cursor: { after_score: 0.7, after_id: 'p2' },
    };
    vi.spyOn(api, 'listPatterns').mockResolvedValue(response);

    await usePatternLibraryStore.getState().loadMore({});

    const state = usePatternLibraryStore.getState();
    expect(state.items.map((i) => i.id)).toEqual(['p1', 'p2']);
    expect(state.cursor).toEqual({ after_score: 0.7, after_id: 'p2' });
    expect(state.hasMore).toBe(true);
  });

  it('loadMore no-ops when hasMore is false', async () => {
    usePatternLibraryStore.setState({ hasMore: false });
    const spy = vi.spyOn(api, 'listPatterns');

    await usePatternLibraryStore.getState().loadMore({});

    expect(spy).not.toHaveBeenCalled();
  });

  it('loadMore second call terminates when next_cursor is null', async () => {
    vi.spyOn(api, 'listPatterns').mockResolvedValue({
      items: [makeItem('p1', 0.8)],
      next_cursor: null,
    });

    await usePatternLibraryStore.getState().loadMore({});

    expect(usePatternLibraryStore.getState().hasMore).toBe(false);
    expect(usePatternLibraryStore.getState().cursor).toBeNull();
  });

  it('removePattern optimistically splices and rolls back on error', async () => {
    usePatternLibraryStore.setState({
      items: [makeItem('p1', 0.8), makeItem('p2', 0.7)],
      hasMore: true,
    });
    vi.spyOn(api, 'deletePattern').mockRejectedValue(new Error('boom'));

    await expect(
      usePatternLibraryStore.getState().removePattern('p1'),
    ).rejects.toThrow();

    expect(
      usePatternLibraryStore.getState().items.map((i) => i.id),
    ).toEqual(['p1', 'p2']);
  });

  it('removePattern commits on success', async () => {
    usePatternLibraryStore.setState({
      items: [makeItem('p1', 0.8), makeItem('p2', 0.7)],
      hasMore: true,
    });
    vi.spyOn(api, 'deletePattern').mockResolvedValue(undefined);

    await usePatternLibraryStore.getState().removePattern('p1');

    expect(
      usePatternLibraryStore.getState().items.map((i) => i.id),
    ).toEqual(['p2']);
  });

  it('reset clears all state', () => {
    usePatternLibraryStore.setState({
      items: [makeItem('p1', 0.8)],
      cursor: { after_score: 0.5, after_id: 'x' },
      hasMore: false,
      loading: true,
      error: 'err',
    });

    usePatternLibraryStore.getState().reset();

    const state = usePatternLibraryStore.getState();
    expect(state.items).toEqual([]);
    expect(state.cursor).toBeNull();
    expect(state.hasMore).toBe(true);
    expect(state.loading).toBe(false);
    expect(state.error).toBeNull();
  });
});
