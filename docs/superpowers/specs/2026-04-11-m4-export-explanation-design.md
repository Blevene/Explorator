# M4 — Export and Explanation: Design Specification

**Version**: v1.0
**Date**: 2026-04-11
**Status**: Draft
**Branch**: `feat/m4-export-explanation` (to be created)

---

## 1. Overview

M4 bridges Explorator and the DAW. Users can export finalists as MIDI files for Ableton, get AI-generated explanations of why candidates work, compare arrangements side-by-side, and review a provenance trail of every decision made during exploration.

### Sub-Milestone Breakdown

| Sub-milestone | Depends On | Deliverable |
|---|---|---|
| **M4a** | M3 complete | MIDI export, JSON sidecar, RenderArtifact/ExportPackage persistence, export modal |
| **M4b** | M3 complete | CandidateExplanation (on-demand), comparison view, provenance trace + session history panel |

M4a and M4b are independent — no cross-dependency. The natural build order is M4a first (highest user value), but they could be parallelized.

### Key Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | pretty_midi for MIDI rendering, not music21 | VoicingEvent/BassNoteEvent map directly to pretty_midi Note objects (pitch, start, end, velocity). music21 requires constructing Stream objects — unnecessary indirection. |
| D2 | Two MIDI modes: combined multi-track + separate files per voice | User chose both. Combined is convenient (one drag into Ableton). Separate gives flexible routing (bass to one instrument, chords to another). |
| D3 | JSON sidecar is human-readable, not round-trip | Target consumer is the user working in Ableton. Flat structure, no internal IDs, no Neo4j references. Not designed for re-import. |
| D4 | On-demand explanation generation | Avoids burning Gemini Pro calls on candidates the user may never inspect. Click "Explain", spinner, result cached in Neo4j. |
| D5 | Comparison view uses stacked rows with shared time axis | Piano rolls aligned vertically so bar positions correspond exactly. Better for spotting voicing differences at specific beats vs. side-by-side columns. |
| D6 | Live provenance capture, no retroactive backfill | Existing sessions are test data. ProvenanceRecorder instruments graph nodes going forward. |
| D7 | Basic session history panel in M4b, not deferred | M3 lesson: data without visualization feels disjointed. Capture + display in the same milestone. |
| D8 | Dedicated export modal, not inline card action | Batch export is the primary workflow — select multiple candidates, choose formats, export once. |

### Exit Criteria

User can export finalists as MIDI for Ableton (combined or separate tracks) with a JSON sidecar, get on-demand AI explanations of candidate strengths, compare 2-3 arrangements side-by-side with aligned piano rolls and score overlays, and review a chronological history of session decisions.

---

## 2. M4a — MIDI & JSON Export

### 2.1 MIDI Renderer — `domain/export/midi_renderer.py`

Converts an ArrangementCandidate into MIDI bytes using pretty_midi.

**Inputs:**
- `ArrangementCandidate` (with resolved `VoicingPlan` and `BassLine`)
- `bpm: float` (from GenreProfile or CreativeBrief)
- `beats_per_bar: int` (from CreativeBrief meter, default 4)
- `mode: Literal["combined", "separate"]`

**Time conversion:**

Bar/beat/duration (our event model) → absolute seconds:

```
time_sec = ((bar - 1) * beats_per_bar + (beat - 1)) * (60.0 / bpm)
duration_sec = duration_beats * (60.0 / bpm)
```

**Track construction:**

- **Chord track**: Iterates `VoicingPlan.voicing_events`. For each `VoicingEvent`, converts every pitch string (e.g., `"C3"`) to a MIDI note number using a pitch-to-midi utility. Creates a `pretty_midi.Note` for each pitch with the event's start/end times and velocity 80 (default). Instrument: Acoustic Grand Piano (GM program 0).
- **Bass track**: Iterates `BassLine.note_events`. For each `BassNoteEvent`, converts the pitch string to MIDI, creates a `Note` with the event's velocity. Instrument: Electric Bass Finger (GM program 33).

