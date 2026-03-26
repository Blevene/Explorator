import type { CandidateSummary } from '../services/api';

interface CandidateCardProps {
  candidate: CandidateSummary;
}

export default function CandidateCard({ candidate }: CandidateCardProps) {
  const shortId = candidate.candidate_id.slice(0, 8);
  const score = candidate.weighted_total;
  const scoreColor =
    score >= 0.75 ? 'text-green-400' : score >= 0.5 ? 'text-yellow-400' : 'text-red-400';

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col gap-3 hover:border-gray-700 transition-colors">
      {/* Header: ID + score */}
      <div className="flex items-center justify-between gap-2">
        <span className="text-purple-400 font-mono text-xs truncate" title={candidate.candidate_id}>
          #{shortId}
        </span>
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full bg-gray-800 ${scoreColor}`}>
          {(score * 100).toFixed(0)}%
        </span>
      </div>

      {/* Chord symbols */}
      <div>
        <p className="font-mono text-sm text-white tracking-wide">
          {candidate.chord_symbols.join(' → ')}
        </p>
        {candidate.roman_numerals.length > 0 && (
          <p className="font-mono text-xs text-gray-500 mt-1">
            {candidate.roman_numerals.join(' → ')}
          </p>
        )}
      </div>

      {/* Key / mode badge */}
      <div>
        <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">
          {candidate.key_center} {candidate.mode}
        </span>
      </div>

      {/* Rationale */}
      {candidate.rationale && (
        <p className="text-gray-400 text-xs leading-relaxed line-clamp-2">{candidate.rationale}</p>
      )}

      {/* Tags */}
      {candidate.intent_tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {candidate.intent_tags.map((tag) => (
            <span key={tag} className="text-xs bg-gray-800 text-gray-500 px-2 py-0.5 rounded">
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Score breakdown */}
      {Object.keys(candidate.scores).length > 0 && (
        <div className="border-t border-gray-800 pt-2 grid grid-cols-2 gap-x-4 gap-y-1">
          {Object.entries(candidate.scores).map(([key, val]) => (
            <div key={key} className="flex justify-between text-xs">
              <span className="text-gray-600 capitalize">{key.replace(/_/g, ' ')}</span>
              <span className="text-gray-400">{(val * 100).toFixed(0)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
