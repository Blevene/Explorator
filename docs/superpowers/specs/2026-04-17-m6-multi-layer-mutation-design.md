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

New entity. ULID prefix: `am_`. Does **not** extend `BaseEntity` — it's a provenance record, not a lifecycle entity. No `status`, `version`, or `metadata` fields needed. Same reasoning as `GenreResearchJob` in M5c.

```python
class ArrangementMutation(BaseModel):
    id: str                              # am_{ULID}
    source_arrangement_id: str           # the arrangement being mutated
    layer: Literal["voicing", "bass", "groove", "melody"]
    direction: str                       # the user's hint or auto-selected direction
    parameter_changes: dict[str, Any]    # what was changed — see 2.1.1 for shapes per layer
    result_arrangement_id: str           # the new arrangement produced
    source: Literal["auto", "manual"]    # search loop vs user-triggered
    round_number: int
    created_at: datetime
```

Stored in Neo4j as a node linked to both source and result arrangements for provenance.

**2.1.1 parameter_changes shapes per layer:**

| Layer | Shape | Example |
|-------|-------|---------|
| Voicing | `{"default_voicing_type": str, "default_register": str, ...}` | `{"default_voicing_type": "open", "default_register": "high"}` |
| Bass | `{"default_bass_mode": str, "rhythmic_density": str}` | `{"default_bass_mode": "syncopated", "rhythmic_density": "active"}` |
| Groove | `{"comp_density": str, "syncopation_level": str, "swing_amount": float}` | `{"comp_density": "busy", "syncopation_level": "heavy"}` |
| Melody | `{"nudge_directive": str}` | `{"nudge_directive": "increase rhythmic density..."}` |

### 2.2 Direction Hints Per Layer

Each layer has 3-4 creative direction hints plus "surprise me."

**Voicing** (maps to `VoicingPreferences` fields):

| Direction | Parameter Changes |
|-----------|------------------|
| "more open" | `default_voicing_type` → `"open"`, `default_register` one step up on scale `[low, mid, mid_high, high]` |
| "more dense" | `default_voicing_type` → `"closed"`, `default_density` → `"dense"`, `default_voice_count` += 1 (capped at 6) |
| "different type" | `default_voicing_type` → next in genre's `variant_voicing_types` list (wraps around; if current not in list, picks first) |
| "surprise me" | `default_voicing_type` → random from genre's `variant_voicing_types`, `default_register` → random from `[low, mid, mid_high, high]` |

**Bass** (maps to `BassPreferences` fields):

| Direction | Parameter Changes |
|-----------|------------------|
| "more active" | `default_bass_mode` → `"syncopated"`, `rhythmic_density` → `"active"` |
| "more grounding" | `default_bass_mode` → `"pedal"`, `rhythmic_density` → `"sparse"` |
| "different mode" | `default_bass_mode` → next in genre's `variant_bass_modes` list (wraps around; if current not in list, picks first) |
| "surprise me" | `default_bass_mode` → random from `variant_bass_modes` |

**Groove** (maps to `groove_tendencies` fields on genre profile):

| Direction | Parameter Changes |
|-----------|------------------|
| "busier" | `comp_density` one step up on scale `[sparse, moderate, busy]`, `syncopation_level` one step up on scale `[none, light, moderate, heavy]` |
| "sparser" | `comp_density` one step down, `syncopation_level` one step down |
| "more swing" | `swing_amount` on `GroovePattern` output += 0.3 (capped at 1.0). Note: `swing_amount` lives on the generated `GroovePattern`, not on preferences — the mutator directly patches the output, then `GrooveGenerator` applies the new swing to the pattern events. |
| "surprise me" | random `comp_density` + random `syncopation_level` within genre's `experimentation_envelope.groove_deviation_tolerance` |

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

### 2.4 Arrangement Hydration

`ArrangementCandidate` stores layer **references** (FK IDs), not embedded layer data:

```python
class ArrangementCandidate(CandidateBase):
    progression_candidate_id: str
    voicing_plan_id: str | None
    bass_line_id: str | None
    melodic_complement_id: str | None
    groove_pattern_id: str | None
```

To mutate a layer, the `ArrangementMutator` needs the full layer objects. A new `ArrangementHydrator` service loads the complete "hydrated arrangement" from Neo4j:

