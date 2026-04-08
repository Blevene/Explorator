# M2c: Playback & Visualization Design

**Date**: 2026-04-08
**Status**: Approved
**Milestone**: M2c (of M2a/M2b/M2c split)
**Depends on**: M2b Arrangement Evaluation (complete)

## 1. Overview

M2c adds the frontend experience for browsing, visualizing, and hearing arrangements. Users select a progression, trigger realization, then explore arrangement variants through a split-panel view with a piano roll visualization and Tone.js playback.

This completes the full M2 exit criteria: "explore realizations, see scorecards, hear basic playback."

### Key Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | All three components in one milestone | Piano roll without playback is less useful; they deliver value together |
| D2 | Read-only piano roll (no editing) | Exploration tool, not an editor; editing is massive scope |
| D3 | Genre-matched Tone.js synths with PolySynth/MonoSynth defaults | Marginally more work than basic synths, dramatically better sound per genre |
| D4 | Full transport (play/pause/stop, tempo, loop, mute, volume) | Producers expect these controls; per-track mute isolates voicing vs bass |
| D5 | Split-panel layout (list left, detail right) | DAW-adjacent feel; matches previous design exploration preference |
| D6 | Single-progression realization per trigger | Batch realization deferred; simpler UX for M2c |

### Design Language

See `docs/DESIGN.md` for the full studio monitor aesthetic: dark foundation, amber voicing notes, cyan bass notes, genre-specific accents, monospace musical data.

## 2. Component Architecture

### New Components

| Component | Responsibility |
|---|---|
| `ArrangementList.tsx` | Left panel — compact arrangement cards grouped by ArrangementFamily |
| `ArrangementCard.tsx` | Single arrangement summary: voicing type + bass mode badges, score bar |
| `ArrangementDetail.tsx` | Right panel container — orchestrates transport + piano roll + scores |
| `PianoRoll.tsx` | Canvas-based pitch grid visualization (hero element) |
| `TransportBar.tsx` | Play/pause/stop, tempo slider, loop, per-track mute, volume |
| `ScorePanel.tsx` | Horizontal bar chart of 9 scoring dimensions, collapsible |

### Modified Components

| Component | Changes |
|---|---|
| `SessionWorkspace.tsx` | Add view mode toggle (generation / realization), realization trigger flow |
| `CandidateCard.tsx` | Add "Realize" button |

### New Stores

| Store | State |
|---|---|
| `arrangementStore.ts` | arrangements, families, selectedArrangementId, loading, error |
| `audioStore.ts` | playing, paused, tempo, loop, mutedTracks, volume, currentBar |

### New Services

| Service | Responsibility |
|---|---|
| `audioEngine.ts` | Tone.js wrapper: init context, create synths, schedule playback, genre presets |
| `midiUtils.ts` | Named pitch → MIDI number conversion (e.g., "C4" → 60) |

### New Dependencies

- `tone` (Tone.js) — audio synthesis. No other new deps.

## 3. Data Flow

```
User clicks "Realize" on CandidateCard
  → POST /v1/sessions/{id}/realization-rounds (SSE stream)
  → SSE progress shown in PromptBar (reuses existing progress pattern)
  → On realization_completed:
    → Workspace switches to "realization" view mode
    → GET /v1/candidates/{id}/arrangements → arrangementStore
    → ArrangementList renders grouped cards

User clicks ArrangementCard
  → GET /v1/arrangements/{id} → full detail with voicing_events + bass_events
  → ArrangementDetail renders: TransportBar + PianoRoll + ScorePanel

User clicks Play
  → audioEngine.play(arrangement, tempo, genre)
  → Tone.js schedules notes, Transport starts
  → audioStore.currentBar updates via requestAnimationFrame
  → PianoRoll playback cursor sweeps in sync
```

**No new backend endpoints needed.** M2a + M2b already provide all required API surface:
- `POST /v1/sessions/{id}/realization-rounds` — trigger realization (SSE)
- `GET /v1/candidates/{id}/arrangements` — list with scores, status, rank
- `GET /v1/arrangements/{id}` — full detail with voicing_plan + bass_line + scorecard

## 4. Piano Roll

Canvas-based rendering for performance.

### Grid

- **X axis**: bars divided into beats. Each bar = `barWidth` px (e.g., 200px). Total width = bars × barWidth. Horizontally scrollable for long progressions.
- **Y axis**: MIDI pitch range. Auto-calculated from actual notes: find min/max MIDI across all voicing + bass events, add 1 octave padding each side. Each semitone = `rowHeight` px (e.g., 8px).
- **Grid lines**: beat lines at `slate-800`, bar lines at `slate-700`. Bar numbers at top.
- **Pitch labels**: octave markers (C2, C3, C4, C5) on left edge. Not every semitone.

