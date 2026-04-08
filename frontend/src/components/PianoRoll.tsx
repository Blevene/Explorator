import { useEffect, useRef } from "react"
import type { ArrangementDetail } from "../services/api"
import { pitchToMidi, midiToPitchLabel } from "../services/midiUtils"
import { useAudioStore } from "../stores/audioStore"

interface PianoRollProps {
  arrangement: ArrangementDetail
  genre: string
}

const BAR_WIDTH = 200
const ROW_HEIGHT = 8
const LABEL_WIDTH = 48
const HEADER_HEIGHT = 24

const GENRE_ACCENT: Record<string, string> = {
  dream_pop: "#a78bfa",
  synthwave: "#f472b6",
  cinematic: "#eab308",
}

function getAccent(genre: string): string {
  const key = genre.toLowerCase().replace(/[\s-]/g, "_")
  return GENRE_ACCENT[key] ?? GENRE_ACCENT["dream_pop"]
}

function collectMidiValues(arrangement: ArrangementDetail): number[] {
  const midis: number[] = []
  arrangement.voicing_plan?.voicing_events.forEach((ev) => {
    ev.pitches.forEach((p) => midis.push(pitchToMidi(p)))
  })
  arrangement.bass_line?.note_events.forEach((ev) => {
    midis.push(pitchToMidi(ev.pitch))
  })
  return midis
}