```python
class HydratedArrangement:
    """An arrangement with all referenced layers loaded."""
    arrangement: dict[str, Any]           # ArrangementCandidate dict
    progression: dict[str, Any]           # chord symbols, key, mode
    voicing_plan: dict[str, Any] | None   # VoicingPlan with note events
    voicing_strategy: dict[str, Any] | None  # VoicingStrategyResponse (see 2.4.1)
    bass_line: dict[str, Any] | None      # BassLine with note events
    groove_pattern: dict[str, Any] | None # GroovePattern with events
    melodic_complement: dict[str, Any] | None  # MelodicComplement with note events
    genre_profile: dict[str, Any]         # full genre profile

class ArrangementHydrator:
    def __init__(self, driver: AsyncDriver) -> None: ...
    
    async def hydrate(self, arrangement_id: str) -> HydratedArrangement:
        """Load arrangement + all referenced layers + genre profile from Neo4j."""
```

Lives at `domain/realization/arrangement_hydrator.py`.

### 2.4.1 Voicing Strategy Persistence (prerequisite)

Currently `voicing_strategies` are stored in LangGraph state but **not persisted to Neo4j**. Voicing mutation needs the original strategy to patch it (e.g., change all `voicing_type` fields to `"open"`) without an LLM call.

**M6a prerequisite:** Persist voicing strategies to Neo4j as part of `persist_realization`. Each `VoicingPlan` gains a `strategy: dict[str, Any]` field storing the `VoicingStrategyResponse` dict that produced it. This is a small schema addition — `VoicingPlan.strategy` as an optional dict, persisted alongside the plan.

### 2.4.2 Current Params Extraction

The `DirectionResolver` needs `current_params` to decide what to change. These are extracted from the hydrated arrangement:

| Layer | Current Params Source |
|-------|---------------------|
| Voicing | `voicing_strategy.voicing_type`, `voicing_plan.register`, `voicing_plan.density` — or fall back to genre profile's `voicing_preferences` defaults |
| Bass | `bass_line.bass_mode`, `bass_line.rhythmic_density` — or fall back to genre profile's `bass_preferences` defaults |
| Groove | `groove_pattern.comp_density`, `groove_pattern.syncopation_level`, `groove_pattern.swing_amount` — or fall back to genre profile's `groove_tendencies` |
| Melody | Not needed — melody mutation always generates a fresh strategy with a nudge directive |

Fallback to genre defaults ensures mutation works even if layer metadata is incomplete.

### 2.4.3 Selective Layer Regeneration

New service at `domain/realization/arrangement_mutator.py`:

```python
class ArrangementMutator:
    async def mutate_layer(
        self,
        hydrated: HydratedArrangement,
        layer: str,
        new_params: dict[str, Any],
        gemini: GeminiClient | None = None,  # only needed for melody
    ) -> dict[str, Any]:
        """Regenerate one layer, preserving all others. Returns new ArrangementCandidate dict."""
```

Per-layer regeneration:

| Layer mutated | What runs | What's preserved | Cross-layer deps |
|---------------|-----------|-----------------|-----------------|
| Voicing | Patch `voicing_strategy` with new params → `VoicingGenerator.realize()` | bass, groove, melody | None |
| Bass | `BassLineGenerator.generate()` with new `BassPreferences` | voicing, groove, melody | Needs `groove_pattern` for rhythmic alignment |
| Groove | `GrooveGenerator.generate()` with new `groove_tendencies` | voicing, bass, melody | None |
| Melody | Gemini strategy call with nudge directive → `MelodyGenerator.realize()` | voicing, bass, groove | Needs `voicing_plan` note events for collision avoidance |

The new arrangement gets a fresh ID (`ac_{ULID}`) and links back to the source via `metadata.mutated_from`. It shares the same `progression_candidate_id` — chords didn't change. New layer objects (e.g., new `VoicingPlan`) get fresh IDs too. Preserved layers keep their original IDs.

**Collision handling:** When voicing is mutated, the existing melody is preserved even if it now collides with the new voicing. The `collision_risk` evaluator flags it, and the UI surfaces a warning. The user can then mutate melody separately. This keeps layers truly independent.

### 2.5 Search Loop Integration

**Current graph architecture:**
```
check_stop → [persist_realization | mutate]
mutate → [evaluate_progressions | evaluate_arrangements]  (via last_mutation_scope)
```

