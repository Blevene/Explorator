import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { listPatterns, toggleCuration } from '../patterns';

const origFetch = global.fetch;

beforeEach(() => {
  global.fetch = vi.fn();
});

afterEach(() => {
  global.fetch = origFetch;
});

describe('patterns API', () => {
  it('listPatterns threads curated_only into querystring', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [], next_cursor: null }),
    });
    await listPatterns({ curated_only: true });
    const url = (global.fetch as any).mock.calls[0][0];
    expect(url).toMatch(/curated_only=true/);
  });

  it('listPatterns omits curated_only when false/undefined', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [], next_cursor: null }),
    });
    await listPatterns({});
    const url = (global.fetch as any).mock.calls[0][0];
    expect(url).not.toMatch(/curated_only/);
  });

  it('toggleCuration POSTs to the right URL with curated boolean', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        arrangement_id: 'arr_x',
        is_curated: true,
        curated_at: '2026-04-24T12:00:00Z',
        affected_pattern_ids: ['pat_1', 'pat_2'],
      }),
    });
    const result = await toggleCuration('arr_x', true);
    const [url, init] = (global.fetch as any).mock.calls[0];
    expect(url).toMatch(/\/v1\/arrangements\/arr_x\/curation$/);
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ curated: true });
    expect(result.is_curated).toBe(true);
    expect(result.affected_pattern_ids).toEqual(['pat_1', 'pat_2']);
  });
});
