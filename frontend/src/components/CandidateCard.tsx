import type { CandidateSummary } from '../services/api';

interface CandidateCardProps {
  candidate: CandidateSummary;
  index: number;
  onClick?: () => void;
  onRealize?: (candidateId: string) => void;
  onMutate?: (candidateId: string) => void;
}

const LABELS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];

function scoreColor(score: number): string {
  if (score >= 8.0) return 'text-green-400 bg-green-900/30';
  if (score >= 6.0) return 'text-yellow-400 bg-yellow-900/30';
  return 'text-red-400 bg-red-900/30';
}

export default function CandidateCard({ candidate, index, onClick, onRealize, onMutate }: CandidateCardProps) {
  const label = LABELS[index] || `#${index + 1}`;
  const score = candidate.weighted_total;

  return (
    <div
      onClick={onClick}
      className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col gap-3 hover:border-purple-500/50 transition-colors cursor-pointer"
    >
      {/* Header: label + score */}
      <div className="flex items-center justify-between">
        <span className="text-purple-400 font-bold text-sm">
          Candidate {label}
        </span>
        <div className="flex items-center gap-2">
          {candidate.metadata?.mutated_from && (
            <span className="text-xs bg-cyan-900/40 text-cyan-400 px-2 py-0.5 rounded-full">
              ⟳ mutated
            </span>
          )}
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${scoreColor(score)}`}>
            {score.toFixed(1)}
          </span>
        </div>
      </div>

      {/* Chord symbols */}
      <div>
        <p className="font-mono text-sm text-white tracking-wide leading-relaxed">
          {candidate.chord_symbols.join(' → ')}
        </p>
        {candidate.roman_numerals.length > 0 && (
          <p className="font-mono text-xs text-gray-500 mt-1">
            {candidate.roman_numerals.join(' → ')}
          </p>
        )}
      </div>

      {/* Key / mode badge */}
      <div className="flex gap-2">
        <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">
          {candidate.key_center} {candidate.mode}
        </span>
        {candidate.intent_tags.map((tag) => (
          <span key={tag} className="text-xs bg-gray-800 text-gray-500 px-2 py-0.5 rounded">
            {tag}
          </span>
        ))}
      </div>

      {/* Rationale — full text, no truncation */}
      {candidate.rationale && (
        <p className="text-gray-400 text-xs leading-relaxed">{candidate.rationale}</p>
      )}

      {/* Score breakdown */}
      {Object.keys(candidate.scores).length > 0 && (
        <div className="border-t border-gray-800 pt-2 grid grid-cols-2 gap-x-4 gap-y-1">
          {Object.entries(candidate.scores).map(([key, val]) => (
            <div key={key} className="flex justify-between text-xs">
              <span className="text-gray-600 capitalize">{key.replace(/_/g, ' ')}</span>
              <span className="text-gray-400">{val.toFixed(1)}</span>
            </div>
          ))}
        </div>
      )}

      {onRealize && (
        <button
          onClick={(e) => { e.stopPropagation(); onRealize(candidate.candidate_id) }}
          className="mt-3 w-full py-1.5 text-xs font-medium rounded bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors"
        >
          Realize
        </button>
      )}
      {onMutate && (
        <button
          onClick={(e) => { e.stopPropagation(); onMutate(candidate.candidate_id) }}
          className="mt-1 w-full py-1.5 text-xs font-medium rounded bg-cyan-900/50 hover:bg-cyan-800/50 text-cyan-300 transition-colors"
        >
          ⟳ Mutate
        </button>
      )}
    </div>
  );
}
