import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useGenreDetailDrawer } from '../useGenreDetailDrawer';

// Mock getGenreDetail; each test installs its own resolver/rejection.
vi.mock('../../services/api', () => ({
  getGenreDetail: vi.fn(),
}));

import { getGenreDetail } from '../../services/api';
const mockGetGenreDetail = getGenreDetail as unknown as ReturnType<typeof vi.fn>;

function wrapper({ initialEntries }: { initialEntries: string[] }) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route path="/genres" element={<>{children}</>} />
        </Routes>
      </MemoryRouter>
    );
  };
}

beforeEach(() => {
  mockGetGenreDetail.mockReset();
});

describe('useGenreDetailDrawer', () => {
  it('starts closed when no ?detail param is present', () => {
    const { result } = renderHook(() => useGenreDetailDrawer(), {
      wrapper: wrapper({ initialEntries: ['/genres'] }),
    });
    expect(result.current.genre).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(mockGetGenreDetail).not.toHaveBeenCalled();
  });

  it('hydrates when ?detail is present on mount', async () => {
    mockGetGenreDetail.mockResolvedValueOnce({ genre: 'ambient', display_name: 'Ambient' });
    const { result } = renderHook(() => useGenreDetailDrawer(), {
      wrapper: wrapper({ initialEntries: ['/genres?detail=ambient'] }),
    });
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(mockGetGenreDetail).toHaveBeenCalledWith('ambient');
    expect(result.current.genre).toEqual({ genre: 'ambient', display_name: 'Ambient' });
  });

  it('open() writes ?detail to the URL and triggers hydration', async () => {
    mockGetGenreDetail.mockResolvedValueOnce({ genre: 'shoegaze' });
    const { result } = renderHook(() => useGenreDetailDrawer(), {
      wrapper: wrapper({ initialEntries: ['/genres'] }),
    });
    act(() => result.current.open('shoegaze'));
    await waitFor(() => expect(result.current.genre).toEqual({ genre: 'shoegaze' }));
    expect(mockGetGenreDetail).toHaveBeenCalledWith('shoegaze');
  });

  it('close() clears the drawer and removes ?detail from the URL', async () => {
    mockGetGenreDetail.mockResolvedValueOnce({ genre: 'jazz' });
    const { result } = renderHook(() => useGenreDetailDrawer(), {
      wrapper: wrapper({ initialEntries: ['/genres?detail=jazz'] }),
    });
    await waitFor(() => expect(result.current.genre).not.toBeNull());
    act(() => result.current.close());
    await waitFor(() => expect(result.current.genre).toBeNull());
  });

  it('strips ?detail from the URL when getGenreDetail rejects (404)', async () => {
    mockGetGenreDetail.mockRejectedValueOnce(new Error('404'));
    const { result } = renderHook(() => useGenreDetailDrawer(), {
      wrapper: wrapper({ initialEntries: ['/genres?detail=nonexistent'] }),
    });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.genre).toBeNull();
    // Subsequent re-fetch attempts shouldn't fire — the URL was cleared.
    expect(mockGetGenreDetail).toHaveBeenCalledTimes(1);
  });

  it('cancels an in-flight fetch when the slug changes mid-flight', async () => {
    // First request: never resolve until we explicitly let it finish.
    let resolveFirst: (v: any) => void = () => {};
    const firstPromise = new Promise((res) => { resolveFirst = res; });
    mockGetGenreDetail.mockReturnValueOnce(firstPromise);
    // Second request: resolves quickly.
    mockGetGenreDetail.mockResolvedValueOnce({ genre: 'shoegaze' });

    const { result } = renderHook(() => useGenreDetailDrawer(), {
      wrapper: wrapper({ initialEntries: ['/genres?detail=ambient'] }),
    });
    expect(result.current.loading).toBe(true);

    // Switch to a different slug while the first request is still pending.
    act(() => result.current.open('shoegaze'));
    await waitFor(() => expect(result.current.genre).toEqual({ genre: 'shoegaze' }));

    // Now resolve the FIRST (cancelled) request — should not overwrite state.
    act(() => resolveFirst({ genre: 'ambient' }));
    // Give microtasks a chance to flush; state must remain shoegaze.
    await new Promise((r) => setTimeout(r, 20));
    expect(result.current.genre).toEqual({ genre: 'shoegaze' });
  });
});
