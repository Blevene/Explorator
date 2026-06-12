# M4c: Comparison Playback — DAW-Lane Mute/Solo

## Overview

Add audio playback to ComparisonView with per-candidate-lane mute/solo controls, enabling instant A/B/C switching between up to 3 arrangements on a shared transport.

**Why:** Visual comparison of stacked piano rolls is limited. Hearing the difference is immediately meaningful. The DAW lane approach (mute/unmute/solo) is more powerful than sequential playback because you can A/B switch instantly without waiting for a full loop.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Max lanes | 3 | Matches existing comparison selection limit |
| Transport isolation | Independent from single-arrangement playback | Comparison has different audio needs (N synth pairs). Opening comparison stops single-arrangement playback and vice versa. |
| Solo/mute model | Full DAW logic per lane | S + M buttons per lane. Solo = only soloed lanes play. Mute always wins over solo. Max 3 lanes keeps state space trivial. |
| Track granularity | Lane-level only | No per-track chords/bass controls in comparison. Single-arrangement view already handles that. Comparison is about "which arrangement sounds better overall." |
| Transport controls | Play/pause, stop, loop, tempo | Volume omitted — system volume is sufficient for relative comparison. Tempo included because arrangements can sound different at different speeds. |
| Cursor | Synchronized across all lanes, dimmed on inaudible lanes | Dimmed cursor preserves spatial awareness on silenced lanes without implying playback. |
| Architecture | Separate engine + store | `comparisonAudioEngine.ts` + `comparisonAudioStore.ts`. Clean separation from single-arrangement path. Shared utilities extracted, no premature abstractions. |

## Architecture

### New Files

**`frontend/src/stores/comparisonAudioStore.ts`**

Flat Zustand store matching the style of `audioStore.ts`:

```ts
interface ComparisonAudioState {
  // Transport
  playing: boolean
  paused: boolean
  tempo: number              // default: 120
  loop: boolean              // default: true
  currentPosition: number

  // Lane mute/solo — keyed by candidate ID
  mutedLanes: Record<string, boolean>
  soloedLanes: Record<string, boolean>

  // Setters
  setPlaying(playing: boolean): void
  setPaused(paused: boolean): void
  setTempo(tempo: number): void
  setLoop(loop: boolean): void
  setCurrentPosition(position: number): void
  toggleMute(candidateId: string): void
  toggleSolo(candidateId: string): void
  reset(): void
}
```

Lane state populates lazily — if a candidate ID isn't in the record, it's unmuted/unsoloed by default.

Audibility is computed inline wherever needed (not a store method):

```ts
const anySoloed = Object.values(soloedLanes).some(Boolean)
const audible = !mutedLanes[id] && (!anySoloed || soloedLanes[id])
```

**`frontend/src/services/comparisonAudioEngine.ts`**

Manages N synth pairs on a single Tone.js Transport. Module-level state like `audioEngine.ts`.

Key structures:
- `synths: Record<string, { poly, mono, vol }>` — one PolySynth + MonoSynth + Volume node per candidate
- All synth pairs route through their own Volume node to destination
- Volume node per lane handles mute/solo (lane-level, not per-track)

Public API:

```ts
playComparison(
  arrangements: Map<string, ArrangementDetail>,
  tempo: number,
  genre: string,
): Promise<void>
// 1. audioEngine.stop() — kill single-arrangement playback
// 2. useAudioStore.getState().reset() — clear stale per-track mute state
// 3. Create synth pairs per candidate ID
// 4. loopEnd = max duration across all arrangements
// 5. Schedule all events for all lanes on shared Transport (no per-event mute checks)
// 6. Start transport + rAF position tracking → comparisonAudioStore

pause(): void
// Pause transport, stop rAF, set comparisonAudioStore: playing=false, paused=true

resume(): void
// Resume transport, restart rAF, set comparisonAudioStore: playing=true, paused=false

stop(): void
// Stop + cancel transport, stop rAF, dispose synths, set comparisonAudioStore: playing=false, paused=false, currentPosition=0
setTempo(bpm: number): void
setLoop(enabled: boolean): void
setLaneMute(candidateId: string, muted: boolean): void
// Sets synths[candidateId].vol.mute = muted
dispose(): void
```

### Extracted Utilities

Two items extracted from `audioEngine.ts` so both engines can import them:

**`frontend/src/services/audioPresets.ts`**
- `GENRE_PRESETS` constant and `getPreset(genre)` function
- `SynthOptions` and `GenrePreset` interfaces
- `deepMerge` helper
- `buildPolySynth(T, preset)` and `buildMonoSynth(T, preset)` factory functions

