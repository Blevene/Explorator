import { useState } from "react"

interface ScorePanelProps {
  scores: Record<string, number>
  weightedTotal: number
}

const ARRANGEMENT_DIMS = ["voice_leading", "register_density", "playability"]
const PROGRESSION_DIMS = [
  "genre_fit",
  "emotional_fit",
  "theoretical_coherence",
  "cadence_quality",
  "novelty",
  "loopability",
]

function barColor(score: number): string {
  if (score >= 8) return "bg-emerald-400"
  if (score >= 6) return "bg-amber-400"
  return "bg-rose-400"
}

function labelColor(score: number): string {
  if (score >= 8) return "text-emerald-400"
  if (score >= 6) return "text-amber-400"
  return "text-rose-400"
}

function totalColor(score: number): string {
  if (score >= 8) return "text-emerald-400"
  if (score >= 6) return "text-amber-400"
  return "text-rose-400"
}

function ScoreDimension({ name, value }: { name: string; value: number }) {
  const pct = Math.min(100, Math.max(0, (value / 10) * 100))
  return (
    <div className="flex items-center gap-2">
      <span className="text-slate-400 text-xs w-36 shrink-0 capitalize">
        {name.replace(/_/g, " ")}
      </span>
      <div className="flex-1 bg-slate-700 rounded-full h-1.5">
        <div
          className={`h-1.5 rounded-full ${barColor(value)}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-xs font-mono w-8 text-right ${labelColor(value)}`}>
        {(value ?? 0).toFixed(1)}
      </span>
    </div>
  )
}

function ScoreGroup({
  title,
  dims,
  scores,
}: {
  title: string
  dims: string[]
  scores: Record<string, number>
}) {
  const available = dims.filter((d) => d in scores)
  if (available.length === 0) return null
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-slate-500 text-xs uppercase tracking-wider">{title}</span>
      {available.map((dim) => (
        <ScoreDimension key={dim} name={dim} value={scores[dim]} />
      ))}
    </div>
  )
}

export default function ScorePanel({ scores, weightedTotal }: ScorePanelProps) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="bg-slate-900 border-t border-slate-700">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2">
        <div className="flex items-center gap-3">
          <span className="text-slate-400 text-xs uppercase tracking-wider">Scores</span>
          <span className={`text-base font-bold font-mono ${totalColor(weightedTotal ?? 0)}`}>
            {(weightedTotal ?? 0).toFixed(2)}
          </span>
        </div>
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="text-slate-500 hover:text-slate-300 text-sm font-bold w-5 h-5 flex items-center justify-center transition-colors"
          aria-label={collapsed ? "Expand scores" : "Collapse scores"}
        >
          {collapsed ? "+" : "−"}
        </button>
      </div>

      {/* Body */}
      {!collapsed && (
        <div className="px-4 pb-4 flex flex-col gap-4">
          <ScoreGroup title="Arrangement" dims={ARRANGEMENT_DIMS} scores={scores} />
          <ScoreGroup title="Progression" dims={PROGRESSION_DIMS} scores={scores} />
        </div>
      )}
    </div>
  )
}
