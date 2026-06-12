# M2c Playback & Visualization Implementation Plan


**Goal:** Add a split-panel arrangement view with canvas piano roll, Tone.js playback with genre presets, and full transport controls so users can see and hear their realized arrangements.

**Architecture:** Frontend-only changes. No new backend endpoints. New components (ArrangementList, ArrangementCard, ArrangementDetail, PianoRoll, TransportBar, ScorePanel) plus two Zustand stores (arrangement, audio) and a Tone.js audio engine service. SessionWorkspace gains a view mode toggle between generation and realization views.

**Tech Stack:** React 19, TypeScript, Tailwind CSS v4, Zustand, Tone.js, HTML Canvas API

**Spec:** `docs/design/specs/2026-04-08-m2c-playback-visualization-design.md`
**Design Language:** `docs/DESIGN.md`

---

## File Structure

### New Files

```
frontend/src/
  components/
    ArrangementList.tsx         # Left panel — grouped arrangement cards
    ArrangementCard.tsx         # Compact arrangement summary card
    ArrangementDetail.tsx       # Right panel — transport + piano roll + scores
    PianoRoll.tsx               # Canvas-based pitch grid visualization
    TransportBar.tsx            # Playback controls
    ScorePanel.tsx              # 9-dimension bar chart, collapsible
  stores/
    arrangementStore.ts         # Arrangements, families, selected ID
    audioStore.ts               # Playback state (playing, tempo, muted, etc.)
  services/
    audioEngine.ts              # Tone.js wrapper, genre presets, scheduling
    midiUtils.ts                # Named pitch → MIDI conversion
```

### Modified Files

```
frontend/
  package.json                  # Add tone dependency
  src/services/api.ts           # Add arrangement types + fetch wrappers
  src/components/CandidateCard.tsx  # Add "Realize" button
  src/views/SessionWorkspace.tsx    # View mode toggle, realization flow
```

---

## Task 1: Install Tone.js + MIDI Utilities

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/services/midiUtils.ts`

- [ ] **Step 1: Install Tone.js**

```bash
cd frontend && npm install tone
```

- [ ] **Step 2: Create midiUtils.ts**

```typescript
// frontend/src/services/midiUtils.ts

/**
 * Convert a named pitch (e.g., "C4", "B-4", "F#3") to MIDI number.
 * Handles music21's flat notation: "B-4" → Bb4 → MIDI 70.
 */

const NOTE_TO_SEMITONE: Record<string, number> = {
  C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11,
}