**Pitch conversion:**

Reuse the existing pitch parsing from `music21_adapter.py` or `midiUtils.ts`. The backend needs a `pitch_str_to_midi(pitch: str) -> int` utility that handles:
- Standard notation: `"C4"` → 60, `"A3"` → 57
- Flats (music21 format): `"B-3"` → 58 (per existing `feedback_music21_flats` memory)
- Sharps: `"F#4"` → 66

**Output modes:**

- `combined`: Returns `bytes` — one MIDI file with two tracks (chords + bass).
- `separate`: Returns `dict[str, bytes]` — `{"chords": bytes, "bass": bytes}`, each a single-track MIDI file.

**Function signature:**

```python
def render_midi(
    voicing_plan: VoicingPlan,
    bass_line: BassLine,
    bpm: float,
    beats_per_bar: int = 4,
    mode: Literal["combined", "separate"] = "combined",
) -> bytes | dict[str, bytes]:
    ...
```

### 2.2 JSON Renderer — `domain/export/json_renderer.py`

Produces a human-readable JSON sidecar document — a reference for use alongside the DAW.

**Function signature:**

```python
def render_json(
    session: Session,
    creative_brief: CreativeBrief,
    candidate: ProgressionCandidate,
    arrangement: ArrangementCandidate,
    voicing_plan: VoicingPlan,
    bass_line: BassLine,
    scores: dict[str, float],
    mutation_summaries: list[str],
) -> str:
    ...
```

**Output structure:**

```json
{
  "explorator_version": "0.4.0",
  "exported_at": "2026-04-11T16:30:00Z",
  "session": {
    "id": "...",
    "prompt": "dreamy synthwave progression, 4 bars",
    "genre": "synthwave",
    "bpm": 118,
    "key": "C major",
    "meter": "4/4"
  },
  "candidate": {
    "id": "...",
    "label": "C",
    "role": "best",
    "chords": ["Cmaj7", "Am7", "Fmaj7", "G7"],
    "roman_numerals": ["Imaj7", "vim7", "IVmaj7", "V7"],
    "scores": {
      "tension_curve": 0.82,
      "voice_leading": 0.91,
      "register_density": 0.78,
      "playability": 0.85
    },
    "voicings": [
      {
        "bar": 1,
        "beat": 1.0,
        "chord": "Cmaj7",
        "pitches": ["C3", "E3", "G3", "B3"],
        "duration_beats": 4.0
      }
    ],
    "bass_line": [
      {
        "bar": 1,
        "beat": 1.0,
        "pitch": "C2",
        "velocity": 90,
        "duration_beats": 2.0
      }
    ],
    "lineage": {
      "origin_round": 1,
      "mutations": ["reharmonize bar 3", "smooth voice leading"]
    }
  }
}
```

**Design rules:**
- No internal Neo4j IDs in the output — use human-readable identifiers only.
- Scores are final evaluation values, not raw sub-component breakdowns.
- Lineage is a summary (mutation description strings), not the full provenance graph.
- One JSON file per candidate.

### 2.3 Export Orchestrator — `domain/export/orchestrator.py`

Coordinates rendering and persistence for an export request.

**Flow:**

1. Receives export request: `arrangement_candidate_ids`, `formats` (midi_combined, midi_separate, json).
2. For each candidate:
   a. Loads the ArrangementCandidate, VoicingPlan, BassLine, ProgressionCandidate from Neo4j.
   b. Resolves BPM and meter from CreativeBrief/GenreProfile.
   c. For each requested format, calls the appropriate renderer.
   d. Writes rendered bytes to disk at `exports/{session_id}/{package_id}/`.
   e. Creates a RenderArtifact node in Neo4j for each file.
3. Creates an ExportPackage node linking all artifacts and candidates.
4. Returns the ExportPackage with artifact metadata.

