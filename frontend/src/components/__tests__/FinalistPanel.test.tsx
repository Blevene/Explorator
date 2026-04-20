import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import FinalistPanel from '../FinalistPanel';
import * as patternsApi from '../../api/patterns';
import type { ArrangementSummary, FinalSelection } from '../../services/api';

const finalSelection: FinalSelection = {
  selected_candidate_ids: ['arr_01'],
  selection_roles: { arr_01: 'safest' },
  selection_notes: [],
};

const arrangements: ArrangementSummary[] = [{
  id: 'arr_01', weighted_total: 0.8, rationale: 'test',
} as ArrangementSummary];

beforeEach(() => vi.restoreAllMocks());

describe('FinalistPanel Save to library button', () => {
  it('fires harvestSessionFinalists and shows success toast', async () => {
    const spy = vi.spyOn(patternsApi, 'harvestSessionFinalists').mockResolvedValue({
      session_id: 'sess_01',
      upserted_count: 5,
      skipped_count: 0,
      skipped_reasons: [],
      upserted_pattern_ids: [],
    });

    render(
      <FinalistPanel
        finalSelection={finalSelection}
        arrangements={arrangements}
        selectedId={null}
        onSelect={vi.fn()}
        sessionId="sess_01"
      />,
    );

    fireEvent.click(screen.getByTestId('save-finalists-to-library'));

    await waitFor(() => expect(spy).toHaveBeenCalledWith('sess_01'));
  });

  it('disables button while saving', async () => {
    vi.spyOn(patternsApi, 'harvestSessionFinalists').mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve({
        session_id: 'sess_01', upserted_count: 0, skipped_count: 0,
        skipped_reasons: [], upserted_pattern_ids: [],
      }), 100)),
    );

    render(
      <FinalistPanel
        finalSelection={finalSelection}
        arrangements={arrangements}
        selectedId={null}
        onSelect={vi.fn()}
        sessionId="sess_01"
      />,
    );

    const button = screen.getByTestId('save-finalists-to-library') as HTMLButtonElement;
    fireEvent.click(button);

    expect(button.disabled).toBe(true);
  });
});
