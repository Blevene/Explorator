import { useEffect, useRef } from "react"
import type { ArrangementDetail } from "../services/api"
import { pitchToMidi, midiToPitchLabel } from "../services/midiUtils"
import { useAudioStore } from "../stores/audioStore"
import { CANVAS_COLORS } from "../utils/designTokens"

interface PianoRollProps {
  arrangement: ArrangementDetail
  genre: string
  compact?: boolean
  showCursor?: boolean
  barWidth?: number
  dimmed?: boolean
  currentPosition?: number
  playing?: boolean
  totalBars?: number
}

const DEFAULT_BAR_WIDTH = 90 // Fit 8-bar progressions in ~720px + labels
const DEFAULT_ROW_HEIGHT = 8
const COMPACT_ROW_HEIGHT = 6
const LABEL_WIDTH = 48
const HEADER_HEIGHT = 24

function getAccent(genre: string): string {
  const key = genre.toLowerCase().replace(/[\s-]/g, "_")
  return CANVAS_COLORS.genreAccent[key] ?? CANVAS_COLORS.voicingNote
}

function collectMidiValues(arrangement: ArrangementDetail): number[] {
  const midis: number[] = []
  arrangement.voicing_plan?.voicing_events.forEach((ev) => {
    ev.pitches.forEach((p) => midis.push(pitchToMidi(p)))
  })
  arrangement.bass_line?.note_events.forEach((ev) => {
    midis.push(pitchToMidi(ev.pitch))
  })
  arrangement.melodic_complement?.note_events.forEach((ev) => {
    midis.push(pitchToMidi(ev.pitch))
  })
  return midis
}

