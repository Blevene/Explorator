import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import GenreManagement from '../GenreManagement';
import { useCapabilitiesStore } from '../../stores/capabilitiesStore';
import type { Capabilities } from '../../services/api';

// Stub the genre-research store: GenreManagement calls fetchGenres/fetchDrafts on
// mount and reads `genres` / `pendingDrafts`. We only need the library view to render.
const storeState = {
  genres: [{ genre: 'dream_pop', display_name: 'Dream Pop' }],
  pendingDrafts: [{ job_id: 'j1', genre_name: 'Shoegaze', created_at: '2026-06-06T00:00:00Z' }],
  activeJobId: null,
  activeJobStatus: null,
  progressDetail: null,
  errorMessage: null,
  reviewDraft: null,
  fetchGenres: vi.fn().mockResolvedValue(undefined),
  fetchDrafts: vi.fn().mockResolvedValue(undefined),
  startResearch: vi.fn(),
  fetchDraftDetail: vi.fn(),
  doApproveDraft: vi.fn(),
  doRejectDraft: vi.fn(),
  reset: vi.fn(),
};

vi.mock('../../stores/genreResearchStore', () => ({
  useGenreResearchStore: () => storeState,
}));

vi.mock('../../hooks/useGenreDetailDrawer', () => ({
  useGenreDetailDrawer: () => ({ genre: null, loading: false, open: vi.fn(), close: vi.fn() }),
}));

const MEMORY: Capabilities = {
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

const NEO4J: Capabilities = {
  persistence_mode: 'neo4j',
  features: { ...MEMORY.features, genre_research: true, durable_persistence: true },
};

function renderGenres() {
  return render(
    <MemoryRouter initialEntries={['/genres']}>
      <GenreManagement />
    </MemoryRouter>,
  );
}

describe('GenreManagement research gating', () => {
  beforeEach(() => {
    useCapabilitiesStore.setState({ capabilities: null, loading: false, error: null });
  });
  afterEach(() => {
    useCapabilitiesStore.setState({ capabilities: null, loading: false, error: null });
  });

  it('shows research affordances + library when genre_research is available', () => {
    useCapabilitiesStore.setState({ capabilities: NEO4J });
    renderGenres();
    expect(screen.getByRole('button', { name: 'Research New Genre' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Pending Review' })).toBeInTheDocument();
    // Genre library still visible.
    expect(screen.getByText('Dream Pop')).toBeInTheDocument();
  });

  it('hides research affordances but keeps the genre library in memory mode', () => {
    useCapabilitiesStore.setState({ capabilities: MEMORY });
    renderGenres();
    expect(screen.queryByRole('button', { name: 'Research New Genre' })).toBeNull();
    expect(screen.queryByRole('heading', { name: 'Pending Review' })).toBeNull();
    // Library (served from YAML) remains.
    expect(screen.getByText('Dream Pop')).toBeInTheDocument();
    expect(screen.getByText('Installed Genres')).toBeInTheDocument();
  });
});
