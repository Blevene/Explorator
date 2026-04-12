import { useEffect } from "react"
import type { ArrangementDetail } from "../services/api"
import { recordComparison } from "../services/api"
import { useCandidateStore } from "../stores/candidateStore"
import { scoreColorVar } from "../utils/designTokens"
import PianoRoll from "./PianoRoll"

interface ComparisonViewProps {
  sessionId: string
  genre: string
  arrangements: Map<string, ArrangementDetail>
  onClose: () => void
}

const SCORE_DIMENSIONS = [
  "voice_leading",
  "tension_curve",
  "playability",
  "register_density",
  "genre_fit",
  "novelty",
]

function dimensionLabel(dim: string): string {
  return dim
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ")
}


export default function ComparisonView({
  sessionId,
  genre,
  arrangements,
  onClose,
}: ComparisonViewProps) {
  const { selectedForComparison, clearComparison } = useCandidateStore()

  const candidateIds = selectedForComparison
  const comparedArrangements = candidateIds
    .map((id) => arrangements.get(id))
    .filter((a): a is ArrangementDetail => a !== undefined)

  // Fire-and-forget comparison recording
  useEffect(() => {
    if (comparedArrangements.length >= 2) {
      const labels: Record<string, string> = {}
      comparedArrangements.forEach((a, i) => {
        labels[a.id] = String.fromCharCode(65 + i) // A, B, C
      })
      recordComparison(
        sessionId,
        candidateIds,
        SCORE_DIMENSIONS,
        labels,
      )
    }
  }, [candidateIds.join(",")])

  if (comparedArrangements.length < 2) {
    return (
      <div className="p-4 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
        Select at least 2 candidates to compare.
      </div>
    )
  }

  // Collect all scores for leader highlighting
  const allScores: Record<string, Record<string, number>> = {}
  comparedArrangements.forEach((a) => {
    allScores[a.id] = a.scorecard?.scores ?? {}
  })

  const leaders: Record<string, string> = {}
  SCORE_DIMENSIONS.forEach((dim) => {
    let bestId = ""
    let bestScore = -1
    comparedArrangements.forEach((a) => {
      const s = allScores[a.id]?.[dim] ?? 0
      if (s > bestScore) {
        bestScore = s
        bestId = a.id
      }
    })
    if (bestId) leaders[dim] = bestId
  })

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{ background: 'var(--surface-1)', border: '1px solid var(--border-default)' }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-2"
        style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border-default)' }}
      >
        <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
          Comparing {comparedArrangements.length} candidates
        </span>
        <button
          onClick={() => {
            clearComparison()
            onClose()
          }}
          className="text-xs transition-colors"
          style={{ color: 'var(--text-muted)' }}
          onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-secondary)')}
          onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
        >
          Close
        </button>
      </div>

      {/* Stacked piano rolls */}
      <div style={{ borderBottom: '1px solid var(--border-subtle)' }}>
        {comparedArrangements.map((a, i) => (
          <div
            key={a.id}
            className="flex"
            style={{ borderBottom: i < comparedArrangements.length - 1 ? '1px solid var(--border-subtle)' : 'none' }}
          >
            {/* Left rail: label + score */}
            <div
              className="w-16 flex-shrink-0 flex flex-col items-center justify-center py-2"
              style={{ background: 'var(--surface-2)', borderRight: '1px solid var(--border-subtle)' }}
            >
              <span className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
                {String.fromCharCode(65 + i)}
              </span>
              <span className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                {(a.scorecard?.weighted_total ?? a.weighted_total ?? 0).toFixed(1)}
              </span>
            </div>
            <div className="flex-1">
              <PianoRoll
                arrangement={a}
                genre={genre}
                compact
                showCursor={false}
                barWidth={70}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Score comparison table */}
      <div className="p-4">
        <h3
          className="text-xs font-medium uppercase tracking-wider mb-2"
          style={{ color: 'var(--text-muted)' }}
        >
          Score Comparison
        </h3>
        <div className="space-y-1">
          {SCORE_DIMENSIONS.map((dim) => (
            <div key={dim} className="flex items-center text-xs">
              <span className="w-32 truncate" style={{ color: 'var(--text-muted)' }}>
                {dimensionLabel(dim)}
              </span>
              <div className="flex-1 flex gap-4">
                {comparedArrangements.map((a, i) => {
                  const score = allScores[a.id]?.[dim] ?? 0
                  const isLeader = leaders[dim] === a.id
                  return (
                    <span
                      key={a.id}
                      className="font-mono"
                      style={{ color: scoreColorVar(score), fontWeight: isLeader ? 700 : 400, opacity: isLeader ? 1 : 0.7 }}
                    >
                      {String.fromCharCode(65 + i)}: {score.toFixed(1)}
                    </span>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