The existing `mutate` node already uses `last_mutation_scope` to route post-mutation. **M6a extends the existing `mutate` node** rather than adding a parallel node. The `mutate` node gains arrangement mutation capability alongside its existing harmonic mutation.

**Updated routing:**

The `_route_after_stop` function gains a third path. The existing `mutate` node is renamed to `harmonic_mutate`, and a new `arrangement_mutate` node is added:

```
check_stop → [persist_realization | harmonic_mutate | arrangement_mutate]
harmonic_mutate → evaluate_progressions  (existing behavior, unchanged)
arrangement_mutate → evaluate_arrangements  (new — skips harmonic eval)
```

**Score-based routing logic:**

The `AggregateScorecard.scores` dict contains all dimension scores as a flat dict (e.g., `{"genre_fit": 0.8, "smoothness_score": 0.6, ...}`). We partition these into harmonic vs arrangement dimensions:

```python
HARMONIC_DIMENSIONS = {"genre_fit", "emotional_fit", "theoretical_coherence", "cadence_quality", "novelty", "loopability"}
ARRANGEMENT_DIMENSIONS = {"smoothness_score", "common_tone_retention_score", "resolution_quality",
                          "register_balance_score", "spacing_quality", "groove_authenticity",
                          "rhythmic_coherence", "style_alignment", "melody_support_score", "collision_risk_score"}

def _route_after_stop(state: ExplorationState) -> str:
    if state.get("stop_condition_met"):
        return "persist_realization"
    
    scorecards = state.get("scorecards", [])
    if not scorecards:
        return "harmonic_mutate"
    
    # Average scores across top candidates, partitioned by dimension type
    harmonic_scores, arrangement_scores = [], []
    for sc in scorecards:
        scores = sc.get("scores", {})
        for dim, val in scores.items():
            if dim in HARMONIC_DIMENSIONS:
                harmonic_scores.append(val)
            elif dim in ARRANGEMENT_DIMENSIONS:
                arrangement_scores.append(val)
    
    harmonic_avg = sum(harmonic_scores) / len(harmonic_scores) if harmonic_scores else 0.5
    arrangement_avg = sum(arrangement_scores) / len(arrangement_scores) if arrangement_scores else 0.5
    
    # Threshold: 0.1 on a 0-1 scale — a 10% gap is meaningful
    if harmonic_avg < arrangement_avg - 0.1:
        return "harmonic_mutate"
    elif arrangement_avg < harmonic_avg - 0.1:
        return "arrangement_mutate"
    else:
        # Scores are close — alternate to explore both axes
        round_number = state.get("round_number", 1)
        return "arrangement_mutate" if round_number % 2 == 0 else "harmonic_mutate"
```

**Arrangement mutation node behavior:**

1. Identifies the weakest-scoring arrangement dimension across top candidates
2. Maps dimension to layer (see mapping below)
3. Auto-selects direction based on score gap and current params (see 2.5.1)
4. Calls `ArrangementMutator.mutate_layer()` for affected arrangements
5. Appends new layer objects to state lists (`voicing_plans`, `bass_lines`, etc.) — does NOT clear existing entries
6. Creates new `ArrangementCandidate` entries referencing mixed old/new layer IDs
7. Sets `last_mutation_scope` to `"arrangement"` and returns updated state
8. Routes to `evaluate_arrangements` (skips harmonic evaluation — chords unchanged)

**Dimension-to-layer mapping** (uses actual evaluation model field names):

| Weak Dimension (from `AggregateScorecard.scores`) | Target Layer |
|---------------------------------------------------|-------------|
| `smoothness_score` (VoiceLeadingEvaluation) | voicing |
| `common_tone_retention_score` (VoiceLeadingEvaluation) | voicing |
| `resolution_quality` (VoiceLeadingEvaluation) | voicing |
| `register_balance_score` (RegisterDensityEvaluation) | voicing |
| `spacing_quality` (RegisterDensityEvaluation) | voicing |
| `groove_authenticity` (GrooveEvaluation) | groove |
| `rhythmic_coherence` (GrooveEvaluation) | groove |
| `style_alignment` (GrooveEvaluation) | groove |
| `melody_support_score` (MelodyHarmonyEvaluation) | melody |
| `collision_risk_score` (MelodyHarmonyEvaluation) | melody if `melody_support_score` is also below 0.5, else voicing |

**2.5.1 Auto-Direction Selection Algorithm**

When the search loop picks a layer to mutate, it selects a direction based on the current params and which way the score needs to move:

