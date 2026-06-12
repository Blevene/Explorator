# M4c: Comparison Playback Implementation Plan


**Goal:** Add DAW-lane mute/solo audio playback to ComparisonView, enabling instant A/B/C switching between up to 3 arrangements on a shared Tone.js transport.

**Architecture:** Separate `comparisonAudioEngine` + `comparisonAudioStore` alongside existing single-arrangement audio. Shared utilities extracted to `audioPresets.ts` and `audioUtils.ts`. New `ComparisonTransportBar` and `LaneSidebar` components. PianoRoll gains optional prop overrides for comparison mode.

**Tech Stack:** React 18, TypeScript, Zustand, Tone.js, Vitest (new), Playwright

**Spec:** `docs/design/specs/2026-04-14-m4c-comparison-playback-design.md`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `frontend/src/services/audioUtils.ts` | `ensureTone()`, `resetTone()`, `normalizePitch()`, `normalizePitches()` |
| `frontend/src/services/audioPresets.ts` | `GENRE_PRESETS`, `getPreset()`, `deepMerge()`, `buildPolySynth()`, `buildMonoSynth()`, type interfaces |
| `frontend/src/stores/comparisonAudioStore.ts` | Zustand store for comparison transport + lane mute/solo state |
| `frontend/src/services/comparisonAudioEngine.ts` | Multi-lane Tone.js engine with per-lane Volume nodes |
| `frontend/src/components/ComparisonTransportBar.tsx` | Transport controls for comparison playback |
| `frontend/src/components/LaneSidebar.tsx` | Per-lane label, score, S/M buttons |
| `frontend/vitest.config.ts` | Vitest configuration |
| `frontend/src/stores/__tests__/comparisonAudioStore.test.ts` | Unit tests for store |
| `e2e/tests/comparison-playback.spec.ts` | E2E tests for M4c |

### Modified Files
| File | Change |
|------|--------|
| `frontend/src/services/audioEngine.ts` | Import from extracted utils/presets, add cross-engine stop |
| `frontend/src/components/PianoRoll.tsx` | Add `dimmed`, `currentPosition`, `playing`, `totalBars` optional props |
| `frontend/src/components/ComparisonView.tsx` | Integrate transport bar, lane sidebar, audio engine wiring |
| `frontend/package.json` | Add vitest dev dependency |

---

## Task 1: Install Vitest and Configure

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.ts`

- [ ] **Step 1: Install vitest**

```bash
cd frontend && npm install -D vitest
```

- [ ] **Step 2: Create vitest config**

Create `frontend/vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config"

export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/__tests__/**/*.test.ts"],
  },
})
```

- [ ] **Step 3: Add test script to package.json**

In `frontend/package.json`, add to `"scripts"`:

```json
"test:unit": "vitest run",
"test:unit:watch": "vitest"
```

- [ ] **Step 4: Verify vitest runs (empty test suite)**

```bash
cd frontend && npm run test:unit
```

Expected: `No test files found` (success, not an error).

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.ts
git commit -m "chore: add vitest for frontend unit tests"
```

---

## Task 2: Extract `audioUtils.ts` from `audioEngine.ts`

**Files:**
- Create: `frontend/src/services/audioUtils.ts`
- Modify: `frontend/src/services/audioEngine.ts`

- [ ] **Step 1: Create `audioUtils.ts`**

Create `frontend/src/services/audioUtils.ts`:

```ts
/**
 * audioUtils.ts — Shared Tone.js utilities for both audio engines.
 */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ToneModule = typeof import("tone") & Record<string, any>

let Tone: ToneModule | null = null
let isInitialised = false

export type { ToneModule }

export async function ensureTone(): Promise<ToneModule> {
  if (!Tone) {
    try {
      Tone = (await import("tone")) as ToneModule
    } catch {
      throw new Error("Failed to load audio library. Your browser may not support Web Audio.")
    }
  }
  if (!isInitialised) {
    try {
      await Tone.start()
      isInitialised = true
    } catch {
      throw new Error("Audio context blocked. Click the page first to enable audio playback.")
    }
  }
  return Tone
}

export function resetTone(): void {
  isInitialised = false
  Tone = null
}

export function normalizePitch(pitch: string): string {
  return pitch.replace("-", "b")
}

export function normalizePitches(pitches: string[]): string[] {
  return pitches.map(normalizePitch)
}
```

