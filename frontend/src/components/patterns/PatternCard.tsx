import { useState } from 'react';
import type { PatternItem } from '../../api/types';
import { usePatternLibraryStore } from '../../stores/patternLibraryStore';
import { useCapabilitiesStore } from '../../stores/capabilitiesStore';
import { StarButton } from '../StarButton';
import Dialog from '../Dialog';

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
  const can = useCapabilitiesStore((s) => s.can);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const handleDelete = () => setConfirmOpen(true);
  const confirmDelete = () => {
    setConfirmOpen(false);
    onDelete(pattern.id);
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
            disabled={!can('curation')}
            disabledTitle="Curation requires the database (limited mode)"
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
      {confirmOpen && (
        <Dialog
          onClose={() => setConfirmOpen(false)}
          labelledBy={`confirm-delete-${pattern.id}`}
          panelClassName="rounded-xl p-6 w-full max-w-sm mx-4"
          panelStyle={{ background: 'var(--surface-2)', border: '1px solid var(--border-default)' }}
        >
          <h3
            id={`confirm-delete-${pattern.id}`}
            className="text-sm font-semibold mb-2"
            style={{ color: 'var(--text-primary)' }}
          >
            Delete this pattern?
          </h3>
          <p className="text-xs mb-5" style={{ color: 'var(--text-secondary)' }}>
            <span className="font-mono">{shortHash(pattern.source_candidate_id)}</span> · {pattern.pattern_type} ·{' '}
            {pattern.genre}. This cannot be undone.
          </p>
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => setConfirmOpen(false)}
              className="px-4 py-1.5 text-xs rounded-lg transition-colors"
              style={{ background: 'var(--surface-3)', color: 'var(--text-secondary)' }}
            >
              Cancel
            </button>
            <button
              onClick={confirmDelete}
              className="px-4 py-1.5 text-xs rounded-lg font-medium transition-colors"
              style={{ background: 'var(--score-low)', color: 'var(--surface-0)' }}
            >
              Delete
            </button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
