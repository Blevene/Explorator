# M6 — Multi-Layer Mutation & Realization Refinement: Design Spec

**Date:** 2026-04-17
**Status:** Draft
**Depends on:** M5 (complete), M3a mutation loop, M2 realization pipeline

## 1. Overview

M6 extends the mutation system from chord-only to full arrangement-level mutation across all four realization layers (voicing, bass, groove, melody). Currently, mutation only acts on chord progressions — everything else gets rebuilt from scratch. M6 lets the user (and the search loop) say "keep the chords but make the bass more active" or "try open voicings" without losing the harmonic foundation.

Three sub-milestones:

| Sub-milestone | Feature | Scope |
|---------------|---------|-------|
| M6a | Arrangement-Level Mutation | Full spec — first build |
| M6b | Inner Voice Parts | Outline only |
| M6c | Instrument-Aware Realization | Outline only |

**Key decisions from brainstorming:**

- Four mutable layers: voicing, bass, groove, melody — each with creative direction hints
- Hybrid mutation: automatic (search loop picks based on score weakness) + manual (user triggers per-track)
- Direction hints, not parameter knobs: "more active" / "more open" / "surprise me"
- Voicing/bass/groove mutations are parameter swaps + deterministic regeneration (no LLM). Only melody mutation calls Gemini.
- Selective layer regeneration: mutating bass doesn't re-run voicing, groove, or melody
- Collision warnings when voicing mutation causes melody conflicts — user-visible, not auto-fixed

---

## 2. M6a — Arrangement-Level Mutation

### 2.1 ArrangementMutation Model

New entity. ULID prefix: `am_`.

```python
class ArrangementMutation(BaseModel):
    id: str                              # am_{ULID}
    source_arrangement_id: str           # the arrangement being mutated
    layer: Literal["voicing", "bass", "groove", "melody"]
    direction: str                       # the user's hint or auto-selected direction
    parameter_changes: dict[str, Any]    # what was changed (e.g., {"bass_mode": "syncopated"})
    result_arrangement_id: str           # the new arrangement produced
    source: Literal["auto", "manual"]    # search loop vs user-triggered
    round_number: int
    created_at: datetime
```

Stored in Neo4j as a node linked to both source and result arrangements for provenance.

### 2.2 Direction Hints Per Layer

Each layer has 3-4 creative direction hints plus "surprise me."

**Voicing:**

| Direction | Parameter Changes |
|-----------|------------------|
| "more open" | `voicing_type` → `open`, shift `register` one step up |
| "more dense" | `voicing_type` → `closed`, `density` → `dense`, `voice_count` += 1 |
| "different type" | cycle to next type from genre's `variant_voicing_types` |
| "surprise me" | random pick from genre's `variant_voicing_types` + random register shift |

**Bass:**

| Direction | Parameter Changes |
|-----------|------------------|
| "more active" | `bass_mode` → `syncopated`, `rhythmic_density` → `active` |
| "more grounding" | `bass_mode` → `pedal`, `rhythmic_density` → `sparse` |
| "different mode" | cycle to next mode from genre's `variant_bass_modes` |
| "surprise me" | random pick from `variant_bass_modes` |

**Groove:**

| Direction | Parameter Changes |
|-----------|------------------|
| "busier" | `comp_density` one step up (sparse→moderate→busy), `syncopation_level` one step up |
| "sparser" | `comp_density` one step down, `syncopation_level` one step down |
| "more swing" | `swing_amount` += 0.3 (capped at 1.0) |
| "surprise me" | random density + random syncopation within genre envelope |

**Melody:**

| Direction | Parameter Changes |
|-----------|------------------|
| "more movement" | nudge directive: "increase rhythmic density and use more leaping motion" |
| "simpler" | nudge directive: "reduce note density, favor longer note values and stepwise motion" |
| "different contour" | nudge directive: "use a contrasting contour shape from the current melody" |
| "surprise me" | nudge directive: "take a fresh creative approach to the melody" |

Melody is the only layer that re-invokes Gemini (for a new strategy). Voicing/bass/groove mutations are deterministic parameter swaps.