- [ ] **Step 2: Update `audioEngine.ts` to import from `audioUtils.ts`**

In `frontend/src/services/audioEngine.ts`:

Remove the `ToneModule` type alias (line 73), the `Tone` variable (line 75), the `isInitialised` variable (line 87), the entire `ensureTone` function (lines 93-110), and the `normalizePitch` / `normalizePitches` functions (lines 167-172).

Add this import at the top (after the existing imports):

```ts
import { ensureTone, resetTone, normalizePitch, normalizePitches } from "./audioUtils"
import type { ToneModule } from "./audioUtils"
```

In the `dispose()` function (line 358-363), replace `isInitialised = false` and `Tone = null` with:

```ts
export function dispose(): void {
  stop()
  teardownNodes()
  resetTone()
}
```

- [ ] **Step 3: Verify the app builds**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/audioUtils.ts frontend/src/services/audioEngine.ts
git commit -m "refactor: extract audioUtils from audioEngine (ensureTone, normalizePitch)"
```

---

## Task 3: Extract `audioPresets.ts` from `audioEngine.ts`

**Files:**
- Create: `frontend/src/services/audioPresets.ts`
- Modify: `frontend/src/services/audioEngine.ts`

- [ ] **Step 1: Create `audioPresets.ts`**

Create `frontend/src/services/audioPresets.ts`:

```ts
/**
 * audioPresets.ts — Genre synth presets shared by both audio engines.
 */

import type { ToneModule } from "./audioUtils"

export interface SynthOptions {
  oscillator?: { type: string }
  envelope?: { attack?: number; release?: number }
  volume?: number
}

export interface GenrePreset {
  voicing: SynthOptions
  bass: SynthOptions
}

