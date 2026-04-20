import { usePatternFiltersStore } from '../../stores/patternFiltersStore';

const PATTERN_TYPES = ['progression', 'voicing', 'bass', 'groove', 'melody'] as const;

export function PatternFilters() {
  const filters = usePatternFiltersStore((s) => s.filters);
  const setFilter = usePatternFiltersStore((s) => s.setFilter);

  return (
    <div className="flex gap-3 mb-4" data-testid="pattern-filters">
      <label className="flex items-center gap-2 text-sm" style={{ color: 'var(--text-muted)' }}>
        Genre:
        <input
          type="text"
          value={filters.genre ?? ''}
          onChange={(e) => setFilter({ genre: e.target.value || undefined })}
          placeholder="all"
          className="px-2 py-1 rounded"
          style={{ background: 'var(--surface-2)', color: 'var(--text-primary)' }}
        />
      </label>
      <label className="flex items-center gap-2 text-sm" style={{ color: 'var(--text-muted)' }}>
        Type:
        <select
          value={filters.pattern_type ?? ''}
          onChange={(e) => setFilter({ pattern_type: e.target.value || undefined })}
          className="px-2 py-1 rounded"
          style={{ background: 'var(--surface-2)', color: 'var(--text-primary)' }}
        >
          <option value="">all</option>
          {PATTERN_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </label>
    </div>
  );
}