**`frontend/src/services/audioUtils.ts`**
- `ensureTone()` — lazy-loads Tone.js and starts audio context on first user gesture. The module-level `Tone` reference and `isInitialised` flag live here, shared by both engines.
- `resetTone()` — sets `isInitialised = false` and `Tone = null`. Called by `audioEngine.dispose()` (and `comparisonAudioEngine.dispose()` if needed) so the audio context can be re-initialized after a full teardown.
- `normalizePitch(pitch)` — converts music21 flats (`E-3`) to Tone.js (`Eb3`)
- `normalizePitches(pitches)` — maps over array

`audioEngine.ts` is updated to import from these two files instead of defining them inline. No behavior change.

### New Components

**`frontend/src/components/ComparisonTransportBar.tsx`**

Shared transport bar at the top of ComparisonView. Controls:
- Play/pause toggle button
- Stop button
- Tempo slider (60–200 BPM)
- Loop toggle

Reads from `comparisonAudioStore`. Calls `comparisonAudioEngine` methods.

Props:
```ts
interface ComparisonTransportBarProps {
  arrangements: Map<string, ArrangementDetail>
  genre: string
  onClose: () => void
}
```

The play handler calls `comparisonAudioEngine.playComparison(arrangements, tempo, genre)` inside a try/catch. On error (e.g., audio context blocked by browser), display an inline error message — same pattern as `TransportBar.tsx`.

**`frontend/src/components/LaneSidebar.tsx`**

Per-lane sidebar replacing the current minimal label+score sidebar in ComparisonView.

Props:
```ts
interface LaneSidebarProps {
  candidateId: string
  label: string           // "A", "B", "C"
  score: number           // weighted_total
  audible: boolean        // controls opacity of label/score
}
```

Contains:
- Candidate label badge (A/B/C)
- Weighted total score
- S button — yellow (`#eab308`) background when active, default otherwise
- M button — red (`#ef4444`) background when active, default otherwise

Clicks call `comparisonAudioStore.toggleSolo(candidateId)` / `toggleMute(candidateId)`.

### Modified Components

**`frontend/src/components/ComparisonView.tsx`**

Changes:
1. Import `ComparisonTransportBar` and `LaneSidebar`
2. Replace header with `ComparisonTransportBar`
3. Replace left-rail sidebar with `LaneSidebar` per lane
4. Pass `showCursor={true}`, `dimmed={!audible}`, `currentPosition={comparisonAudioStore.currentPosition}`, and `playing={comparisonAudioStore.playing}` to each `PianoRoll`
5. Add `useEffect` on mount:
   - Call `audioEngine.stop()` to kill single-arrangement playback
   - Call `useAudioStore.getState().reset()` to clear stale per-track mute state
6. Add `useEffect` watching `mutedLanes` / `soloedLanes`:
   - Compute audibility per lane
   - Call `comparisonAudioEngine.setLaneMute(id, !audible)` for each lane
7. On unmount: call `comparisonAudioEngine.stop()` and `comparisonAudioStore.getState().reset()` to clear lane mute/solo state. This ensures reopening comparison starts fresh.

**`frontend/src/components/PianoRoll.tsx`**

Add optional props:
```ts
dimmed?: boolean           // When true, entire canvas renders at reduced opacity
currentPosition?: number   // Override store position (for comparison mode)
playing?: boolean          // Override store playing state (for comparison mode)
```

PianoRoll currently reads `playing`, `currentPosition`, and `mutedTracks` from `useAudioStore`. When `currentPosition` or `playing` props are provided, use them instead of the store values. This allows ComparisonView to pipe in values from `comparisonAudioStore` without PianoRoll needing to know which store to read from. When these props are omitted (single-arrangement mode), PianoRoll falls back to reading `useAudioStore` as before.

When `dimmed` is `true`, apply 20% opacity via CSS on the canvas container. This is independent of the existing per-track dimming from `audioStore.mutedTracks` — per-track dimming handles voicing/bass within a single arrangement, while `dimmed` handles lane-level audibility in comparison mode. Per-track dimming remains functional in comparison mode but is effectively a no-op since `audioStore.reset()` clears `mutedTracks` to `{ voicing: false, bass: false }` on comparison mount.

Cursor rendering: when `dimmed` is true, draw cursor at reduced opacity (matching the lane dimming).

**`frontend/src/services/audioEngine.ts`**

1. Replace inline `GENRE_PRESETS`, `getPreset`, `deepMerge`, `buildPolySynth`, `buildMonoSynth`, `normalizePitch`, `normalizePitches` with imports from `audioPresets.ts` and `audioUtils.ts`
2. Add cross-engine stop in `play()`:
   ```ts
   // At the top of play(), before transport.stop():
   comparisonAudioEngine.stop()
   ```

