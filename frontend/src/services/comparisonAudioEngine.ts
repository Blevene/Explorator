/**
 * comparisonAudioEngine.ts — Multi-lane Tone.js engine for comparison playback.
 *
 * Manages N synth pairs (one PolySynth + MonoSynth per lane) on a single
 * shared Transport. Lane silencing via Volume.mute — no schedule-time checks.
 */

import type { ArrangementDetail } from "./api"
import { ensureTone, normalizePitch, normalizePitches } from "./audioUtils"
import type { ToneModule } from "./audioUtils"
import { getPreset, buildPolySynth, buildMonoSynth } from "./audioPresets"
import { useComparisonAudioStore } from "../stores/comparisonAudioStore"
import { useAudioStore } from "../stores/audioStore"
import * as audioEngine from "./audioEngine"

// ---------------------------------------------------------------------------
// Module-level state
// ---------------------------------------------------------------------------

interface LaneSynths {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  poly: any
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  mono: any
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  vol: any
}

let synths: Record<string, LaneSynths> = {}
let rafId: number | null = null

// ---------------------------------------------------------------------------
// rAF position tracking
// ---------------------------------------------------------------------------

function startPositionTracking(T: ToneModule, tempo: number): void {
  const store = useComparisonAudioStore.getState()

  const tick = (): void => {
    const transport = T.getTransport()
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
// Dispose all synth nodes
// ---------------------------------------------------------------------------

function teardownNodes(): void {
  for (const lane of Object.values(synths)) {
    lane.poly?.dispose()
    lane.mono?.dispose()
    lane.vol?.dispose()
  }
  synths = {}
}

// ---------------------------------------------------------------------------
// Event scheduling (no per-event mute checks — Volume.mute handles silencing)
// ---------------------------------------------------------------------------

function scheduleVoicing(
  T: ToneModule,
  candidateId: string,
  arrangement: ArrangementDetail,
): void {
  if (!arrangement.voicing_plan) return
  const transport = T.getTransport()
  const lane = synths[candidateId]
  if (!lane) return

  for (const ev of arrangement.voicing_plan.voicing_events) {
    const time = `${ev.bar}:${ev.beat - 1}:0`
    const dur = `0:${ev.duration_beats}:0`
    const pitches = normalizePitches(ev.pitches)

    transport.schedule((t: number) => {
      lane.poly?.triggerAttackRelease(pitches, dur, t)
    }, time)
  }
}

function scheduleBass(
  T: ToneModule,
  candidateId: string,
  arrangement: ArrangementDetail,
): void {
  if (!arrangement.bass_line) return
  const transport = T.getTransport()
  const lane = synths[candidateId]
  if (!lane) return

  for (const ev of arrangement.bass_line.note_events) {
    const time = `${ev.bar}:${ev.beat - 1}:0`
    const dur = `0:${ev.duration_beats}:0`
    const vel = ev.velocity / 127
    const pitch = normalizePitch(ev.pitch)

    transport.schedule((t: number) => {
      lane.mono?.triggerAttackRelease(pitch, dur, t, vel)
    }, time)
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export async function playComparison(
  arrangements: Map<string, ArrangementDetail>,
  tempo: number,
  genre: string,
): Promise<void> {
  const T = await ensureTone()
  const transport = T.getTransport()

  // Stop any existing playback (both engines)
  audioEngine.stop()
  useAudioStore.getState().reset()
  stop()

  // Apply tempo
  transport.bpm.value = tempo

  // Calculate loopEnd from the longest arrangement
  let maxBars = 8
  for (const arrangement of arrangements.values()) {
    const allBars = [
      ...(arrangement.voicing_plan?.voicing_events ?? []).map((e) => e.bar + Math.ceil(e.duration_beats / 4)),
      ...(arrangement.bass_line?.note_events ?? []).map((e) => e.bar + Math.ceil(e.duration_beats / 4)),
    ]
    if (allBars.length > 0) {
      maxBars = Math.max(maxBars, Math.max(...allBars))
    }
  }

  const store = useComparisonAudioStore.getState()
  transport.loop = store.loop
  transport.loopStart = "0:0:0"
  transport.loopEnd = `${maxBars}:0:0`

  // Build synth pairs per lane
  const preset = getPreset(genre)

  for (const [candidateId, arrangement] of arrangements.entries()) {
    const vol = new T.Volume(-6).toDestination()
    const poly = buildPolySynth(T, preset.voicing)
    poly.connect(vol)
    const mono = buildMonoSynth(T, preset.bass)
    mono.connect(vol)

    synths[candidateId] = { poly, mono, vol }

    // Schedule events
    scheduleVoicing(T, candidateId, arrangement)
    scheduleBass(T, candidateId, arrangement)
  }

  // Start
  transport.start()
  startPositionTracking(T, tempo)

  store.setPlaying(true)
  store.setPaused(false)
}

export function pause(): void {
  ensureTone().then((T) => {
    T.getTransport().pause()
    stopPositionTracking()
    const store = useComparisonAudioStore.getState()
    store.setPlaying(false)
    store.setPaused(true)
  })
}

export function resume(): void {
  ensureTone().then((T) => {
    const store = useComparisonAudioStore.getState()
    T.getTransport().start()
    startPositionTracking(T, store.tempo)
    store.setPlaying(true)
    store.setPaused(false)
  })
}

export function stop(): void {
  stopPositionTracking()
  teardownNodes()
  const store = useComparisonAudioStore.getState()
  store.setPlaying(false)
  store.setPaused(false)
  store.setCurrentPosition(0)

  // Cancel transport only if Tone is loaded
  ensureTone().then((T) => {
    const transport = T.getTransport()
    transport.stop()
    transport.cancel()
  }).catch(() => {
    // Tone not loaded — nothing to stop
  })
}

export function setTempo(bpm: number): void {
  ensureTone().then((T) => {
    T.getTransport().bpm.value = bpm
    useComparisonAudioStore.getState().setTempo(bpm)
  })
}

export function setLoop(enabled: boolean): void {
  ensureTone().then((T) => {
    T.getTransport().loop = enabled
    useComparisonAudioStore.getState().setLoop(enabled)
  })
}

export function setLaneMute(candidateId: string, muted: boolean): void {
  const lane = synths[candidateId]
  if (lane) lane.vol.mute = muted
}

export function dispose(): void {
  stop()
  teardownNodes()
}
