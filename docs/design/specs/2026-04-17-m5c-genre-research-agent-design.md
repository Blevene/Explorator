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

Terminal statuses: `approved`, `rejected`, `failed` (not in STEP_ORDER).

```python
GenreResearchStatus = Literal[
    "researching", "drafting", "critiquing", "refining",
    "validating", "pending_review", "approved", "rejected", "failed",
]
```

### 2.2 Pydantic Models

```python
class CritiqueIssue(BaseModel):
    """A single issue found during critique."""
    severity: Literal["major", "minor"]
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
    profile: GenreProfileYAML    # validated against schema at parse time
    rules: GenreRulesYAML        # validated against schema at parse time
    grammar: HarmonicGrammarYAML # validated against schema at parse time

class GenreCritiqueResponse(BaseModel):
    """Structured output from critique step."""
    issues: list[CritiqueIssue]
    passed: bool               # True if no major issues — skip refine

class GenreResearchJob(BaseModel):
    id: str                            # grj_{ULID}
    genre_name: str
    reference_artists: list[str]
    status: GenreResearchStatus        # typed status — see STEP_ORDER + terminal statuses
    research_log: str                  # raw research output from Pro
    critique_trail: list[CritiqueEntry]
    draft_yamls: dict[str, Any]        # {profile: {}, rules: {}, grammar: {}} — dict for Neo4j serialization
    rejection_reason: str | None = None
    error_message: str | None = None   # populated when status is "failed"
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
    critique_trail: list[dict[str, Any]]  # CritiqueEntry dicts — serialized for LangGraph transport
    refine_iteration: int              # 0, 1, or 2 — incremented by the refine node on entry
    needs_refine: bool                 # set by critique node based on major issues
    validation_errors: list[str]       # populated by validate node; empty = valid

    # Control
    status: str
    on_progress: ProgressCallback      # reuse existing type from engine/state.py
```

### 3.2 Graph Structure

```
research → draft → critique → [needs_refine?] → refine → critique
                                    ↓ no
                               validate → [valid?] → output → END
                                            ↓ no
                                          output → END (status=pending_review with errors visible)
```

```python
def build_genre_research_graph(gemini: GeminiClient, driver: AsyncDriver) -> Any:
    graph = StateGraph(GenreResearchState)

    graph.add_node("research", partial(research_genre, gemini=gemini, driver=driver))    # ModelTier.PRO
    graph.add_node("draft", partial(draft_yamls, gemini=gemini, driver=driver))          # ModelTier.FLASH
    graph.add_node("critique", partial(critique_draft, gemini=gemini, driver=driver))    # ModelTier.FLASH
    graph.add_node("refine", partial(refine_draft, gemini=gemini, driver=driver))        # ModelTier.FLASH
    graph.add_node("validate", partial(validate_draft, driver=driver))                   # deterministic
    graph.add_node("output", partial(output_draft, driver=driver))                       # persist to Neo4j

    graph.set_entry_point("research")
    graph.add_edge("research", "draft")
    graph.add_edge("draft", "critique")
    graph.add_conditional_edges("critique", route_after_critique, {
        "refine": "refine",
        "validate": "validate",
    })
    graph.add_edge("refine", "critique")
    graph.add_conditional_edges("validate", route_after_validate, {
        "output": "output",
    })
    graph.add_edge("output", END)

    return graph.compile()
```

**Per-node Neo4j status updates:** Every node receives the `driver` and calls `GenreResearchRepository.update_job(job_id, {"status": <current_status>})` on entry. This ensures crash recovery — if the server dies mid-pipeline, the Neo4j node reflects the last step entered rather than being stuck at `researching`.

### 3.3 Conditional Routing

```python
def route_after_critique(state: GenreResearchState) -> str:
    if state.get("needs_refine") and state.get("refine_iteration", 0) < 2:
        return "refine"
    return "validate"

def route_after_validate(state: GenreResearchState) -> str:
    # Always routes to output — validation errors (if any) are stored on the job
    # and surfaced in the review UI. The user decides whether to approve or reject.
    return "output"
```

**Critique → refine loop:** If critique flags major issues and refine iterations < 2, loop back. Otherwise proceed to validate (remaining issues flagged for human attention in review view).

**Validation failure handling:** If `validation_errors` is non-empty after the validate step, the output node still persists the job with status `pending_review` but includes the validation errors. The review UI surfaces these errors alongside the draft YAMLs so the user can reject with context. This avoids a `failed` state for validation issues — the user always gets to see what was generated.

**Refine iteration tracking:** The refine node MUST increment `refine_iteration` on entry (before calling the LLM). This prevents infinite loops — `route_after_critique` checks the counter.

