import { useState } from "react"
import { scoreColorVar, scoreTierGlyph } from "../utils/designTokens"

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

function ScoreDimension({ name, value }: { name: string; value: number }) {
  const pct = Math.min(100, Math.max(0, (value / 10) * 100))
  const color = scoreColorVar(value)
  const glyph = scoreTierGlyph(value)
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs w-36 shrink-0 capitalize" style={{ color: "var(--text-secondary)" }}>
        {name.replace(/_/g, " ")}
      </span>
      <div className="flex-1 rounded-full h-1.5" style={{ background: "var(--border-default)" }}>
        <div
          className="h-1.5 rounded-full"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="text-xs font-mono w-12 text-right tabular-nums" style={{ color }}>
        <span aria-hidden="true" className="mr-1">{glyph}</span>
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
      <span className="text-xs uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
        {title}
      </span>
      {available.map((dim) => (
        <ScoreDimension key={dim} name={dim} value={scores[dim]} />
      ))}
    </div>
  )
}

export default function ScorePanel({ scores, weightedTotal }: ScorePanelProps) {
  const [collapsed, setCollapsed] = useState(false)
  const total = weightedTotal ?? 0
  const totalColor = scoreColorVar(total)
  const totalGlyph = scoreTierGlyph(total)

  return (
    <div style={{ background: "var(--surface-1)", borderTop: "1px solid var(--border-default)" }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2">
        <div className="flex items-center gap-3">
          <span className="text-xs uppercase tracking-wider" style={{ color: "var(--text-secondary)" }}>
            Scores
          </span>
          <span className="text-base font-bold font-mono tabular-nums" style={{ color: totalColor }}>
            <span aria-hidden="true" className="mr-1">{totalGlyph}</span>
            {total.toFixed(2)}
          </span>
        </div>
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="text-sm font-bold w-5 h-5 flex items-center justify-center transition-colors text-[var(--text-muted)] hover:text-[var(--text-primary)]"
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