### Note Rendering

- **Voicing notes**: amber (`amber-400`) rectangles. One per pitch in `VoicingEvent.pitches[]`. Positioned at correct bar/beat × MIDI row. Width = `duration_beats / 4 * barWidth`. Height = `rowHeight - 1px`. Rounded corners (2px).
- **Bass notes**: cyan (`cyan-400`) rectangles. Same positioning logic from `BassNoteEvent`.
- **Muted tracks**: notes fade to 20% opacity when track is muted.

### MIDI Conversion

Named pitches → MIDI via a frontend lookup table in `midiUtils.ts`. No music21 in the browser.

```
C4 = 60, C#4 = 61, D4 = 62, ... B4 = 71, C5 = 72
Y position = (maxMidi - noteMidi) * rowHeight
```

Handles flats: `B-4` (music21 format) → `Bb4` → MIDI 70.

### Playback Cursor

- Thin vertical line (2px, genre accent color) sweeping left-to-right.
- Position synced to `Tone.Transport.position` via `requestAnimationFrame` → `audioStore.currentBar`.
- Only visible during playback.

### Load Animation

Notes fade in with staggered delay per bar (left to right, 50ms per bar) per DESIGN.md.

## 5. Audio Engine

`audioEngine.ts` encapsulates all Tone.js interaction. React components interact only via `audioStore`.

### Synth Configuration

```
Default voicing: Tone.PolySynth(Tone.Synth)
Default bass: Tone.MonoSynth
```

### Genre Presets (parameter overrides)

**Dream Pop:**
- Voicing: attack 0.3s, release 1.5s, volume -12dB
- Bass: sine oscillator, attack 0.1s, release 1.0s

**Synthwave:**
- Voicing: attack 0.01s, release 0.4s, sawtooth oscillator, slight detune
- Bass: square oscillator, attack 0.005s, release 0.3s

**Cinematic:**
- Voicing: attack 0.15s, release 2.0s, triangle oscillator
- Bass: sine oscillator, attack 0.2s, release 2.0s

### Scheduling

1. `audioEngine.play(arrangement, tempo, genre)` called on play
2. Reads `voicing_events` and `bass_events` from arrangement data
3. Pitches are already in Tone.js-compatible format ("C4", "E4", etc.)
4. Schedules via `Tone.Transport`:
   - Voicing: `polySynth.triggerAttackRelease(pitches, duration, time)`
   - Bass: `monoSynth.triggerAttackRelease(pitch, duration, time)`
   - Time = beat position converted to seconds at current BPM
5. Loop: `Tone.Transport.loop = true`, `loopEnd` = total bars in beats notation

### Muting

Each synth has independent `Tone.Volume` node. Mute = volume to -Infinity. Unmute = restore to genre preset level.

### Position Reporting

`requestAnimationFrame` loop reads `Tone.Transport.seconds`, converts to bar position, writes to `audioStore.currentBar`. Piano roll cursor redraws.

### Lifecycle

Audio context initialized on first user interaction (browser autoplay policy). `audioEngine.init()` called on first play click, not on page load. Subsequent plays reuse the context.

## 6. Transport Bar

48px fixed height, top of detail panel.

| Control | Type | Default | Behavior |
|---|---|---|---|
| Play/Pause | Toggle icon | Paused | Start/resume or pause. Icon swaps. |
| Stop | Icon button | — | Stop and reset to bar 1. |
| Tempo | Slider + number | 120 BPM | Range 60-200. Updates Transport.bpm in real-time. |
| Loop | Toggle icon | On | Active = genre accent color. |
| Mute Voicing | Toggle icon | Unmuted | Amber when active, dimmed when muted. |
| Mute Bass | Toggle icon | Unmuted | Cyan when active, dimmed when muted. |
| Volume | Horizontal slider | -6dB | Range -60dB to 0dB. |

All controls read/write `audioStore`. No direct Tone.js imports in the component.

Styling: minimal chrome, icons without borders, `slate-500` default, `slate-200` hover, genre accent for active toggles. Tooltips on hover, no visible labels.

## 7. Score Panel

Below piano roll, collapsible (default expanded).

**Layout:** Horizontal bar chart with two groups:

**Arrangement scores** (M2b evaluators):
- voice_leading, register_density, playability

