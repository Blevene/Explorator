import { useAudioStore } from "../stores/audioStore"
import * as audioEngine from "../services/audioEngine"
import type { ArrangementDetail } from "../services/api"

interface TransportBarProps {
  arrangement: ArrangementDetail | null
  genre: string
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

function Divider() {
  return <div className="w-px h-8 bg-slate-700 mx-1 self-center" />
}

export default function TransportBar({ arrangement, genre }: TransportBarProps) {
  const { playing, paused, tempo, loop, mutedTracks, volume } = useAudioStore()
  const accent = getAccent(genre)

  function handlePlayPause() {
    if (!arrangement) return
    if (playing) {
      audioEngine.pause()
    } else if (paused) {
      audioEngine.resume()
    } else {
      audioEngine.play(arrangement, tempo, genre)
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

  function handleVolumeChange(e: React.ChangeEvent<HTMLInputElement>) {
    audioEngine.setVolume(Number(e.target.value))
  }

  const isPlayActive = playing
  const isLoopActive = loop
  const isVoicingMuted = mutedTracks.voicing
  const isBassMuted = mutedTracks.bass

  return (
    <div className="h-12 bg-slate-900 border-b border-slate-700 flex items-center px-3 gap-1">

      {/* Play / Pause */}
      <button
        onClick={handlePlayPause}
        disabled={!arrangement}
        title={playing ? "Pause" : paused ? "Resume" : "Play"}
        className="p-2 rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        style={{ color: isPlayActive ? accent : undefined }}
      >
        {playing ? (
          // Pause bars
          <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" className={isPlayActive ? "" : "text-slate-500 hover:text-slate-200"}>
            <rect x="2" y="1" width="4" height="12" rx="1" />
            <rect x="8" y="1" width="4" height="12" rx="1" />
          </svg>
        ) : (
          // Play triangle
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

      <Divider />

      {/* Tempo slider */}
      <div className="flex items-center gap-2">
        <span className="text-slate-500 text-xs select-none">BPM</span>
        <input
          type="range"
          min={60}
          max={200}
          value={tempo}
          onChange={handleTempoChange}
          title={`Tempo: ${tempo} BPM`}
          className="w-24 accent-slate-400 cursor-pointer"
        />
        <span className="text-slate-300 text-xs font-mono w-8 text-right">{tempo}</span>
      </div>

      <Divider />

      {/* Loop toggle */}
      <button
        onClick={handleLoopToggle}
        title={isLoopActive ? "Loop on" : "Loop off"}
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
          className={isLoopActive ? "" : "text-slate-500 hover:text-slate-200"}
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
        className="px-2 py-1 rounded text-xs font-bold transition-colors"
        style={!isVoicingMuted ? { color: "#fbbf24" } : { color: "#475569" }}
      >
        V
      </button>

      {/* Mute Bass */}
      <button
        onClick={handleBassMute}
        title={isBassMuted ? "Unmute bass" : "Mute bass"}
        className="px-2 py-1 rounded text-xs font-bold transition-colors"
        style={!isBassMuted ? { color: "#22d3ee" } : { color: "#475569" }}
      >
        B
      </button>

      <Divider />

      {/* Volume slider */}
      <div className="flex items-center gap-2">
        <span className="text-slate-500 text-xs select-none">Vol</span>
        <input
          type="range"
          min={-60}
          max={0}
          value={volume}
          onChange={handleVolumeChange}
          title={`Volume: ${volume} dB`}
          className="w-24 accent-slate-400 cursor-pointer"
        />
        <span className="text-slate-300 text-xs font-mono w-10 text-right">{volume} dB</span>
      </div>

    </div>
  )
}
