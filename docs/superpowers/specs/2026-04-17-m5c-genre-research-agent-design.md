# M5c — Genre Research Agent: Design Spec

**Date:** 2026-04-17
**Status:** Draft
**Depends on:** M5 umbrella spec (sections 4.1-4.7), existing genre YAML infrastructure

## 1. Overview

M5c adds a full in-app agentic workflow for creating new genre profiles. The user requests a genre from the web UI, a LangGraph-powered agentic loop researches and drafts the YAML files, the user reviews and approves in-app, and the approved genre propagates to disk and Neo4j.

**Key decisions from brainstorming:**

- Single YAML-per-genre structure preserved (profile + rules + grammar as three separate files matching existing `genres/`, `rules/`, `grammars/` directories)
- Gemini Pro for research step only; Gemini Flash for draft/critique/refine (cost optimization)
- Drafts live in Neo4j only until approved — approval writes YAML files to disk and triggers sync
- LangGraph state machine (separate graph, not added to exploration pipeline)
- SSE progress at step + substep granularity
- Prompt templates as separate Markdown files for versioning
- `melodic_tendencies` optional in generated output — omitted if agent lacks confidence, system uses defaults
- Top-level "Genres" nav item in frontend

---

## 2. GenreResearchJob Model

Does **not** extend `BaseEntity` — its lifecycle (researching → ... → approved/rejected) doesn't map to standard active/archived semantics. ULID prefix: `grj_`. Stored as a Neo4j node.

### 2.1 Status as Single Source of Truth

Status drives step tracking. No separate `current_step` field — derive step number from status when needed for SSE.

```python
STEP_ORDER = [
    "researching",    # Step 1
    "drafting",       # Step 2
    "critiquing",     # Step 3
    "refining",       # Step 4
    "validating",     # Step 5
    "pending_review",  # Step 6
]

def step_number(status: str) -> int:
    """Derive step number from status string."""
    return STEP_ORDER.index(status) + 1 if status in STEP_ORDER else 0
```

Terminal statuses: `approved`, `rejected` (not in STEP_ORDER).

### 2.2 Pydantic Models

```python
class CritiqueIssue(BaseModel):
    """A single issue found during critique."""
    severity: str          # "major" | "minor"
    field: str             # which part of the YAML is affected
    suggestion: str        # actionable fix

class CritiqueEntry(BaseModel):
    """A single critique/refine iteration."""
    iteration: int
    issues: list[CritiqueIssue]
    passed: bool           # True if no major issues found
    resolution: str        # summary of how issues were addressed (empty on last critique if passed)

class GenreDraftResponse(BaseModel):
    """Structured output from draft and refine steps."""
    profile: dict[str, Any]    # matches GenreProfileYAML schema
    rules: dict[str, Any]      # matches GenreRulesYAML schema
    grammar: dict[str, Any]    # matches HarmonicGrammarYAML schema

class GenreCritiqueResponse(BaseModel):
    """Structured output from critique step."""
    issues: list[CritiqueIssue]
    passed: bool               # True if no major issues — skip refine

class GenreResearchJob(BaseModel):
    id: str                            # grj_{ULID}
    genre_name: str
    reference_artists: list[str]
    status: str                        # see STEP_ORDER + approved/rejected
    research_log: str                  # raw research output from Pro
    critique_trail: list[CritiqueEntry]
    draft_yamls: dict[str, Any]        # {profile: {}, rules: {}, grammar: {}}
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime
```

`research_log` and `critique_trail` are stored as JSON string properties on the Neo4j node (always read together with the job).

---

## 3. LangGraph Genre Research Graph

Separate graph from the exploration pipeline. Built via `build_genre_research_graph()` in `engine/genre_research_graph.py`.

### 3.1 State

```python
class GenreResearchState(TypedDict, total=False):
    job_id: str
    genre_name: str
    reference_artists: list[str]

    # Step outputs
    research_log: str
    draft_yamls: dict[str, Any]        # {profile: {}, rules: {}, grammar: {}}
    critique_trail: list[dict]
    refine_iteration: int              # 0, 1, or 2
    needs_refine: bool                 # set by critique node
    validation_errors: list[str]

    # Control
    status: str
    on_progress: ProgressCallback      # reuse existing type from engine/state.py
```

