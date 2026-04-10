import type { ArrangementSummary, FinalSelection } from '../services/api';

interface FinalistPanelProps {
  finalSelection: FinalSelection;
  arrangements: ArrangementSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

const ROLE_CONFIG: Record<string, { label: string; color: string }> = {
  safest: { label: 'Safest', color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50' },
  best_loop: { label: 'Best Loop', color: 'bg-amber-500/20 text-amber-400 border-amber-500/50' },
  most_experimental: { label: 'Most Experimental', color: 'bg-violet-500/20 text-violet-400 border-violet-500/50' },
};

function scoreColor(score: number): string {
  if (score >= 8) return 'text-emerald-400';
  if (score >= 6) return 'text-amber-400';
  return 'text-rose-400';
}

export default function FinalistPanel({
  finalSelection,
  arrangements,
  selectedId,
  onSelect,
}: FinalistPanelProps) {
  const { selection_roles, selected_candidate_ids } = finalSelection;
  if (selected_candidate_ids.length === 0) return null;

  const arrLookup = new Map(arrangements.map((a) => [a.id, a]));

  return (
    <div className="border-b border-slate-700 bg-slate-900/50">
      <div className="px-3 py-2 border-b border-slate-800">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          Finalists
        </h3>
      </div>
      <div className="flex flex-col gap-1 p-2">
        {selected_candidate_ids.map((id) => {
          const arr = arrLookup.get(id);
          if (!arr) return null;
          const role = selection_roles[id];
          const config = ROLE_CONFIG[role] || { label: role, color: 'bg-slate-700 text-slate-300' };

          return (
            <div
              key={id}
              onClick={() => onSelect(id)}
              className={[
                'border rounded-md p-3 cursor-pointer transition-all',
                selectedId === id
                  ? 'border-l-4 border-purple-500 bg-slate-800'
                  : 'border-slate-700 bg-slate-900 hover:bg-slate-800',
              ].join(' ')}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className={`text-xs px-2 py-0.5 rounded-full border ${config.color}`}>
                  {config.label}
                </span>
                <span className={`text-sm font-bold font-mono ${scoreColor(arr.weighted_total)}`}>
                  {(arr.weighted_total ?? 0).toFixed(2)}
                </span>
              </div>
              <p className="text-slate-500 text-xs truncate">{arr.rationale}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
