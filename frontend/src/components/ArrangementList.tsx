import type { ArrangementSummary, CandidateSummary, FinalSelection } from "../services/api"
import ArrangementCard from "./ArrangementCard"
import FinalistPanel from "./FinalistPanel"

interface ArrangementListProps {
  arrangements: ArrangementSummary[]
  candidates: CandidateSummary[]
  selectedId: string | null
  onSelect: (id: string) => void
  genre: string
  finalSelection?: FinalSelection | null
}

export default function ArrangementList({
  arrangements,
  candidates,
  selectedId,
  onSelect,
  genre,
  finalSelection,
}: ArrangementListProps) {
  // Build candidate lookup by id
  const candidateLookup = new Map<string, CandidateSummary>(
    candidates.map((c) => [c.candidate_id, c])
  )

  // Group arrangements by progression_candidate_id
  const grouped = new Map<string, ArrangementSummary[]>()
  for (const arr of arrangements) {
    const group = grouped.get(arr.progression_candidate_id) ?? []
    group.push(arr)
    grouped.set(arr.progression_candidate_id, group)
  }

  // Sort each group by rank_within_round
  for (const [key, group] of grouped) {
    grouped.set(key, [...group].sort((a, b) => a.rank_within_round - b.rank_within_round))
  }

  if (grouped.size === 0) {
    return (
      <div className="w-72 shrink-0 bg-slate-950 border-r border-slate-700 flex items-center justify-center">
        <p className="text-slate-500 text-sm">No arrangements</p>
      </div>
    )
  }

  return (
    <div className="w-72 shrink-0 bg-slate-950 border-r border-slate-700 overflow-y-auto flex flex-col">
      {finalSelection && finalSelection.selected_candidate_ids.length > 0 && (
        <FinalistPanel
          finalSelection={finalSelection}
          arrangements={arrangements}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      )}
      {[...grouped.entries()].map(([candidateId, group]) => {
        const candidate = candidateLookup.get(candidateId)
        const familyLabel = candidate
          ? candidate.chord_symbols.join(" → ")
          : candidateId

        return (
          <div key={candidateId} className="flex flex-col">
            {/* Family header */}
            <div className="px-3 py-2 bg-slate-900 border-b border-slate-800 sticky top-0 z-10">
              <p className="text-xs font-mono text-slate-300 truncate" title={familyLabel}>
                {familyLabel}
              </p>
            </div>

            {/* Cards */}
            <div className="flex flex-col gap-1 p-2">
              {group.map((arr) => (
                <ArrangementCard
                  key={arr.id}
                  arrangement={arr}
                  selected={arr.id === selectedId}
                  onClick={() => onSelect(arr.id)}
                  genre={genre}
                />
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
