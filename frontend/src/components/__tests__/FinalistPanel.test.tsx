import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import FinalistPanel from '../FinalistPanel';
import { useArrangementStore } from '../../stores/arrangementStore';

const finalSelection = {
  selected_candidate_ids: ['arr_1', 'arr_2'],
  selection_roles: { arr_1: 'safest', arr_2: 'best_loop' },
} as any;

const arrangements = [
  { id: 'arr_1', weighted_total: 8.5, rationale: 'Safe', is_curated: false, curated_at: null } as any,
  { id: 'arr_2', weighted_total: 7.2, rationale: 'Loopy', is_curated: true, curated_at: '2026-04-24T12:00:00Z' } as any,
];

describe('FinalistPanel curation', () => {
  beforeEach(() => {
    useArrangementStore.getState().reset();
  });

  it('no longer renders the "Save to library" button', () => {
    render(
      <FinalistPanel
        finalSelection={finalSelection}
        arrangements={arrangements}
        selectedId={null}
        onSelect={vi.fn()}
        sessionId="sess_1"
      />,
    );
    expect(screen.queryByTestId('save-finalists-to-library')).toBeNull();
  });

  it('renders stars per finalist matching their is_curated state', () => {
    render(
      <FinalistPanel
        finalSelection={finalSelection}
        arrangements={arrangements}
        selectedId={null}
        onSelect={vi.fn()}
        sessionId="sess_1"
      />,
    );
    expect(screen.getByLabelText('Mark as curated')).toBeInTheDocument();
    expect(screen.getByLabelText('Remove from curated')).toBeInTheDocument();
  });

  it('renders disabled star when arrangement.is_curated is null (not yet harvested)', () => {
    render(
      <FinalistPanel
        finalSelection={finalSelection}
        arrangements={[
          { id: 'arr_1', weighted_total: 8.5, rationale: 'x', is_curated: null, curated_at: null } as any,
          { id: 'arr_2', weighted_total: 7.2, rationale: 'y', is_curated: null, curated_at: null } as any,
        ]}
        selectedId={null}
        onSelect={vi.fn()}
        sessionId="sess_1"
      />,
    );
    const stars = screen.getAllByRole('button', { name: 'Mark as curated' });
    stars.forEach((s) => expect(s).toHaveAttribute('aria-disabled', 'true'));
  });

  it('clicking star calls arrangementStore.toggleCuration and does not select the card', () => {
    const spy = vi.spyOn(useArrangementStore.getState(), 'toggleCuration').mockResolvedValue();
    const onSelect = vi.fn();
    render(
      <FinalistPanel
        finalSelection={finalSelection}
        arrangements={arrangements}
        selectedId={null}
        onSelect={onSelect}
        sessionId="sess_1"
      />,
    );
    fireEvent.click(screen.getByLabelText('Mark as curated'));
    expect(spy).toHaveBeenCalledWith('arr_1', true);
    expect(onSelect).not.toHaveBeenCalled();
  });
});