### 3.2 Graph Structure

```
research → draft → critique → [needs_refine?] → refine → critique
                                    ↓ no
                               validate → output → END
```

```python
def build_genre_research_graph(gemini: GeminiClient, driver: AsyncDriver) -> Any:
    graph = StateGraph(GenreResearchState)

    graph.add_node("research", partial(research_genre, gemini=gemini))    # ModelTier.PRO
    graph.add_node("draft", partial(draft_yamls, gemini=gemini))          # ModelTier.FLASH
    graph.add_node("critique", partial(critique_draft, gemini=gemini))    # ModelTier.FLASH
    graph.add_node("refine", partial(refine_draft, gemini=gemini))        # ModelTier.FLASH
    graph.add_node("validate", validate_draft)                            # deterministic
    graph.add_node("output", partial(output_draft, driver=driver))        # persist to Neo4j

    graph.set_entry_point("research")
    graph.add_edge("research", "draft")
    graph.add_edge("draft", "critique")
    graph.add_conditional_edges("critique", route_after_critique, {
        "refine": "refine",
        "validate": "validate",
    })
    graph.add_edge("refine", "critique")
    graph.add_edge("validate", "output")
    graph.add_edge("output", END)

    return graph.compile()
```

### 3.3 Conditional Routing

```python
def route_after_critique(state: GenreResearchState) -> str:
    if state.get("needs_refine") and state.get("refine_iteration", 0) < 2:
        return "refine"
    return "validate"
```

If critique flags major issues and refine iterations < 2, loop back. Otherwise proceed to validate (remaining issues flagged for human attention in review view).

### 3.4 LLM Context Per Step

| Step | Tier | Context provided |
|------|------|-----------------|
| Research | PRO | Genre name, reference artists |
| Draft | FLASH | Genre name, research log |
| Critique | FLASH | Genre name, draft YAMLs only (fresh context — no research log) |
| Refine | FLASH | Genre name, research log, draft YAMLs, critique |

The critique step uses fresh context (only draft + genre name) to ensure independent review not biased by generation rationale.

### 3.5 SSE Progress Events

Each node emits progress via `on_progress` callback at entry and at meaningful substep points:

```python
# Example from research node
await on_progress("genre_research", {"status": "researching", "detail": "Researching harmonic vocabulary..."})
await on_progress("genre_research", {"status": "researching", "detail": "Researching voicing conventions..."})
await on_progress("genre_research", {"status": "researching", "detail": "Researching bass patterns..."})
```

Event type is always `"genre_research"`. Data contains `status` (current step) and `detail` (substep description).

---

## 4. Prompt Templates

Prompts stored as Markdown files for easier tracking and versioning. A thin Python loader handles variable injection.

### 4.1 File Structure

```
prompts/genre_research/
    research.md      # Gemini Pro — deep genre research
    draft.md         # Gemini Flash — synthesize research into YAML structures
    critique.md      # Gemini Flash — independent review of draft
    refine.md        # Gemini Flash — apply critique to improve draft
```

### 4.2 Loader

`prompts/genre_research.py` reads MD files and injects variables via simple string substitution (`{genre_name}`, `{research_log}`, `{draft_yamls}`, `{critique}`).

```python
def load_prompt(template_name: str, **kwargs: str) -> str:
    """Load an MD prompt template and inject variables."""
    path = Path(__file__).parent / "genre_research" / f"{template_name}.md"
    template = path.read_text()
    return template.format(**kwargs)
```

### 4.3 Template Summaries

**research.md** — Instructs Gemini Pro to research the genre's harmonic vocabulary, voicing conventions, bass patterns, groove tendencies, common devices, and experimentation boundaries. If reference artists are provided, uses them as anchoring context. Output: unstructured text (research log).

**draft.md** — Instructs Gemini Flash to synthesize the research log into three YAML structures matching `GenreProfileYAML`, `GenreRulesYAML`, and `HarmonicGrammarYAML` schemas. `melodic_tendencies` is marked optional — include only if the research provides confident basis. Output: structured JSON via `GenreDraftResponse`.