export default function PianoRoll({ arrangement, genre }: PianoRollProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const { playing, currentPosition, mutedTracks } = useAudioStore()

  const voicingEvents = arrangement.voicing_plan?.voicing_events ?? []
  const bassEvents = arrangement.bass_line?.note_events ?? []
  const hasEvents = voicingEvents.length > 0 || bassEvents.length > 0

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1

    // Calculate MIDI range
    const midiValues = collectMidiValues(arrangement)
    const octavePad = 12 // 1 octave
    const minMidi = midiValues.length > 0 ? Math.min(...midiValues) - octavePad : 48
    const maxMidi = midiValues.length > 0 ? Math.max(...midiValues) + octavePad : 84

    // Calculate total bars
    const allBars = [
      ...voicingEvents.map((e) => e.bar + Math.ceil(e.duration_beats / 4)),
      ...bassEvents.map((e) => e.bar + Math.ceil(e.duration_beats / 4)),
    ]
    const totalBars = allBars.length > 0 ? Math.max(...allBars) : 8

    const rows = maxMidi - minMidi + 1
    const canvasWidth = LABEL_WIDTH + totalBars * BAR_WIDTH
    const canvasHeight = HEADER_HEIGHT + rows * ROW_HEIGHT

    // Set canvas logical and physical size
    canvas.width = canvasWidth * dpr
    canvas.height = canvasHeight * dpr
    canvas.style.width = `${canvasWidth}px`
    canvas.style.height = `${canvasHeight}px`
    ctx.scale(dpr, dpr)

    // Background
    ctx.fillStyle = "#0f172a" // slate-900
    ctx.fillRect(0, 0, canvasWidth, canvasHeight)

    // Draw horizontal pitch rows (alternating subtle bg for black keys)
    for (let midi = minMidi; midi <= maxMidi; midi++) {
      const noteInOctave = midi % 12
      const isBlackKey = [1, 3, 6, 8, 10].includes(noteInOctave)
      const y = HEADER_HEIGHT + (maxMidi - midi) * ROW_HEIGHT

      if (isBlackKey) {
        ctx.fillStyle = "#1e293b" // slate-800 subtle
        ctx.fillRect(LABEL_WIDTH, y, totalBars * BAR_WIDTH, ROW_HEIGHT)
      }
    }

    // Draw beat and bar grid lines
    for (let bar = 0; bar <= totalBars; bar++) {
      for (let beat = 0; beat < 4; beat++) {
        const x = LABEL_WIDTH + bar * BAR_WIDTH + beat * (BAR_WIDTH / 4)
        if (beat === 0) {
          // Bar line
          ctx.strokeStyle = "#334155" // slate-700
          ctx.lineWidth = 1
        } else {
          // Beat line
          ctx.strokeStyle = "#1e293b" // slate-800
          ctx.lineWidth = 0.5
        }
        ctx.beginPath()
        ctx.moveTo(x, HEADER_HEIGHT)
        ctx.lineTo(x, canvasHeight)
        ctx.stroke()
      }
    }

    // Header background
    ctx.fillStyle = "#0f172a"
    ctx.fillRect(0, 0, canvasWidth, HEADER_HEIGHT)

    // Bar numbers in header
    ctx.fillStyle = "#64748b" // slate-500
    ctx.font = "10px monospace"
    ctx.textAlign = "center"
    for (let bar = 1; bar <= totalBars; bar++) {
      const x = LABEL_WIDTH + (bar - 1) * BAR_WIDTH + BAR_WIDTH / 2
      ctx.fillText(`${bar}`, x, HEADER_HEIGHT - 6)
    }

    // Pitch labels on left edge — only C octave markers
    ctx.textAlign = "right"
    ctx.font = "9px monospace"
    for (let midi = minMidi; midi <= maxMidi; midi++) {
      if (midi % 12 === 0) {
        const label = midiToPitchLabel(midi)
        const y = HEADER_HEIGHT + (maxMidi - midi) * ROW_HEIGHT + ROW_HEIGHT - 1
        ctx.fillStyle = "#94a3b8" // slate-400
        ctx.fillText(label, LABEL_WIDTH - 4, y)
      }
    }

    // Draw voicing notes — amber-400
    const voicingOpacity = mutedTracks.voicing ? 0.2 : 1.0
    ctx.globalAlpha = voicingOpacity
    for (const ev of voicingEvents) {
      const x = LABEL_WIDTH + ((ev.bar - 1) + (ev.beat - 1) / 4) * BAR_WIDTH
      const noteWidth = Math.max(4, (ev.duration_beats / 4) * BAR_WIDTH - 2)

      for (const pitch of ev.pitches) {
        const midi = pitchToMidi(pitch)
        if (midi < minMidi || midi > maxMidi) continue
        const y = HEADER_HEIGHT + (maxMidi - midi) * ROW_HEIGHT + 1

        ctx.fillStyle = "#fbbf24" // amber-400
        ctx.beginPath()
        ctx.roundRect(x, y, noteWidth, ROW_HEIGHT - 2, 2)
        ctx.fill()
      }
    }
    ctx.globalAlpha = 1.0

    // Draw bass notes — cyan-400
    const bassOpacity = mutedTracks.bass ? 0.2 : 1.0
    ctx.globalAlpha = bassOpacity
    for (const ev of bassEvents) {
      const midi = pitchToMidi(ev.pitch)
      if (midi < minMidi || midi > maxMidi) continue
      const x = LABEL_WIDTH + ((ev.bar - 1) + (ev.beat - 1) / 4) * BAR_WIDTH
      const y = HEADER_HEIGHT + (maxMidi - midi) * ROW_HEIGHT + 1
      const noteWidth = Math.max(4, (ev.duration_beats / 4) * BAR_WIDTH - 2)

      ctx.fillStyle = "#22d3ee" // cyan-400
      ctx.beginPath()
      ctx.roundRect(x, y, noteWidth, ROW_HEIGHT - 2, 2)
      ctx.fill()
    }
    ctx.globalAlpha = 1.0

    // Playback cursor
    if (playing) {
      const cursorX = LABEL_WIDTH + currentPosition * BAR_WIDTH
      ctx.strokeStyle = getAccent(genre)
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.moveTo(cursorX, 0)
      ctx.lineTo(cursorX, canvasHeight)
      ctx.stroke()
    }
  }, [arrangement, currentPosition, playing, mutedTracks, genre, voicingEvents, bassEvents])

  // Auto-scroll to keep cursor in view
  useEffect(() => {
    if (!playing || !containerRef.current) return
    const container = containerRef.current
    const cursorX = LABEL_WIDTH + currentPosition * BAR_WIDTH
    const scrollLeft = container.scrollLeft
    const viewWidth = container.clientWidth

    if (cursorX > scrollLeft + viewWidth - 80) {
      container.scrollLeft = cursorX - viewWidth / 2
    } else if (cursorX < scrollLeft + 80) {
      container.scrollLeft = cursorX - viewWidth / 2
    }
  }, [currentPosition, playing])

  if (!hasEvents) {
    return (
      <div className="flex items-center justify-center h-48 bg-slate-900 text-slate-500 text-sm">
        No events to display
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className="overflow-x-auto overflow-y-auto bg-slate-900"
      style={{ maxHeight: "400px" }}
    >
      <canvas ref={canvasRef} />
    </div>
  )
}