**File naming convention:**

| Format | Filename |
|---|---|
| midi_combined | `candidate-{label}-chords-bass.mid` |
| midi_separate (chords) | `candidate-{label}-chords.mid` |
| midi_separate (bass) | `candidate-{label}-bass.mid` |
| json | `candidate-{label}.json` |

### 2.4 Neo4j Persistence

**Existing models used as-is** (from `models/export.py`):

- `RenderArtifact` — artifact_type, candidate_id, path, render_metadata
- `ExportPackage` — session_id, included_candidate_ids, included_artifact_ids, formats, notes

**Existing schema constraints** (from `graph/schema.py`, lines 52-58):

Already defined for CandidateExplanation, ComparisonView, RenderArtifact, ExportPackage, ProvenanceTrace. No schema changes needed.

**New relationships:**

```cypher
(RenderArtifact)-[:RENDERS]->(ArrangementCandidate)
(ExportPackage)-[:INCLUDES]->(RenderArtifact)
(ExportPackage)-[:INCLUDES_CANDIDATE]->(ArrangementCandidate)
```

**New repositories** (following BaseRepository pattern):

| Repository | File |
|---|---|
| `RenderArtifactRepo` | `graph/render_artifact_repo.py` |
| `ExportPackageRepo` | `graph/export_package_repo.py` |

**Session cascade delete extension:**

The existing session delete endpoint must also:
1. Query all ExportPackage nodes for the session.
2. For each package, query its RenderArtifact nodes.
3. Delete the files at each artifact's `path`.
4. Delete the RenderArtifact and ExportPackage nodes.
5. Remove `exports/{session_id}/` directory.

### 2.5 API Surface

**New router:** `api/routes/exports.py`

| Method | Path | Description |
|---|---|---|
| `POST` | `/sessions/{session_id}/export` | Create export package |
| `GET` | `/sessions/{session_id}/exports` | List export packages for session |
| `GET` | `/exports/{package_id}/artifacts/{artifact_id}/download` | Download a single artifact |

**POST `/sessions/{session_id}/export` request body:**

```json
{
  "arrangement_candidate_ids": ["abc123", "def456"],
  "formats": ["midi_combined", "midi_separate", "json"]
}
```

Note: these are ArrangementCandidate IDs specifically — the export needs voicing and bass data which only exist at the arrangement level.

**POST response:** The created ExportPackage with artifact metadata (ids, filenames, types, download paths).

**Download endpoint:** Streams file bytes with:
- `Content-Type: audio/midi` or `application/json`
- `Content-Disposition: attachment; filename="candidate-C-chords-bass.mid"`

**No SSE needed.** MIDI rendering is sub-second. The POST is synchronous — render, persist, return.

### 2.6 Frontend — Export Modal

**New component:** `ExportModal.tsx`

Triggered by an "Export" button in the session toolbar (alongside existing controls in `SessionWorkspace.tsx`).

**Modal contents:**
- **Candidate selector**: Checkboxes listing all arrangement candidates with label, role badge, and chord summary. Finalists (best/runner-up/wildcard) pre-checked.
- **Format selector**: Checkboxes for Combined MIDI, Separate MIDI, JSON. Combined MIDI and JSON pre-checked.
- **Export button**: "Export N candidates" with count updating dynamically.
- **Export history**: Below the form, a collapsible list of previous exports for this session (package timestamp, candidates, formats) with re-download links.

**Post-export behavior:**
- On success, modal shows a confirmation with download links for each artifact.
- If multiple files, offer a "Download All" that zips them client-side (using JSZip or similar lightweight library).

**New store:** `exportStore.ts` — tracks export packages for the current session, loading states.

**API client additions** in `services/api.ts`:
- `createExportPackage(sessionId, candidateIds, formats)`
- `listExportPackages(sessionId)`
- `getArtifactDownloadUrl(packageId, artifactId)` (constructs the download URL)