**critique.md** — Instructs Gemini Flash to independently review draft YAMLs for musical accuracy, internal consistency, completeness relative to existing genres, and plausible weight ranges. Receives only the draft and genre name (fresh context). Output: structured JSON via `GenreCritiqueResponse`.

**refine.md** — Instructs Gemini Flash to apply the critique's suggestions, using the original research log for informed corrections. Output: structured JSON via `GenreDraftResponse` (same as draft step).

---

## 5. Backend API

Seven endpoints on a new `genre_research.router` mounted alongside the existing `genres.router` in `app.py`. All under `/v1/`.

### 5.1 Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/genres/research` | Kick off research job |
| GET | `/v1/genres/research/{job_id}` | Poll job status |
| GET | `/v1/genres/research/{job_id}/stream` | SSE progress stream |
| GET | `/v1/genres/drafts` | List pending drafts |
| GET | `/v1/genres/drafts/{job_id}` | Get draft detail |
| POST | `/v1/genres/drafts/{job_id}/approve` | Approve draft |
| POST | `/v1/genres/drafts/{job_id}/reject` | Reject draft |

### 5.2 Endpoint Details

**POST `/v1/genres/research`**
- Body: `{genre_name: str, reference_artists?: list[str]}`
- Returns 409 Conflict if `genre_name` matches an existing genre (check YAML files) or an in-progress job (check Neo4j)
- Creates `GenreResearchJob` in Neo4j with status `researching`
- Starts LangGraph graph execution as a background task
- Returns `{job_id: str}` immediately

**GET `/v1/genres/research/{job_id}`**
- Returns full `GenreResearchJob` JSON

**GET `/v1/genres/research/{job_id}/stream`**
- Returns `EventSourceResponse` using `SSEChannel` (same pattern as rounds streaming)
- Emits `genre_research` events with `{status, detail}` data
- Closes when job reaches `pending_review`, `approved`, or `rejected`

**GET `/v1/genres/drafts`**
- Returns list of jobs with `status=pending_review`
- Response: `{items: [{job_id, genre_name, created_at}]}`

**GET `/v1/genres/drafts/{job_id}`**
- Returns full detail: draft YAMLs (profile, rules, grammar), research log, critique trail
- 404 if job doesn't exist or isn't in `pending_review` status

**POST `/v1/genres/drafts/{job_id}/approve`**
- Writes three YAML files to disk:
  - `domain/style/genres/{genre_name}.yaml` (profile)
  - `domain/style/rules/{genre_name}_rules.yaml` (rules)
  - `domain/style/grammars/{genre_name}_grammar.yaml` (grammar)
- Calls `StyleService.sync_genres_to_neo4j()` to propagate to graph
- Sets job status to `approved`

**POST `/v1/genres/drafts/{job_id}/reject`**
- Body: `{reason?: str}`
- Sets job status to `rejected`, stores rejection reason

### 5.3 Neo4j Repository

New `GenreResearchRepository` in `graph/genre_research_repo.py` with CRUD operations:
- `create_job(job)` — create node
- `get_job(job_id)` — read by ID
- `update_job(job_id, updates)` — partial update (status, draft_yamls, etc.)
- `list_pending_drafts()` — filter by status
- `job_exists_for_genre(genre_name)` — check for in-progress duplicates

---

## 6. Frontend — Genre Management View

Top-level "Genres" nav item. State managed by `genreResearchStore.ts` (Zustand).

### 6.1 Store

```typescript
interface GenreResearchStore {
    // Genre library
    genres: GenreSummary[]
    pendingDrafts: GenreResearchJobSummary[]

    // Active research
    activeJobId: string | null
    activeJobStatus: string | null
    progressDetail: string | null

    // Review
    reviewDraft: GenreResearchJobDetail | null

    // Actions
    fetchGenres: () => Promise<void>
    fetchDrafts: () => Promise<void>
    startResearch: (genreName: string, referenceArtists?: string[]) => Promise<void>
    connectProgress: (jobId: string) => void
    fetchDraftDetail: (jobId: string) => Promise<void>
    approveDraft: (jobId: string) => Promise<void>
    rejectDraft: (jobId: string, reason?: string) => Promise<void>
}
```