export function pitchToMidi(pitch: string): number {
  // Normalize music21 flat notation: "B-4" → "Bb4"
  const normalized = pitch.replace("-", "b")

  // Parse: note name, accidental, octave
  const match = normalized.match(/^([A-G])(#|b)?(\d)$/)
  if (!match) return 60 // fallback to middle C

  const [, note, accidental, octaveStr] = match
  const base = NOTE_TO_SEMITONE[note]
  const octave = parseInt(octaveStr, 10)
  let midi = (octave + 1) * 12 + base

  if (accidental === "#") midi += 1
  if (accidental === "b") midi -= 1

  return midi
}

export function midiToPitchLabel(midi: number): string {
  const NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
  const octave = Math.floor(midi / 12) - 1
  const note = NOTES[midi % 12]
  return `${note}${octave}`
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit src/services/midiUtils.ts 2>&1 || true
```

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/services/midiUtils.ts
git commit -m "feat(m2c): install Tone.js and add MIDI utilities"
```

---

## Task 2: API Types + Fetch Wrappers

**Files:**
- Modify: `frontend/src/services/api.ts`

- [ ] **Step 1: Add arrangement types and fetch functions**

Add to the end of `frontend/src/services/api.ts`:

```typescript
// --- M2c Arrangement Types ---

export interface VoicingEvent {
  bar: number
  beat: number
  duration_beats: number
  pitches: string[]
  chord_symbol: string
}

export interface BassNoteEvent {
  bar: number
  beat: number
  duration_beats: number
  pitch: string
  velocity: number
}

export interface ArrangementSummary {
  id: string
  status: "draft" | "selected" | "rejected"
  progression_candidate_id: string
  voicing_plan_id: string
  bass_line_id: string
  weighted_total: number
  rank_within_round: number
  rationale: string
}

export interface ArrangementDetail extends ArrangementSummary {
  voicing_plan: {
    global_strategy: string
    density_level: string
    register_profile: string
    voicing_events: VoicingEvent[]
  } | null
  bass_line: {
    style_mode: string
    note_events: BassNoteEvent[]
  } | null
  scorecard?: {
    scores: Record<string, number>
    weighted_total: number
    rank_within_round: number
  }
}

// --- M2c API Functions ---

const API_BASE = "http://localhost:8000/v1"

export async function listArrangements(candidateId: string): Promise<ArrangementSummary[]> {
  const res = await fetch(`${API_BASE}/candidates/${candidateId}/arrangements`)
  if (!res.ok) throw new Error(`Failed to list arrangements: ${res.status}`)
  return res.json()
}

export async function getArrangement(arrangementId: string): Promise<ArrangementDetail> {
  const res = await fetch(`${API_BASE}/arrangements/${arrangementId}`)
  if (!res.ok) throw new Error(`Failed to get arrangement: ${res.status}`)
  return res.json()
}

export async function triggerRealizationSSE(
  sessionId: string,
  progressionCandidateIds: string[],
): Promise<Response> {
  return fetch(`${API_BASE}/sessions/${sessionId}/realization-rounds`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ progression_candidate_ids: progressionCandidateIds }),
  })
}
```

Note: Check the existing `api.ts` for the actual `API_BASE` pattern — it may use a different base URL or env variable. Match whatever exists.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat(m2c): add arrangement API types and fetch wrappers"
```

---

## Task 3: Zustand Stores

**Files:**
- Create: `frontend/src/stores/arrangementStore.ts`
- Create: `frontend/src/stores/audioStore.ts`

- [ ] **Step 1: Create arrangementStore**

```typescript
// frontend/src/stores/arrangementStore.ts

import { create } from "zustand"
import type { ArrangementDetail, ArrangementSummary } from "../services/api"

interface ArrangementState {
  arrangements: ArrangementSummary[]
  selectedArrangementId: string | null
  selectedDetail: ArrangementDetail | null
  loading: boolean
  error: string | null

  setArrangements: (arrangements: ArrangementSummary[]) => void
  setSelectedArrangementId: (id: string | null) => void
  setSelectedDetail: (detail: ArrangementDetail | null) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  reset: () => void
}

export const useArrangementStore = create<ArrangementState>((set) => ({
  arrangements: [],
  selectedArrangementId: null,
  selectedDetail: null,
  loading: false,
  error: null,

  setArrangements: (arrangements) => set({ arrangements }),
  setSelectedArrangementId: (id) => set({ selectedArrangementId: id }),
  setSelectedDetail: (detail) => set({ selectedDetail: detail }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  reset: () =>
    set({
      arrangements: [],
      selectedArrangementId: null,
      selectedDetail: null,
      loading: false,
      error: null,
    }),
}))
```

- [ ] **Step 2: Create audioStore**

```typescript
// frontend/src/stores/audioStore.ts

import { create } from "zustand"

interface AudioState {
  playing: boolean
  paused: boolean
  tempo: number
  loop: boolean
  mutedTracks: { voicing: boolean; bass: boolean }
  volume: number // dB, range -60 to 0
  currentPosition: number // 0-based float: 0.0 = bar 1 start, 1.5 = bar 2 beat 3

  setPlaying: (playing: boolean) => void
  setPaused: (paused: boolean) => void
  setTempo: (tempo: number) => void
  setLoop: (loop: boolean) => void
  toggleMute: (track: "voicing" | "bass") => void
  setVolume: (volume: number) => void
  setCurrentPosition: (position: number) => void
  reset: () => void
}

export const useAudioStore = create<AudioState>((set) => ({
  playing: false,
  paused: false,
  tempo: 120,
  loop: true,
  mutedTracks: { voicing: false, bass: false },
  volume: -6,
  currentPosition: 0,

  setPlaying: (playing) => set({ playing }),
  setPaused: (paused) => set({ paused }),
  setTempo: (tempo) => set({ tempo }),
  setLoop: (loop) => set({ loop }),
  toggleMute: (track) =>
    set((state) => ({
      mutedTracks: {
        ...state.mutedTracks,
        [track]: !state.mutedTracks[track],
      },
    })),
  setVolume: (volume) => set({ volume }),
  setCurrentPosition: (position) => set({ currentPosition: position }),
  reset: () =>
    set({
      playing: false,
      paused: false,
      tempo: 120,
      loop: true,
      mutedTracks: { voicing: false, bass: false },
      volume: -6,
      currentPosition: 0,
    }),
}))
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/stores/arrangementStore.ts frontend/src/stores/audioStore.ts
git commit -m "feat(m2c): add arrangement and audio Zustand stores"
```

---

## Task 4: Audio Engine

**Files:**
- Create: `frontend/src/services/audioEngine.ts`

- [ ] **Step 1: Create audioEngine.ts**

```typescript
// frontend/src/services/audioEngine.ts

/**
 * Tone.js wrapper for arrangement playback.
 * React components interact via audioStore, never import Tone directly.
 */

import type { ArrangementDetail } from "./api"
import { useAudioStore } from "../stores/audioStore"

// Lazy-loaded Tone.js (reduces initial bundle)
let Tone: typeof import("tone") | null = null
let polySynth: any = null
let monoSynth: any = null
let voicingVolume: any = null
let bassVolume: any = null
let animFrameId: number | null = null
let initialized = false

// Genre synth presets (merged into defaults)
const GENRE_PRESETS: Record<string, { voicing: any; bass: any }> = {
  dream_pop: {
    voicing: { envelope: { attack: 0.3, release: 1.5 }, volume: -12 },
    bass: { oscillator: { type: "sine" }, envelope: { attack: 0.1, release: 1.0 } },
  },
  synthwave: {
    voicing: { oscillator: { type: "sawtooth" }, envelope: { attack: 0.01, release: 0.4 }, volume: -8 },
    bass: { oscillator: { type: "square" }, envelope: { attack: 0.005, release: 0.3 } },
  },
  cinematic: {
    voicing: { oscillator: { type: "triangle" }, envelope: { attack: 0.15, release: 2.0 }, volume: -10 },
    bass: { oscillator: { type: "sine" }, envelope: { attack: 0.2, release: 2.0 } },
  },
}

async function ensureInit(): Promise<typeof import("tone")> {
  if (!Tone) {
    Tone = await import("tone")
  }
  if (!initialized) {
    await Tone.start()

    voicingVolume = new Tone.Volume(-6).toDestination()
    bassVolume = new Tone.Volume(-6).toDestination()

    polySynth = new Tone.PolySynth(Tone.Synth).connect(voicingVolume)
    monoSynth = new Tone.MonoSynth().connect(bassVolume)

    initialized = true
  }
  return Tone
}

function applyGenrePreset(genre: string): void {
  const preset = GENRE_PRESETS[genre]
  if (!preset || !polySynth || !monoSynth) return

  // Deep merge: preset overrides defaults
  if (preset.voicing) {
    polySynth.set(preset.voicing)
  }
  if (preset.bass) {
    monoSynth.set(preset.bass)
  }
}

function startPositionTracking(totalBars: number): void {
  const store = useAudioStore.getState()
  const update = () => {
    if (!Tone) return
    const seconds = Tone.getTransport().seconds
    const beatsPerSecond = store.tempo / 60
    const totalBeats = seconds * beatsPerSecond
    const barPosition = totalBeats / 4 // 4 beats per bar
    useAudioStore.getState().setCurrentPosition(barPosition)
    animFrameId = requestAnimationFrame(update)
  }
  animFrameId = requestAnimationFrame(update)
}

function stopPositionTracking(): void {
  if (animFrameId !== null) {
    cancelAnimationFrame(animFrameId)
    animFrameId = null
  }
}

export async function play(
  arrangement: ArrangementDetail,
  tempo: number,
  genre: string,
): Promise<void> {
  const T = await ensureInit()
  const transport = T.getTransport()

  // Clear previous schedule
  transport.cancel()
  transport.stop()
  transport.position = 0

  // Apply genre preset
  applyGenrePreset(genre)

  // Set tempo and loop
  transport.bpm.value = tempo
  const store = useAudioStore.getState()
  transport.loop = store.loop

  // Calculate total bars
  const voicingEvents = arrangement.voicing_plan?.voicing_events ?? []
  const bassEvents = arrangement.bass_line?.note_events ?? []
  const maxBar = Math.max(
    ...voicingEvents.map((e) => e.bar),
    ...bassEvents.map((e) => e.bar),
    1,
  )
  transport.loopEnd = `${maxBar}:0:0`

  // Schedule voicing events
  const { mutedTracks } = store
  for (const event of voicingEvents) {
    if (event.duration_beats <= 0) continue
    const time = `${event.bar - 1}:${event.beat - 1}:0`
    const duration = `0:${event.duration_beats}:0`
    transport.schedule((t) => {
      if (!useAudioStore.getState().mutedTracks.voicing) {
        polySynth.triggerAttackRelease(event.pitches, duration, t)
      }
    }, time)
  }

  // Schedule bass events
  for (const event of bassEvents) {
    if (event.duration_beats <= 0) continue
    const time = `${event.bar - 1}:${event.beat - 1}:0`
    const duration = `0:${event.duration_beats}:0`
    transport.schedule((t) => {
      if (!useAudioStore.getState().mutedTracks.bass) {
        monoSynth.triggerAttackRelease(event.pitch, duration, t)
      }
    }, time)
  }

  // Start
  transport.start()
  useAudioStore.getState().setPlaying(true)
  useAudioStore.getState().setPaused(false)
  startPositionTracking(maxBar)
}

export function pause(): void {
  if (!Tone) return
  Tone.getTransport().pause()
  useAudioStore.getState().setPlaying(false)
  useAudioStore.getState().setPaused(true)
  stopPositionTracking()
}

export function resume(): void {
  if (!Tone) return
  Tone.getTransport().start()
  useAudioStore.getState().setPlaying(true)
  useAudioStore.getState().setPaused(false)
  startPositionTracking(0)
}

export function stop(): void {
  if (!Tone) return
  const transport = Tone.getTransport()
  transport.stop()
  transport.position = 0
  useAudioStore.getState().setPlaying(false)
  useAudioStore.getState().setPaused(false)
  useAudioStore.getState().setCurrentPosition(0)
  stopPositionTracking()
}

export function setTempo(bpm: number): void {
  if (!Tone) return
  Tone.getTransport().bpm.value = bpm
  useAudioStore.getState().setTempo(bpm)
}

export function setLoop(loop: boolean): void {
  if (!Tone) return
  Tone.getTransport().loop = loop
  useAudioStore.getState().setLoop(loop)
}

export function setVoicingMute(muted: boolean): void {
  if (!voicingVolume) return
  voicingVolume.volume.value = muted ? -Infinity : -6
}

export function setBassMute(muted: boolean): void {
  if (!bassVolume) return
  bassVolume.volume.value = muted ? -Infinity : -6
}

export function setVolume(db: number): void {
  if (!voicingVolume || !bassVolume) return
  const { mutedTracks } = useAudioStore.getState()
  if (!mutedTracks.voicing) voicingVolume.volume.value = db
  if (!mutedTracks.bass) bassVolume.volume.value = db
  useAudioStore.getState().setVolume(db)
}

export function dispose(): void {
  stop()
  polySynth?.dispose()
  monoSynth?.dispose()
  voicingVolume?.dispose()
  bassVolume?.dispose()
  polySynth = null
  monoSynth = null
  voicingVolume = null
  bassVolume = null
  initialized = false
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/services/audioEngine.ts
git commit -m "feat(m2c): add Tone.js audio engine with genre presets"
```

---

## Task 5: PianoRoll Component

**Files:**
- Create: `frontend/src/components/PianoRoll.tsx`

- [ ] **Step 1: Create PianoRoll.tsx**

This is the hero component — a canvas-based pitch grid.

```typescript
// frontend/src/components/PianoRoll.tsx

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
const PADDING_OCTAVES = 1

// Colors from DESIGN.md
const COLORS = {
  background: "#020617",    // slate-950
  gridBeat: "#1e293b",      // slate-800
  gridBar: "#334155",       // slate-700
  voicing: "#fbbf24",       // amber-400
  bass: "#22d3ee",          // cyan-400
  voicingMuted: "rgba(251, 191, 36, 0.2)",
  bassMuted: "rgba(34, 211, 238, 0.2)",
  label: "#94a3b8",         // slate-400
  cursor: {
    dream_pop: "#a78bfa",   // violet-400
    synthwave: "#f472b6",   // pink-400
    cinematic: "#eab308",   // yellow-500
  } as Record<string, string>,
}

export default function PianoRoll({ arrangement, genre }: PianoRollProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const { currentPosition, playing, mutedTracks } = useAudioStore()

  // Compute MIDI range from events
  const voicingEvents = arrangement.voicing_plan?.voicing_events ?? []
  const bassEvents = arrangement.bass_line?.note_events ?? []

  const allMidi: number[] = []
  for (const e of voicingEvents) {
    for (const p of e.pitches) allMidi.push(pitchToMidi(p))
  }
  for (const e of bassEvents) {
    allMidi.push(pitchToMidi(e.pitch))
  }

  if (allMidi.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500">
        No events to display
      </div>
    )
  }

  const minMidi = Math.min(...allMidi) - PADDING_OCTAVES * 12
  const maxMidi = Math.max(...allMidi) + PADDING_OCTAVES * 12
  const totalBars = Math.max(...voicingEvents.map((e) => e.bar), ...bassEvents.map((e) => e.bar), 1)

  const gridWidth = totalBars * BAR_WIDTH
  const gridHeight = (maxMidi - minMidi + 1) * ROW_HEIGHT

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const dpr = window.devicePixelRatio || 1
    const totalWidth = LABEL_WIDTH + gridWidth
    const totalHeight = HEADER_HEIGHT + gridHeight

    canvas.width = totalWidth * dpr
    canvas.height = totalHeight * dpr
    canvas.style.width = `${totalWidth}px`
    canvas.style.height = `${totalHeight}px`

    const ctx = canvas.getContext("2d")
    if (!ctx) return
    ctx.scale(dpr, dpr)

    // Clear
    ctx.fillStyle = COLORS.background
    ctx.fillRect(0, 0, totalWidth, totalHeight)

    // Draw grid
    ctx.strokeStyle = COLORS.gridBeat
    ctx.lineWidth = 0.5
    for (let beat = 0; beat <= totalBars * 4; beat++) {
      const x = LABEL_WIDTH + (beat / 4) * BAR_WIDTH
      ctx.strokeStyle = beat % 4 === 0 ? COLORS.gridBar : COLORS.gridBeat
      ctx.lineWidth = beat % 4 === 0 ? 1 : 0.5
      ctx.beginPath()
      ctx.moveTo(x, HEADER_HEIGHT)
      ctx.lineTo(x, totalHeight)
      ctx.stroke()
    }

    // Bar numbers
    ctx.fillStyle = COLORS.label
    ctx.font = "11px 'JetBrains Mono', monospace"
    for (let bar = 1; bar <= totalBars; bar++) {
      const x = LABEL_WIDTH + (bar - 1) * BAR_WIDTH + 4
      ctx.fillText(`${bar}`, x, HEADER_HEIGHT - 6)
    }

    // Pitch labels (C octave markers)
    for (let midi = minMidi; midi <= maxMidi; midi++) {
      if (midi % 12 === 0) {
        const y = HEADER_HEIGHT + (maxMidi - midi) * ROW_HEIGHT
        ctx.fillStyle = COLORS.label
        ctx.font = "10px 'JetBrains Mono', monospace"
        ctx.fillText(midiToPitchLabel(midi), 4, y + ROW_HEIGHT * 0.7)
        // Subtle horizontal guide line
        ctx.strokeStyle = COLORS.gridBeat
        ctx.lineWidth = 0.5
        ctx.beginPath()
        ctx.moveTo(LABEL_WIDTH, y)
        ctx.lineTo(totalWidth, y)
        ctx.stroke()
      }
    }

    // Draw notes helper
    const drawNote = (midi: number, bar: number, beat: number, duration: number, color: string) => {
      const x = LABEL_WIDTH + ((bar - 1) + (beat - 1) / 4) * BAR_WIDTH
      const y = HEADER_HEIGHT + (maxMidi - midi) * ROW_HEIGHT
      const w = (duration / 4) * BAR_WIDTH
      const h = ROW_HEIGHT - 1

      ctx.fillStyle = color
      ctx.beginPath()
      ctx.roundRect(x, y, Math.max(w, 4), h, 2)
      ctx.fill()
    }

    // Draw voicing notes
    const voicingColor = mutedTracks.voicing ? COLORS.voicingMuted : COLORS.voicing
    for (const event of voicingEvents) {
      for (const pitch of event.pitches) {
        drawNote(pitchToMidi(pitch), event.bar, event.beat, event.duration_beats, voicingColor)
      }
    }

    // Draw bass notes
    const bassColor = mutedTracks.bass ? COLORS.bassMuted : COLORS.bass
    for (const event of bassEvents) {
      drawNote(pitchToMidi(event.pitch), event.bar, event.beat, event.duration_beats, bassColor)
    }

    // Playback cursor
    if (playing && currentPosition >= 0) {
      const cursorX = LABEL_WIDTH + currentPosition * BAR_WIDTH
      const cursorColor = COLORS.cursor[genre] || "#a78bfa"
      ctx.strokeStyle = cursorColor
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.moveTo(cursorX, HEADER_HEIGHT)
      ctx.lineTo(cursorX, totalHeight)
      ctx.stroke()
    }
  }, [arrangement, currentPosition, playing, mutedTracks, genre])

  // Auto-scroll to keep cursor visible
  useEffect(() => {
    if (!playing || !containerRef.current) return
    const cursorX = LABEL_WIDTH + currentPosition * BAR_WIDTH
    const container = containerRef.current
    const viewLeft = container.scrollLeft
    const viewRight = viewLeft + container.clientWidth
    const margin = container.clientWidth * 0.3

    if (cursorX < viewLeft + margin || cursorX > viewRight - margin) {
      container.scrollLeft = cursorX - container.clientWidth * 0.3
    }
  }, [currentPosition, playing])

  return (
    <div ref={containerRef} className="overflow-x-auto overflow-y-auto flex-1 bg-slate-950">
      <canvas ref={canvasRef} />
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/PianoRoll.tsx
git commit -m "feat(m2c): add canvas-based PianoRoll component"
```

---

## Task 6: TransportBar Component

**Files:**
- Create: `frontend/src/components/TransportBar.tsx`

- [ ] **Step 1: Create TransportBar.tsx**

```typescript
// frontend/src/components/TransportBar.tsx

import { useAudioStore } from "../stores/audioStore"
import * as audioEngine from "../services/audioEngine"
import type { ArrangementDetail } from "../services/api"

interface TransportBarProps {
  arrangement: ArrangementDetail | null
  genre: string
}

export default function TransportBar({ arrangement, genre }: TransportBarProps) {
  const { playing, paused, tempo, loop, mutedTracks, volume } = useAudioStore()

  const handlePlayPause = async () => {
    if (!arrangement) return
    if (playing) {
      audioEngine.pause()
    } else if (paused) {
      audioEngine.resume()
    } else {
      await audioEngine.play(arrangement, tempo, genre)
    }
  }

  const handleStop = () => {
    audioEngine.stop()
  }

  const handleTempoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    audioEngine.setTempo(Number(e.target.value))
  }

  const handleLoopToggle = () => {
    audioEngine.setLoop(!loop)
  }

  const handleVoicingMute = () => {
    const newMuted = !mutedTracks.voicing
    useAudioStore.getState().toggleMute("voicing")
    audioEngine.setVoicingMute(newMuted)
  }

  const handleBassMute = () => {
    const newMuted = !mutedTracks.bass
    useAudioStore.getState().toggleMute("bass")
    audioEngine.setBassMute(newMuted)
  }

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    audioEngine.setVolume(Number(e.target.value))
  }

  const genreAccent: Record<string, string> = {
    dream_pop: "text-violet-400",
    synthwave: "text-pink-400",
    cinematic: "text-yellow-500",
  }
  const accent = genreAccent[genre] || "text-violet-400"

  return (
    <div className="flex items-center gap-3 px-4 h-12 bg-slate-900 border-b border-slate-700 shrink-0">
      {/* Play/Pause */}
      <button
        onClick={handlePlayPause}
        disabled={!arrangement}
        className="text-slate-500 hover:text-slate-200 disabled:opacity-30 transition-colors"
        title={playing ? "Pause" : "Play"}
      >
        {playing ? (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <rect x="5" y="4" width="3" height="12" rx="1" />
            <rect x="12" y="4" width="3" height="12" rx="1" />
          </svg>
        ) : (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <polygon points="5,3 17,10 5,17" />
          </svg>
        )}
      </button>

      {/* Stop */}
      <button
        onClick={handleStop}
        className="text-slate-500 hover:text-slate-200 transition-colors"
        title="Stop"
      >
        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
          <rect x="3" y="3" width="10" height="10" rx="1" />
        </svg>
      </button>

      {/* Separator */}
      <div className="w-px h-6 bg-slate-700" />

      {/* Tempo */}
      <div className="flex items-center gap-2">
        <input
          type="range"
          min="60"
          max="200"
          value={tempo}
          onChange={handleTempoChange}
          className="w-20 accent-slate-400"
          title="Tempo"
        />
        <span className="text-xs text-slate-400 font-mono w-12">{tempo} BPM</span>
      </div>

      {/* Separator */}
      <div className="w-px h-6 bg-slate-700" />

      {/* Loop */}
      <button
        onClick={handleLoopToggle}
        className={`text-sm transition-colors ${loop ? accent : "text-slate-500 hover:text-slate-200"}`}
        title="Loop"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path d="M17 1l4 4-4 4" />
          <path d="M3 11V9a4 4 0 0 1 4-4h14" />
          <path d="M7 23l-4-4 4-4" />
          <path d="M21 13v2a4 4 0 0 1-4 4H3" />
        </svg>
      </button>

      {/* Separator */}
      <div className="w-px h-6 bg-slate-700" />

      {/* Mute Voicing */}
      <button
        onClick={handleVoicingMute}
        className={`text-xs font-mono px-2 py-1 rounded transition-colors ${
          mutedTracks.voicing ? "text-slate-600 bg-slate-800" : "text-amber-400 bg-amber-400/10"
        }`}
        title="Mute Voicing"
      >
        V
      </button>

      {/* Mute Bass */}
      <button
        onClick={handleBassMute}
        className={`text-xs font-mono px-2 py-1 rounded transition-colors ${
          mutedTracks.bass ? "text-slate-600 bg-slate-800" : "text-cyan-400 bg-cyan-400/10"
        }`}
        title="Mute Bass"
      >
        B
      </button>

      {/* Separator */}
      <div className="w-px h-6 bg-slate-700" />

      {/* Volume */}
      <input
        type="range"
        min="-60"
        max="0"
        value={volume}
        onChange={handleVolumeChange}
        className="w-16 accent-slate-400"
        title={`Volume: ${volume}dB`}
      />
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/TransportBar.tsx
git commit -m "feat(m2c): add TransportBar playback controls"
```

---

## Task 7: ScorePanel + ArrangementCard + ArrangementList

**Files:**
- Create: `frontend/src/components/ScorePanel.tsx`
- Create: `frontend/src/components/ArrangementCard.tsx`
- Create: `frontend/src/components/ArrangementList.tsx`

- [ ] **Step 1: Create ScorePanel.tsx**

```typescript
// frontend/src/components/ScorePanel.tsx

import { useState } from "react"

interface ScorePanelProps {
  scores: Record<string, number>
  weightedTotal: number
}

const ARRANGEMENT_DIMS = ["voice_leading", "register_density", "playability"]
const PROGRESSION_DIMS = ["genre_fit", "emotional_fit", "theoretical_coherence", "cadence_quality", "novelty", "loopability"]

function scoreColor(score: number): string {
  if (score >= 8) return "bg-emerald-400"
  if (score >= 6) return "bg-amber-400"
  return "bg-rose-400"
}

function formatLabel(dim: string): string {
  return dim.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

export default function ScorePanel({ scores, weightedTotal }: ScorePanelProps) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="bg-slate-900 border-t border-slate-700 shrink-0">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between px-4 py-2 text-xs text-slate-400 hover:text-slate-200 transition-colors"
      >
        <span>
          Scores — <span className="text-slate-100 font-mono">{weightedTotal.toFixed(1)}</span>
        </span>
        <span>{collapsed ? "+" : "-"}</span>
      </button>

      {!collapsed && (
        <div className="px-4 pb-3 space-y-3">
          {/* Arrangement scores */}
          <div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Arrangement</div>
            {ARRANGEMENT_DIMS.map((dim) => {
              const val = scores[dim] ?? 0
              return (
                <div key={dim} className="flex items-center gap-2 h-5">
                  <span className="text-[11px] text-slate-400 w-28 truncate">{formatLabel(dim)}</span>
                  <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${scoreColor(val)} transition-all duration-200`}
                      style={{ width: `${val * 10}%` }}
                    />
                  </div>
                  <span className="text-[11px] font-mono text-slate-300 w-6 text-right">{val.toFixed(1)}</span>
                </div>
              )
            })}
          </div>

          {/* Progression scores */}
          <div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Progression</div>
            {PROGRESSION_DIMS.map((dim) => {
              const val = scores[dim] ?? 0
              return (
                <div key={dim} className="flex items-center gap-2 h-5">
                  <span className="text-[11px] text-slate-400 w-28 truncate">{formatLabel(dim)}</span>
                  <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${scoreColor(val)} transition-all duration-200`}
                      style={{ width: `${val * 10}%` }}
                    />
                  </div>
                  <span className="text-[11px] font-mono text-slate-300 w-6 text-right">{val.toFixed(1)}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Create ArrangementCard.tsx**

```typescript
// frontend/src/components/ArrangementCard.tsx

import type { ArrangementSummary } from "../services/api"

interface ArrangementCardProps {
  arrangement: ArrangementSummary
  selected: boolean
  onClick: () => void
  genre: string
}

const genreBorder: Record<string, string> = {
  dream_pop: "border-l-violet-400",
  synthwave: "border-l-pink-400",
  cinematic: "border-l-yellow-500",
}

function scoreColor(score: number): string {
  if (score >= 8) return "text-emerald-400"
  if (score >= 6) return "text-amber-400"
  return "text-rose-400"
}

export default function ArrangementCard({ arrangement, selected, onClick, genre }: ArrangementCardProps) {
  const isRejected = arrangement.status === "rejected"
  const border = selected ? genreBorder[genre] || "border-l-violet-400" : "border-l-transparent"

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2 border-l-2 ${border} transition-all ${
        selected ? "bg-slate-800" : "bg-slate-900 hover:bg-slate-800/50"
      } ${isRejected ? "opacity-40" : ""}`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* Voicing type badge */}
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-400/10 text-amber-400 font-mono">
            {arrangement.rationale.split(" + ")[0]?.slice(0, 12) || "voicing"}
          </span>
          {/* Bass mode badge */}
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-400/10 text-cyan-400 font-mono">
            {arrangement.rationale.split(" + ")[1]?.replace(" bass", "") || "bass"}
          </span>
        </div>
        {/* Score */}
        <span className={`text-xs font-mono ${scoreColor(arrangement.weighted_total)}`}>
          {arrangement.weighted_total.toFixed(1)}
        </span>
      </div>
      {arrangement.status === "selected" && (
        <div className="text-[9px] text-emerald-400/60 mt-1">#{arrangement.rank_within_round}</div>
      )}
    </button>
  )
}
```

- [ ] **Step 3: Create ArrangementList.tsx**

```typescript
// frontend/src/components/ArrangementList.tsx

import type { ArrangementSummary, CandidateSummary } from "../services/api"
import ArrangementCard from "./ArrangementCard"

interface ArrangementListProps {
  arrangements: ArrangementSummary[]
  candidates: CandidateSummary[]
  selectedId: string | null
  onSelect: (id: string) => void
  genre: string
}

export default function ArrangementList({
  arrangements,
  candidates,
  selectedId,
  onSelect,
  genre,
}: ArrangementListProps) {
  // Group by progression_candidate_id
  const groups = new Map<string, ArrangementSummary[]>()
  for (const arr of arrangements) {
    const list = groups.get(arr.progression_candidate_id) || []
    list.push(arr)
    groups.set(arr.progression_candidate_id, list)
  }

  // Sort within each group by rank
  for (const [, list] of groups) {
    list.sort((a, b) => a.rank_within_round - b.rank_within_round)
  }

  // Build candidate lookup for chord symbols
  const candidateLookup = new Map<string, CandidateSummary>()
  for (const c of candidates) {
    candidateLookup.set(c.candidate_id, c)
  }

  return (
    <div className="w-72 bg-slate-900 border-r border-slate-700 overflow-y-auto shrink-0">
      <div className="px-3 py-2 text-xs text-slate-500 uppercase tracking-wider border-b border-slate-800">
        Arrangements
      </div>
      {[...groups.entries()].map(([progId, arrs]) => {
        const candidate = candidateLookup.get(progId)
        const chords = candidate?.chord_symbols?.join(" \u2192 ") || progId.slice(0, 12)

        return (
          <div key={progId}>
            {/* Family header */}
            <div className="px-3 py-1.5 text-[11px] font-mono text-slate-400 bg-slate-950 border-b border-slate-800 truncate">
              {chords}
            </div>
            {/* Arrangement cards */}
            {arrs.map((arr) => (
              <ArrangementCard
                key={arr.id}
                arrangement={arr}
                selected={arr.id === selectedId}
                onClick={() => onSelect(arr.id)}
                genre={genre}
              />
            ))}
          </div>
        )
      })}
      {arrangements.length === 0 && (
        <div className="px-3 py-8 text-sm text-slate-600 text-center">
          No arrangements yet
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ScorePanel.tsx frontend/src/components/ArrangementCard.tsx frontend/src/components/ArrangementList.tsx
git commit -m "feat(m2c): add ScorePanel, ArrangementCard, and ArrangementList"
```

---

## Task 8: ArrangementDetail Container

**Files:**
- Create: `frontend/src/components/ArrangementDetail.tsx`

- [ ] **Step 1: Create ArrangementDetail.tsx**

```typescript
// frontend/src/components/ArrangementDetail.tsx

import type { ArrangementDetail as ArrangementDetailType } from "../services/api"
import PianoRoll from "./PianoRoll"
import TransportBar from "./TransportBar"
import ScorePanel from "./ScorePanel"

interface ArrangementDetailProps {
  arrangement: ArrangementDetailType | null
  genre: string
}

export default function ArrangementDetail({ arrangement, genre }: ArrangementDetailProps) {
  if (!arrangement) {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-950 text-slate-600">
        <p>Select an arrangement to view details</p>
      </div>
    )
  }

  const scores = arrangement.scorecard?.scores ?? {}
  const weightedTotal = arrangement.scorecard?.weighted_total ?? arrangement.weighted_total ?? 0

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-slate-950">
      {/* Transport */}
      <TransportBar arrangement={arrangement} genre={genre} />

      {/* Piano Roll (hero, takes remaining space) */}
      <PianoRoll arrangement={arrangement} genre={genre} />

      {/* Score Panel (collapsible, bottom) */}
      <ScorePanel scores={scores} weightedTotal={weightedTotal} />
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ArrangementDetail.tsx
git commit -m "feat(m2c): add ArrangementDetail container component"
```

---

## Task 9: CandidateCard "Realize" Button

**Files:**
- Modify: `frontend/src/components/CandidateCard.tsx`

- [ ] **Step 1: Add Realize button to CandidateCard**

Read the current `CandidateCard.tsx`. Add an `onRealize` callback prop and a "Realize" button at the bottom of the card.

Add to the component props:
```typescript
onRealize?: (candidateId: string) => void
```

Add at the bottom of the card (before the closing `</div>`):
```typescript
{onRealize && (
  <button
    onClick={(e) => {
      e.stopPropagation()
      onRealize(candidate.candidate_id)
    }}
    className="mt-3 w-full py-1.5 text-xs font-medium rounded bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors"
  >
    Realize
  </button>
)}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/CandidateCard.tsx
git commit -m "feat(m2c): add Realize button to CandidateCard"
```

---

## Task 10: SessionWorkspace View Mode + Realization Flow

**Files:**
- Modify: `frontend/src/views/SessionWorkspace.tsx`

- [ ] **Step 1: Add realization view mode**

This is the largest modification. Read the current `SessionWorkspace.tsx` carefully, then add:

1. **New state**: `viewMode: "generation" | "realization"`, `realizingCandidateId: string | null`
2. **Import new components**: `ArrangementList`, `ArrangementDetail`
3. **Import new stores**: `useArrangementStore`
4. **Import new API functions**: `listArrangements`, `getArrangement`, `triggerRealizationSSE`

**Realization trigger flow** (new function `handleRealize`):
```typescript
const handleRealize = async (candidateId: string) => {
  if (!sessionId) return
  setRealizingCandidateId(candidateId)
  setCurrentNode("load_context")
  setLoading(true)

  try {
    const response = await triggerRealizationSSE(sessionId, [candidateId])
    if (!response.ok || !response.body) throw new Error("Realization failed")

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ""

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split(/\r?\n/)
      buffer = lines.pop() || ""

      for (const line of lines) {
        if (line.startsWith("data:")) {
          try {
            const data = JSON.parse(line.slice(5).trim())
            if (data.node) setCurrentNode(data.node)
          } catch { /* skip non-JSON */ }
        }
      }
    }

    // Load arrangements
    const arrangements = await listArrangements(candidateId)
    useArrangementStore.getState().setArrangements(arrangements)
    setViewMode("realization")

    // Auto-select best arrangement
    if (arrangements.length > 0) {
      const best = arrangements.reduce((a, b) =>
        (a.weighted_total ?? 0) > (b.weighted_total ?? 0) ? a : b
      )
      handleSelectArrangement(best.id)
    }
  } catch (err: any) {
    setError(err.message || "Realization failed")
  } finally {
    setLoading(false)
    setCurrentNode(null)
    setRealizingCandidateId(null)
  }
}
```

**Arrangement selection** (new function):
```typescript
const handleSelectArrangement = async (arrangementId: string) => {
  useArrangementStore.getState().setSelectedArrangementId(arrangementId)
  try {
    const detail = await getArrangement(arrangementId)
    useArrangementStore.getState().setSelectedDetail(detail)
  } catch (err: any) {
    setError(err.message || "Failed to load arrangement")
  }
}
```

**Render logic**: When `viewMode === "realization"`, render the split-panel layout instead of the candidate grid:

```tsx
{viewMode === "realization" ? (
  <div className="flex flex-1 min-h-0">
    <ArrangementList
      arrangements={arrangementStore.arrangements}
      candidates={candidates}
      selectedId={arrangementStore.selectedArrangementId}
      onSelect={handleSelectArrangement}
      genre={session?.genre || "dream_pop"}
    />
    <ArrangementDetail
      arrangement={arrangementStore.selectedDetail}
      genre={session?.genre || "dream_pop"}
    />
  </div>
) : (
  /* existing candidate grid */
)}
```

Add a "Back to progressions" link at the top of the realization view:
```tsx
{viewMode === "realization" && (
  <button
    onClick={() => { setViewMode("generation"); audioEngine.stop(); }}
    className="text-xs text-slate-500 hover:text-slate-300 mb-2"
  >
    &larr; Back to progressions
  </button>
)}
```

**Pass `onRealize` to CandidateCard**:
```tsx
<CandidateCard
  key={c.candidate_id}
  candidate={c}
  index={i}
  onRealize={handleRealize}
/>
```

**Update SSE node tracking**: Add M2b node names to the progress display:
- load_context, plan_voicings, generate_bass, assemble, evaluate_arrangements, rank_and_select, persist_realization

- [ ] **Step 2: Verify the app builds**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Fix any TypeScript errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/SessionWorkspace.tsx
git commit -m "feat(m2c): add realization view mode with split-panel layout"
```

---

## Task 11: Final Verification

- [ ] **Step 1: Build check**

```bash
cd frontend && npm run build 2>&1 | tail -20
```
Expected: Build succeeds with no errors.

- [ ] **Step 2: Verify all new files exist**

```bash
ls frontend/src/components/Arrangement*.tsx frontend/src/components/PianoRoll.tsx frontend/src/components/TransportBar.tsx frontend/src/components/ScorePanel.tsx frontend/src/stores/arrangement*.ts frontend/src/stores/audio*.ts frontend/src/services/audioEngine.ts frontend/src/services/midiUtils.ts
```

- [ ] **Step 3: Check for type errors**

```bash
cd frontend && npx tsc --noEmit 2>&1 | tail -20
```

- [ ] **Step 4: Run backend tests to ensure no regressions**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/ -q --tb=short 2>&1 | tail -5
```

- [ ] **Step 5: Commit any fixups**

```bash
git status && git add -A && git commit -m "fix(m2c): resolve build errors" 2>/dev/null || echo "Nothing to commit"
```
