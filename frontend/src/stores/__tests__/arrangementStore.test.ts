import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useArrangementStore } from '../arrangementStore';
import * as api from '../../api/patterns';
import { toast } from '../../lib/toast';

vi.mock('../../lib/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

describe('arrangementStore.toggleCuration', () => {
  beforeEach(() => {
    useArrangementStore.getState().reset();
    (toast.success as any).mockClear();
    (toast.error as any).mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('optimistically flips is_curated on the matching arrangement', async () => {
    useArrangementStore.setState({
      arrangements: [
        { id: 'arr_x', is_curated: false, curated_at: null } as any,
        { id: 'arr_y', is_curated: false, curated_at: null } as any,
      ],
    });
    vi.spyOn(api, 'toggleCuration').mockResolvedValue({
      arrangement_id: 'arr_x', is_curated: true,
      curated_at: '2026-04-24T12:00:00Z',
      affected_pattern_ids: ['p1'],
    });

    await useArrangementStore.getState().toggleCuration('arr_x', true);

    const { arrangements } = useArrangementStore.getState();
    expect(arrangements.find((a) => a.id === 'arr_x')!.is_curated).toBe(true);
    expect(arrangements.find((a) => a.id === 'arr_y')!.is_curated).toBe(false);
  });

  it('reverts + error-toasts on API failure', async () => {
    useArrangementStore.setState({
      arrangements: [{ id: 'arr_x', is_curated: false, curated_at: null } as any],
    });
    vi.spyOn(api, 'toggleCuration').mockRejectedValue(new Error('bad'));

    await expect(
      useArrangementStore.getState().toggleCuration('arr_x', true),
    ).rejects.toThrow();

    expect(useArrangementStore.getState().arrangements[0].is_curated).toBe(false);
    expect(toast.error).toHaveBeenCalledWith('Failed to update curation');
  });

  it('mirrors optimistic flip onto selectedDetail when it matches', async () => {
    useArrangementStore.setState({
      arrangements: [{ id: 'arr_x', is_curated: false, curated_at: null } as any],
      selectedDetail: { id: 'arr_x', is_curated: false, curated_at: null } as any,
    });
    vi.spyOn(api, 'toggleCuration').mockResolvedValue({
      arrangement_id: 'arr_x', is_curated: true,
      curated_at: '2026-04-24T12:00:00Z',
      affected_pattern_ids: ['p1'],
    });

    await useArrangementStore.getState().toggleCuration('arr_x', true);

    const detail = useArrangementStore.getState().selectedDetail;
    expect(detail!.is_curated).toBe(true);
    expect(detail!.curated_at).toBe('2026-04-24T12:00:00Z');
  });

  it('reverts selectedDetail on API failure', async () => {
    useArrangementStore.setState({
      arrangements: [{ id: 'arr_x', is_curated: false, curated_at: null } as any],
      selectedDetail: { id: 'arr_x', is_curated: false, curated_at: null } as any,
    });
    vi.spyOn(api, 'toggleCuration').mockRejectedValue(new Error('bad'));

    await expect(
      useArrangementStore.getState().toggleCuration('arr_x', true),
    ).rejects.toThrow();

    expect(useArrangementStore.getState().selectedDetail!.is_curated).toBe(false);
  });

  it('leaves selectedDetail untouched when it points at a different arrangement', async () => {
    useArrangementStore.setState({
      arrangements: [{ id: 'arr_x', is_curated: false, curated_at: null } as any],
      selectedDetail: { id: 'arr_other', is_curated: false, curated_at: null } as any,
    });
    vi.spyOn(api, 'toggleCuration').mockResolvedValue({
      arrangement_id: 'arr_x', is_curated: true,
      curated_at: '2026-04-24T12:00:00Z',
      affected_pattern_ids: ['p1'],
    });

    await useArrangementStore.getState().toggleCuration('arr_x', true);

    expect(useArrangementStore.getState().selectedDetail!.id).toBe('arr_other');
    expect(useArrangementStore.getState().selectedDetail!.is_curated).toBe(false);
  });
});