### Unchanged

- `TransportBar.tsx` — single-arrangement transport, no changes
- `audioStore.ts` — no changes
- `CandidateCard.tsx` — no changes
- `ArrangementDetail.tsx` — no changes
- `candidateStore.ts` — no changes

## Cross-Engine Coordination

Two-line handshake, no shared state:

- `comparisonAudioEngine.playComparison()` calls `audioEngine.stop()` + `useAudioStore.getState().reset()` first
- `audioEngine.play()` calls `comparisonAudioEngine.stop()` first

This ensures only one engine is ever producing audio. The `audioStore.reset()` call in the comparison engine clears any stale per-track mute state that would otherwise cause PianoRoll to dim individual tracks incorrectly in comparison mode.

## Tone.js Details

**Synth allocation:** Up to 3 candidate lanes × 2 synths (poly + mono) = 6 synth instances max. Each lane's pair shares one Volume node. Total: 6 synths + 3 Volume nodes. Well within browser audio budget.

**Event scheduling:** All lanes' events are scheduled on the single shared Transport. Unlike `audioEngine.ts` (which checks `mutedTracks` at schedule time per event), the comparison engine does NOT use schedule-time audibility checks. Lane silencing is handled exclusively via `Volume.mute` on each lane's Volume node. This is simpler, handles mid-note silencing correctly, and avoids per-event store reads. The `setLaneMute(id, muted)` method sets `synths[id].vol.mute = muted`.

**Loop end calculation:** `loopEnd = max(totalBars across all arrangements)`. Shorter arrangements will have silence at the end of the loop — correct DAW behavior.

**Position tracking:** Single rAF loop updates `comparisonAudioStore.currentPosition`. All PianoRoll instances read from this one value. Cursor position is identical across lanes by construction.

**Bar alignment:** All PianoRolls in comparison mode should render the same number of bars (the max across all arrangements) so lanes align visually. ComparisonView computes `maxBars` and passes it to each PianoRoll via the existing `barCount` mechanism or by padding arrangement data. This ensures bar lines and cursors line up across stacked lanes.

**Lazy Tone.js loading:** `ensureTone()` is extracted to `audioUtils.ts` so both engines import it. Since Tone.js is a singleton (one audio context), both engines share the same context safely.

## Visual Behavior

**Lane audibility states:**

| State | Notes | Cursor | Sidebar | Audio |
|-------|-------|--------|---------|-------|
| Audible (no solo active) | Full opacity | Full opacity, genre-colored | Full opacity | Playing |
| Soloed | Full opacity | Full opacity, genre-colored | Full opacity, S button yellow | Playing |
| Implicitly silenced (another lane soloed) | Full opacity | Full opacity | Full opacity, no button lit | Silent |
| Muted | 20% opacity | 20% opacity | 20% opacity, M button red | Silent |
| Muted + Soloed | 20% opacity | 20% opacity | 20% opacity, S yellow + M red | Silent (mute wins) |

**Rationale for "implicitly silenced" vs "muted" visual treatment:** When lane B is soloed, lane A goes silent but isn't explicitly muted — the user didn't choose to silence it. Keeping it visually full helps the user remember what's happening (solo on B) vs what they did (mute on A). Only explicit mute dims the lane.

## Testing

**Unit tests — `comparisonAudioStore`:**
- Toggle mute on/off
- Toggle solo on/off
- Audibility: no solo active → all unmuted lanes audible
- Audibility: one lane soloed → only that lane audible (unless also muted)
- Audibility: mute wins over solo
- Reset clears all state

**E2E tests (Playwright):**
- Open comparison with 2+ candidates → transport bar and lane sidebars render
- Click play → cursors appear and move on all lanes
- Click solo on lane B → lanes A/C dim (if muted behavior) or stay visible (if just implicitly silenced), audio state changes
- Click mute on lane B while soloed → all lanes silent
- Click stop → cursors reset to position 0
- Navigate to single-arrangement and click play → comparison playback stops
- Open comparison while single-arrangement is playing → single-arrangement stops

## Scope Boundaries

**In scope:**
- Comparison playback with lane-level mute/solo
- Shared transport (play/pause/stop/tempo/loop)
- Synchronized cursor across lanes
- Cross-engine coordination
- Utility extraction from audioEngine

**Out of scope:**
- Per-track (chords/bass) mute within comparison lanes
- Volume control in comparison transport
- Cross-lane track mixing (e.g., bass from A + chords from B)
- Keyboard shortcuts for mute/solo
- Waveform visualization