```python
def _auto_select_direction(layer: str, weak_dimension: str, current_params: dict, genre_profile: dict) -> str:
    """Pick the most likely helpful direction based on what's weak."""
    
    if layer == "voicing":
        current_type = current_params.get("default_voicing_type", "closed")
        current_density = current_params.get("default_density", "medium")
        if weak_dimension in ("register_balance_score", "spacing_quality"):
            # spacing issues → try opening up
            return "more open" if current_type == "closed" else "different type"
        if weak_dimension in ("smoothness_score", "common_tone_retention_score"):
            # voice leading issues → try closer voicing for better continuity
            return "more dense" if current_type == "open" else "different type"
        return "surprise me"
    
    if layer == "bass":
        current_mode = current_params.get("default_bass_mode", "supportive")
        # bass issues rarely surface in scoring — default to variety
        return "different mode"
    
    if layer == "groove":
        if weak_dimension == "groove_authenticity":
            # authenticity low → try matching genre defaults more closely
            return "surprise me"  # random within genre envelope
        if weak_dimension == "rhythmic_coherence":
            current_density = current_params.get("comp_density", "moderate")
            return "sparser" if current_density == "busy" else "busier"
        return "surprise me"
    
    if layer == "melody":
        if weak_dimension == "collision_risk_score":
            return "different contour"  # change shape to avoid collisions
        if weak_dimension == "melody_support_score":
            return "more movement"  # add activity for better harmonic support
        return "surprise me"
    
    return "surprise me"
```

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

**Error handling:**

| Condition | Response |
|-----------|----------|
| `arrangement_id` not found in Neo4j | 404 `{"detail": "Arrangement not found"}` |
| `layer` not one of the four valid values | 422 `{"detail": "Invalid layer. Must be voicing, bass, groove, or melody"}` |
| `direction` not recognized for the layer | 422 `{"detail": "Invalid direction for layer"}` |
| Gemini timeout/error during melody mutation | SSE error event `{"status": "failed", "detail": "..."}`, no new arrangement created |
| Active search loop running for this session | 409 `{"detail": "Search loop in progress — wait for it to complete"}` |

**SSE events** (event type: `"arrangement_mutation"`):

```python
# Progress events
{"status": "loading", "detail": "Loading arrangement..."}
{"status": "resolving", "detail": "Applying direction: more open"}
{"status": "regenerating", "detail": "Regenerating voicing layer..."}
{"status": "evaluating", "detail": "Evaluating new arrangement..."}
# Terminal event
{"status": "complete", "detail": "Mutation complete", "arrangement_id": "ac_01J..."}
# Error event
{"status": "failed", "detail": "Melody strategy generation failed: timeout"}
```

**Flow:**
1. Validate inputs (404/422 checks)
2. Check no active search loop for this session (409 check)
3. Create SSE channel, return `EventSourceResponse`
4. Background task:
   a. Hydrate source arrangement via `ArrangementHydrator`
   b. Extract current params for the target layer
   c. `DirectionResolver.resolve()` → parameter changes
   d. `ArrangementMutator.mutate_layer()` → new arrangement
   e. Persist new arrangement + `ArrangementMutation` provenance node to Neo4j
   f. Run arrangement evaluators on the new arrangement
   g. Send `complete` event with new arrangement ID
5. On error: send `failed` event, close channel

**This operates outside the search loop.** One-shot "give me a variant." No ranking — the user is the judge. Manual mutation is disabled while a search loop round is active for the same session to prevent concurrent Neo4j writes.

### 2.7 Frontend — Mutation Popovers

**Trigger:** Right-click or long-press (300ms) on track buttons in the transport bar. Click-to-mute behavior is preserved.

A fourth button **"Groove"** is added to the transport bar between Bass and Melody. Unlike the other three track buttons, Groove is **mutation-only** — it does not have a mute/unmute function since groove is a timing template applied to other tracks, not a separate audio source. Its visual style matches the other track buttons but uses `--accent-primary` (amber) as its accent color. When no groove pattern exists on the arrangement, the button is dimmed (`opacity-40`).

Visual affordance: subtle `···` indicator (3 dots, `text-[8px]`, `--text-muted`) appears below each track button on hover of the transport bar area, signaling right-click/long-press for mutation options.

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

