import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PatternLibraryBrowser from '../PatternLibraryBrowser';
import * as api from '../../api/patterns';
import { usePatternLibraryStore } from '../../stores/patternLibraryStore';
import { usePatternFiltersStore } from '../../stores/patternFiltersStore';

beforeEach(() => {
  usePatternLibraryStore.getState().reset();
  usePatternFiltersStore.setState({ filters: {} });
  vi.restoreAllMocks();
});

describe('PatternLibraryBrowser', () => {
  it('shows empty state when no items', async () => {
    vi.spyOn(api, 'listPatterns').mockResolvedValue({ items: [], next_cursor: null });

    render(<MemoryRouter><PatternLibraryBrowser /></MemoryRouter>);

    await waitFor(() => expect(screen.getByTestId('empty-state')).toBeInTheDocument());
  });

  it('renders pattern list when items exist', async () => {
    vi.spyOn(api, 'listPatterns').mockResolvedValue({
      items: [{
        id: 'pat_0001', pattern_type: 'progression', genre: 'jazz',
        tags: [], source_candidate_id: 'c', abstracted_pattern: {},
        success_metrics: { weighted_total: 0.8 }, notes: '',
        created_at: '2026-04-19T00:00:00Z',
        is_curated: false, curated_at: null,
      }],
      next_cursor: null,
    });

    render(<MemoryRouter><PatternLibraryBrowser /></MemoryRouter>);

    await waitFor(() => expect(screen.getByTestId('pattern-card-pat_0001')).toBeInTheDocument());
    expect(screen.queryByTestId('empty-state')).not.toBeInTheDocument();
  });
});