### 2.7 Dependencies

**Backend — new pip dependency:**
- `pretty-midi` — MIDI file creation. Add to `pyproject.toml`.

**Frontend — new npm dependency:**
- `jszip` — client-side zip for multi-file downloads. Add to `package.json`.

---

## 3. M4b — Explanation, Comparison & Provenance

### 3.1 CandidateExplanation — On-Demand Generation

**Trigger:** User clicks "Explain" button on a CandidateCard. If explanation exists in Neo4j for that candidate, return it immediately. Otherwise, generate via Gemini Pro and cache.

**Prompt — `prompts/explanation.py`:**

Follows the centralized prompt pattern (returns `(user_prompt, system_prompt)` tuple).

**Prompt inputs:**
- Chord progression (symbols + Roman numerals)
- Key center and mode
- Genre name and relevant genre rules
- All evaluation scores with dimension names
- Mutation lineage summary (if candidate was mutated)

**Gemini structured output schema** (matches existing `CandidateExplanation` model):

```python
{
    "summary": str,           # One-sentence character description
    "why_it_works": list[str],          # What makes it effective in this genre
    "what_is_experimental": list[str],  # What's unconventional or risky
    "recommended_use_cases": list[str]  # Where to use it (intro, verse, bridge...)
}
```

**Model selection:** Gemini Pro (not Flash). Explanation quality matters — this is user-facing creative writing, not high-volume scoring.

**New repository:** `graph/candidate_explanation_repo.py` — CRUD for CandidateExplanation nodes + `EXPLAINS` relationship.

**New relationship:**

```cypher
(CandidateExplanation)-[:EXPLAINS]->(ArrangementCandidate)
```

### 3.2 Explanation API & Frontend

**New endpoints in `api/routes/explanations.py`:**

| Method | Path | Description |
|---|---|---|
| `POST` | `/candidates/{candidate_id}/explain` | Generate or return cached explanation |
| `GET` | `/candidates/{candidate_id}/explanation` | Get cached explanation (404 if not generated) |

The POST endpoint is the primary entry point. It checks Neo4j for an existing explanation, returns it if found, otherwise calls Gemini Pro, persists, and returns.

**Frontend — explanation on arrangement cards:**

The "Explain" button appears on ArrangementCards in the realization view (not on ProgressionCandidate cards in the generation view), since explanations require arrangement-level context (voicings, scores, bass).

- New "Explain" button on each `ArrangementCard.tsx`.
- Click triggers POST to `/candidates/{id}/explain` with the ArrangementCandidate ID.
- While waiting: button shows spinner + "Generating explanation..." text.
- On response: collapsible explanation section expands below the card's score display, showing all four fields (summary, why_it_works, what_is_experimental, recommended_use_cases).
- Subsequent clicks toggle the section open/closed (no re-fetch — cached).

### 3.3 Comparison View

**Access pattern:** User checks 2-3 candidates via checkboxes on CandidateCards, then clicks a "Compare" button that appears in the toolbar when 2+ candidates are selected.

**New component:** `ComparisonView.tsx`

**Layout — stacked rows with shared time axis:**

```
          Bar 1        Bar 2        Bar 3        Bar 4
  C ─── [piano roll ─────────────────────────────────]  best
  A ─── [piano roll ─────────────────────────────────]  runner-up
  E ─── [piano roll ─────────────────────────────────]  wildcard

  ─── Score Comparison ───────────────────────────────
  Voice Leading    C: 0.91    A: 0.87    E: 0.74
  Tension          C: 0.82    A: 0.79    E: 0.90
  Playability      C: 0.85    A: 0.88    E: 0.70
  Register         C: 0.78    A: 0.81    E: 0.92
```

