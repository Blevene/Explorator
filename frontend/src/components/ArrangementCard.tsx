import { useState } from "react"
import type { ArrangementSummary, CandidateExplanation } from "../services/api"
import { generateExplanation } from "../services/api"

interface ArrangementCardProps {
  arrangement: ArrangementSummary
  selected: boolean
  onClick: () => void
  genre: string
}

const GENRE_ACCENT: Record<string, string> = {
  dream_pop: "border-violet-500",
  synthwave: "border-pink-500",
  cinematic: "border-yellow-500",
}

function getAccentBorder(genre: string): string {
  const key = genre.toLowerCase().replace(/[\s-]/g, "_")
  return GENRE_ACCENT[key] ?? GENRE_ACCENT["dream_pop"]
}

function scoreColor(score: number): string {
  if (score >= 8) return "text-emerald-400"
  if (score >= 6) return "text-amber-400"
  return "text-rose-400"
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
  const accentBorder = getAccentBorder(genre)

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
      className={[
        "border rounded-md p-3 cursor-pointer transition-all",
        selected
          ? `border-l-4 ${accentBorder} bg-slate-800 border-slate-700`
          : "border-slate-700 bg-slate-900 hover:bg-slate-800",
        isRejected ? "opacity-40" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {/* Score */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-slate-500 text-xs">
          #{arrangement.rank_within_round}
        </span>
        <span className={`text-sm font-bold font-mono ${scoreColor(arrangement.weighted_total)}`}>
          {(arrangement.weighted_total ?? 0).toFixed(2)}
        </span>
      </div>

      {/* Badges */}
      {badges ? (
        <div className="flex flex-wrap gap-1">
          <span className="text-xs bg-amber-400/10 text-amber-400 px-1.5 py-0.5 rounded font-mono">
            {badges.voicing}
          </span>
          <span className="text-xs bg-cyan-400/10 text-cyan-400 px-1.5 py-0.5 rounded font-mono">
            {badges.bass}
          </span>
        </div>
      ) : (
        <p className="text-slate-500 text-xs truncate">{arrangement.rationale}</p>
      )}

      {/* Explain button */}
      {!isRejected && (
        <button
          onClick={handleExplain}
          disabled={explaining}
          className="mt-2 text-xs px-2 py-1 rounded border border-slate-600 text-slate-400 hover:text-slate-200 hover:border-slate-500 transition-colors disabled:opacity-50"
        >
          {explaining ? (
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 border border-slate-400 border-t-transparent rounded-full animate-spin" />
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
        <p className="mt-1 text-xs text-rose-400">{explainError}</p>
      )}

      {/* Explanation display */}
      {showExplanation && explanation && (
        <div className="mt-2 pt-2 border-t border-slate-700 text-xs space-y-2">
          <p className="text-slate-300 italic">{explanation.summary}</p>

          {explanation.why_it_works.length > 0 && (
            <div>
              <span className="text-emerald-400 font-medium">Why it works:</span>
              <ul className="list-disc list-inside text-slate-400 mt-0.5">
                {explanation.why_it_works.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {explanation.what_is_experimental.length > 0 && (
            <div>
              <span className="text-amber-400 font-medium">Experimental:</span>
              <ul className="list-disc list-inside text-slate-400 mt-0.5">
                {explanation.what_is_experimental.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {explanation.recommended_use_cases.length > 0 && (
            <div>
              <span className="text-sky-400 font-medium">Use cases:</span>
              <ul className="list-disc list-inside text-slate-400 mt-0.5">
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