### 2.3 DirectionResolver Service

New service at `domain/realization/direction_resolver.py`:

```python
class DirectionResolver:
    def resolve(
        self,
        layer: str,
        direction: str,
        current_params: dict[str, Any],
        genre_profile: dict[str, Any],
    ) -> dict[str, Any]:
        """Translate creative direction into concrete parameter changes."""
```

Returns a dict of parameter changes to apply. For melody, returns `{"nudge_directive": "..."}` instead of parameter swaps.

Deterministic — no LLM call. Uses the genre profile's variant lists and preference fields to pick valid targets (e.g., won't suggest `drop2` voicing if it's not in the genre's `variant_voicing_types`).

### 2.4 Selective Layer Regeneration

New service at `domain/realization/arrangement_mutator.py`:

```python
class ArrangementMutator:
    async def mutate_layer(
        self,
        source_arrangement: dict[str, Any],
        layer: str,
        new_params: dict[str, Any],
        genre_profile: dict[str, Any],
        gemini: GeminiClient | None = None,  # only needed for melody
    ) -> dict[str, Any]:
        """Regenerate one layer of an arrangement, preserving all others."""
```

Per-layer regeneration:

| Layer mutated | What runs | What's preserved |
|---------------|-----------|-----------------|
| Voicing | `VoicingGenerator.realize()` with new params | bass, groove, melody |
| Bass | `BassLineGenerator.generate()` with new params | voicing, groove, melody |
| Groove | `GrooveGenerator.generate()` with new params | voicing, bass, melody |
| Melody | Gemini strategy call with nudge + `MelodyGenerator.realize()` | voicing, bass, groove |

The new arrangement gets a fresh ID (`ac_{ULID}`) and links back to the source via `metadata.mutated_from`. It shares the same `progression_candidate_id` — chords didn't change.

**Collision handling:** When voicing is mutated, the existing melody is preserved even if it now collides with the new voicing. The `collision_risk` evaluator flags it, and the UI surfaces a warning. The user can then mutate melody separately. This keeps layers truly independent.

### 2.5 Search Loop Integration

**Current routing after check_stop:**
```
check_stop → [persist | harmonic_mutate]
```

**M6a adds a third path:**
```
check_stop → [persist | harmonic_mutate | arrangement_mutate]
```

**Score-based routing logic:**

```python
def _route_after_stop(state: ExplorationState) -> str:
    if state.get("stop_condition_met"):
        return "persist_realization"
    
    # Compare harmonic vs arrangement score averages
    scorecards = state.get("scorecards", [])
    
    # Harmonic dimensions: harmonic_coherence, cadence_quality, novelty
    harmonic_avg = average of harmonic dimension scores across top candidates
    
    # Arrangement dimensions: voice_leading, register_density, groove_authenticity, melody_support
    arrangement_avg = average of arrangement dimension scores across top candidates
    
    if harmonic_avg < arrangement_avg - 0.5:
        return "harmonic_mutate"       # chords are clearly the weak link
    elif arrangement_avg < harmonic_avg - 0.5:
        return "arrangement_mutate"    # realization is clearly the weak link
    else:
        # Scores are close — alternate between harmonic and arrangement mutation
        round_number = state.get("round_number", 1)
        return "arrangement_mutate" if round_number % 2 == 0 else "harmonic_mutate"
```

**Arrangement mutation node in the search loop:**
1. Identifies the weakest-scoring arrangement dimension across top candidates
2. Maps dimension to layer (register_density → voicing, groove_authenticity → groove, etc.)
3. Uses DirectionResolver to pick direction based on score gap and current params
4. Calls ArrangementMutator.mutate_layer() for affected arrangements
5. Routes back to `evaluate_arrangements` (skips harmonic evaluation — chords unchanged)

**Dimension-to-layer mapping:**

| Weak Dimension | Target Layer |
|----------------|-------------|
| voice_leading_score | voicing |
| register_density_score | voicing |
| groove_authenticity | groove |
| rhythmic_coherence | groove |
| style_alignment | groove |
| melody_support_score | melody |
| collision_risk_score | voicing (to fix collision) or melody |

