import type { ArrangementSummary, FinalSelection } from '../services/api';
import { useArrangementStore } from '../stores/arrangementStore';
import { StarButton } from './StarButton';

interface FinalistPanelProps {
  finalSelection: FinalSelection;
  arrangements: ArrangementSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  sessionId: string;
}

const ROLE_CONFIG: Record<string, { label: string; accent: string }> = {
  safest: { label: 'Safest', accent: 'var(--role-safest)' },
  best_loop: { label: 'Best Loop', accent: 'var(--role-loop)' },
  most_experimental: { label: 'Most Experimental', accent: 'var(--role-experimental)' },
};

function scoreColor(score: number): string {
  if (score >= 8) return 'var(--score-high)';
  if (score >= 6) return 'var(--score-mid)';
  return 'var(--score-low)';
}

export default function FinalistPanel({
  finalSelection,
  arrangements,
  selectedId,
  onSelect,
}: FinalistPanelProps) {
  const { selection_roles, selected_candidate_ids } = finalSelection;
  const toggleCuration = useArrangementStore((s) => s.toggleCuration);
  if (selected_candidate_ids.length === 0) return null;

  const arrLookup = new Map(arrangements.map((a) => [a.id, a]));

  return (
    <div style={{ borderBottom: '1px solid var(--border-default)', background: 'var(--surface-1)' }}>
      <div className="px-3 py-2" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
        <div className="flex items-center gap-2">
          <div
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: 'var(--accent-primary)' }}
          />
          <h3
            className="text-xs font-semibold uppercase tracking-widest"
            style={{ color: 'var(--accent-primary)' }}
          >
            Finalists
          </h3>
        </div>
      </div>
      <div className="flex flex-col gap-1 p-2">
        {selected_candidate_ids.map((id) => {
          const arr = arrLookup.get(id);
          if (!arr) return null;
          const role = selection_roles[id];
          const config = ROLE_CONFIG[role] || { label: role, accent: 'var(--text-muted)' };
          const isSelected = selectedId === id;
          const isCurated = arr.is_curated ?? null;

          return (
            <div
              key={id}
              onClick={() => onSelect(id)}
              className="rounded-md p-3 cursor-pointer transition-all"
              style={{
                background: isSelected ? 'var(--surface-3)' : 'var(--surface-2)',
                borderLeft: isSelected ? `3px solid ${config.accent}` : '3px solid transparent',
                border: isSelected ? undefined : '1px solid var(--border-subtle)',
              }}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span
                  className="text-xs font-semibold px-2 py-0.5 rounded-full"
                  style={{ background: `${config.accent}20`, color: config.accent, border: `1px solid ${config.accent}40` }}
                >
                  {config.label}
                </span>
                <div
                  className="flex items-center gap-1"
                  onClick={(e) => e.stopPropagation()}
                >
                  <span
                    className="text-sm font-bold font-mono"
                    style={{ color: scoreColor(arr.weighted_total) }}
                  >
                    {(arr.weighted_total ?? 0).toFixed(2)}
                  </span>
                  <StarButton
                    isCurated={isCurated}
                    onToggle={(next) => {
                      void toggleCuration(id, next).catch(() => {
                        // Store already toasts on failure; swallow.
                      });
                    }}
                  />
                </div>
              </div>
              <p className="text-xs truncate" style={{ color: 'var(--text-muted)' }}>{arr.rationale}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