### 6.2 View States

**Genre Library (default)**
- Lists existing genres (from `GET /v1/genres`) with display names
- Lists pending drafts (from `GET /v1/genres/drafts`) with status badges
- "Research New Genre" button opens request form

**Research In-Progress**
- Shown after submitting a research request
- Connects to SSE stream at `GET /v1/genres/research/{job_id}/stream`
- Step indicator: Research → Draft → Critique → Refine → Validate — current step highlighted
- Substep detail text below indicator (e.g., "Researching voicing conventions...")
- Follows existing SSE consumption pattern from rounds

**Review View**
- Shown when draft reaches `pending_review`
- Three formatted cards: profile, rules, grammar — rendered as readable key-value sections, not raw YAML
- Expandable panels for research log and critique trail (transparency)
- Approve and Reject buttons
- Reject shows optional reason text field

---

## 7. Scope Boundaries

- No inline YAML editing in the UI — reject with notes and re-run, or edit files manually
- No partial approval — all three YAMLs or none
- No auto-research on session creation — genre library is explicitly managed
- No genre deletion from UI in M5c — manual file removal if needed
- `melodic_tendencies` optional — omitted if agent lacks confidence, melody generator uses defaults

---

## 8. E2E Tests

Five new tests:

| Test | Verifies |
|------|----------|
| Research job lifecycle | POST `/research` → SSE stream emits step + substep events → job reaches `pending_review` |
| Review draft content | Draft detail returns all three YAML structures + research log + critique trail |
| Approve flow | Approve → YAML files on disk → genre in `GET /genres` list → usable in session |
| Reject flow | Reject with reason → status `rejected` → reason stored → not in library |
| Duplicate prevention | POST for existing genre → 409; POST for in-progress job → 409 |

---

## 9. File Inventory

### New Files

| File | Purpose |
|------|---------|
| `models/genre_research.py` | `GenreResearchJob`, `CritiqueEntry`, `CritiqueIssue`, `GenreDraftResponse`, `GenreCritiqueResponse`, `step_number()`, `STEP_ORDER` |
| `engine/genre_research_graph.py` | `GenreResearchState`, `build_genre_research_graph()`, `route_after_critique()` |
| `engine/nodes/genre_research/research.py` | Research node (ModelTier.PRO) |
| `engine/nodes/genre_research/draft.py` | Draft node (ModelTier.FLASH) |
| `engine/nodes/genre_research/critique.py` | Critique node (ModelTier.FLASH, fresh context) |
| `engine/nodes/genre_research/refine.py` | Refine node (ModelTier.FLASH) |
| `engine/nodes/genre_research/validate.py` | Validate node (deterministic — validates `draft_yamls` against `GenreProfileYAML`, `GenreRulesYAML`, `HarmonicGrammarYAML` schemas from `domain/style/schema.py`) |
| `engine/nodes/genre_research/output.py` | Output node (persist to Neo4j) |
| `prompts/genre_research/research.md` | Research prompt template (Pro) |
| `prompts/genre_research/draft.md` | Draft prompt template (Flash) |
| `prompts/genre_research/critique.md` | Critique prompt template (Flash) |
| `prompts/genre_research/refine.md` | Refine prompt template (Flash) |
| `prompts/genre_research.py` | MD loader + variable injection |
| `graph/genre_research_repo.py` | Neo4j CRUD for `GenreResearchJob` |
| `api/routes/genre_research.py` | 7 API endpoints |
| `frontend/src/stores/genreResearchStore.ts` | Zustand store |
| `frontend/src/components/GenreManagement.tsx` | Genre management page |
| `e2e/tests/test_genre_research.py` | 5 E2E tests |

### Modified Files

| File | Change |
|------|--------|
| `api/app.py` | Mount `genre_research.router` |
| `api/deps.py` | Add dependency provider for `GenreResearchRepository` |
| Frontend nav component | Add "Genres" nav item |
