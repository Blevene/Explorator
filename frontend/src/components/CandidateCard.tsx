import { useState } from 'react';
import type { CandidateSummary } from '../services/api';

interface CandidateCardProps {
  candidate: CandidateSummary;
  index: number;
  onClick?: () => void;
  onRealize?: (candidateId: string) => void;
  onMutate?: (candidateId: string) => void;
  onDismiss?: (candidateId: string) => void;
}

const LABELS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];

function scoreColor(score: number): string {
  if (score >= 8.0) return 'var(--score-high)';
  if (score >= 6.0) return 'var(--score-mid)';
  return 'var(--score-low)';
}

interface MutationOp {
  operation: string;
  original: string;
  new: string;
  description: string;
}

function MutationLog({ parentChords, ops, onDismiss }: { parentChords: string[]; ops: MutationOp[]; onDismiss?: () => void }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="pt-2" style={{ borderTop: '1px solid var(--border-subtle)' }}>
      <button
        onClick={(e) => { e.stopPropagation(); setExpanded(x => !x); }}
        className="flex items-center gap-1.5 text-xs font-medium w-full"
        style={{ color: 'var(--accent-secondary)' }}
      >
        <span>{expanded ? '\u25BE' : '\u25B8'}</span>
        <span>Mutation log ({ops.length} change{ops.length !== 1 ? 's' : ''})</span>
      </button>

      {expanded && (
        <div className="mt-2 space-y-2">
          {/* Parent progression */}
          <div>
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Parent: </span>
            <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
              {parentChords.join(' \u2192 ')}
            </span>
          </div>

          {/* Changes */}
          {ops.map((op, i) => (
            <div key={i} className="text-xs flex flex-col gap-0.5">
              <div className="flex items-center gap-1.5">
                <span className="font-mono px-1.5 py-0.5 rounded" style={{ background: 'var(--surface-3)', color: 'var(--accent-secondary)' }}>
                  {op.operation.replace(/_/g, ' ')}
                </span>
                {op.original && op.new && (
                  <span className="font-mono">
                    <span style={{ color: 'var(--score-low)' }}>{op.original}</span>
                    {' \u2192 '}
                    <span style={{ color: 'var(--score-high)' }}>{op.new}</span>
                  </span>
                )}
              </div>
              {op.description && (
                <span style={{ color: 'var(--text-muted)' }}>{op.description}</span>
              )}
            </div>
          ))}

          {/* Dismiss mutation */}
          {onDismiss && (
            <button
              onClick={(e) => { e.stopPropagation(); onDismiss(); }}
              className="text-xs font-medium mt-1 transition-colors"
              style={{ color: 'var(--score-low)' }}
            >
              Dismiss this mutation
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function CandidateCard({ candidate, index, onClick, onRealize, onMutate, onDismiss }: CandidateCardProps) {
  const label = LABELS[index] || `#${index + 1}`;
  const score = candidate.weighted_total;
  const parentChords = candidate.metadata?.parent_chord_symbols as string[] | undefined;
  const mutationOps = candidate.metadata?.mutation_ops as MutationOp[] | undefined;

  return (
    <div
      onClick={onClick}
      className="rounded-lg p-4 flex flex-col gap-3 transition-all cursor-pointer card-interactive"
      style={{
        background: 'var(--surface-2)',
        border: '1px solid var(--border-subtle)',
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold" style={{ color: 'var(--accent-primary)' }}>
          {label}
        </span>
        <div className="flex items-center gap-2">
          {!!candidate.metadata?.mutated_from && (
            <span
              className="text-xs px-2 py-0.5 rounded-full font-mono"
              style={{ background: 'var(--accent-secondary-dim)', color: 'var(--accent-secondary)' }}
            >
              mutated
            </span>
          )}
          <span
            className="text-xs font-bold font-mono px-2 py-0.5 rounded-full"
            style={{ color: scoreColor(score), background: `${scoreColor(score)}15` }}
          >
            {score.toFixed(1)}
          </span>
        </div>
      </div>

      {/* Chords */}
      <div>
        <p className="font-mono text-sm tracking-wide leading-relaxed" style={{ color: 'var(--text-primary)' }}>
          {candidate.chord_symbols.join(' \u2192 ')}
        </p>
        {candidate.roman_numerals.length > 0 && (
          <p className="font-mono text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
            {candidate.roman_numerals.join(' \u2192 ')}
          </p>
        )}
      </div>

      {/* Badges */}
      <div className="flex gap-2 flex-wrap">
        <span className="text-xs px-2 py-0.5 rounded" style={{ background: 'var(--surface-3)', color: 'var(--text-secondary)' }}>
          {candidate.key_center} {candidate.mode}
        </span>
        {candidate.intent_tags.map((tag) => (
          <span key={tag} className="text-xs px-2 py-0.5 rounded" style={{ background: 'var(--surface-3)', color: 'var(--text-muted)' }}>
            {tag}
          </span>
        ))}
      </div>

      {/* Rationale */}
      {candidate.rationale && (
        <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{candidate.rationale}</p>
      )}

      {/* Mutation log — shows parent progression and what changed */}
      {parentChords && mutationOps && mutationOps.length > 0 && (
        <MutationLog
          parentChords={parentChords}
          ops={mutationOps}
          onDismiss={onDismiss ? () => onDismiss(candidate.candidate_id) : undefined}
        />
      )}

      {/* Score breakdown */}
      {Object.keys(candidate.scores).length > 0 && (
        <div className="pt-2 grid grid-cols-2 gap-x-4 gap-y-1" style={{ borderTop: '1px solid var(--border-subtle)' }}>
          {Object.entries(candidate.scores).map(([key, val]) => (
            <div key={key} className="flex justify-between text-xs">
              <span className="capitalize" style={{ color: 'var(--text-muted)' }}>{key.replace(/_/g, ' ')}</span>
              <span className="font-mono" style={{ color: 'var(--text-secondary)' }}>{val.toFixed(1)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Actions */}
      {onRealize && (
        <button
          onClick={(e) => { e.stopPropagation(); onRealize(candidate.candidate_id) }}
          className="mt-1 w-full py-1.5 text-xs font-medium rounded-md transition-colors"
          style={{ background: 'var(--accent-primary-dim)', color: 'var(--accent-primary)' }}
        >
          View Arrangements
        </button>
      )}
      {onMutate && (
        <button
          onClick={(e) => { e.stopPropagation(); onMutate(candidate.candidate_id) }}
          className="w-full py-1.5 text-xs font-medium rounded-md transition-colors"
          style={{ background: 'var(--accent-secondary-dim)', color: 'var(--accent-secondary)' }}
        >
          Mutate
        </button>
      )}
    </div>
  );
}
