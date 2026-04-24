import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PatternCard } from '../PatternCard';
import type { PatternItem } from '../../../api/types';
import { usePatternLibraryStore } from '../../../stores/patternLibraryStore';

const item: PatternItem = {
  id: 'pat_0001',
  pattern_type: 'progression',
  genre: 'jazz',
  tags: ['role:safest', 'cadence:authentic'],
  source_candidate_id: 'cand_0001_xyz',
  abstracted_pattern: { foo: 'bar' },
  success_metrics: { weighted_total: 0.87 },
  notes: 'ii-V-I with tritone sub',
  created_at: '2026-04-19T00:00:00Z',
  is_curated: false,
  curated_at: null,
};

describe('PatternCard', () => {
  it('renders type, genre, score, short-hash source, tags, notes', () => {
    render(<PatternCard pattern={item} onDelete={vi.fn()} />);
    expect(screen.getByText('progression')).toBeInTheDocument();
    expect(screen.getByText('jazz')).toBeInTheDocument();
    expect(screen.getByText('0.87')).toBeInTheDocument();
    expect(screen.getByText(/0001_xyz/)).toBeInTheDocument();
    expect(screen.getByText('role:safest')).toBeInTheDocument();
    expect(screen.getByText('ii-V-I with tritone sub')).toBeInTheDocument();
  });

  it('calls onDelete when confirmed', () => {
    const onDelete = vi.fn();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<PatternCard pattern={item} onDelete={onDelete} />);
    fireEvent.click(screen.getByLabelText('Delete pat_0001'));
    expect(onDelete).toHaveBeenCalledWith('pat_0001');
  });

  it('does not call onDelete when cancelled', () => {
    const onDelete = vi.fn();
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<PatternCard pattern={item} onDelete={onDelete} />);
    fireEvent.click(screen.getByLabelText('Delete pat_0001'));
    expect(onDelete).not.toHaveBeenCalled();
  });
});

describe('PatternCard curation', () => {
  beforeEach(() => {
    usePatternLibraryStore.getState().reset();
  });

  it('renders filled star when pattern.is_curated is true', () => {
    const curated: PatternItem = { ...item, is_curated: true, curated_at: '2026-04-24T12:00:00Z' };
    render(<PatternCard pattern={curated} onDelete={vi.fn()} />);
    expect(screen.getByLabelText('Remove from curated')).toBeInTheDocument();
  });

  it('renders outlined star when pattern.is_curated is false', () => {
    const uncurated: PatternItem = { ...item, is_curated: false, curated_at: null };
    render(<PatternCard pattern={uncurated} onDelete={vi.fn()} />);
    expect(screen.getByLabelText('Mark as curated')).toBeInTheDocument();
  });

  it('clicking star calls patternLibraryStore.toggleCuration with source_candidate_id', () => {
    const spy = vi.spyOn(usePatternLibraryStore.getState(), 'toggleCuration')
      .mockResolvedValue();
    const p: PatternItem = { ...item, is_curated: false, curated_at: null };
    render(<PatternCard pattern={p} onDelete={vi.fn()} />);
    fireEvent.click(screen.getByLabelText('Mark as curated'));
    expect(spy).toHaveBeenCalledWith(item.source_candidate_id, true);
  });
});