**Error handling:** If any node raises an unhandled exception (LLM timeout, rate limit, Neo4j connection error), the route handler wraps `graph.ainvoke()` in a try/except that sets the job status to `failed` with `error_message`, emits an SSE error event, and closes the channel. This follows the existing pattern in `rounds.py`.

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

`prompts/genre_research.py` reads MD files and injects variables via `str.replace()` substitution (`{genre_name}`, `{research_log}`, `{draft_yamls}`, `{critique}`). Uses `str.replace()` instead of `str.format()` to avoid breakage when prompt templates or injected variables contain literal `{` / `}` characters (common in JSON/YAML examples within prompts and in LLM-generated content).

```python
def load_prompt(template_name: str, **kwargs: str) -> str:
    """Load an MD prompt template and inject variables."""
    path = Path(__file__).parent / "genre_research" / f"{template_name}.md"
    template = path.read_text()
    for key, value in kwargs.items():
        template = template.replace(f"{{{key}}}", str(value))
    return template
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
- Validates `genre_name`: must be a valid identifier (alphanumeric + underscores, no special characters) since it becomes a file path on approval
- Returns 409 Conflict if `genre_name` matches an existing genre (check YAML files) or an in-progress job (check Neo4j)
- Creates `GenreResearchJob` in Neo4j with status `researching`
- Creates an `SSEChannel` and stores it in an in-memory `dict[str, SSEChannel]` keyed by `job_id` (module-level `_channels` dict in the route module)
- Starts LangGraph graph execution as a background task via `asyncio.create_task()`, passing the channel's `send` method as the `on_progress` callback
- On task completion (success or failure), removes the channel from `_channels` and calls `channel.close()`
- Returns `{job_id: str}` immediately

**GET `/v1/genres/research/{job_id}`**
- Returns full `GenreResearchJob` JSON

**GET `/v1/genres/research/{job_id}/stream`**
- Looks up `SSEChannel` from in-memory `_channels[job_id]`; returns 404 if not found (job doesn't exist or already completed)
- Returns `EventSourceResponse` using the shared channel (same pattern as rounds streaming)
- Emits `genre_research` events with `{status, detail}` data
- Closes when job reaches `pending_review`, `failed`, `approved`, or `rejected`

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
- **Partial failure handling:** If YAML write succeeds but sync fails, the YAML files are deleted and 500 is returned. As a safety net, the existing `lifespan` startup hook calls `sync_genres_to_neo4j()` on server restart, which would pick up any orphaned YAML files. Status is only set to `approved` after sync succeeds.

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

Top-level "Genres" nav item. State managed by `genreResearchStore.ts` (Zustand). The view is a single-page application at route `/genres` with three inline view states (no sub-routes).

### 6.1 Design Direction

The existing Explorator aesthetic is deep blue-black surfaces (`--surface-0` through `--surface-4`), amber primary accent (`--accent-primary`), Outfit font, and subtle noise texture. The Genre Management view follows this system exactly but has its own character: it's an **agentic workflow monitor** — part library catalog, part mission control for dispatching AI research agents.

**Key design moments:**
- Genre cards in the library use genre-specific accent colors (extending the existing `--genre-*` tokens) as a left border stripe — a visual shorthand for identity
- The research progress indicator is the signature interaction: a horizontal step rail with nodes that illuminate sequentially, with a pulsing glow on the active step
- The review view presents the three YAML structures as side-by-side dossier cards — structured data displayed as labeled fields, not raw code

### 6.2 Store

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

### 6.3 View State 1: Genre Library (default)

**Layout:** Centered container (`max-w-4xl`), matching the Dashboard's centered content pattern.

**Header row:**
- Page title: "Genres" in `text-2xl font-light` with `--text-primary`
- Subtitle: "Genre library & research" in `text-xs tracking-widest uppercase` with `--text-muted` (mirrors Dashboard subtitle pattern)
- "Research New Genre" button: right-aligned, amber primary style (`--accent-primary` bg, `--surface-0` text, `rounded-lg font-medium text-sm`)

**Genre cards** (existing genres):
- `--surface-2` background, `--border-subtle` border, `rounded-xl`
- Left border accent: 3px solid genre-specific color (e.g., `--genre-dream-pop: #a78bfa`). New genres get dynamically assigned colors from a predefined palette.
- Content: display name in `text-sm font-medium --text-primary`, genre slug in `font-mono text-xs --text-muted`
- Hover: `card-interactive` class (border → `--accent-primary-dim`, bg → `--surface-3`)
- Staggered fade-in: `card-animated` with `animation-delay` per card index (`index * 50ms`)

