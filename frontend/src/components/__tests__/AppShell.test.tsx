import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import AppShell from '../AppShell';
import { useCapabilitiesStore } from '../../stores/capabilitiesStore';
import type { Capabilities } from '../../services/api';

const NEO4J: Capabilities = {
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

function renderShell() {
  return render(
    <MemoryRouter initialEntries={['/genres']}>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/genres" element={<div>genres view</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe('AppShell limited mode', () => {
  beforeEach(() => {
    useCapabilitiesStore.setState({ capabilities: null, loading: false, error: null });
  });
  afterEach(() => {
    useCapabilitiesStore.setState({ capabilities: null, loading: false, error: null });
  });

  it('hides gated nav (Patterns) and shows no banner before capabilities load (fail closed)', () => {
    renderShell();
    expect(screen.queryByTestId('limited-mode-banner')).toBeNull();
    // Gated nav stays hidden until capabilities confirm the feature is on.
    expect(screen.queryByRole('link', { name: 'Patterns' })).toBeNull();
    // Ungated nav is always visible.
    expect(screen.getByRole('link', { name: 'Genres' })).toBeInTheDocument();
  });

  it('shows no banner and Patterns nav in neo4j mode', () => {
    useCapabilitiesStore.setState({ capabilities: NEO4J });
    renderShell();
    expect(screen.queryByTestId('limited-mode-banner')).toBeNull();
    expect(screen.getByRole('link', { name: 'Patterns' })).toBeInTheDocument();
  });

  it('shows the banner and hides Patterns nav in memory mode', () => {
    useCapabilitiesStore.setState({ capabilities: MEMORY });
    renderShell();
    expect(screen.getByTestId('limited-mode-banner')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Patterns' })).toBeNull();
    // Genres nav (no feature gate) stays visible.
    expect(screen.getByRole('link', { name: 'Genres' })).toBeInTheDocument();
  });
});
