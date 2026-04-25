import { useState } from "react"
import { useAudioStore } from "../stores/audioStore"
import * as audioEngine from "../services/audioEngine"
import { genreAccentVar } from "../utils/designTokens"
import type { ArrangementDetail } from "../services/api"

interface TransportBarProps {
  arrangement: ArrangementDetail | null
  genre: string
}

function Divider() {
  return <div className="w-px h-8 mx-1 self-center" style={{ background: "var(--border-default)" }} />
}

export default function TransportBar({ arrangement, genre }: TransportBarProps) {
  const { playing, paused, tempo, loop, mutedTracks, volume } = useAudioStore()
  const accent = genreAccentVar(genre)

  const [audioError, setAudioError] = useState<string | null>(null)

  async function handlePlayPause() {
    if (!arrangement) return
    setAudioError(null)
    try {
      if (playing) {
        audioEngine.pause()
      } else if (paused) {
        audioEngine.resume()
      } else {
        await audioEngine.play(arrangement, tempo, genre)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Audio playback failed"
      setAudioError(msg)
    }
  }

  function handleStop() {
    audioEngine.stop()
  }

  function handleTempoChange(e: React.ChangeEvent<HTMLInputElement>) {
    audioEngine.setTempo(Number(e.target.value))
  }

  function handleLoopToggle() {
    audioEngine.setLoop(!loop)
  }

  function handleVoicingMute() {
    audioEngine.setVoicingMute(!mutedTracks.voicing)
  }

  function handleBassMute() {
    audioEngine.setBassMute(!mutedTracks.bass)
  }

  function handleMelodyMute() {
    audioEngine.setMelodyMute(!mutedTracks.melody)
  }

  function handleVolumeChange(e: React.ChangeEvent<HTMLInputElement>) {
    audioEngine.setVolume(Number(e.target.value))
  }

  const isPlayActive = playing
  const isLoopActive = loop
  const isVoicingMuted = mutedTracks.voicing
  const isBassMuted = mutedTracks.bass
  const isMelodyMuted = mutedTracks.melody

  return (
    <div
      className="h-12 flex items-center px-3 gap-1"
      style={{ background: "var(--surface-1)", borderBottom: "1px solid var(--border-default)" }}
    >

      {/* Play / Pause */}
      <button
        onClick={handlePlayPause}
        disabled={!arrangement}
        title={playing ? "Pause" : paused ? "Resume" : "Play"}
        aria-label={playing ? "Pause" : paused ? "Resume" : "Play"}
        className="p-2 rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        style={{ color: isPlayActive ? accent : undefined }}
      >
        {playing ? (
          // Pause bars
          <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" className={isPlayActive ? "" : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"}>
            <rect x="2" y="1" width="4" height="12" rx="1" />
            <rect x="8" y="1" width="4" height="12" rx="1" />
          </svg>
        ) : (
          // Play triangle
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

      <Divider />

      {/* Tempo slider */}
      <div className="flex items-center gap-2">
        <span className="text-xs select-none" style={{ color: "var(--text-muted)" }}>BPM</span>
        <input
          type="range"
          min={60}
          max={200}
          value={tempo}
          onChange={handleTempoChange}
          title={`Tempo: ${tempo} BPM`}
          aria-label={`Tempo: ${tempo} BPM`}
          className="w-24 cursor-pointer accent-[var(--text-secondary)]"
        />
        <span className="text-xs font-mono w-8 text-right" style={{ color: "var(--text-primary)" }}>{tempo}</span>
      </div>

      <Divider />

      {/* Loop toggle */}
      <button
        onClick={handleLoopToggle}
        title={isLoopActive ? "Loop on" : "Loop off"}
        aria-label={isLoopActive ? "Disable loop" : "Enable loop"}
        aria-pressed={isLoopActive}
        className="p-2 rounded transition-colors"
        style={isLoopActive ? { color: accent } : undefined}
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
          className={isLoopActive ? "" : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"}
        >
          <path d="M1 4h10a4 4 0 0 1 4 4v0a4 4 0 0 1-4 4H5" />
          <polyline points="3 7 1 4 4 2" />
          <polyline points="11 10 13 13 10 15" />
        </svg>
      </button>

      <Divider />

      {/* Mute Voicing */}
      <button
        onClick={handleVoicingMute}
        title={isVoicingMuted ? "Unmute voicing" : "Mute voicing"}
        aria-pressed={!isVoicingMuted}
        className="px-2 py-1 rounded text-xs font-medium transition-colors"
        style={!isVoicingMuted
          ? { color: "var(--accent-primary)", background: "var(--accent-primary-dim)" }
          : { color: "var(--text-muted)" }}
      >
        Chords
      </button>

      {/* Mute Bass */}
      <button
        onClick={handleBassMute}
        title={isBassMuted ? "Unmute bass" : "Mute bass"}
        aria-pressed={!isBassMuted}
        className="px-2 py-1 rounded text-xs font-medium transition-colors"
        style={!isBassMuted
          ? { color: "var(--accent-secondary)", background: "var(--accent-secondary-dim)" }
          : { color: "var(--text-muted)" }}
      >
        Bass
      </button>

      {/* Mute Melody */}
      <button
        onClick={handleMelodyMute}
        title={isMelodyMuted ? "Unmute melody" : "Mute melody"}
        aria-pressed={!isMelodyMuted}
        className="px-2 py-1 rounded text-xs font-medium transition-colors"
        style={!isMelodyMuted
          ? { color: "var(--accent-tertiary)", background: "var(--accent-tertiary-dim)" }
          : { color: "var(--text-muted)" }}
      >
        Melody
      </button>

      <Divider />

      {/* Volume slider */}
      <div className="flex items-center gap-2">
        <span className="text-xs select-none" style={{ color: "var(--text-muted)" }}>Vol</span>
        <input
          type="range"
          min={-60}
          max={0}
          value={volume}
          onChange={handleVolumeChange}
          title={`Volume: ${volume} dB`}
          aria-label={`Volume: ${volume} dB`}
          className="w-24 cursor-pointer accent-[var(--text-secondary)]"
        />
        <span className="text-xs font-mono w-10 text-right" style={{ color: "var(--text-primary)" }}>{volume} dB</span>
      </div>

      {/* Audio error */}
      {audioError && (
        <span className="text-xs ml-2 truncate" style={{ color: "var(--danger-text)" }} title={audioError}>
          Audio: {audioError}
        </span>
      )}

    </div>
  )
}
