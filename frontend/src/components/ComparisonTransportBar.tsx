import { useState } from "react"
import { useComparisonAudioStore } from "../stores/comparisonAudioStore"
import * as comparisonAudioEngine from "../services/comparisonAudioEngine"
import type { ArrangementDetail } from "../services/api"

interface ComparisonTransportBarProps {
  arrangements: Map<string, ArrangementDetail>
  genre: string
  onClose: () => void
}

const GENRE_ACCENT: Record<string, string> = {
  dream_pop: "#a78bfa",
  synthwave: "#f472b6",
  cinematic: "#eab308",
}

function getAccent(genre: string): string {
  const key = genre.toLowerCase().replace(/[\s-]/g, "_")
  return GENRE_ACCENT[key] ?? GENRE_ACCENT["dream_pop"]
}

export default function ComparisonTransportBar({ arrangements, genre, onClose }: ComparisonTransportBarProps) {
  const { playing, paused, tempo, loop } = useComparisonAudioStore()
  const accent = getAccent(genre)
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
        className="p-2 rounded transition-colors"
        style={{ color: playing ? accent : undefined }}
      >
        {playing ? (
          <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" className={playing ? "" : "text-slate-500 hover:text-slate-200"}>
            <rect x="2" y="1" width="4" height="12" rx="1" />
            <rect x="8" y="1" width="4" height="12" rx="1" />
          </svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" className="text-slate-500 hover:text-slate-200">
            <polygon points="2,1 12,7 2,13" />
          </svg>
        )}
      </button>

      {/* Stop */}
      <button
        onClick={handleStop}
        title="Stop"
        className="p-2 rounded transition-colors"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" className="text-slate-500 hover:text-slate-200">
          <rect x="1" y="1" width="12" height="12" rx="1" />
        </svg>
      </button>

      {/* Tempo */}
      <div className="flex items-center gap-2 mx-2">
        <span className="text-slate-500 text-xs select-none">BPM</span>
        <input
          type="range"
          min={60}
          max={200}
          value={tempo}
          onChange={handleTempoChange}
          title={`Tempo: ${tempo} BPM`}
          className="w-20 accent-slate-400 cursor-pointer"
        />
        <span className="text-slate-300 text-xs font-mono w-8 text-right">{tempo}</span>
      </div>

      {/* Loop */}
      <button
        onClick={handleLoopToggle}
        title={loop ? "Loop on" : "Loop off"}
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
          className={loop ? "" : "text-slate-500 hover:text-slate-200"}
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
        className="p-2 rounded transition-colors text-slate-500 hover:text-slate-200 ml-2"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <line x1="2" y1="2" x2="12" y2="12" />
          <line x1="12" y1="2" x2="2" y2="12" />
        </svg>
      </button>

      {/* Error */}
      {audioError && (
        <span className="text-rose-400 text-xs ml-2 truncate" title={audioError}>
          Audio: {audioError}
        </span>
      )}
    </div>
  )
}
