import type { ArrangementSummary } from "../services/api"

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
          {arrangement.weighted_total.toFixed(2)}
        </span>
      </div>

      {/* Badges */}
      {badges ? (
        <div className="flex flex-wrap gap-1">
          <span className="text-xs bg-slate-700 text-slate-300 px-1.5 py-0.5 rounded">
            {badges.voicing}
          </span>
          <span className="text-xs bg-slate-700 text-slate-400 px-1.5 py-0.5 rounded">
            {badges.bass}
          </span>
        </div>
      ) : (
        <p className="text-slate-500 text-xs truncate">{arrangement.rationale}</p>
      )}
    </div>
  )
}