### 2.6 Manual Mutation API

**New endpoint:**

```
POST /v1/arrangements/{arrangement_id}/mutate
Body: {
    layer: "voicing" | "bass" | "groove" | "melody",
    direction: string
}
Response: SSE stream with progress events → final new arrangement
```

**Flow:**
1. Load source arrangement from Neo4j
2. Load genre profile
3. DirectionResolver translates direction → parameter changes
4. ArrangementMutator regenerates the target layer
5. Persist new arrangement to Neo4j
6. Evaluate the new arrangement (run arrangement evaluators)
7. Return new arrangement via SSE

**This operates outside the search loop.** One-shot "give me a variant." No ranking — the user is the judge.

### 2.7 Frontend — Mutation Popovers

**Trigger:** Right-click or long-press (300ms) on track buttons in the transport bar. Click-to-mute behavior is preserved.

A fourth button **"Groove"** is added to the transport bar between Bass and Melody.

Visual affordance: subtle `···` indicator (3 dots, `text-[8px]`, `--text-muted`) appears below each track button on hover of the transport bar area.

**Popover design:**

Appears above the track button (avoids overlapping piano roll below):

- `--surface-2` background, `--border-default` border, `rounded-lg`
- Width: `180px` fixed
- Shadow: `0 -4px 16px rgba(0,0,0,0.3)` (upward, since popover is above)
- Header row: current value in `font-mono text-[10px] --text-muted` on `--surface-3` background
- Direction rows: `px-3 py-2`, `text-xs --text-secondary`, hover `--surface-4`
- Diamond marker `◆` in the track's accent color (amber=voicing, blue=bass, `--accent-primary`=groove, emerald=melody)
- `card-animated` entrance (fade + translateY)
- Dismiss: click outside or Escape

**Loading state:** After clicking a direction, popover closes, track button shows `step-active` pulse animation until mutation completes.

**Mutation result:** New arrangement appears as a card in the arrangement sidebar with:
- Mutation badge: colored pill `"Bass → syncopated"` in the track's accent color
- Source link: `"variant of B"` in `text-[10px] --text-muted`

### 2.8 Frontend — Collision Warning Banner

When `collision_risk` > 0.3 after any mutation, a slim banner appears between transport bar and piano roll:

- Height: `32px`, `--surface-3` background, `--score-mid` (amber) left border 3px
- Warning icon + text: `text-xs --text-secondary`, "Melody-voicing collisions detected"
- "Fix melody" shortcut button: `text-xs font-medium --accent-tertiary`, triggers melody mutation with "different contour" direction
- Dismissable with X button
- `substep-fade` entrance animation

### 2.9 E2E Tests (M6a)

Six new tests:

| Test | Verifies |
|------|----------|
| Manual voicing mutation | POST mutate with layer=voicing → new arrangement with different voicing, bass/groove/melody preserved |
| Manual bass mutation | POST mutate with layer=bass → bass mode changed, voicing/groove/melody preserved |
| Manual melody mutation | POST mutate with layer=melody → new melody strategy generated, voicing/bass/groove preserved |
| Search loop arrangement mutation | Run search → arrangement mutation triggers when arrangement scores are weaker than harmonic scores |
| Collision warning | Mutate voicing to cause collision → collision_risk score increases → API returns elevated score |
| Direction resolver | DirectionResolver produces valid parameter changes for all layers and directions |

### 2.10 File Inventory (M6a)

**New files:**

| File | Purpose |
|------|---------|
| `models/arrangement_mutation.py` | `ArrangementMutation` model |
| `domain/realization/direction_resolver.py` | Direction → parameter mapping |
| `domain/realization/arrangement_mutator.py` | Selective layer regeneration |
| `engine/nodes/arrangement_mutate.py` | LangGraph node for search loop arrangement mutation |
| `prompts/melody_nudge.py` | Melody nudge directive builder |
| `graph/arrangement_mutation_repo.py` | Neo4j CRUD for ArrangementMutation |
| `api/routes/arrangement_mutations.py` | POST /arrangements/{id}/mutate endpoint |
| `frontend/src/components/MutationPopover.tsx` | Track mutation popover component |
| `frontend/src/components/CollisionWarning.tsx` | Collision warning banner |
| `e2e/tests/arrangement-mutation.spec.ts` | 6 E2E tests |

