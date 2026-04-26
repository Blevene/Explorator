import { useEffect } from 'react';
import { PatternFilters } from '../components/patterns/PatternFilters';
import { PatternList } from '../components/patterns/PatternList';
import { LoadMoreButton } from '../components/patterns/LoadMoreButton';
import { EmptyState } from '../components/patterns/EmptyState';
import { usePatternFiltersStore } from '../stores/patternFiltersStore';
import { usePatternLibraryStore } from '../stores/patternLibraryStore';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export default function PatternLibraryBrowser() {
  useDocumentTitle('Pattern Library');
  const filters = usePatternFiltersStore((s) => s.filters);
  const items = usePatternLibraryStore((s) => s.items);
  const loading = usePatternLibraryStore((s) => s.loading);
  const reset = usePatternLibraryStore((s) => s.reset);
  const loadMore = usePatternLibraryStore((s) => s.loadMore);

  useEffect(() => {
    reset();
    void loadMore(filters);
    // Intentionally depend on the individual filter fields rather than
    // `filters` itself — the store reference can change identity on
    // unrelated updates and would re-fire the load every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.genre, filters.pattern_type, filters.curated_only, reset, loadMore]);

  const showEmpty = !loading && items.length === 0;

  return (
    <div className="px-8 py-12">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-2xl font-light mb-8" style={{ color: 'var(--text-primary)' }}>
          Pattern Library
        </h1>
        <PatternFilters />
        {showEmpty ? <EmptyState /> : <PatternList />}
        <LoadMoreButton />
      </div>
    </div>
  );
}
