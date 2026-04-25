import type { PatternItem } from '../../api/types';
import { usePatternLibraryStore } from '../../stores/patternLibraryStore';
import { StarButton } from '../StarButton';

interface Props {
  pattern: PatternItem;
  onDelete: (id: string) => void;
}

function shortHash(id: string): string {
  return id.length > 8 ? id.slice(-8) : id;
}

export function PatternCard({ pattern, onDelete }: Props) {
  const score = pattern.success_metrics.weighted_total ?? 0;
  const toggleCuration = usePatternLibraryStore((s) => s.toggleCuration);
  const handleDelete = () => {
    if (confirm('Delete this pattern? This cannot be undone.')) {
      onDelete(pattern.id);
    }
  };

  return (
    <div
      data-testid={`pattern-card-${pattern.id}`}
      className="rounded-md p-3 border"
      style={{
        background: 'var(--surface-2)',
        borderColor: 'var(--border-subtle)',
      }}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span
            className="text-xs font-semibold px-2 py-0.5 rounded-full"
            style={{ background: 'var(--surface-3)', color: 'var(--text-primary)' }}
          >
            {pattern.pattern_type}
          </span>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {pattern.genre}
          </span>
          <span className="text-sm font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
            {score.toFixed(2)}
          </span>
          <span
            className="text-xs font-mono"
            style={{ color: 'var(--text-muted)' }}
            title={pattern.source_candidate_id}
          >
            src: {shortHash(pattern.source_candidate_id)}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <StarButton
            isCurated={pattern.is_curated}
            onToggle={(next) => {
              void toggleCuration(pattern.source_candidate_id, next).catch(() => {
                // Store already toasts on failure; swallow.
              });
            }}
          />
          <button
            onClick={handleDelete}
            aria-label={`Delete ${pattern.id}`}
            className="text-xs px-2 py-1 rounded transition-colors bg-transparent text-[var(--text-muted)] hover:text-[var(--score-low)] focus-visible:text-[var(--score-low)]"
          >
            Delete
          </button>
        </div>
      </div>
      {pattern.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {pattern.tags.map((t) => (
            <span
              key={t}
              className="text-xs px-1.5 py-0.5 rounded"
              style={{ background: 'var(--surface-1)', color: 'var(--text-muted)' }}
            >
              {t}
            </span>
          ))}
        </div>
      )}
      <details>
        <summary className="text-xs cursor-pointer" style={{ color: 'var(--text-muted)' }}>
          abstracted_pattern
        </summary>
        <pre
          className="text-xs mt-1 p-2 rounded overflow-x-auto"
          style={{ background: 'var(--surface-1)', color: 'var(--text-muted)' }}
        >
          {JSON.stringify(pattern.abstracted_pattern, null, 2)}
        </pre>
      </details>
      {pattern.notes && (
        <p className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
          {pattern.notes}
        </p>
      )}
    </div>
  );
}