**Components:**
- **Shared time axis header**: Bar numbers aligned to the piano roll grid.
- **Candidate rows**: Label + role badge on the left rail, mini piano roll spanning the full width. Piano rolls reuse the existing `PianoRoll.tsx` component in a compact/read-only mode.
- **Score comparison section**: Below the piano rolls. Each dimension on its own row with all candidate values color-coded by candidate. Highlights the leader per dimension.
- **Explanation section**: If explanations have been generated for any compared candidates, show them below scores in a collapsible section.

**Data flow:** The comparison view is purely frontend — it reads arrangement data already loaded in `candidateStore` and `arrangementStore`. No new backend endpoint needed to render the view.

**ComparisonView persistence:** When the user opens a comparison, the frontend fires a POST to record a `ComparisonView` node in Neo4j (lightweight — just the candidate IDs and timestamp). This feeds provenance without blocking the UI. The `comparison_axes` field stores the score dimensions being compared (e.g., `["voice_leading", "tension_curve", "playability", "register_density"]`). The `labels` field maps candidate IDs to their display labels (e.g., `{"abc": "C", "def": "A"}`).

**New endpoint in `api/routes/comparisons.py`:**

| Method | Path | Description |
|---|---|---|
| `POST` | `/sessions/{session_id}/comparisons` | Record a comparison event |

**New repository:** `graph/comparison_view_repo.py` — CRUD for ComparisonView nodes + `COMPARES` relationships.

**New store additions in `candidateStore.ts`:**
- `selectedForComparison: Set<string>` — arrangement candidate IDs checked for comparison.
- `toggleComparison(candidateId)` / `clearComparison()` actions.

### 3.4 Provenance Trace — Live Capture

**ProvenanceRecorder** — lightweight recorder that graph nodes call during execution.

**Design:**

```python
class ProvenanceEvent(BaseModel):
    """Single provenance event."""
    timestamp: datetime
    action: str          # generate, mutate, feedback, rank_and_select, export
    object_id: str       # ID of the primary object involved
    round_number: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)
```

The recorder is not a separate class — provenance events are appended directly to a list on `ExplorationState`:

```python
# Added to ExplorationState (state.py)
provenance_events: list[dict[str, Any]]  # Accumulated during graph execution
```

**Instrumented nodes:**

| Node | Action | Details |
|---|---|---|
| `generate` | `generate` | round_number, candidate_count, prompt summary |
| `mutate` | `mutate` | source_candidate_id, mutation_type, result_candidate_id |
| `load_memory` (feedback path) | `feedback` | feedback_text, weight_deltas |
| `rank_and_select` | `rank_and_select` | role_assignments (dict of candidate_id → role) |
| export orchestrator | `export` | candidate_ids, formats, package_id |

Each node appends its event(s) to `state["provenance_events"]` during execution. Minimal overhead — one dict append per action.

**Persistence:**

At the end of a graph run, `persist_round` (or the export orchestrator for export events) writes the accumulated events:

1. Load or create the session's `ProvenanceTrace` node.
2. Append new events to the trace's `events` list.
3. Update the node in Neo4j.

The `ProvenanceTrace` is linked to the session: `(Session)-[:HAS_PROVENANCE]->(ProvenanceTrace)`.

### 3.5 Session History Panel

**New component:** `SessionHistory.tsx`

A chronological timeline of provenance events displayed as a sidebar panel or collapsible section in `SessionWorkspace.tsx`.

**Layout:**

```
Session History
───────────────
● Generated 6 candidates              Round 1    2:31 PM
● Mutated C → reharmonize bar 3       Round 2    2:33 PM
● Feedback: "more tension in bar 2"              2:34 PM
● Ranked finalists (C, A, E)          Round 2    2:34 PM
● Exported C, E as MIDI + JSON                   2:41 PM
```

**Design:**
- Vertical timeline with action icons/dots, action description, round number (if applicable), timestamp.
- Auto-scrolls to newest event.
- Collapsible — doesn't consume space when the user is focused on exploration.
- Populated by fetching the ProvenanceTrace from the backend.

