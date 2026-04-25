import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { PatternFilters } from '../components/patterns/PatternFilters';
import { PatternList } from '../components/patterns/PatternList';
import { LoadMoreButton } from '../components/patterns/LoadMoreButton';
import { EmptyState } from '../components/patterns/EmptyState';
import { usePatternFiltersStore } from '../stores/patternFiltersStore';
import { usePatternLibraryStore } from '../stores/patternLibraryStore';

export default function PatternLibraryBrowser() {
  const filters = usePatternFiltersStore((s) => s.filters);
  const items = usePatternLibraryStore((s) => s.items);
  const loading = usePatternLibraryStore((s) => s.loading);
  const reset = usePatternLibraryStore((s) => s.reset);
  const loadMore = usePatternLibraryStore((s) => s.loadMore);

  useEffect(() => {
    reset();
    void loadMore(filters);
  }, [filters.genre, filters.pattern_type, filters.curated_only, reset, loadMore]);

  const showEmpty = !loading && items.length === 0;

  return (
    <div className="min-h-dvh px-8 py-12">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-light" style={{ color: 'var(--text-primary)' }}>
            Pattern Library
          </h1>
          <Link
            to="/"
            className="text-xs tracking-wider uppercase"
            style={{ color: 'var(--text-muted)' }}
          >
            &larr; Dashboard
          </Link>
        </div>
        <PatternFilters />
        {showEmpty ? <EmptyState /> : <PatternList />}
        <LoadMoreButton />
      </div>
    </div>
  );
}