When `collision_risk_score` > 0.3 after any mutation, a slim banner appears between transport bar and piano roll. The 0.3 threshold means 30% or more of strong-beat positions have unison or minor-2nd collisions between melody and voicing — perceptible as "wrong notes" to most listeners. The `collision_risk_score` field on `MelodyHarmonyEvaluation` is normalized 0.0 (no collisions) to 1.0 (every strong beat collides). 0.3 is the "clearly audible" threshold.

- Height: `32px`, `--surface-3` background, `--score-mid` (amber) left border 3px
- Warning icon + text: `text-xs --text-secondary`, "Melody-voicing collisions detected"
- "Fix melody" shortcut button: `text-xs font-medium --accent-tertiary`, triggers melody mutation with "different contour" direction
- Dismissable with X button
- `substep-fade` entrance animation

### 2.9 Melody Nudge Prompt

New file: `prompts/melody_nudge.py`. Builds a modified melody strategy prompt that includes the nudge directive from the direction hint.

```python
def melody_nudge_prompt(
    original_strategy: dict[str, Any],
    nudge_directive: str,
    chord_symbols: list[str],
    key_center: str,
    mode: str,
    genre: str,
    voicing_ceiling_notes: list[str],
) -> tuple[str, str]:
    """Build a nudged melody strategy prompt. Returns (user_prompt, system_prompt)."""
```

The user prompt includes:
1. The original melody strategy (as context for what was there before)
2. The nudge directive (e.g., "increase rhythmic density and use more leaping motion")
3. The same constraints as the original melody prompt (chord symbols, key, voicing ceiling)
4. Instruction: "Generate a NEW melody strategy that addresses the nudge while respecting all constraints. Do not simply repeat the original."

System prompt: same as the standard melody strategy prompt. Tier: `ModelTier.FLASH`.

The response is a fresh `MelodicStrategyResponse` — same structured output as the original melody generation. The `MelodyGenerator.realize()` then runs deterministically on the new strategy.

### 2.10 E2E Tests (M6a)

Six new tests:

| Test | Verifies |
|------|----------|
| Manual voicing mutation | POST mutate with layer=voicing → new arrangement with different voicing, bass/groove/melody preserved |
| Manual bass mutation | POST mutate with layer=bass → bass mode changed, voicing/groove/melody preserved |
| Manual melody mutation | POST mutate with layer=melody → new melody strategy generated, voicing/bass/groove preserved |
| Search loop arrangement mutation | Run search → arrangement mutation triggers when arrangement scores are weaker than harmonic scores |
| Collision warning | Mutate voicing to cause collision → collision_risk score increases → API returns elevated score |
| Direction resolver | DirectionResolver produces valid parameter changes for all layers and directions |

### 2.11 File Inventory (M6a)

**New files:**

| File | Purpose |
|------|---------|
| `models/arrangement_mutation.py` | `ArrangementMutation` model, `HydratedArrangement` dataclass |
| `domain/realization/direction_resolver.py` | Direction → parameter mapping + auto-direction selection |
| `domain/realization/arrangement_mutator.py` | Selective layer regeneration |
| `domain/realization/arrangement_hydrator.py` | Load arrangement + all referenced layers from Neo4j |
| `engine/nodes/arrangement_mutate.py` | LangGraph node for search loop arrangement mutation |
| `prompts/melody_nudge.py` | Melody nudge prompt builder (see section 2.9) |
| `graph/arrangement_mutation_repo.py` | Neo4j CRUD for `ArrangementMutation` provenance nodes |
| `api/routes/arrangement_mutations.py` | POST /arrangements/{id}/mutate endpoint with SSE |
| `frontend/src/components/MutationPopover.tsx` | Track mutation popover component |
| `frontend/src/components/CollisionWarning.tsx` | Collision warning banner |
| `e2e/tests/arrangement-mutation.spec.ts` | 6 E2E tests |

**Modified files:**

| File | Change |
|------|--------|
| `engine/graph.py` | Rename `mutate` → `harmonic_mutate`, add `arrangement_mutate` node, update `_route_after_stop` with three-way routing |
| `engine/state.py` | `last_mutation_scope` already supports `"arrangement"` — no change needed |
| `engine/nodes/persist_realization.py` | Persist `voicing_strategies` to Neo4j alongside voicing plans (prerequisite 2.4.1) |
| `models/realization.py` | Add optional `strategy: dict[str, Any]` field to `VoicingPlan` |
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