**Pending draft cards** (research jobs awaiting review):
- Same card structure but with a status badge: amber `--accent-primary` pill badge reading "Pending Review"
- Click navigates to Review View (view state 3)

**Empty state** (if no genres exist beyond the three defaults): subtle prompt text, "No custom genres yet. Research your first one."

**Request form** (inline, appears below the button when clicked):
- Matches Dashboard input pattern: `rounded-xl p-px` gradient border wrapper → `--surface-2` inner panel
- Genre name input: `--surface-1` bg, `--border-subtle` border, placeholder "e.g. lo-fi hip hop, post-rock, ambient techno..."
- Reference artists textarea: same styling, placeholder "Optional: reference artists for style anchoring"
- Submit button: "Start Research" in amber, disabled when genre name empty
- Genre name validated client-side: lowercase, alphanumeric + underscores only (auto-slugified from display input)

### 6.4 View State 2: Research In-Progress

Replaces the library view while a research job is active. Centered layout.

**Step rail** (horizontal progress indicator):
- 5 step nodes connected by lines, horizontally centered
- Each node: 28px circle, `--surface-3` bg, `--border-default` border
- Completed steps: `--accent-tertiary` (#34d399 emerald) fill, check icon
- Active step: `--accent-primary` (#f0b429 amber) border with a subtle pulsing glow animation (`box-shadow: 0 0 12px var(--accent-primary-dim)`, animated opacity 0.4 → 0.8 over 1.5s ease-in-out infinite)
- Future steps: `--surface-3` fill, `--border-subtle` border, `--text-muted` label
- Step labels below each node: "Research", "Draft", "Critique", "Refine", "Validate" in `text-xs --text-secondary`
- Connecting lines: 2px, `--border-subtle` for future, `--accent-tertiary` for completed segments

**Substep detail panel** (below step rail):
- `--surface-2` card, `rounded-xl`, `--border-subtle` border
- Genre name as header: `text-lg font-medium --text-primary`
- Current substep text: `text-sm --text-secondary`, updates in real-time from SSE
- Text transitions with a subtle `card-fade-in` animation on each update (opacity 0→1, translateY 2px→0, 150ms)

**Refine loop indicator** (when critique → refine → critique cycles):
- The step rail shows "Refine" step with iteration badge: small `font-mono text-[10px]` circle showing "1/2" or "2/2"
- If critique passes (no refine needed), the "Refine" step shows a skip indicator (dashed border, dimmed)

**Error state** (job fails):
- Active step node turns `--score-low` (#f87171 red)
- Error message displayed in substep panel with red accent
- "Back to Library" button

### 6.5 View State 3: Review View

Shown when a draft reaches `pending_review`. Full-width within the container.

**Header:**
- Genre name: `text-xl font-medium --text-primary`
- Status badge: "Pending Review" in amber pill
- If `validation_errors` present: additional "Validation Warnings" badge in `--score-low` red

**Draft cards** (three columns on desktop, stacked on mobile):
- Three `--surface-2` cards in a `grid grid-cols-3 gap-4` layout (collapses to `grid-cols-1` on narrow viewports)
- Card headers: "Profile", "Rules", "Grammar" in `text-sm font-semibold uppercase tracking-wider --text-muted`
- Card content: structured key-value fields, not raw YAML
  - **Profile card:** Genre name, display name, harmonic vocabulary (as tag pills), tendencies (as labeled values), common devices (as list), experimentation envelope (as labeled bars)
  - **Rules card:** Rules listed with name, type badge, weight (as score bar `score-bar-animated`), description. Anti-patterns listed separately with severity badge (red for high, amber for medium)
  - **Grammar card:** Chord qualities (as tag pills), cadence archetypes (as list), harmonic rhythm defaults (as labeled values), functional motion bias (as labeled bars)
- Tag pills: `rounded-full px-2 py-0.5 text-[11px] font-mono` with `--surface-4` bg, `--text-secondary` text
- Score bars: reuse existing `score-bar-animated` pattern (colored bar proportional to 0-1 value)

**Validation errors panel** (if present):
- Below draft cards, `--surface-2` card with `--score-low` left border (3px)
- Lists each validation error as a row with error text in `text-sm --text-secondary`

**Research log & critique trail** (expandable):
- Two collapsible sections below the draft cards
- Collapsed: `--surface-2` row with section title + chevron icon
- Expanded: monospace text (`font-mono text-xs`) in a `--surface-1` pre-formatted block, `max-h-64 overflow-y-auto`
- Critique trail: shows iterations with issue severity badges (major in `--score-low`, minor in `--score-mid`), resolution text

**Action buttons** (bottom of review):
- Fixed bottom bar within the view (not global sticky — scrolls with content but always visible at the end)
- "Approve" button: `--accent-tertiary` (#34d399 emerald) bg, `--surface-0` text, `rounded-lg font-medium`
- "Reject" button: `--surface-3` bg, `--text-secondary` text, `rounded-lg font-medium`
- On reject click: inline textarea slides open with `--surface-1` bg for rejection reason, plus "Confirm Reject" button in `--score-low` red

### 6.6 Navigation Integration

The "Genres" nav item is added to the main app layout. Since the current app uses React Router with `/` (Dashboard) and `/session/:id` (SessionWorkspace), the genre view registers as `/genres`.

- Nav link: appears in the Dashboard hero area as a secondary link, or as a subtle top bar if one exists
- Active state: amber underline or highlight matching existing nav patterns
- The genre view is a standalone page (not nested within SessionWorkspace)

### 6.7 CSS Additions

New CSS added to `index.css`:

```css
/* Genre research step rail pulse */
@keyframes step-pulse {
  0%, 100% { box-shadow: 0 0 8px var(--accent-primary-dim); }
  50% { box-shadow: 0 0 16px var(--accent-primary-dim); }
}

.step-active {
  animation: step-pulse 1.5s ease-in-out infinite;
}

/* Substep text transition */
@keyframes substep-fade {
  from { opacity: 0; transform: translateY(2px); }
  to { opacity: 1; transform: translateY(0); }
}

.substep-update {
  animation: substep-fade 150ms ease-out both;
}
```

### 6.8 New CSS Custom Properties

```css
:root {
  /* Genre accent palette for dynamically-created genres */
  --genre-accent-1: #f472b6;  /* pink — assigned to first custom genre */
  --genre-accent-2: #38bdf8;  /* sky — second */
  --genre-accent-3: #fb923c;  /* orange — third */
  --genre-accent-4: #a3e635;  /* lime — fourth */
  --genre-accent-5: #e879f9;  /* fuchsia — fifth */
  /* Cycles after 5 — these supplement the existing --genre-dream-pop, --genre-synthwave, --genre-cinematic tokens */
}
```

---

## 7. Scope Boundaries

- No inline YAML editing in the UI — reject with notes and re-run, or edit files manually
- No partial approval — all three YAMLs or none
- No auto-research on session creation — genre library is explicitly managed
- No genre deletion from UI in M5c — manual file removal if needed
- `melodic_tendencies` optional — omitted if agent lacks confidence, melody generator uses defaults
- **Schema prerequisite:** `GenreProfileYAML` in `domain/style/schema.py` must be extended with an optional `melodic_tendencies: dict[str, Any] = Field(default_factory=dict)` (uses `Any` not `str` because real YAML files have mixed types: int for phrase_length, bool for rest_between_phrases) field before M5c implementation. The field already exists in the YAML files on disk but is not yet in the Pydantic schema — the validate node would reject it without this update.

---

## 8. E2E Tests

Six new tests:

| Test | Verifies |
|------|----------|
| Research job lifecycle | POST `/research` → SSE stream emits step + substep events → job reaches `pending_review` |
| Review draft content | Draft detail returns all three YAML structures + research log + critique trail (including any validation errors if present) |
| Approve flow | Approve → YAML files written to disk → genre appears in `GET /genres` list |
| New genre usable in session | After approval, start a generation session with the new genre → progression candidates are generated successfully |
| Reject flow | Reject with reason → status `rejected` → reason stored → genre not in library |
| Duplicate prevention | POST for existing genre → 409; POST for in-progress job → 409 |

---

## 9. File Inventory

### New Files

| File | Purpose |
|------|---------|
| `models/genre_research.py` | `GenreResearchJob`, `CritiqueEntry`, `CritiqueIssue`, `GenreDraftResponse`, `GenreCritiqueResponse`, `step_number()`, `STEP_ORDER` |
| `engine/genre_research_graph.py` | `GenreResearchState`, `build_genre_research_graph()`, `route_after_critique()` |
| `engine/nodes/genre_research/__init__.py` | Package init |
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
| `e2e/tests/test_genre_research.py` | 6 E2E tests |

### Modified Files

| File | Change |
|------|--------|
| `api/app.py` | Mount `genre_research.router` |
| `api/deps.py` | Add dependency provider for `GenreResearchRepository` |
| `domain/style/schema.py` | Add optional `melodic_tendencies` field to `GenreProfileYAML` |
| Frontend nav component | Add "Genres" nav item |