**Modified files:**

| File | Change |
|------|--------|
| `engine/graph.py` | Add `arrangement_mutate` node, update `_route_after_stop` with three-way routing |
| `engine/state.py` | Add `last_mutation_scope: "arrangement"` option |
| `api/app.py` | Mount arrangement mutations router |
| `frontend/src/components/TransportBar.tsx` | Add Groove button, right-click/long-press handlers, `···` indicators |
| `frontend/src/components/ArrangementDetail.tsx` | Add CollisionWarning between transport and piano roll |
| `frontend/src/stores/arrangementStore.ts` | Add mutation actions |
| `frontend/src/services/api.ts` | Add mutation API functions |

---

## 3. M6b Outline — Inner Voice Parts

**Purpose:** Add counterpoint lines between melody and bass — inner voice parts that fill out the harmonic texture. Think string quartet inner parts or synth pad lines weaving through the harmony.

**Key decisions (to be detailed when M6b is built):**

- **Model:** `InnerVoicePlan` (stubbed in V1 spec) specifies voice count, motion rules, register constraints per inner voice
- **Generation:** LLM strategy phase (how many voices, motion style) + deterministic realization (pitch selection with collision avoidance against all existing layers)
- **Genre-driven:** Genre profile gains an `inner_voice_tendency` field — some genres want inner voices (neo_soul, city_pop), others don't (techno, minimalism)
- **Pipeline placement:** After melody generation, before assembly
- **Evaluation:** New `InnerVoiceEvaluator` checking voice independence, spacing, collision avoidance across all layers
- **Mutation integration:** Inner voices become a fifth mutable layer using M6a infrastructure — "add more voices" / "simplify texture" / "surprise me"

**Dependencies:** M6a (arrangement mutation infrastructure), M5b (melody — inner voices must avoid melody collisions)

---

## 4. M6c Outline — Instrument-Aware Realization

**Purpose:** Adapt voicing choices to the physical and timbral constraints of specific instruments. Currently all voicing is instrument-agnostic — same rules whether targeting piano, Rhodes, guitar, or strings.

**Key decisions (to be detailed when M6c is built):**

- **Model:** `InstrumentRealizationPlan` (stubbed in V1 spec) specifies instrument roles (lead, pad, bass, rhythm) and orchestration notes
- **Instrument profiles:** Each instrument gets a profile defining playable range, max simultaneous notes, idiomatic voicing patterns (guitar avoids wide stretches, strings favor sustained voicings, Rhodes favors close-position 7ths)
- **Genre integration:** Genre profiles already have `playback_hints.melody_preset` from M5b — M6c extends to full instrument assignment per track
- **Affects VoicingGenerator:** Register limits, voice count caps, voicing type preferences become instrument-dependent
- **Frontend:** Instrument selector per track (dropdown or popover on transport bar)
- **Mutation integration:** Instrument swaps are arrangement mutations — "try this on Rhodes" triggers voicing regeneration with new constraints using M6a infrastructure

**Dependencies:** M6a (mutation infrastructure), M5b (playback_hints pattern)

---

## 5. Scope Boundaries

**In scope for M6a:**
- Four-layer arrangement mutation (voicing, bass, groove, melody)
- Direction hints with deterministic resolution (except melody)
- Selective layer regeneration
- Search loop three-way routing (harmonic vs arrangement mutation)
- Manual per-track mutation from UI
- Collision detection and user-facing warnings
- Provenance tracking (ArrangementMutation nodes in Neo4j)

**Not in scope for M6a:**
- Inner voice parts (M6b)
- Instrument-aware voicing (M6c)
- Multi-layer simultaneous mutation (one layer at a time)
- Undo/revert mutation (user can go back to original arrangement)
- Auto-fixing collisions (user-triggered, not automatic)