**Progression scores** (M1, shared across variants):
- genre_fit, emotional_fit, theoretical_coherence, cadence_quality, novelty, loopability

Each dimension: thin horizontal bar, width proportional to score (0-10), value label at right. Color per DESIGN.md score colors (emerald 8+, amber 6-8, rose <6).

Weighted total displayed prominently above the bars.

Bar widths animate on load (200ms ease-out).

## 8. Workspace Integration

### View Modes

`SessionWorkspace` gains a `viewMode` state: `"generation"` | `"realization"`.

**Generation mode** (default): existing M1 view — PromptBar + CandidateCard grid. No changes except "Realize" button on cards.

**Realization mode**: split-panel — ArrangementList (left, 280px) + ArrangementDetail (right, flex). Back link at top returns to generation mode.

### Realization Trigger

CandidateCard "Realize" button:
1. POST realization-round with that single candidate's ID
2. SSE progress shown in PromptBar (reuses progress pill pattern with M2a/M2b node names: load_context, plan_voicings, generate_bass, assemble, evaluate_arrangements, rank_and_select, persist_realization)
3. On `realization_completed`: switch to realization mode, load arrangements

### Arrangement List

Left panel, grouped by `ArrangementFamily`:
- Family header: progression chord symbols (e.g., "Cmaj7 → Am9 → Fmaj7 → G7")
- Variant cards below: badges for voicing type + bass mode, weighted_total score bar
- Selected card: left border in genre accent, subtle background lift
- Cards ordered by rank_within_round (best first)
- "selected" status cards shown normally, "rejected" cards dimmed/collapsed

## 9. File Structure

### New Files

```
frontend/src/
  components/
    ArrangementList.tsx
    ArrangementCard.tsx
    ArrangementDetail.tsx
    PianoRoll.tsx
    TransportBar.tsx
    ScorePanel.tsx
  stores/
    arrangementStore.ts
    audioStore.ts
  services/
    audioEngine.ts
    midiUtils.ts
```

### Modified Files

```
frontend/src/
  views/SessionWorkspace.tsx      # view mode toggle, realization flow
  components/CandidateCard.tsx    # "Realize" button
  services/api.ts                 # arrangement types + fetch wrappers
  package.json                    # add tone dependency
```

## 10. API Types (frontend)

New TypeScript types in `services/api.ts`:

```typescript
interface ArrangementSummary {
  id: string
  status: "draft" | "selected" | "rejected"
  progression_candidate_id: string
  voicing_plan_id: string
  bass_line_id: string
  weighted_total: number
  rank_within_round: number
  rationale: string
}

interface ArrangementDetail extends ArrangementSummary {
  voicing_plan: {
    global_strategy: string
    density_level: string
    register_profile: string
    voicing_events: VoicingEvent[]
  }
  bass_line: {
    style_mode: string
    note_events: BassNoteEvent[]
  }
  scorecard?: {
    scores: Record<string, number>
    weighted_total: number
    rank_within_round: number
  }
}

interface VoicingEvent {
  bar: number
  beat: number
  duration_beats: number
  pitches: string[]
  chord_symbol: string
}

interface BassNoteEvent {
  bar: number
  beat: number
  duration_beats: number
  pitch: string
  velocity: number
}
```

## 11. Performance Considerations

- **Piano roll**: Canvas rendering, not DOM elements. Redraws only on arrangement change or playback cursor update.
- **Playback cursor**: `requestAnimationFrame` loop, lightweight (reads one value, draws one line).
- **Audio scheduling**: All notes scheduled upfront on play, not per-frame. Tone.js Transport handles timing.
- **Arrangement list**: Static after load. No real-time updates needed.
- **Audio context**: Lazy init on first play. No overhead on page load.

## 12. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Browser autoplay policy blocks audio | No sound on first click | Init audio context on user gesture; show "Click to enable audio" if needed |
| Tone.js bundle size (~150KB gzipped) | Slower initial load | Lazy import: `const Tone = await import('tone')` on first play |
| Canvas piano roll blurry on HiDPI | Fuzzy rendering | Set canvas width/height to `devicePixelRatio * CSS size`, scale context |
| Named pitches with flats (music21 "B-4" format) | MIDI conversion fails | midiUtils normalizes: "B-4" → "Bb4" → MIDI 70 |
| Long progressions overflow piano roll width | Notes too compressed | Horizontal scroll with fixed barWidth; no dynamic compression |
| Genre not available in frontend | Can't apply synth preset | API already returns genre in session data; fall back to default preset |
