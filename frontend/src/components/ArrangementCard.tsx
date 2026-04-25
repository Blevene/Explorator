import { useState } from "react"
import type { ArrangementSummary, CandidateExplanation } from "../services/api"
import { generateExplanation } from "../services/api"
import { scoreColorVar, genreAccentVar } from "../utils/designTokens"

interface ArrangementCardProps {
  arrangement: ArrangementSummary
  selected: boolean
  onClick: () => void
  genre: string
}

function parseBadges(rationale: string): { voicing: string; bass: string } | null {
  const parts = rationale.split(" + ")
  if (parts.length < 2) return null
  return { voicing: parts[0].trim(), bass: parts[1].trim() }
}

export default function ArrangementCard({
  arrangement,
  selected,
  onClick,
  genre,
}: ArrangementCardProps) {
  const isRejected = arrangement.status === "rejected"
  const badges = parseBadges(arrangement.rationale)

  const [explanation, setExplanation] = useState<CandidateExplanation | null>(null)
  const [explaining, setExplaining] = useState(false)
  const [explainError, setExplainError] = useState<string | null>(null)
  const [showExplanation, setShowExplanation] = useState(false)

  const handleExplain = async (e: React.MouseEvent) => {
    e.stopPropagation()

    if (explanation) {
      setShowExplanation(!showExplanation)
      return
    }

    setExplaining(true)
    setExplainError(null)
    try {
      const result = await generateExplanation(arrangement.id)
      setExplanation(result)
      setShowExplanation(true)
    } catch (err) {
      setExplainError(err instanceof Error ? err.message : "Failed to generate explanation")
    } finally {
      setExplaining(false)
    }
  }

  return (
    <div
      onClick={onClick}
      className="rounded-md p-3 cursor-pointer transition-all"
      style={{
        background: selected ? "var(--surface-3)" : "var(--surface-1)",
        border: "1px solid var(--border-default)",
        borderLeft: selected
          ? `4px solid ${genreAccentVar(genre)}`
          : "1px solid var(--border-default)",
        opacity: isRejected ? 0.4 : 1,
      }}
    >
      {/* Score */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          #{arrangement.rank_within_round}
        </span>
        <span
          className="text-sm font-bold font-mono"
          style={{ color: scoreColorVar(arrangement.weighted_total) }}
        >
          {(arrangement.weighted_total ?? 0).toFixed(2)}
        </span>
      </div>

      {/* Badges */}
      {badges ? (
        <div className="flex flex-wrap gap-1">
          <span
            className="text-xs px-1.5 py-0.5 rounded font-mono"
            style={{
              background: "var(--accent-primary-dim)",
              color: "var(--accent-primary)",
            }}
          >
            {badges.voicing}
          </span>
          <span
            className="text-xs px-1.5 py-0.5 rounded font-mono"
            style={{
              background: "var(--accent-secondary-dim)",
              color: "var(--accent-secondary)",
            }}
          >
            {badges.bass}
          </span>
        </div>
      ) : (
        <p className="text-xs truncate" style={{ color: "var(--text-muted)" }}>
          {arrangement.rationale}
        </p>
      )}

      {/* Explain button */}
      {!isRejected && (
        <button
          onClick={handleExplain}
          disabled={explaining}
          aria-expanded={!!explanation && showExplanation}
          className="mt-2 text-xs px-2 py-1 rounded border transition-colors disabled:opacity-50
                     border-[var(--border-default)] hover:border-[var(--border-bright)] focus-visible:border-[var(--border-bright)]
                     text-[var(--text-secondary)] hover:text-[var(--text-primary)] focus-visible:text-[var(--text-primary)]"
        >
          {explaining ? (
            <span className="flex items-center gap-1">
              <span
                className="w-3 h-3 border border-t-transparent rounded-full animate-spin"
                style={{ borderColor: "var(--text-secondary)", borderTopColor: "transparent" }}
              />
              Generating...
            </span>
          ) : explanation ? (
            showExplanation ? "Hide explanation" : "Show explanation"
          ) : (
            "Explain"
          )}
        </button>
      )}

      {/* Explain error */}
      {explainError && (
        <p className="mt-1 text-xs" style={{ color: "var(--score-low)" }}>
          {explainError}
        </p>
      )}

      {/* Explanation display */}
      {showExplanation && explanation && (
        <div
          className="mt-2 pt-2 text-xs space-y-2"
          style={{ borderTop: "1px solid var(--border-default)" }}
        >
          <p style={{ color: "var(--text-primary)", fontStyle: "italic" }}>
            {explanation.summary}
          </p>

          {explanation.why_it_works.length > 0 && (
            <div>
              <span className="font-medium" style={{ color: "var(--score-high)" }}>
                Why it works:
              </span>
              <ul className="list-disc list-inside mt-0.5" style={{ color: "var(--text-secondary)" }}>
                {explanation.why_it_works.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {explanation.what_is_experimental.length > 0 && (
            <div>
              <span className="font-medium" style={{ color: "var(--score-mid)" }}>
                Experimental:
              </span>
              <ul className="list-disc list-inside mt-0.5" style={{ color: "var(--text-secondary)" }}>
                {explanation.what_is_experimental.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {explanation.recommended_use_cases.length > 0 && (
            <div>
              <span className="font-medium" style={{ color: "var(--accent-secondary)" }}>
                Use cases:
              </span>
              <ul className="list-disc list-inside mt-0.5" style={{ color: "var(--text-secondary)" }}>
                {explanation.recommended_use_cases.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