export default function PianoRoll({
  arrangement,
  genre,
  compact = false,
  showCursor = true,
  barWidth: barWidthProp,
  dimmed = false,
  currentPosition: currentPositionProp,
  playing: playingProp,
  totalBars: totalBarsProp,
}: PianoRollProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Always call useAudioStore (Rules of Hooks); ignore cursor values when showCursor=false
  const audioStoreState = useAudioStore()
  const playing = playingProp ?? audioStoreState.playing
  const currentPosition = currentPositionProp ?? audioStoreState.currentPosition
  const { mutedTracks } = audioStoreState

  const BAR_WIDTH = barWidthProp ?? DEFAULT_BAR_WIDTH
  const ROW_HEIGHT = compact ? COMPACT_ROW_HEIGHT : DEFAULT_ROW_HEIGHT

  const voicingEvents = arrangement.voicing_plan?.voicing_events ?? []
  const bassEvents = arrangement.bass_line?.note_events ?? []
  const melodyEvents = arrangement.melodic_complement?.note_events ?? []
  const hasEvents = voicingEvents.length > 0 || bassEvents.length > 0 || melodyEvents.length > 0

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1

    // Calculate MIDI range
    const midiValues = collectMidiValues(arrangement)
    const octavePad = compact ? 6 : 12
    const minMidi = midiValues.length > 0 ? Math.min(...midiValues) - octavePad : 48
    const maxMidi = midiValues.length > 0 ? Math.max(...midiValues) + octavePad : 84

    // Calculate total bars
    const allBars = [
      ...voicingEvents.map((e) => e.bar + Math.ceil(e.duration_beats / 4)),
      ...bassEvents.map((e) => e.bar + Math.ceil(e.duration_beats / 4)),
      ...melodyEvents.map((e) => e.bar + Math.ceil(e.duration_beats / 4)),
    ]
    const computedBars = allBars.length > 0 ? Math.max(...allBars) : 8
    const totalBars = totalBarsProp ?? computedBars

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
    ctx.fillStyle = CANVAS_COLORS.background
    ctx.fillRect(0, 0, canvasWidth, canvasHeight)

    // Draw horizontal pitch rows (alternating subtle bg for black keys)
    for (let midi = minMidi; midi <= maxMidi; midi++) {
      const noteInOctave = midi % 12
      const isBlackKey = [1, 3, 6, 8, 10].includes(noteInOctave)
      const y = HEADER_HEIGHT + (maxMidi - midi) * ROW_HEIGHT

      if (isBlackKey) {
        ctx.fillStyle = CANVAS_COLORS.gridLine
        ctx.fillRect(LABEL_WIDTH, y, totalBars * BAR_WIDTH, ROW_HEIGHT)
      }
    }

    // Draw beat and bar grid lines
    for (let bar = 0; bar <= totalBars; bar++) {
      for (let beat = 0; beat < 4; beat++) {
        const x = LABEL_WIDTH + bar * BAR_WIDTH + beat * (BAR_WIDTH / 4)
        if (beat === 0) {
          // Bar line
          ctx.strokeStyle = CANVAS_COLORS.barLine
          ctx.lineWidth = 1
        } else {
          // Beat line
          ctx.strokeStyle = CANVAS_COLORS.gridLine
          ctx.lineWidth = 0.5
        }
        ctx.beginPath()
        ctx.moveTo(x, HEADER_HEIGHT)
        ctx.lineTo(x, canvasHeight)
        ctx.stroke()
      }
    }

    // Header background
    ctx.fillStyle = CANVAS_COLORS.headerBg
    ctx.fillRect(0, 0, canvasWidth, HEADER_HEIGHT)

    // Bar numbers in header
    ctx.fillStyle = CANVAS_COLORS.headerText
    ctx.font = compact ? "8px monospace" : "10px monospace"
    ctx.textAlign = "center"
    for (let bar = 1; bar <= totalBars; bar++) {
      const x = LABEL_WIDTH + (bar - 1) * BAR_WIDTH + BAR_WIDTH / 2
      ctx.fillText(`${bar}`, x, HEADER_HEIGHT - 6)
    }

    // Pitch labels on left edge — C octave markers
    ctx.textAlign = "right"
    ctx.font = compact ? "7px monospace" : "9px monospace"
    for (let midi = minMidi; midi <= maxMidi; midi++) {
      // In compact mode, label every octave (C); in full mode, same
      if (midi % 12 === 0) {
        const label = midiToPitchLabel(midi)
        const y = HEADER_HEIGHT + (maxMidi - midi) * ROW_HEIGHT + ROW_HEIGHT - 1
        ctx.fillStyle = CANVAS_COLORS.labelText
        ctx.fillText(label, LABEL_WIDTH - 4, y)
      }
    }

    // Draw voicing notes — amber-400
    const voicingOpacity = mutedTracks.voicing ? 0.2 : 1.0
    ctx.globalAlpha = voicingOpacity
    for (const ev of voicingEvents) {
      const x = LABEL_WIDTH + (ev.bar + (ev.beat - 1) / 4) * BAR_WIDTH
      const noteWidth = Math.max(compact ? 2 : 4, (ev.duration_beats / 4) * BAR_WIDTH - 2)

      for (const pitch of ev.pitches) {
        const midi = pitchToMidi(pitch)
        if (midi < minMidi || midi > maxMidi) continue
        const y = HEADER_HEIGHT + (maxMidi - midi) * ROW_HEIGHT + 1

        ctx.fillStyle = CANVAS_COLORS.voicingNote
        ctx.beginPath()
        ctx.roundRect(x, y, noteWidth, ROW_HEIGHT - 2, compact ? 1 : 2)
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
      const x = LABEL_WIDTH + (ev.bar + (ev.beat - 1) / 4) * BAR_WIDTH
      const y = HEADER_HEIGHT + (maxMidi - midi) * ROW_HEIGHT + 1
      const noteWidth = Math.max(compact ? 2 : 4, (ev.duration_beats / 4) * BAR_WIDTH - 2)

      ctx.fillStyle = CANVAS_COLORS.bassNote
      ctx.beginPath()
      ctx.roundRect(x, y, noteWidth, ROW_HEIGHT - 2, compact ? 1 : 2)
      ctx.fill()
    }
    ctx.globalAlpha = 1.0

    // Draw melody notes — emerald green
    const melodyOpacity = mutedTracks.melody ? 0.2 : 1.0
    ctx.globalAlpha = melodyOpacity
    for (const ev of melodyEvents) {
      const midi = pitchToMidi(ev.pitch)
      if (midi < minMidi || midi > maxMidi) continue
      const x = LABEL_WIDTH + (ev.bar + (ev.beat - 1) / 4) * BAR_WIDTH
      const y = HEADER_HEIGHT + (maxMidi - midi) * ROW_HEIGHT + 1
      const noteWidth = Math.max(compact ? 2 : 4, (ev.duration_beats / 4) * BAR_WIDTH - 2)

      ctx.fillStyle = CANVAS_COLORS.melodyNote
      ctx.beginPath()
      ctx.roundRect(x, y, noteWidth, ROW_HEIGHT - 2, compact ? 1 : 2)
      ctx.fill()
    }
    ctx.globalAlpha = 1.0

    // Groove accent overlay
    const grooveEvents = arrangement?.groove_pattern?.pattern_events ?? []
    const beatsPerBar = 4
    for (const ev of grooveEvents) {
      if (!ev.accent) continue
      // Draw accent marker as dashed vertical line at the beat position, repeated for each bar
      for (let bar = 0; bar < totalBars; bar++) {
        const x = LABEL_WIDTH + (bar + (ev.beat - 1) / beatsPerBar) * BAR_WIDTH
        ctx.strokeStyle = 'rgba(250, 204, 21, 0.25)' // yellow-400 at 25% opacity
        ctx.lineWidth = 1
        ctx.setLineDash([4, 4])
        ctx.beginPath()
        ctx.moveTo(x, 0)
        ctx.lineTo(x, canvasHeight)
        ctx.stroke()
        ctx.setLineDash([])
      }
    }

    // Playback cursor
    if (showCursor && playing) {
      const cursorX = LABEL_WIDTH + currentPosition * BAR_WIDTH
      ctx.strokeStyle = getAccent(genre)
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.moveTo(cursorX, 0)
      ctx.lineTo(cursorX, canvasHeight)
      ctx.stroke()
    }
  }, [arrangement, currentPosition, playing, mutedTracks, genre, voicingEvents, bassEvents, melodyEvents, BAR_WIDTH, ROW_HEIGHT, compact, showCursor, totalBarsProp])

  // Auto-scroll to keep cursor in view
  useEffect(() => {
    if (!showCursor || !playing || !containerRef.current) return
    const container = containerRef.current
    const cursorX = LABEL_WIDTH + currentPosition * BAR_WIDTH
    const scrollLeft = container.scrollLeft
    const viewWidth = container.clientWidth

    if (cursorX > scrollLeft + viewWidth - 80) {
      container.scrollLeft = cursorX - viewWidth / 2
    } else if (cursorX < scrollLeft + 80) {
      container.scrollLeft = cursorX - viewWidth / 2
    }
  }, [currentPosition, playing, showCursor, BAR_WIDTH])

  if (!hasEvents) {
    return (
      <div
        className={`flex items-center justify-center ${compact ? "h-24" : "h-48"} text-sm`}
        style={{ background: 'var(--surface-1)', color: 'var(--text-muted)' }}
      >
        No events to display
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className="overflow-x-auto overflow-y-auto"
      style={{
        background: 'var(--surface-1)',
        maxHeight: compact ? "220px" : "400px",
        opacity: dimmed ? 0.2 : 1,
        transition: "opacity 150ms ease",
      }}
    >
      <canvas ref={canvasRef} />
    </div>
  )
}
