import { usePatternLibraryStore } from '../../stores/patternLibraryStore';
import { usePatternFiltersStore } from '../../stores/patternFiltersStore';

export function LoadMoreButton() {
  const hasMore = usePatternLibraryStore((s) => s.hasMore);
  const loading = usePatternLibraryStore((s) => s.loading);
  const loadMore = usePatternLibraryStore((s) => s.loadMore);
  const filters = usePatternFiltersStore((s) => s.filters);

  if (!hasMore) return null;

  return (
    <button
      onClick={() => loadMore(filters)}
      disabled={loading}
      data-testid="load-more-button"
      className="mt-4 px-4 py-2 rounded disabled:opacity-30"
      style={{ background: 'var(--surface-2)', color: 'var(--text-primary)' }}
    >
      {loading ? 'Loading...' : 'Load more'}
    </button>
  );
}