**New endpoint in `api/routes/sessions.py`:**

| Method | Path | Description |
|---|---|---|
| `GET` | `/sessions/{session_id}/provenance` | Return the session's ProvenanceTrace |

**New repository:** `graph/provenance_trace_repo.py` — CRUD for ProvenanceTrace nodes.

---

## 4. Model Updates

### 4.1 Existing Models — No Changes Needed

All M4 Pydantic models already exist in `models/export.py`:
- `ProvenanceTrace`
- `CandidateExplanation`
- `ComparisonView`
- `RenderArtifact`
- `ExportPackage`

All Neo4j schema constraints already exist in `graph/schema.py` (lines 52-60).

### 4.2 New Model

**`ProvenanceEvent`** — added to `models/export.py`:

```python
class ProvenanceEvent(BaseModel):
    """Single event in a provenance timeline."""
    timestamp: datetime
    action: str
    object_id: str
    round_number: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)
```

This is used for structured validation but stored as dicts in the ProvenanceTrace's `events` list.

### 4.3 State Addition

**`ExplorationState`** — add one field:

```python
provenance_events: list[dict[str, Any]]  # Accumulated provenance events
```

Cleared at the start of each graph invocation (same pattern as `current_round_candidates`).

---

## 5. File Storage

**Root directory:** `exports/` at the project root (sibling to `backend/`, `frontend/`).

**Structure:**

```
exports/
  {session_id}/
    {package_id}/
      candidate-C-chords-bass.mid
      candidate-C-chords.mid
      candidate-C-bass.mid
      candidate-C.json
      candidate-E-chords-bass.mid
      candidate-E.json
```

**Configuration:** Export root path is read from config (`EXPORT_DIR` env var, defaults to `./exports`).

**Lifecycle:** Files are deleted when the session is cascade-deleted. The session delete handler removes `exports/{session_id}/` after cleaning up Neo4j nodes.

**Gitignore:** `exports/` added to `.gitignore`.

---

## 6. Error Handling

| Failure | Handling |
|---|---|
| Candidate has no arrangement data | Return 400 with message identifying which candidate lacks realization. Export other candidates normally. |
| MIDI rendering fails (malformed pitch) | Log the error, skip that candidate, include warning in ExportPackage.notes. |
| Disk write fails | Return 500. No partial ExportPackage created. |
| Gemini explanation timeout | Return 504 with "Explanation generation timed out. Try again." |
| Gemini explanation malformed | Retry once with stricter prompt. If still invalid, return 502. |
| Provenance write fails | Log warning, do not fail the parent operation. Provenance is non-critical. |

---

## 7. Testing Strategy

### M4a Tests

**Unit tests:**
- `test_midi_renderer.py` — pitch conversion, time conversion, combined vs. separate modes, empty events edge case.
- `test_json_renderer.py` — output structure validation, no internal IDs present, lineage summary correctness.
- `test_export_orchestrator.py` — correct file naming, artifact count, package assembly.

**Integration tests:**
- `test_export_flow.py` — full flow from ArrangementCandidate in Neo4j through export to file on disk. Validates MIDI is parseable by pretty_midi, JSON is valid.
- Session cascade delete cleans up files.

### M4b Tests

**Unit tests:**
- `test_explanation_prompt.py` — prompt construction with various inputs (mutated vs. unmutated, different genres).
- `test_provenance_recorder.py` — event accumulation, clearing between runs.

**Integration tests:**
- `test_explanation_flow.py` — generate, cache, re-fetch returns cached (no second Gemini call).
- `test_provenance_flow.py` — run a graph execution, verify ProvenanceTrace contains expected events.

**E2E tests** (Playwright):
- Export modal opens, candidate/format selection works, download triggers.
- Explain button shows spinner, then explanation content.
- Comparison view renders with correct candidate count.
- Session history panel shows events.
