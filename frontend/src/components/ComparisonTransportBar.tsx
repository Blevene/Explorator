import { useState } from "react"
import { useComparisonAudioStore } from "../stores/comparisonAudioStore"
import * as comparisonAudioEngine from "../services/comparisonAudioEngine"
import { genreAccentVar } from "../utils/designTokens"
import type { ArrangementDetail } from "../services/api"

interface ComparisonTransportBarProps {
  arrangements: Map<string, ArrangementDetail>
  genre: string
  onClose: () => void
}

export default function ComparisonTransportBar({ arrangements, genre, onClose }: ComparisonTransportBarProps) {
  const { playing, paused, tempo, loop } = useComparisonAudioStore()
  const accent = genreAccentVar(genre)
  const [audioError, setAudioError] = useState<string | null>(null)

  async function handlePlayPause() {
    setAudioError(null)
    try {
      if (playing) {
        comparisonAudioEngine.pause()
      } else if (paused) {
        comparisonAudioEngine.resume()
      } else {
        await comparisonAudioEngine.playComparison(arrangements, tempo, genre)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Audio playback failed"
      setAudioError(msg)
    }
  }

  function handleStop() {
    comparisonAudioEngine.stop()
  }

  function handleTempoChange(e: React.ChangeEvent<HTMLInputElement>) {
    comparisonAudioEngine.setTempo(Number(e.target.value))
  }

  function handleLoopToggle() {
    comparisonAudioEngine.setLoop(!loop)
  }

  const candidateCount = arrangements.size

  return (
    <div
      className="flex items-center px-4 py-2 gap-2"
      style={{ background: "var(--surface-2)", borderBottom: "1px solid var(--border-default)" }}
    >
      {/* Label */}
      <span className="text-xs font-semibold tracking-wider" style={{ color: "var(--text-muted)" }}>
        COMPARING {candidateCount} CANDIDATES
      </span>

      <div className="flex-1" />

      {/* Play/Pause */}
      <button
        onClick={handlePlayPause}
        title={playing ? "Pause" : paused ? "Resume" : "Play"}
        aria-label={playing ? "Pause" : paused ? "Resume" : "Play"}
        className="p-2 rounded transition-colors"
        style={{ color: playing ? accent : undefined }}
      >
        {playing ? (
          <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" className={playing ? "" : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"}>
            <rect x="2" y="1" width="4" height="12" rx="1" />
            <rect x="8" y="1" width="4" height="12" rx="1" />
          </svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" className="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
            <polygon points="2,1 12,7 2,13" />
          </svg>
        )}
      </button>

      {/* Stop */}
      <button
        onClick={handleStop}
        title="Stop"
        aria-label="Stop"
        className="p-2 rounded transition-colors"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" className="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
          <rect x="1" y="1" width="12" height="12" rx="1" />
        </svg>
      </button>

      {/* Tempo */}
      <div className="flex items-center gap-2 mx-2">
        <span className="text-xs select-none" style={{ color: "var(--text-muted)" }}>BPM</span>
        <input
          type="range"
          min={60}
          max={200}
          value={tempo}
          onChange={handleTempoChange}
          title={`Tempo: ${tempo} BPM`}
          aria-label={`Tempo: ${tempo} BPM`}
          className="w-20 cursor-pointer accent-[var(--text-secondary)]"
        />
        <span className="text-xs font-mono w-8 text-right" style={{ color: "var(--text-primary)" }}>{tempo}</span>
      </div>

      {/* Loop */}
      <button
        onClick={handleLoopToggle}
        title={loop ? "Loop on" : "Loop off"}
        aria-label={loop ? "Disable loop" : "Enable loop"}
        aria-pressed={loop}
        className="p-2 rounded transition-colors"
        style={loop ? { color: accent } : undefined}
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={loop ? "" : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"}
        >
          <path d="M1 4h10a4 4 0 0 1 4 4v0a4 4 0 0 1-4 4H5" />
          <polyline points="3 7 1 4 4 2" />
          <polyline points="11 10 13 13 10 15" />
        </svg>
      </button>

      {/* Close */}
      <button
        onClick={onClose}
        title="Close comparison"
        aria-label="Close comparison"
        className="p-2 rounded transition-colors text-[var(--text-muted)] hover:text-[var(--text-primary)] ml-2"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <line x1="2" y1="2" x2="12" y2="12" />
          <line x1="12" y1="2" x2="2" y2="12" />
        </svg>
      </button>

      {/* Error */}
      {audioError && (
        <span className="text-xs ml-2 truncate" style={{ color: "var(--danger-text)" }} title={audioError}>
          Audio: {audioError}
        </span>
      )}
    </div>
  )
}