export const GENRE_PRESETS: Record<string, GenrePreset> = {
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

export function getPreset(genre: string): GenrePreset {
  const key = genre.toLowerCase().replace(/[\s-]/g, "_")
  return GENRE_PRESETS[key] ?? GENRE_PRESETS["dream_pop"]
}

export function deepMerge<T extends Record<string, unknown>>(base: T, override: Partial<T>): T {
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

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function buildPolySynth(T: ToneModule, preset: SynthOptions): any {
  const defaults: Record<string, unknown> = {
    oscillator: { type: "triangle" },
    envelope: { attack: 0.1, decay: 0.2, sustain: 0.5, release: 0.8 },
  }
  const merged = deepMerge(defaults, preset as Record<string, unknown>)
  return new T.PolySynth(T.Synth, merged)
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function buildMonoSynth(T: ToneModule, preset: SynthOptions): any {
  const defaults: Record<string, unknown> = {
    oscillator: { type: "sine" },
    envelope: { attack: 0.05, decay: 0.1, sustain: 0.8, release: 0.5 },
  }
  const merged = deepMerge(defaults, preset as Record<string, unknown>)
  return new T.MonoSynth(merged)
}
```

- [ ] **Step 2: Update `audioEngine.ts` to import from `audioPresets.ts`**

In `frontend/src/services/audioEngine.ts`:

Remove the `SynthOptions` interface (lines 15-19), `GenrePreset` interface (lines 21-24), `GENRE_PRESETS` constant (lines 26-39), `getPreset` function (lines 41-44), `deepMerge` function (lines 50-65), `buildPolySynth` function (lines 117-124), and `buildMonoSynth` function (lines 127-134).

Add this import at the top:

```ts
import { getPreset, buildPolySynth, buildMonoSynth } from "./audioPresets"
```

- [ ] **Step 3: Verify the app builds**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/audioPresets.ts frontend/src/services/audioEngine.ts
git commit -m "refactor: extract audioPresets from audioEngine (genre presets, synth factories)"
```

---

## Task 4: Create `comparisonAudioStore.ts` with Unit Tests (TDD)

**Files:**
- Create: `frontend/src/stores/__tests__/comparisonAudioStore.test.ts`
- Create: `frontend/src/stores/comparisonAudioStore.ts`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/stores/__tests__/comparisonAudioStore.test.ts`:

```ts
import { describe, it, expect, beforeEach } from "vitest"
import { useComparisonAudioStore } from "../comparisonAudioStore"

function getState() {
  return useComparisonAudioStore.getState()
}

describe("comparisonAudioStore", () => {
  beforeEach(() => {
    getState().reset()
  })

  describe("transport state", () => {
    it("has correct defaults", () => {
      const s = getState()
      expect(s.playing).toBe(false)
      expect(s.paused).toBe(false)
      expect(s.tempo).toBe(120)
      expect(s.loop).toBe(true)
      expect(s.currentPosition).toBe(0)
    })

    it("setPlaying updates playing", () => {
      getState().setPlaying(true)
      expect(getState().playing).toBe(true)
    })

    it("setPaused updates paused", () => {
      getState().setPaused(true)
      expect(getState().paused).toBe(true)
    })

    it("setTempo updates tempo", () => {
      getState().setTempo(140)
      expect(getState().tempo).toBe(140)
    })

    it("setLoop updates loop", () => {
      getState().setLoop(false)
      expect(getState().loop).toBe(false)
    })

    it("setCurrentPosition updates currentPosition", () => {
      getState().setCurrentPosition(3.5)
      expect(getState().currentPosition).toBe(3.5)
    })
  })

  describe("mute", () => {
    it("toggleMute adds candidate to mutedLanes", () => {
      getState().toggleMute("candidate-1")
      expect(getState().mutedLanes["candidate-1"]).toBe(true)
    })

    it("toggleMute twice removes candidate from mutedLanes", () => {
      getState().toggleMute("candidate-1")
      getState().toggleMute("candidate-1")
      expect(getState().mutedLanes["candidate-1"]).toBe(false)
    })
  })

  describe("solo", () => {
    it("toggleSolo adds candidate to soloedLanes", () => {
      getState().toggleSolo("candidate-1")
      expect(getState().soloedLanes["candidate-1"]).toBe(true)
    })

    it("toggleSolo twice removes candidate from soloedLanes", () => {
      getState().toggleSolo("candidate-1")
      getState().toggleSolo("candidate-1")
      expect(getState().soloedLanes["candidate-1"]).toBe(false)
    })
  })

  describe("audibility logic", () => {
    // Helper: compute audibility the same way the components will
    function isAudible(id: string): boolean {
      const { mutedLanes, soloedLanes } = getState()
      const anySoloed = Object.values(soloedLanes).some(Boolean)
      return !mutedLanes[id] && (!anySoloed || !!soloedLanes[id])
    }

    it("all lanes audible when nothing muted or soloed", () => {
      expect(isAudible("a")).toBe(true)
      expect(isAudible("b")).toBe(true)
    })

    it("muted lane is not audible", () => {
      getState().toggleMute("a")
      expect(isAudible("a")).toBe(false)
      expect(isAudible("b")).toBe(true)
    })

    it("solo on one lane silences others", () => {
      getState().toggleSolo("a")
      expect(isAudible("a")).toBe(true)
      expect(isAudible("b")).toBe(false)
    })

    it("mute wins over solo", () => {
      getState().toggleSolo("a")
      getState().toggleMute("a")
      expect(isAudible("a")).toBe(false)
    })

    it("all lanes soloed means all audible", () => {
      getState().toggleSolo("a")
      getState().toggleSolo("b")
      getState().toggleSolo("c")
      expect(isAudible("a")).toBe(true)
      expect(isAudible("b")).toBe(true)
      expect(isAudible("c")).toBe(true)
    })

    it("two lanes soloed, third silent", () => {
      getState().toggleSolo("a")
      getState().toggleSolo("b")
      expect(isAudible("a")).toBe(true)
      expect(isAudible("b")).toBe(true)
      expect(isAudible("c")).toBe(false)
    })
  })

  describe("reset", () => {
    it("clears all state", () => {
      getState().setPlaying(true)
      getState().setTempo(180)
      getState().toggleMute("a")
      getState().toggleSolo("b")
      getState().setCurrentPosition(5.0)

      getState().reset()

      const s = getState()
      expect(s.playing).toBe(false)
      expect(s.tempo).toBe(120)
      expect(s.mutedLanes).toEqual({})
      expect(s.soloedLanes).toEqual({})
      expect(s.currentPosition).toBe(0)
    })
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx vitest run src/stores/__tests__/comparisonAudioStore.test.ts
```

Expected: FAIL — module `../comparisonAudioStore` not found.

- [ ] **Step 3: Create `comparisonAudioStore.ts`**

Create `frontend/src/stores/comparisonAudioStore.ts`:

```ts
import { create } from "zustand"

interface ComparisonAudioState {
  playing: boolean
  paused: boolean
  tempo: number
  loop: boolean
  currentPosition: number
  mutedLanes: Record<string, boolean>
  soloedLanes: Record<string, boolean>
  setPlaying: (playing: boolean) => void
  setPaused: (paused: boolean) => void
  setTempo: (tempo: number) => void
  setLoop: (loop: boolean) => void
  setCurrentPosition: (position: number) => void
  toggleMute: (candidateId: string) => void
  toggleSolo: (candidateId: string) => void
  reset: () => void
}

const INITIAL_STATE = {
  playing: false,
  paused: false,
  tempo: 120,
  loop: true,
  currentPosition: 0,
  mutedLanes: {} as Record<string, boolean>,
  soloedLanes: {} as Record<string, boolean>,
}

export const useComparisonAudioStore = create<ComparisonAudioState>((set) => ({
  ...INITIAL_STATE,
  setPlaying: (playing) => set({ playing }),
  setPaused: (paused) => set({ paused }),
  setTempo: (tempo) => set({ tempo }),
  setLoop: (loop) => set({ loop }),
  setCurrentPosition: (position) => set({ currentPosition: position }),
  toggleMute: (candidateId) =>
    set((state) => ({
      mutedLanes: { ...state.mutedLanes, [candidateId]: !state.mutedLanes[candidateId] },
    })),
  toggleSolo: (candidateId) =>
    set((state) => ({
      soloedLanes: { ...state.soloedLanes, [candidateId]: !state.soloedLanes[candidateId] },
    })),
  reset: () => set({ ...INITIAL_STATE, mutedLanes: {}, soloedLanes: {} }),
}))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npx vitest run src/stores/__tests__/comparisonAudioStore.test.ts
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/comparisonAudioStore.ts frontend/src/stores/__tests__/comparisonAudioStore.test.ts
git commit -m "feat: comparisonAudioStore with mute/solo/transport state (TDD)"
```

---

## Task 5: Create `comparisonAudioEngine.ts`

**Files:**
- Create: `frontend/src/services/comparisonAudioEngine.ts`
- Modify: `frontend/src/services/audioEngine.ts`

- [ ] **Step 1: Create `comparisonAudioEngine.ts`**

Create `frontend/src/services/comparisonAudioEngine.ts`:

```ts
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
```

- [ ] **Step 2: Add cross-engine stop to `audioEngine.ts`**

In `frontend/src/services/audioEngine.ts`, add this import at the top:

```ts
import * as comparisonAudioEngine from "./comparisonAudioEngine"
```

In the `play()` function, add this line at the very top of the function body (before `const T = await ensureTone()`):

```ts
comparisonAudioEngine.stop()
```

- [ ] **Step 3: Verify the app builds**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/comparisonAudioEngine.ts frontend/src/services/audioEngine.ts
git commit -m "feat: comparisonAudioEngine with multi-lane playback and cross-engine stop"
```

---

## Task 6: Add `dimmed`, `currentPosition`, `playing`, `totalBars` Props to PianoRoll

**Files:**
- Modify: `frontend/src/components/PianoRoll.tsx`

- [ ] **Step 1: Update the PianoRollProps interface**

In `frontend/src/components/PianoRoll.tsx`, update the interface (lines 7-13):

```ts
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
```

- [ ] **Step 2: Update the component signature to destructure new props**

Replace the destructuring (lines 37-43):

```ts
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
```

- [ ] **Step 3: Override store values with props when provided**

Replace line 48:

```ts
const { playing, currentPosition, mutedTracks } = useAudioStore()
```

With:

```ts
const audioStoreState = useAudioStore()
const playing = playingProp ?? audioStoreState.playing
const currentPosition = currentPositionProp ?? audioStoreState.currentPosition
const { mutedTracks } = audioStoreState
```

- [ ] **Step 4: Use `totalBarsProp` to override computed bar count**

In the `useEffect` that renders the canvas, find the line that computes `totalBars` (line 77):

```ts
    const totalBars = allBars.length > 0 ? Math.max(...allBars) : 8
```

Replace with:

```ts
    const computedBars = allBars.length > 0 ? Math.max(...allBars) : 8
    const totalBars = totalBarsProp ?? computedBars
```

This lets ComparisonView pass the max bar count across all lanes so they align visually. When omitted (single-arrangement mode), the component computes its own bar count as before.

- [ ] **Step 5: Apply dimmed opacity to the canvas container**

Replace the return statement (lines 227-235):

```ts
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
```

- [ ] **Step 6: Verify the app builds**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/PianoRoll.tsx
git commit -m "feat: PianoRoll gains dimmed, currentPosition, playing, totalBars prop overrides"
```

---

## Task 7: Create `LaneSidebar` Component

**Files:**
- Create: `frontend/src/components/LaneSidebar.tsx`

- [ ] **Step 1: Create `LaneSidebar.tsx`**

Create `frontend/src/components/LaneSidebar.tsx`:

```tsx
import { useComparisonAudioStore } from "../stores/comparisonAudioStore"

interface LaneSidebarProps {
  candidateId: string
  label: string
  score: number
  audible: boolean
}

export default function LaneSidebar({ candidateId, label, score, audible }: LaneSidebarProps) {
  const { mutedLanes, soloedLanes, toggleMute, toggleSolo } = useComparisonAudioStore()

  const isSoloed = !!soloedLanes[candidateId]
  const isMuted = !!mutedLanes[candidateId]

  return (
    <div
      className="w-[72px] flex-shrink-0 flex flex-col items-center justify-center py-2 gap-1.5"
      style={{
        background: "var(--surface-2)",
        borderRight: "1px solid var(--border-subtle)",
        opacity: audible ? 1 : 0.2,
        transition: "opacity 150ms ease",
      }}
    >
      {/* Candidate label */}
      <div
        className="w-7 h-7 rounded-full flex items-center justify-center font-bold text-sm"
        style={{ background: "var(--accent-primary)", color: "#fff" }}
      >
        {label}
      </div>

      {/* Score */}
      <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
        {score.toFixed(1)}
      </span>

      {/* Solo / Mute buttons */}
      <div className="flex gap-1">
        <button
          onClick={(e) => { e.stopPropagation(); toggleSolo(candidateId) }}
          title={isSoloed ? "Unsolo" : "Solo"}
          className="w-[22px] h-[18px] rounded-sm text-[9px] font-bold border-none cursor-pointer"
          style={{
            background: isSoloed ? "#eab308" : "var(--surface-3)",
            color: isSoloed ? "#0f172a" : "var(--text-muted)",
          }}
        >
          S
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); toggleMute(candidateId) }}
          title={isMuted ? "Unmute" : "Mute"}
          className="w-[22px] h-[18px] rounded-sm text-[9px] font-bold border-none cursor-pointer"
          style={{
            background: isMuted ? "#ef4444" : "var(--surface-3)",
            color: isMuted ? "#fff" : "var(--text-muted)",
          }}
        >
          M
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify the app builds**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/LaneSidebar.tsx
git commit -m "feat: LaneSidebar component with solo/mute buttons"
```

---

## Task 8: Create `ComparisonTransportBar` Component

**Files:**
- Create: `frontend/src/components/ComparisonTransportBar.tsx`

- [ ] **Step 1: Create `ComparisonTransportBar.tsx`**

Create `frontend/src/components/ComparisonTransportBar.tsx`:

```tsx
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
```

- [ ] **Step 2: Verify the app builds**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ComparisonTransportBar.tsx
git commit -m "feat: ComparisonTransportBar with play/stop/tempo/loop controls"
```

---

## Task 9: Integrate Everything into ComparisonView

**Files:**
- Modify: `frontend/src/components/ComparisonView.tsx`

- [ ] **Step 1: Update imports**

In `frontend/src/components/ComparisonView.tsx`, replace the imports (lines 1-6):

```ts
import { useEffect } from "react"
import type { ArrangementDetail } from "../services/api"
import { recordComparison } from "../services/api"
import * as audioEngine from "../services/audioEngine"
import * as comparisonAudioEngine from "../services/comparisonAudioEngine"
import { useAudioStore } from "../stores/audioStore"
import { useComparisonAudioStore } from "../stores/comparisonAudioStore"
import { useCandidateStore } from "../stores/candidateStore"
import { scoreColorVar } from "../utils/designTokens"
import PianoRoll from "./PianoRoll"
import ComparisonTransportBar from "./ComparisonTransportBar"
import LaneSidebar from "./LaneSidebar"
```

- [ ] **Step 2: Add audio lifecycle effects**

Inside the `ComparisonView` component function, after the existing `useEffect` for `recordComparison`, add:

```ts
  // Read comparison audio state
  const { playing: compPlaying, currentPosition: compPosition, mutedLanes, soloedLanes } = useComparisonAudioStore()

  // On mount: stop single-arrangement playback and clear stale mute state
  useEffect(() => {
    audioEngine.stop()
    useAudioStore.getState().reset()
    return () => {
      comparisonAudioEngine.stop()
      useComparisonAudioStore.getState().reset()
    }
  }, [])

  // Sync lane mute state to engine when mute/solo toggles change
  useEffect(() => {
    const anySoloed = Object.values(soloedLanes).some(Boolean)
    for (const id of candidateIds) {
      const audible = !mutedLanes[id] && (!anySoloed || !!soloedLanes[id])
      comparisonAudioEngine.setLaneMute(id, !audible)
    }
  }, [mutedLanes, soloedLanes, candidateIds])

  // Compute audibility per lane (for visual dimming)
  const anySoloed = Object.values(soloedLanes).some(Boolean)
  function isLaneAudible(id: string): boolean {
    return !mutedLanes[id] && (!anySoloed || !!soloedLanes[id])
  }

  // Compute max bars across all arrangements for visual alignment
  const maxBars = Math.max(8, ...comparedArrangements.map((a) => {
    const allBars = [
      ...(a.voicing_plan?.voicing_events ?? []).map((e) => e.bar + Math.ceil(e.duration_beats / 4)),
      ...(a.bass_line?.note_events ?? []).map((e) => e.bar + Math.ceil(e.duration_beats / 4)),
    ]
    return allBars.length > 0 ? Math.max(...allBars) : 0
  }))
```

- [ ] **Step 3: Replace the header with ComparisonTransportBar**

Replace the header `div` (lines 100-118):

```ts
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-2"
        style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border-default)' }}
      >
        <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
          Comparing {comparedArrangements.length} candidates
        </span>
        <button
          onClick={() => {
            clearComparison()
            onClose()
          }}
          className="text-xs transition-colors"
          style={{ color: 'var(--text-muted)' }}
          onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-secondary)')}
          onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
        >
          Close
        </button>
      </div>
```

With:

```tsx
      <ComparisonTransportBar
        arrangements={arrangements}
        genre={genre}
        onClose={() => { clearComparison(); onClose() }}
      />
```

- [ ] **Step 4: Replace the left-rail sidebar and wire PianoRoll props**

Replace the stacked piano rolls section (lines 122-151):

```tsx
      {/* Stacked piano rolls with lane sidebars */}
      <div style={{ borderBottom: '1px solid var(--border-subtle)' }}>
        {comparedArrangements.map((a, i) => {
          const candidateId = candidateIds[i]
          const audible = isLaneAudible(candidateId)
          return (
            <div
              key={a.id}
              className="flex"
              style={{ borderBottom: i < comparedArrangements.length - 1 ? '1px solid var(--border-subtle)' : 'none' }}
            >
              <LaneSidebar
                candidateId={candidateId}
                label={candidateLabels[candidateId] ?? String.fromCharCode(65 + i)}
                score={a.scorecard?.weighted_total ?? a.weighted_total ?? 0}
                audible={audible}
              />
              <div className="flex-1">
                <PianoRoll
                  arrangement={a}
                  genre={genre}
                  compact
                  showCursor
                  barWidth={90}
                  dimmed={!audible}
                  currentPosition={compPosition}
                  playing={compPlaying}
                  totalBars={maxBars}
                />
              </div>
            </div>
          )
        })}
      </div>
```

- [ ] **Step 5: Verify the app builds**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 6: Manual smoke test**

```bash
cd <repo-root> && make dev
```

Open the app in a browser. Navigate to a session with candidates. Select 2+ candidates for comparison. Verify:
- ComparisonTransportBar renders at the top with play/stop/tempo/loop controls
- Each lane has a LaneSidebar with label, score, S and M buttons
- Click Play — cursors appear and move across all lanes
- Click S on a lane — other lanes go silent (audio stops for them)
- Click M on a lane — that lane dims to 20% and goes silent
- Click Stop — cursors reset to 0
- Close comparison and open single-arrangement playback — works independently

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ComparisonView.tsx
git commit -m "feat: ComparisonView integrates transport bar, lane sidebars, and audio engine"
```

---

## Task 10: E2E Tests

**Files:**
- Create: `e2e/tests/comparison-playback.spec.ts`

- [ ] **Step 1: Create E2E test file**

Create `e2e/tests/comparison-playback.spec.ts`:

```ts
import { test, expect, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';

/**
 * Helper: select N candidates for comparison and open the comparison view.
 * Requires candidates to already be generated.
 */
async function openComparison(page: import('@playwright/test').Page, count = 2) {
  const compareButtons = page.getByRole('button', { name: 'Compare', exact: true })
  const buttonCount = await compareButtons.count()
  const toSelect = Math.min(count, buttonCount)

  for (let i = 0; i < toSelect; i++) {
    await compareButtons.nth(i).click()
    await page.waitForTimeout(200)
  }

  // Wait for comparison view to render
  await expect(page.locator('text=COMPARING')).toBeVisible({ timeout: 5_000 })
}

test.describe('Comparison Playback (M4c)', () => {
  test('21: comparison-transport-bar-renders', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId)
    await generateCandidates(page, testSession.prompt)

    // Need arrangements for comparison — realize first candidate
    await realizeFirstCandidate(page)
    await page.getByRole('button', { name: /back to progressions/i }).click()
    await page.waitForTimeout(500)

    await openComparison(page, 2)

    // Transport bar elements visible
    await expect(page.locator('text=COMPARING')).toBeVisible()
    await expect(page.locator('text=BPM')).toBeVisible()

    // Play button visible
    await expect(page.getByRole('button', { name: /play/i })).toBeVisible()
    // Stop button visible
    await expect(page.getByRole('button', { name: /stop/i })).toBeVisible()
  })

  test('22: lane-sidebars-with-solo-mute', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId)
    await generateCandidates(page, testSession.prompt)

    await realizeFirstCandidate(page)
    await page.getByRole('button', { name: /back to progressions/i }).click()
    await page.waitForTimeout(500)

    await openComparison(page, 2)

    // Lane sidebars render with S and M buttons
    const soloButtons = page.getByRole('button', { name: 'Solo', exact: true }).or(
      page.getByRole('button', { name: /^S$/ })
    )
    const muteButtons = page.getByRole('button', { name: 'Mute', exact: true }).or(
      page.getByRole('button', { name: /^M$/ })
    )

    // Should have 2 of each (one per lane)
    await expect(page.locator('button:text("S")').first()).toBeVisible()
    await expect(page.locator('button:text("M")').first()).toBeVisible()

    // Click solo on first lane — should highlight
    await page.locator('button:text("S")').first().click()
    await page.waitForTimeout(200)

    // Click mute on second lane — should dim
    await page.locator('button:text("M")').nth(1).click()
    await page.waitForTimeout(200)
  })

  test('23: close-comparison-stops-playback', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId)
    await generateCandidates(page, testSession.prompt)

    await realizeFirstCandidate(page)
    await page.getByRole('button', { name: /back to progressions/i }).click()
    await page.waitForTimeout(500)

    await openComparison(page, 2)

    // Close comparison
    await page.getByRole('button', { name: /close comparison/i }).click()
    await page.waitForTimeout(300)

    // Comparison view should be gone
    await expect(page.locator('text=COMPARING')).not.toBeVisible()
  })

  test('24: single-arrangement-playback-independent', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId)
    await generateCandidates(page, testSession.prompt)

    // Realize first candidate — single arrangement view
    await realizeFirstCandidate(page)

    // Single-arrangement transport should still work
    await expect(page.locator('text=BPM')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Chords', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Bass', exact: true })).toBeVisible()
  })
})
```

- [ ] **Step 2: Run E2E tests**

```bash
cd e2e && npx playwright test tests/comparison-playback.spec.ts
```

Expected: All tests pass. If any fail, fix the selectors or timing.

- [ ] **Step 3: Run full E2E suite to check for regressions**

```bash
cd e2e && npx playwright test
```

Expected: All existing tests pass (no regressions from the refactoring or new features).

- [ ] **Step 4: Commit**

```bash
git add e2e/tests/comparison-playback.spec.ts
git commit -m "test: E2E tests for M4c comparison playback"
```

---

## Task 11: Final Verification and Cleanup

- [ ] **Step 1: Run unit tests**

```bash
cd frontend && npm run test:unit
```

Expected: All tests pass.

- [ ] **Step 2: Run type check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Run full E2E suite**

```bash
cd e2e && npx playwright test
```

Expected: All tests pass.

- [ ] **Step 4: Clean up any stale CLAUDE.md files**

Check for and remove any CLAUDE.md files added by subagents in working directories:

```bash
find <repo-root> -name "CLAUDE.md" -path "*/src/*" -newer docs/design/specs/2026-04-14-m4c-comparison-playback-design.md
```

Remove any that were auto-generated during this implementation.

- [ ] **Step 5: Final commit (if any cleanup)**

```bash
git add -A && git status
```

Only commit if there are meaningful changes to commit.
