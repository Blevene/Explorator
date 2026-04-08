/**
 * audioEngine.ts — Tone.js audio engine for Explorator.
 *
 * React components must never import Tone directly.
 * All playback state is synchronised via audioStore.
 */

import type { ArrangementDetail } from "./api"
import { useAudioStore } from "../stores/audioStore"

// ---------------------------------------------------------------------------
// Genre presets
// ---------------------------------------------------------------------------

interface SynthOptions {
  oscillator?: { type: string }
  envelope?: { attack?: number; release?: number }
  volume?: number
}

interface GenrePreset {
  voicing: SynthOptions
  bass: SynthOptions
}

const GENRE_PRESETS: Record<string, GenrePreset> = {
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

function getPreset(genre: string): GenrePreset {
  const key = genre.toLowerCase().replace(/[\s-]/g, "_")
  return GENRE_PRESETS[key] ?? GENRE_PRESETS["dream_pop"]
}

// ---------------------------------------------------------------------------
// Deep-merge helper (shallow second level for our known shape)
// ---------------------------------------------------------------------------

function deepMerge<T extends Record<string, unknown>>(base: T, override: Partial<T>): T {
  const result = { ...base }
  for (const k of Object.keys(override) as Array<keyof T>) {
    const bv = base[k]
    const ov = override[k]
    if (ov !== undefined) {
      if (bv !== null && typeof bv === "object" && !Array.isArray(bv) &&
          ov !== null && typeof ov === "object" && !Array.isArray(ov)) {
        result[k] = { ...(bv as object), ...(ov as object) } as T[keyof T]
      } else {
        result[k] = ov as T[keyof T]
      }
    }
  }
  return result
}

// ---------------------------------------------------------------------------
// Module-level engine state
// ---------------------------------------------------------------------------

// Tone types (resolved after lazy import)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ToneModule = typeof import("tone") & Record<string, any>

let Tone: ToneModule | null = null

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let polySynth: any | null = null
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let monoSynth: any | null = null
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let voicingVol: any | null = null
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let bassVol: any | null = null

let rafId: number | null = null
let isInitialised = false

// ---------------------------------------------------------------------------
// Lazy-load + initialise Tone on first user gesture
// ---------------------------------------------------------------------------

async function ensureTone(): Promise<ToneModule> {
  if (!Tone) {
    Tone = (await import("tone")) as ToneModule
  }
  if (!isInitialised) {
    await Tone.start()
    isInitialised = true
  }
  return Tone
}

// ---------------------------------------------------------------------------
// Build synths with genre preset merged over defaults
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function buildPolySynth(T: ToneModule, preset: SynthOptions): any {
  const defaults: Record<string, unknown> = {
    oscillator: { type: "triangle" },
    envelope: { attack: 0.1, decay: 0.2, sustain: 0.5, release: 0.8 },
  }
  const merged = deepMerge(defaults, preset as Record<string, unknown>)
  return new T.PolySynth(T.Synth, merged)
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function buildMonoSynth(T: ToneModule, preset: SynthOptions): any {
  const defaults: Record<string, unknown> = {
    oscillator: { type: "sine" },
    envelope: { attack: 0.05, decay: 0.1, sustain: 0.8, release: 0.5 },
  }
  const merged = deepMerge(defaults, preset as Record<string, unknown>)
  return new T.MonoSynth(merged)
}

// ---------------------------------------------------------------------------
// rAF position tracking
// ---------------------------------------------------------------------------

function startPositionTracking(tempo: number): void {
  const store = useAudioStore.getState()

  const tick = (): void => {
    if (!Tone) return
    const transport = Tone.getTransport()
    const seconds = transport.seconds
    const barPosition = (seconds * (tempo / 60)) / 4
    store.setCurrentPosition(barPosition)
    rafId = requestAnimationFrame(tick)
  }

  if (rafId !== null) cancelAnimationFrame(rafId)
  rafId = requestAnimationFrame(tick)
}

function stopPositionTracking(): void {
  if (rafId !== null) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
}

// ---------------------------------------------------------------------------
// Scheduling helpers
// ---------------------------------------------------------------------------

function scheduleVoicing(
  T: ToneModule,
  arrangement: ArrangementDetail,
): void {
  if (!arrangement.voicing_plan || !polySynth) return
  const transport = T.getTransport()

  for (const ev of arrangement.voicing_plan.voicing_events) {
    const time = `${ev.bar - 1}:${ev.beat - 1}:0`
    const dur = `0:${ev.duration_beats}:0`

    transport.schedule((t: number) => {
      const { mutedTracks } = useAudioStore.getState()
      if (mutedTracks.voicing) return
      polySynth?.triggerAttackRelease(ev.pitches, dur, t)
    }, time)
  }
}

function scheduleBass(
  T: ToneModule,
  arrangement: ArrangementDetail,
): void {
  if (!arrangement.bass_line || !monoSynth) return
  const transport = T.getTransport()

  for (const ev of arrangement.bass_line.note_events) {
    const time = `${ev.bar - 1}:${ev.beat - 1}:0`
    const dur = `0:${ev.duration_beats}:0`
    const vel = ev.velocity / 127

    transport.schedule((t: number) => {
      const { mutedTracks } = useAudioStore.getState()
      if (mutedTracks.bass) return
      monoSynth?.triggerAttackRelease(ev.pitch, dur, t, vel)
    }, time)
  }
}

// ---------------------------------------------------------------------------
// Dispose active synths / volumes
// ---------------------------------------------------------------------------

function teardownNodes(): void {
  polySynth?.dispose()
  monoSynth?.dispose()
  voicingVol?.dispose()
  bassVol?.dispose()
  polySynth = null
  monoSynth = null
  voicingVol = null
  bassVol = null
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export async function play(
  arrangement: ArrangementDetail,
  tempo: number,
  genre: string,
): Promise<void> {
  const T = await ensureTone()
  const transport = T.getTransport()
  const store = useAudioStore.getState()

  // Stop anything currently running
  transport.stop()
  transport.cancel()
  teardownNodes()

  // Apply tempo
  transport.bpm.value = tempo

  // Loop: compute total bars from voicing events
  const allBars = [
    ...(arrangement.voicing_plan?.voicing_events ?? []).map((e) => e.bar + Math.ceil(e.duration_beats / 4)),
    ...(arrangement.bass_line?.note_events ?? []).map((e) => e.bar + Math.ceil(e.duration_beats / 4)),
  ]
  const totalBars = allBars.length > 0 ? Math.max(...allBars) : 8

  transport.loop = store.loop
  transport.loopStart = "0:0:0"
  transport.loopEnd = `${totalBars}:0:0`

  // Build nodes
  const preset = getPreset(genre)

  voicingVol = new T.Volume(store.volume).toDestination()
  bassVol = new T.Volume(store.volume).toDestination()

  polySynth = buildPolySynth(T, preset.voicing)
  polySynth.connect(voicingVol)

  monoSynth = buildMonoSynth(T, preset.bass)
  monoSynth.connect(bassVol)

  // Mute volumes if already muted
  if (store.mutedTracks.voicing) voicingVol.mute = true
  if (store.mutedTracks.bass) bassVol.mute = true

  // Schedule notes
  scheduleVoicing(T, arrangement)
  scheduleBass(T, arrangement)

  // Start
  transport.start()
  startPositionTracking(tempo)

  store.setPlaying(true)
  store.setPaused(false)
}

export function pause(): void {
  if (!Tone) return
  Tone.getTransport().pause()
  stopPositionTracking()
  const store = useAudioStore.getState()
  store.setPlaying(false)
  store.setPaused(true)
}

export function resume(): void {
  if (!Tone) return
  const store = useAudioStore.getState()
  Tone.getTransport().start()
  startPositionTracking(store.tempo)
  store.setPlaying(true)
  store.setPaused(false)
}

export function stop(): void {
  if (!Tone) return
  const transport = Tone.getTransport()
  transport.stop()
  transport.cancel()
  stopPositionTracking()
  teardownNodes()
  const store = useAudioStore.getState()
  store.setPlaying(false)
  store.setPaused(false)
  store.setCurrentPosition(0)
}

export function setTempo(bpm: number): void {
  if (!Tone) return
  Tone.getTransport().bpm.value = bpm
  useAudioStore.getState().setTempo(bpm)
}

export function setLoop(enabled: boolean): void {
  if (!Tone) return
  Tone.getTransport().loop = enabled
  useAudioStore.getState().setLoop(enabled)
}

export function setVoicingMute(muted: boolean): void {
  if (voicingVol) voicingVol.mute = muted
  const store = useAudioStore.getState()
  if (store.mutedTracks.voicing !== muted) store.toggleMute("voicing")
}

export function setBassMute(muted: boolean): void {
  if (bassVol) bassVol.mute = muted
  const store = useAudioStore.getState()
  if (store.mutedTracks.bass !== muted) store.toggleMute("bass")
}

export function setVolume(db: number): void {
  if (voicingVol) voicingVol.volume.value = db
  if (bassVol) bassVol.volume.value = db
  useAudioStore.getState().setVolume(db)
}

export function dispose(): void {
  stop()
  teardownNodes()
  isInitialised = false
  Tone = null
}
