/**
 * audioEngine.ts — Tone.js audio engine for Explorator.
 *
 * React components must never import Tone directly.
 * All playback state is synchronised via audioStore.
 */

import type { ArrangementDetail } from "./api"
import { useAudioStore } from "../stores/audioStore"
import { ensureTone, resetTone, normalizePitch, normalizePitches } from "./audioUtils"
import type { ToneModule } from "./audioUtils"
import { getPreset, buildPolySynth, buildMonoSynth, MELODY_DEFAULT } from "./audioPresets"
import * as comparisonAudioEngine from "./comparisonAudioEngine"

// ---------------------------------------------------------------------------
// Module-level engine state
// ---------------------------------------------------------------------------

// Cached Tone reference — set after first ensureTone() call in play()
let Tone: ToneModule | null = null

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let polySynth: any | null = null
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let monoSynth: any | null = null
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let voicingVol: any | null = null
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let bassVol: any | null = null
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let melodySynth: any | null = null
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let melodyVol: any | null = null

let rafId: number | null = null

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
// Bars are 0-indexed from the backend, which maps directly to Tone.js
// transport notation (0:0:0 = first bar, first beat).
// ---------------------------------------------------------------------------

function scheduleVoicing(
  T: ToneModule,
  arrangement: ArrangementDetail,
): void {
  if (!arrangement.voicing_plan || !polySynth) return
  const transport = T.getTransport()

  for (const ev of arrangement.voicing_plan.voicing_events) {
    const time = `${ev.bar}:${ev.beat - 1}:0`
    const dur = `0:${ev.duration_beats}:0`
    const pitches = normalizePitches(ev.pitches)

    transport.schedule((t: number) => {
      const { mutedTracks } = useAudioStore.getState()
      if (mutedTracks.voicing) return
      polySynth?.triggerAttackRelease(pitches, dur, t)
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
    const time = `${ev.bar}:${ev.beat - 1}:0`
    const dur = `0:${ev.duration_beats}:0`
    const vel = ev.velocity / 127
    const pitch = normalizePitch(ev.pitch)

    transport.schedule((t: number) => {
      const { mutedTracks } = useAudioStore.getState()
      if (mutedTracks.bass) return
      monoSynth?.triggerAttackRelease(pitch, dur, t, vel)
    }, time)
  }
}

function scheduleMelody(
  T: ToneModule,
  arrangement: ArrangementDetail,
): void {
  if (!arrangement.melodic_complement || !melodySynth) return
  const transport = T.getTransport()

  for (const ev of arrangement.melodic_complement.note_events) {
    const time = `${ev.bar}:${ev.beat - 1}:0`
    const dur = `0:${ev.duration_beats}:0`
    const vel = ev.velocity / 127
    const pitch = normalizePitch(ev.pitch)

    transport.schedule((t: number) => {
      const { mutedTracks } = useAudioStore.getState()
      if (mutedTracks.melody) return
      melodySynth?.triggerAttackRelease(pitch, dur, t, vel)
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
  if (melodySynth) { melodySynth.dispose(); melodySynth = null }
  if (melodyVol) { melodyVol.dispose(); melodyVol = null }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export async function play(
  arrangement: ArrangementDetail,
  tempo: number,
  genre: string,
): Promise<void> {
  comparisonAudioEngine.stop()
  Tone = await ensureTone()
  const T = Tone
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
    ...(arrangement.melodic_complement?.note_events ?? []).map((e) => e.bar + Math.ceil(e.duration_beats / 4)),
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

  melodySynth = buildMonoSynth(T, MELODY_DEFAULT)
  melodyVol = new T.Volume(MELODY_DEFAULT.volume ?? -8).toDestination()
  melodySynth.connect(melodyVol)

  // Mute volumes if already muted
  if (store.mutedTracks.voicing) voicingVol.mute = true
  if (store.mutedTracks.bass) bassVol.mute = true
  melodyVol.mute = store.mutedTracks.melody

  // Schedule notes
  scheduleVoicing(T, arrangement)
  scheduleBass(T, arrangement)
  scheduleMelody(T, arrangement)

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

export function setMelodyMute(muted: boolean): void {
  if (melodyVol) melodyVol.mute = muted
  useAudioStore.getState().toggleMute("melody")
}

export function setVolume(db: number): void {
  if (voicingVol) voicingVol.volume.value = db
  if (bassVol) bassVol.volume.value = db
  useAudioStore.getState().setVolume(db)
}

export function dispose(): void {
  stop()
  teardownNodes()
  resetTone()
  Tone = null
}
