import { useComparisonAudioStore } from "../stores/comparisonAudioStore"

interface LaneSidebarProps {
  candidateId: string
  label: string
  score: number
  audible: boolean
}

export default function LaneSidebar({ candidateId, label, score, audible }: LaneSidebarProps) {
  const { mutedLanes, soloedLanes, toggleMute, toggleSolo } = useComparisonAudioStore()

  const isSoloed = !!soloedLanes[candidateId]
  const isMuted = !!mutedLanes[candidateId]

  return (
    <div
      className="w-[72px] flex-shrink-0 flex flex-col items-center justify-center py-2 gap-1.5"
      style={{
        background: "var(--surface-2)",
        borderRight: "1px solid var(--border-subtle)",
        opacity: audible ? 1 : 0.2,
        transition: "opacity 150ms ease",
      }}
    >
      {/* Candidate label */}
      <div
        className="w-7 h-7 rounded-full flex items-center justify-center font-bold text-sm"
        style={{ background: "var(--accent-primary)", color: "#fff" }}
      >
        {label}
      </div>

      {/* Score */}
      <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
        {score.toFixed(1)}
      </span>

      {/* Solo / Mute buttons — 32×32 hit area; visual letters stay compact */}
      <div className="flex gap-1">
        <button
          onClick={(e) => { e.stopPropagation(); toggleSolo(candidateId) }}
          title={isSoloed ? "Unsolo" : "Solo"}
          aria-label={`${isSoloed ? "Unsolo" : "Solo"} ${label}`}
          aria-pressed={isSoloed}
          className="w-8 h-8 flex items-center justify-center rounded-sm text-[10px] font-bold border-none cursor-pointer"
          style={{
            background: isSoloed ? "var(--accent-primary)" : "var(--surface-3)",
            color: isSoloed ? "var(--surface-0)" : "var(--text-muted)",
          }}
        >
          S
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); toggleMute(candidateId) }}
          title={isMuted ? "Unmute" : "Mute"}
          aria-label={`${isMuted ? "Unmute" : "Mute"} ${label}`}
          aria-pressed={isMuted}
          className="w-8 h-8 flex items-center justify-center rounded-sm text-[10px] font-bold border-none cursor-pointer"
          style={{
            background: isMuted ? "var(--score-low)" : "var(--surface-3)",
            color: isMuted ? "var(--surface-0)" : "var(--text-muted)",
          }}
        >
          M
        </button>
      </div>
    </div>
  )
}
