# M5c Genre Research Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an in-app agentic workflow for researching and creating new genre profiles via a LangGraph pipeline with SSE progress streaming and a React genre management UI.

**Architecture:** A separate LangGraph state graph (6 nodes: research → draft → critique → refine → validate → output) with its own `GenreResearchState`, persisted to Neo4j via `GenreResearchRepository`. Frontend is a new `/genres` route with three view states (library, progress, review). Prompts are Markdown templates loaded by a thin Python loader.

**Tech Stack:** Python 3.12, FastAPI, LangGraph, Neo4j, Pydantic, sse-starlette, Gemini Pro/Flash, React 19, Zustand, Tailwind CSS, Playwright (E2E)

**Spec:** `docs/superpowers/specs/2026-04-17-m5c-genre-research-agent-design.md`

---

## File Map

### New Files (Backend)

| File | Responsibility |
|------|---------------|
| `backend/src/explorator/models/genre_research.py` | Pydantic models: `GenreResearchJob`, `CritiqueEntry`, `CritiqueIssue`, `GenreDraftResponse`, `GenreCritiqueResponse`, `STEP_ORDER`, `step_number()` |
| `backend/src/explorator/graph/genre_research_repo.py` | Neo4j CRUD for `GenreResearchJob` nodes |
| `backend/src/explorator/prompts/genre_research.py` | MD template loader with `str.replace()` injection |
| `backend/src/explorator/prompts/genre_research/research.md` | Research prompt (Gemini Pro) |
| `backend/src/explorator/prompts/genre_research/draft.md` | Draft prompt (Gemini Flash) |
| `backend/src/explorator/prompts/genre_research/critique.md` | Critique prompt (Gemini Flash, fresh context) |
| `backend/src/explorator/prompts/genre_research/refine.md` | Refine prompt (Gemini Flash) |
| `backend/src/explorator/engine/genre_research_graph.py` | `GenreResearchState`, `build_genre_research_graph()`, routing functions |
| `backend/src/explorator/engine/nodes/genre_research/__init__.py` | Package init |
| `backend/src/explorator/engine/nodes/genre_research/research.py` | Research node (ModelTier.PRO) |
| `backend/src/explorator/engine/nodes/genre_research/draft.py` | Draft node (ModelTier.FLASH) |
| `backend/src/explorator/engine/nodes/genre_research/critique.py` | Critique node (ModelTier.FLASH) |
| `backend/src/explorator/engine/nodes/genre_research/refine.py` | Refine node (ModelTier.FLASH) |
| `backend/src/explorator/engine/nodes/genre_research/validate.py` | Validate node (deterministic) |
| `backend/src/explorator/engine/nodes/genre_research/output.py` | Output node (persist to Neo4j) |
| `backend/src/explorator/api/routes/genre_research.py` | 7 API endpoints |

### New Files (Frontend)

| File | Responsibility |
|------|---------------|
| `frontend/src/stores/genreResearchStore.ts` | Zustand store for genre management state + actions |
| `frontend/src/components/GenreManagement.tsx` | Genre management page (library + progress + review views) |

### New Files (Tests)

| File | Responsibility |
|------|---------------|
| `backend/tests/unit/models/test_genre_research.py` | Model validation tests |
| `backend/tests/unit/domain/test_genre_research_validate.py` | Validate node tests (deterministic) |
| `backend/tests/unit/engine/test_genre_research_graph.py` | Graph routing tests |
| `e2e/tests/genre-research.spec.ts` | 6 E2E tests |

### Modified Files

| File | Change |
|------|--------|
| `backend/src/explorator/domain/style/schema.py` | Add optional `melodic_tendencies` field to `GenreProfileYAML` |
| `backend/src/explorator/api/app.py` | Mount `genre_research.router` |
| `backend/src/explorator/api/deps.py` | Add `get_genre_research_repo()` dependency |
| `frontend/src/services/api.ts` | Add genre research API functions |
| `frontend/src/App.tsx` | Add `/genres` route |
| `frontend/src/index.css` | Add `step-pulse` and `substep-fade` animations, genre accent palette |

---

## Task 1: Schema Prerequisite — Add `melodic_tendencies` to `GenreProfileYAML`

**Files:**
- Modify: `backend/src/explorator/domain/style/schema.py`
- Test: `backend/tests/unit/domain/test_genre_loader.py`

- [ ] **Step 1: Write test that validates a genre YAML with melodic_tendencies**

Add to `backend/tests/unit/domain/test_genre_loader.py`:

```python
def test_genre_profile_accepts_melodic_tendencies():
    data = {
        "genre": "test_genre",
        "display_name": "Test Genre",
        "version": 1,
        "melodic_tendencies": {
            "motion_preference": "stepwise",
            "range_placement": "above_voicing",
            "density": "sparse",
        },
    }
    from explorator.domain.style.schema import GenreProfileYAML
    profile = GenreProfileYAML.model_validate(data)
    assert profile.melodic_tendencies["motion_preference"] == "stepwise"


def test_genre_profile_works_without_melodic_tendencies():
    data = {
        "genre": "test_genre",
        "display_name": "Test Genre",
        "version": 1,
    }
    from explorator.domain.style.schema import GenreProfileYAML
    profile = GenreProfileYAML.model_validate(data)
    assert profile.melodic_tendencies == {}
```

- [ ] **Step 2: Run tests to verify the first test fails**

Run: `cd backend && python -m pytest tests/unit/domain/test_genre_loader.py::test_genre_profile_accepts_melodic_tendencies -v`
Expected: FAIL — `melodic_tendencies` field not recognized or stripped

- [ ] **Step 3: Add `melodic_tendencies` to `GenreProfileYAML`**

In `backend/src/explorator/domain/style/schema.py`, add after the `groove_tendencies` field:

```python
    melodic_tendencies: dict[str, str] = Field(default_factory=dict)
```

- [ ] **Step 4: Run both tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/domain/test_genre_loader.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/domain/style/schema.py backend/tests/unit/domain/test_genre_loader.py
git commit -m "feat(m5c): add melodic_tendencies to GenreProfileYAML schema"
```

---

## Task 2: GenreResearchJob Models

**Files:**
- Create: `backend/src/explorator/models/genre_research.py`
- Create: `backend/tests/unit/models/test_genre_research.py`

- [ ] **Step 1: Write model tests**

Create `backend/tests/unit/models/test_genre_research.py`:

```python
"""Tests for genre research models."""

from datetime import datetime, timezone

import pytest

from explorator.models.genre_research import (
    STEP_ORDER,
    CritiqueEntry,
    CritiqueIssue,
    GenreCritiqueResponse,
    GenreDraftResponse,
    GenreResearchJob,
    step_number,
)


class TestStepNumber:
    def test_researching_is_step_1(self):
        assert step_number("researching") == 1

    def test_pending_review_is_step_6(self):
        assert step_number("pending_review") == 6

    def test_approved_returns_0(self):
        assert step_number("approved") == 0

    def test_failed_returns_0(self):
        assert step_number("failed") == 0

    def test_unknown_returns_0(self):
        assert step_number("bogus") == 0


class TestCritiqueIssue:
    def test_valid_major_issue(self):
        issue = CritiqueIssue(severity="major", field="harmonic_vocabulary", suggestion="Add more chord types")
        assert issue.severity == "major"

    def test_invalid_severity_rejected(self):
        with pytest.raises(Exception):
            CritiqueIssue(severity="critical", field="x", suggestion="y")


class TestGenreResearchJob:
    def test_minimal_job(self):
        job = GenreResearchJob(
            id="grj_01JTEST",
            genre_name="lo_fi_hip_hop",
            reference_artists=["Nujabes"],
            status="researching",
            research_log="",
            critique_trail=[],
            draft_yamls={},
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        assert job.genre_name == "lo_fi_hip_hop"
        assert job.error_message is None

    def test_failed_job_with_error(self):
        job = GenreResearchJob(
            id="grj_01JTEST",
            genre_name="test",
            reference_artists=[],
            status="failed",
            research_log="",
            critique_trail=[],
            draft_yamls={},
            error_message="LLM timeout",
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        assert job.status == "failed"
        assert job.error_message == "LLM timeout"


class TestGenreDraftResponse:
    def test_validates_with_typed_schemas(self):
        resp = GenreDraftResponse(
            profile={"genre": "test", "display_name": "Test", "version": 1},
            rules={"rules": [], "anti_patterns": []},
            grammar={
                "genre_profile_id": "genre_test_01",
                "preferred_chord_qualities": [],
                "allowed_borrowed_chords": [],
                "cadence_archetypes": [],
            },
        )
        assert resp.profile.genre == "test"
        assert resp.rules.rules == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/models/test_genre_research.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create the models module**

Create `backend/src/explorator/models/genre_research.py`:

```python
"""Genre research agent models."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from explorator.domain.style.schema import (
    GenreProfileYAML,
    GenreRulesYAML,
    HarmonicGrammarYAML,
)

GenreResearchStatus = Literal[
    "researching",
    "drafting",
    "critiquing",
    "refining",
    "validating",
    "pending_review",
    "approved",
    "rejected",
    "failed",
]

STEP_ORDER = [
    "researching",
    "drafting",
    "critiquing",
    "refining",
    "validating",
    "pending_review",
]


def step_number(status: str) -> int:
    """Derive step number from status string."""
    return STEP_ORDER.index(status) + 1 if status in STEP_ORDER else 0


class CritiqueIssue(BaseModel):
    """A single issue found during critique."""

    severity: Literal["major", "minor"]
    field: str
    suggestion: str


class CritiqueEntry(BaseModel):
    """A single critique/refine iteration."""

    iteration: int
    issues: list[CritiqueIssue] = Field(default_factory=list)
    passed: bool
    resolution: str = ""


class GenreDraftResponse(BaseModel):
    """Structured output from draft and refine steps."""

    profile: GenreProfileYAML
    rules: GenreRulesYAML
    grammar: HarmonicGrammarYAML


class GenreCritiqueResponse(BaseModel):
    """Structured output from critique step."""

    issues: list[CritiqueIssue] = Field(default_factory=list)
    passed: bool


class GenreResearchJob(BaseModel):
    """A genre research job tracked in Neo4j."""

    id: str
    genre_name: str
    reference_artists: list[str] = Field(default_factory=list)
    status: GenreResearchStatus
    research_log: str = ""
    critique_trail: list[CritiqueEntry] = Field(default_factory=list)
    draft_yamls: dict[str, Any] = Field(default_factory=dict)
    rejection_reason: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/models/test_genre_research.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/models/genre_research.py backend/tests/unit/models/test_genre_research.py
git commit -m "feat(m5c): add GenreResearchJob and related models"
```

---

## Task 3: GenreResearchRepository (Neo4j CRUD)

**Files:**
- Create: `backend/src/explorator/graph/genre_research_repo.py`
- Modify: `backend/src/explorator/api/deps.py`

- [ ] **Step 1: Create the repository**

Create `backend/src/explorator/graph/genre_research_repo.py`:

```python
"""Neo4j CRUD for GenreResearchJob nodes."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from neo4j import AsyncDriver

logger = logging.getLogger(__name__)


def _flatten_for_neo4j(data: dict[str, Any]) -> dict[str, Any]:
    """Flatten complex values to JSON strings for Neo4j storage."""
    flat: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            flat[key] = json.dumps(value)
        elif isinstance(value, datetime):
            flat[key] = value.isoformat()
        else:
            flat[key] = value
    return flat


def _unflatten_from_neo4j(props: dict[str, Any]) -> dict[str, Any]:
    """Restore JSON strings back to Python objects."""
    result = dict(props)
    for key in ("draft_yamls", "critique_trail", "reference_artists"):
        if key in result and isinstance(result[key], str):
            try:
                result[key] = json.loads(result[key])
            except (json.JSONDecodeError, TypeError):
                pass
    return result


class GenreResearchRepository:
    """Neo4j CRUD for GenreResearchJob."""

    def __init__(self, driver: AsyncDriver) -> None:
        self.driver = driver

    async def create_job(self, job_data: dict[str, Any]) -> None:
        """Create a new GenreResearchJob node."""
        query = """
            CREATE (j:GenreResearchJob {id: $id})
            SET j += $props
        """
        flat = _flatten_for_neo4j(job_data)
        async with self.driver.session() as session:
            await session.run(query, id=job_data["id"], props=flat)

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get a job by ID."""
        query = "MATCH (j:GenreResearchJob {id: $id}) RETURN properties(j) AS props"
        async with self.driver.session() as session:
            result = await session.run(query, id=job_id)
            record = await result.single()
            if record is None:
                return None
            return _unflatten_from_neo4j(dict(record["props"]))

    async def update_job(self, job_id: str, updates: dict[str, Any]) -> None:
        """Partial update of a job node."""
        updates["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
        flat = _flatten_for_neo4j(updates)
        query = """
            MATCH (j:GenreResearchJob {id: $id})
            SET j += $props
        """
        async with self.driver.session() as session:
            await session.run(query, id=job_id, props=flat)

    async def list_pending_drafts(self) -> list[dict[str, Any]]:
        """List jobs with status=pending_review."""
        query = """
            MATCH (j:GenreResearchJob {status: 'pending_review'})
            RETURN properties(j) AS props
            ORDER BY j.created_at DESC
        """
        async with self.driver.session() as session:
            result = await session.run(query)
            records = await result.data()
            return [_unflatten_from_neo4j(dict(r["props"])) for r in records]

    async def job_exists_for_genre(self, genre_name: str) -> bool:
        """Check if there's an in-progress job for this genre name."""
        query = """
            MATCH (j:GenreResearchJob {genre_name: $name})
            WHERE j.status IN ['researching', 'drafting', 'critiquing', 'refining', 'validating', 'pending_review']
            RETURN count(j) AS cnt
        """
        async with self.driver.session() as session:
            result = await session.run(query, name=genre_name)
            record = await result.single()
            return record is not None and record["cnt"] > 0
```

- [ ] **Step 2: Add dependency provider**

In `backend/src/explorator/api/deps.py`, add:

```python
from explorator.graph.genre_research_repo import GenreResearchRepository

async def get_genre_research_repo() -> GenreResearchRepository:
    """Get genre research repository dependency."""
    driver = await get_driver()
    return GenreResearchRepository(driver)
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/explorator/graph/genre_research_repo.py backend/src/explorator/api/deps.py
git commit -m "feat(m5c): add GenreResearchRepository and dependency provider"
```

---

## Task 4: Prompt Templates (Markdown + Loader)

**Files:**
- Create: `backend/src/explorator/prompts/genre_research.py`
- Create: `backend/src/explorator/prompts/genre_research/research.md`
- Create: `backend/src/explorator/prompts/genre_research/draft.md`
- Create: `backend/src/explorator/prompts/genre_research/critique.md`
- Create: `backend/src/explorator/prompts/genre_research/refine.md`

- [ ] **Step 1: Create the prompt loader**

Create `backend/src/explorator/prompts/genre_research.py`:

```python
"""Markdown-based prompt loader for genre research agent."""

from pathlib import Path


def load_prompt(template_name: str, **kwargs: str) -> str:
    """Load an MD prompt template and inject variables via str.replace().

    Uses str.replace() instead of str.format() to avoid breakage when
    templates or injected variables contain literal { / } characters.
    """
    path = Path(__file__).parent / "genre_research" / f"{template_name}.md"
    template = path.read_text()
    for key, value in kwargs.items():
        template = template.replace(f"{{{key}}}", str(value))
    return template
```

- [ ] **Step 2: Create the research prompt template**

Create `backend/src/explorator/prompts/genre_research/research.md`:

```markdown
# Genre Research: {genre_name}

You are a musicologist researching the genre **{genre_name}** for a music generation system.

{reference_artists_section}

## Research the following areas thoroughly:

### 1. Harmonic Vocabulary
- What chord types are characteristic? (e.g., maj7, sus2, add9, m7, borrowed chords)
- How functionally strong are chord progressions? (strong cadences vs. floating harmony)
- What level of chromaticism and borrowed chord usage is typical?

### 2. Voicing Tendencies
- Open or closed spacing? What register?
- How dense are extensions? (sparse triads vs. rich extended voicings)
- How important is top-voice continuity (smooth voice leading in the top note)?

### 3. Bass Tendencies
- Root-heavy or melodic bass? Pedal tone tolerance?
- Rhythmic activity level? (sparse and grounding vs. active and driving)

### 4. Groove Tendencies
- Comping density? (sparse, moderate, busy)
- Articulation style? (straight, swung, floating, driving)
- Syncopation level? (none, light, moderate, heavy)

### 5. Common Devices
- List 4-6 characteristic musical devices for this genre
- Examples: "shimmering add9 voicings", "chromatic bass walks", "suspended resolutions"

### 6. Experimentation Envelope
- How tolerant is this genre of harmonic deviation? (0.0 = strict, 1.0 = anything goes)
- Voicing deviation tolerance?
- Groove deviation tolerance?

### 7. Voicing & Bass Preferences
- Default voicing type (open, closed, drop2, etc.) and register
- Default voice count and whether extensions are favored
- Default bass mode (supportive, pedal, syncopated) and rhythmic density

### 8. Melodic Tendencies (if you have confident knowledge)
- Motion preference: stepwise, leaping, or mixed?
- Range placement relative to voicing: above, overlapping, or wide?
- Density: sparse, moderate, or active?
- Typical phrase length in bars
- Strong beat preference: chord tones, extensions, or roots?
- Whether rests between phrases are typical

If you lack confident knowledge about melodic tendencies for this genre, say "melodic tendencies: insufficient data" and skip the section.

## Output Format
Write a detailed research document covering each area. Use specific musical terminology. Provide concrete examples where possible.
```

- [ ] **Step 3: Create the draft prompt template**

Create `backend/src/explorator/prompts/genre_research/draft.md`:

```markdown
# Genre Draft: {genre_name}

You are synthesizing research into structured genre data for a music generation system.

## Research Summary

{research_log}

## Task

Convert the research above into three structured YAML-compatible JSON objects:

### 1. Profile
Must include these fields:
- `genre`: "{genre_name}" (snake_case identifier)
- `display_name`: human-readable name
- `version`: 1
- `harmonic_vocabulary`: list of chord type strings
- `harmonic_tendencies`: dict with keys: functional_strength, chromaticism_level, borrowed_chord_tolerance, cadence_closure_preference
- `voicing_tendencies`: dict with keys: spacing, register_bias, extension_density, top_voice_continuity_importance
- `bass_tendencies`: dict with keys: root_emphasis, pedal_tone_tolerance, rhythmic_activity
- `groove_tendencies`: dict with keys: comp_density, articulation_style, syncopation_level
- `common_devices`: list of 4-6 characteristic device description strings
- `experimentation_envelope`: dict with keys: harmonic_deviation_tolerance (0.0-1.0), voicing_deviation_tolerance (0.0-1.0), groove_deviation_tolerance (0.0-1.0)
- `voicing_preferences`: dict with keys: default_voicing_type, default_register, default_density, default_voice_count (int), favor_extensions (bool), top_voice_continuity, variant_voicing_types (list)
- `bass_preferences`: dict with keys: default_bass_mode, default_register, rhythmic_density, variant_bass_modes (list)
- `melodic_tendencies` (OPTIONAL — include only if the research provides confident data): dict with keys: motion_preference, range_placement, density, phrase_length (int), strong_beat_preference, rest_between_phrases (bool)

### 2. Rules
Must include these fields:
- `rules`: list of objects, each with: name, type, weight (0.0-1.0), description, applicability (dict with string keys and list-of-string values)
- `anti_patterns`: list of objects, each with: name, scope, severity (0.0-1.0), description

### 3. Grammar
Must include these fields:
- `genre_profile_id`: "genre_{genre_name}_01"
- `preferred_chord_qualities`: list of chord quality strings
- `allowed_borrowed_chords`: list of borrowed chord descriptions
- `cadence_archetypes`: list of cadence type strings
- `harmonic_rhythm_defaults`: dict mapping time signatures to float values
- `functional_motion_bias`: dict mapping motion types to float weights (0.0-1.0)

Return valid JSON with top-level keys: "profile", "rules", "grammar".
```

- [ ] **Step 4: Create the critique prompt template**

Create `backend/src/explorator/prompts/genre_research/critique.md`:

```markdown
# Genre Critique: {genre_name}

You are an independent music theory reviewer. You have NOT seen the research that produced these drafts — you are reviewing them fresh.

## Draft YAMLs to Review

{draft_yamls}

## Critique Instructions

Review the draft genre data for **{genre_name}** across these dimensions:

1. **Musical Accuracy**: Do the harmonic vocabulary, tendencies, and devices actually match this genre? Flag anything that seems wrong or generic.

2. **Internal Consistency**: Do the profile tendencies, rules, and grammar agree with each other? For example, if harmonic_tendencies says "low functional strength" but grammar has strong cadence archetypes, that's inconsistent.

3. **Completeness**: Compare against what you'd expect for a well-defined genre profile. Are any important chord types missing? Are rules too generic? Are anti-patterns specific enough?

4. **Weight Ranges**: Are all weights between 0.0 and 1.0? Do experimentation_envelope values seem plausible for this genre? Are severity values reasonable?

5. **Structural Correctness**: Are all required fields present? Are list fields actually lists? Are dict fields actually dicts?

## Output Format

Return JSON with:
- `issues`: list of objects with `severity` ("major" or "minor"), `field` (which part is affected), `suggestion` (specific fix)
- `passed`: true if no major issues found, false otherwise

A "major" issue means the data is musically wrong, internally contradictory, or structurally broken. A "minor" issue is a suggestion for improvement.
```

- [ ] **Step 5: Create the refine prompt template**

Create `backend/src/explorator/prompts/genre_research/refine.md`:

```markdown
# Genre Refinement: {genre_name}

You are refining genre data based on an independent critique. You have access to the original research to make informed corrections.

## Original Research

{research_log}

## Current Draft

{draft_yamls}

## Critique to Address

{critique}

## Task

Apply the critique's suggestions to produce an improved version of the three YAML structures. Use the original research to make musically informed corrections — don't just mechanically apply suggestions without considering whether they make sense in context.

Return valid JSON with top-level keys: "profile", "rules", "grammar" — same structure as the original draft.
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/explorator/prompts/genre_research.py backend/src/explorator/prompts/genre_research/
git commit -m "feat(m5c): add genre research prompt templates and loader"
```

---

## Task 5: LangGraph Nodes — Research & Draft

**Files:**
- Create: `backend/src/explorator/engine/nodes/genre_research/__init__.py`
- Create: `backend/src/explorator/engine/nodes/genre_research/research.py`
- Create: `backend/src/explorator/engine/nodes/genre_research/draft.py`

- [ ] **Step 1: Create package init**

Create `backend/src/explorator/engine/nodes/genre_research/__init__.py`:

```python
"""Genre research agent LangGraph nodes."""
```

- [ ] **Step 2: Create research node**

Create `backend/src/explorator/engine/nodes/genre_research/research.py`:

```python
"""Research node — uses Gemini Pro to research a genre."""

import logging
from typing import Any

from explorator.adapters.gemini import GeminiClient, ModelTier
from explorator.graph.genre_research_repo import GenreResearchRepository
from explorator.prompts.genre_research import load_prompt

logger = logging.getLogger(__name__)


async def research_genre(
    state: dict[str, Any],
    *,
    gemini: GeminiClient,
    driver: Any,
) -> dict[str, Any]:
    """Research a genre using Gemini Pro. Returns research_log."""
    job_id = state["job_id"]
    genre_name = state["genre_name"]
    reference_artists = state.get("reference_artists", [])
    callback = state.get("on_progress")

    # Update Neo4j status
    repo = GenreResearchRepository(driver)
    await repo.update_job(job_id, {"status": "researching"})

    # Build reference artists section
    if reference_artists:
        artists_text = (
            "## Reference Artists\n"
            "Use these artists as style anchors:\n"
            + "\n".join(f"- {a}" for a in reference_artists)
            + "\n"
        )
    else:
        artists_text = ""

    # Build prompt
    user_prompt = load_prompt(
        "research",
        genre_name=genre_name,
        reference_artists_section=artists_text,
    )
    system_prompt = (
        f"You are an expert musicologist researching the genre '{genre_name}' "
        "for a music generation system. Be thorough and specific."
    )

    if callback:
        await callback("genre_research", {"status": "researching", "detail": "Researching harmonic vocabulary..."})

    research_log = await gemini.generate_text(
        prompt=user_prompt,
        tier=ModelTier.PRO,
        system_prompt=system_prompt,
    )

    if callback:
        await callback("genre_research", {"status": "researching", "detail": "Research complete"})

    return {"research_log": research_log, "status": "drafting"}
```

- [ ] **Step 3: Create draft node**

Create `backend/src/explorator/engine/nodes/genre_research/draft.py`:

```python
"""Draft node — synthesizes research into structured YAML data using Gemini Flash."""

import json
import logging
from typing import Any

from explorator.adapters.gemini import GeminiClient, ModelTier
from explorator.graph.genre_research_repo import GenreResearchRepository
from explorator.models.genre_research import GenreDraftResponse
from explorator.prompts.genre_research import load_prompt

logger = logging.getLogger(__name__)


async def draft_yamls(
    state: dict[str, Any],
    *,
    gemini: GeminiClient,
    driver: Any,
) -> dict[str, Any]:
    """Draft three YAML structures from research log."""
    job_id = state["job_id"]
    genre_name = state["genre_name"]
    research_log = state["research_log"]
    callback = state.get("on_progress")

    repo = GenreResearchRepository(driver)
    await repo.update_job(job_id, {"status": "drafting"})

    if callback:
        await callback("genre_research", {"status": "drafting", "detail": "Synthesizing research into genre profile..."})

    user_prompt = load_prompt(
        "draft",
        genre_name=genre_name,
        research_log=research_log,
    )
    system_prompt = (
        f"You are a music data engineer creating structured genre data for '{genre_name}'. "
        "Return valid JSON matching the schema exactly."
    )

    draft = await gemini.generate_structured(
        prompt=user_prompt,
        response_model=GenreDraftResponse,
        tier=ModelTier.FLASH,
        system_prompt=system_prompt,
    )

    if callback:
        await callback("genre_research", {"status": "drafting", "detail": "Draft complete"})

    draft_yamls = {
        "profile": draft.profile.model_dump(mode="json"),
        "rules": draft.rules.model_dump(mode="json"),
        "grammar": draft.grammar.model_dump(mode="json"),
    }

    return {"draft_yamls": draft_yamls, "status": "critiquing"}
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/explorator/engine/nodes/genre_research/
git commit -m "feat(m5c): add research and draft LangGraph nodes"
```

---

## Task 6: LangGraph Nodes — Critique & Refine

**Files:**
- Create: `backend/src/explorator/engine/nodes/genre_research/critique.py`
- Create: `backend/src/explorator/engine/nodes/genre_research/refine.py`

- [ ] **Step 1: Create critique node**

Create `backend/src/explorator/engine/nodes/genre_research/critique.py`:

```python
"""Critique node — independent review using Gemini Flash with fresh context."""

import json
import logging
from typing import Any

from explorator.adapters.gemini import GeminiClient, ModelTier
from explorator.graph.genre_research_repo import GenreResearchRepository
from explorator.models.genre_research import CritiqueEntry, GenreCritiqueResponse
from explorator.prompts.genre_research import load_prompt

logger = logging.getLogger(__name__)


async def critique_draft(
    state: dict[str, Any],
    *,
    gemini: GeminiClient,
    driver: Any,
) -> dict[str, Any]:
    """Critique draft YAMLs. Fresh context — no research log provided."""
    job_id = state["job_id"]
    genre_name = state["genre_name"]
    draft_yamls = state["draft_yamls"]
    callback = state.get("on_progress")

    repo = GenreResearchRepository(driver)
    await repo.update_job(job_id, {"status": "critiquing"})

    if callback:
        await callback("genre_research", {"status": "critiquing", "detail": "Reviewing draft for accuracy..."})

    # Fresh context: only draft + genre name, no research log
    user_prompt = load_prompt(
        "critique",
        genre_name=genre_name,
        draft_yamls=json.dumps(draft_yamls, indent=2),
    )
    system_prompt = (
        "You are an independent music theory reviewer. "
        "Assess the genre data objectively without bias. Return valid JSON."
    )

    critique = await gemini.generate_structured(
        prompt=user_prompt,
        response_model=GenreCritiqueResponse,
        tier=ModelTier.FLASH,
        system_prompt=system_prompt,
    )

    if callback:
        detail = "No major issues found" if critique.passed else f"Found {len(critique.issues)} issue(s)"
        await callback("genre_research", {"status": "critiquing", "detail": detail})

    # Build critique trail entry
    iteration = state.get("refine_iteration", 0)
    entry = CritiqueEntry(
        iteration=iteration,
        issues=critique.issues,
        passed=critique.passed,
        resolution="",
    )
    trail = list(state.get("critique_trail", []))
    trail.append(entry.model_dump(mode="json"))

    return {
        "critique_trail": trail,
        "needs_refine": not critique.passed,
        "status": "refining" if not critique.passed else "validating",
    }
```

- [ ] **Step 2: Create refine node**

Create `backend/src/explorator/engine/nodes/genre_research/refine.py`:

```python
"""Refine node — applies critique to improve draft using Gemini Flash."""

import json
import logging
from typing import Any

from explorator.adapters.gemini import GeminiClient, ModelTier
from explorator.graph.genre_research_repo import GenreResearchRepository
from explorator.models.genre_research import GenreDraftResponse
from explorator.prompts.genre_research import load_prompt

logger = logging.getLogger(__name__)


async def refine_draft(
    state: dict[str, Any],
    *,
    gemini: GeminiClient,
    driver: Any,
) -> dict[str, Any]:
    """Refine draft based on critique. Has full context: research + draft + critique."""
    job_id = state["job_id"]
    genre_name = state["genre_name"]
    research_log = state["research_log"]
    draft_yamls = state["draft_yamls"]
    critique_trail = state.get("critique_trail", [])
    callback = state.get("on_progress")

    # Increment iteration counter FIRST
    iteration = state.get("refine_iteration", 0) + 1

    repo = GenreResearchRepository(driver)
    await repo.update_job(job_id, {"status": "refining"})

    if callback:
        await callback("genre_research", {"status": "refining", "detail": f"Refining draft (iteration {iteration}/2)..."})

    # Get the latest critique
    latest_critique = critique_trail[-1] if critique_trail else {}

    user_prompt = load_prompt(
        "refine",
        genre_name=genre_name,
        research_log=research_log,
        draft_yamls=json.dumps(draft_yamls, indent=2),
        critique=json.dumps(latest_critique, indent=2),
    )
    system_prompt = (
        f"You are refining genre data for '{genre_name}' based on reviewer feedback. "
        "Return valid JSON with improved profile, rules, and grammar."
    )

    refined = await gemini.generate_structured(
        prompt=user_prompt,
        response_model=GenreDraftResponse,
        tier=ModelTier.FLASH,
        system_prompt=system_prompt,
    )

    if callback:
        await callback("genre_research", {"status": "refining", "detail": "Refinement complete"})

    # Update the resolution on the last critique entry
    trail = list(critique_trail)
    if trail:
        last = dict(trail[-1])
        last["resolution"] = f"Applied {len(last.get('issues', []))} fix(es) in iteration {iteration}"
        trail[-1] = last

    draft_yamls = {
        "profile": refined.profile.model_dump(mode="json"),
        "rules": refined.rules.model_dump(mode="json"),
        "grammar": refined.grammar.model_dump(mode="json"),
    }

    return {
        "draft_yamls": draft_yamls,
        "critique_trail": trail,
        "refine_iteration": iteration,
        "status": "critiquing",
    }
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/explorator/engine/nodes/genre_research/critique.py backend/src/explorator/engine/nodes/genre_research/refine.py
git commit -m "feat(m5c): add critique and refine LangGraph nodes"
```

---

## Task 7: LangGraph Nodes — Validate & Output

**Files:**
- Create: `backend/src/explorator/engine/nodes/genre_research/validate.py`
- Create: `backend/src/explorator/engine/nodes/genre_research/output.py`
- Create: `backend/tests/unit/domain/test_genre_research_validate.py`

- [ ] **Step 1: Write validate node tests**

Create `backend/tests/unit/domain/test_genre_research_validate.py`:

```python
"""Tests for the validate node (deterministic validation)."""

import pytest

from explorator.engine.nodes.genre_research.validate import _validate_draft_yamls


class TestValidateDraftYamls:
    def test_valid_draft_returns_no_errors(self):
        draft = {
            "profile": {
                "genre": "test",
                "display_name": "Test",
                "version": 1,
                "harmonic_vocabulary": ["maj7"],
                "experimentation_envelope": {"harmonic_deviation_tolerance": 0.5},
            },
            "rules": {"rules": [], "anti_patterns": []},
            "grammar": {
                "genre_profile_id": "genre_test_01",
                "preferred_chord_qualities": [],
                "allowed_borrowed_chords": [],
                "cadence_archetypes": [],
            },
        }
        errors = _validate_draft_yamls(draft)
        assert errors == []

    def test_missing_profile_genre_field(self):
        draft = {
            "profile": {"display_name": "Test", "version": 1},
            "rules": {"rules": [], "anti_patterns": []},
            "grammar": {"genre_profile_id": "x"},
        }
        errors = _validate_draft_yamls(draft)
        assert any("profile" in e.lower() for e in errors)

    def test_envelope_out_of_range(self):
        draft = {
            "profile": {
                "genre": "test",
                "display_name": "Test",
                "version": 1,
                "experimentation_envelope": {"harmonic_deviation_tolerance": 1.5},
            },
            "rules": {"rules": [], "anti_patterns": []},
            "grammar": {"genre_profile_id": "genre_test_01"},
        }
        errors = _validate_draft_yamls(draft)
        assert any("range" in e.lower() or "envelope" in e.lower() for e in errors)

    def test_missing_top_level_key(self):
        draft = {
            "profile": {"genre": "test", "display_name": "Test", "version": 1},
            "grammar": {"genre_profile_id": "genre_test_01"},
        }
        errors = _validate_draft_yamls(draft)
        assert any("rules" in e.lower() for e in errors)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/domain/test_genre_research_validate.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create validate node**

Create `backend/src/explorator/engine/nodes/genre_research/validate.py`:

```python
"""Validate node — deterministic Pydantic schema validation."""

import logging
from typing import Any

from explorator.domain.style.schema import (
    GenreProfileYAML,
    GenreRulesYAML,
    HarmonicGrammarYAML,
)
from explorator.graph.genre_research_repo import GenreResearchRepository

logger = logging.getLogger(__name__)

_SCHEMA_MAP = {
    "profile": GenreProfileYAML,
    "rules": GenreRulesYAML,
    "grammar": HarmonicGrammarYAML,
}


def _validate_draft_yamls(draft_yamls: dict[str, Any]) -> list[str]:
    """Validate draft YAMLs against Pydantic schemas. Returns list of error strings."""
    errors: list[str] = []

    # Check top-level keys
    for key in ("profile", "rules", "grammar"):
        if key not in draft_yamls:
            errors.append(f"Missing top-level key: '{key}'")

    if errors:
        return errors

    # Validate each section against its schema
    for key, schema_cls in _SCHEMA_MAP.items():
        try:
            schema_cls.model_validate(draft_yamls[key])
        except Exception as e:
            errors.append(f"Validation error in {key}: {e}")

    # Check experimentation_envelope ranges
    profile = draft_yamls.get("profile", {})
    envelope = profile.get("experimentation_envelope", {})
    for field, value in envelope.items():
        if isinstance(value, (int, float)) and not (0.0 <= value <= 1.0):
            errors.append(f"Envelope value out of range (0-1): {field}={value}")

    # Check rule weights
    rules = draft_yamls.get("rules", {}).get("rules", [])
    for rule in rules:
        weight = rule.get("weight", 0.5)
        if isinstance(weight, (int, float)) and not (0.0 <= weight <= 1.0):
            errors.append(f"Rule weight out of range (0-1): {rule.get('name', '?')}={weight}")

    return errors


async def validate_draft(
    state: dict[str, Any],
    *,
    driver: Any,
) -> dict[str, Any]:
    """Validate draft YAMLs against schemas. Deterministic — no LLM call."""
    job_id = state["job_id"]
    draft_yamls = state["draft_yamls"]
    callback = state.get("on_progress")

    repo = GenreResearchRepository(driver)
    await repo.update_job(job_id, {"status": "validating"})

    if callback:
        await callback("genre_research", {"status": "validating", "detail": "Validating against schemas..."})

    errors = _validate_draft_yamls(draft_yamls)

    if callback:
        if errors:
            await callback("genre_research", {"status": "validating", "detail": f"Found {len(errors)} validation warning(s)"})
        else:
            await callback("genre_research", {"status": "validating", "detail": "Validation passed"})

    return {"validation_errors": errors, "status": "pending_review"}
```

- [ ] **Step 4: Run validate tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/domain/test_genre_research_validate.py -v`
Expected: All PASS

- [ ] **Step 5: Create output node**

Create `backend/src/explorator/engine/nodes/genre_research/output.py`:

```python
"""Output node — persists final state to Neo4j."""

import logging
from typing import Any

from explorator.graph.genre_research_repo import GenreResearchRepository

logger = logging.getLogger(__name__)


async def output_draft(
    state: dict[str, Any],
    *,
    driver: Any,
) -> dict[str, Any]:
    """Persist draft to Neo4j with status pending_review."""
    job_id = state["job_id"]
    callback = state.get("on_progress")

    repo = GenreResearchRepository(driver)
    await repo.update_job(job_id, {
        "status": "pending_review",
        "research_log": state.get("research_log", ""),
        "critique_trail": state.get("critique_trail", []),
        "draft_yamls": state.get("draft_yamls", {}),
        "validation_errors": state.get("validation_errors", []),
    })

    if callback:
        await callback("genre_research", {"status": "pending_review", "detail": "Ready for review"})

    return {"status": "pending_review"}
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/explorator/engine/nodes/genre_research/validate.py backend/src/explorator/engine/nodes/genre_research/output.py backend/tests/unit/domain/test_genre_research_validate.py
git commit -m "feat(m5c): add validate and output LangGraph nodes"
```

---

## Task 8: LangGraph Graph Assembly

**Files:**
- Create: `backend/src/explorator/engine/genre_research_graph.py`
- Create: `backend/tests/unit/engine/test_genre_research_graph.py`

- [ ] **Step 1: Write routing tests**

Create `backend/tests/unit/engine/test_genre_research_graph.py`:

```python
"""Tests for genre research graph routing logic."""

from explorator.engine.genre_research_graph import route_after_critique, route_after_validate


class TestRouteAfterCritique:
    def test_needs_refine_first_iteration(self):
        state = {"needs_refine": True, "refine_iteration": 0}
        assert route_after_critique(state) == "refine"

    def test_needs_refine_second_iteration(self):
        state = {"needs_refine": True, "refine_iteration": 1}
        assert route_after_critique(state) == "refine"

    def test_needs_refine_at_max_goes_to_validate(self):
        state = {"needs_refine": True, "refine_iteration": 2}
        assert route_after_critique(state) == "validate"

    def test_no_refine_needed(self):
        state = {"needs_refine": False, "refine_iteration": 0}
        assert route_after_critique(state) == "validate"

    def test_missing_keys_defaults_to_validate(self):
        state = {}
        assert route_after_critique(state) == "validate"


class TestRouteAfterValidate:
    def test_always_routes_to_output(self):
        assert route_after_validate({}) == "output"
        assert route_after_validate({"validation_errors": ["some error"]}) == "output"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/engine/test_genre_research_graph.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create the graph module**

Create `backend/src/explorator/engine/genre_research_graph.py`:

```python
"""LangGraph genre research graph — 6-node agentic pipeline.

Flow: research → draft → critique → [refine loop] → validate → output → END
"""

from collections.abc import Awaitable, Callable
from functools import partial
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from neo4j import AsyncDriver

from explorator.adapters.gemini import GeminiClient
from explorator.engine.nodes.genre_research.critique import critique_draft
from explorator.engine.nodes.genre_research.draft import draft_yamls
from explorator.engine.nodes.genre_research.output import output_draft
from explorator.engine.nodes.genre_research.refine import refine_draft
from explorator.engine.nodes.genre_research.research import research_genre
from explorator.engine.nodes.genre_research.validate import validate_draft
from explorator.engine.state import ProgressCallback


class GenreResearchState(TypedDict, total=False):
    """State for the genre research pipeline."""

    job_id: str
    genre_name: str
    reference_artists: list[str]

    # Step outputs
    research_log: str
    draft_yamls: dict[str, Any]
    critique_trail: list[dict[str, Any]]
    refine_iteration: int
    needs_refine: bool
    validation_errors: list[str]

    # Control
    status: str
    on_progress: ProgressCallback


def route_after_critique(state: dict[str, Any]) -> str:
    """Route: refine if needed and under iteration cap, else validate."""
    if state.get("needs_refine") and state.get("refine_iteration", 0) < 2:
        return "refine"
    return "validate"


def route_after_validate(state: dict[str, Any]) -> str:
    """Always route to output — validation errors surfaced in review UI."""
    return "output"


def build_genre_research_graph(gemini: GeminiClient, driver: AsyncDriver) -> Any:
    """Build and compile the genre research LangGraph pipeline."""
    graph = StateGraph(GenreResearchState)

    graph.add_node("research", partial(research_genre, gemini=gemini, driver=driver))
    graph.add_node("draft", partial(draft_yamls, gemini=gemini, driver=driver))
    graph.add_node("critique", partial(critique_draft, gemini=gemini, driver=driver))
    graph.add_node("refine", partial(refine_draft, gemini=gemini, driver=driver))
    graph.add_node("validate", partial(validate_draft, driver=driver))
    graph.add_node("output", partial(output_draft, driver=driver))

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/engine/test_genre_research_graph.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/genre_research_graph.py backend/tests/unit/engine/test_genre_research_graph.py
git commit -m "feat(m5c): add LangGraph genre research graph with routing"
```

---

## Task 9: API Endpoints

**Files:**
- Create: `backend/src/explorator/api/routes/genre_research.py`
- Modify: `backend/src/explorator/api/app.py`

- [ ] **Step 1: Create the route module**

Create `backend/src/explorator/api/routes/genre_research.py`:

```python
"""Genre research API endpoints."""

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any

import ulid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from explorator.adapters.gemini import GeminiClient
from explorator.api.deps import get_gemini_client, get_genre_research_repo, get_neo4j_driver
from explorator.api.sse import SSEChannel
from explorator.domain.style.loader import discover_genres
from explorator.domain.style.service import STYLE_DIR
from explorator.engine.genre_research_graph import build_genre_research_graph
from explorator.graph.genre_research_repo import GenreResearchRepository
from explorator.models.genre_research import step_number

logger = logging.getLogger(__name__)

router = APIRouter(tags=["genre_research"])

# In-memory SSE channels keyed by job_id
_channels: dict[str, SSEChannel] = {}

_GENRE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,48}$")


# --- Request/Response models ---

class StartResearchRequest(BaseModel):
    genre_name: str
    reference_artists: list[str] = Field(default_factory=list)


class StartResearchResponse(BaseModel):
    job_id: str


class DraftSummary(BaseModel):
    job_id: str
    genre_name: str
    created_at: str


class DraftListResponse(BaseModel):
    items: list[DraftSummary]


class RejectRequest(BaseModel):
    reason: str = ""


# --- Endpoints ---

@router.post("/genres/research")
async def start_research(
    request: StartResearchRequest,
    gemini: GeminiClient = Depends(get_gemini_client),  # noqa: B008
    repo: GenreResearchRepository = Depends(get_genre_research_repo),  # noqa: B008
    driver: Any = Depends(get_neo4j_driver),  # noqa: B008
) -> StartResearchResponse:
    """Kick off a genre research job."""
    genre_name = request.genre_name.lower().strip()

    # Validate genre name format
    if not _GENRE_NAME_RE.match(genre_name):
        raise HTTPException(
            status_code=400,
            detail="Genre name must be lowercase alphanumeric with underscores, 2-49 chars",
        )

    # Check for existing genre
    existing = discover_genres(STYLE_DIR)
    if genre_name in existing:
        raise HTTPException(status_code=409, detail=f"Genre '{genre_name}' already exists")

    # Check for in-progress job
    if await repo.job_exists_for_genre(genre_name):
        raise HTTPException(status_code=409, detail=f"Research job already in progress for '{genre_name}'")

    # Create job
    job_id = f"grj_{ulid.new()}"
    now = datetime.now(tz=timezone.utc)
    job_data = {
        "id": job_id,
        "genre_name": genre_name,
        "reference_artists": request.reference_artists,
        "status": "researching",
        "research_log": "",
        "critique_trail": [],
        "draft_yamls": {},
        "created_at": now,
        "updated_at": now,
    }
    await repo.create_job(job_data)

    # Create SSE channel
    channel = SSEChannel()
    _channels[job_id] = channel

    # Build graph and launch
    graph = build_genre_research_graph(gemini, driver)
    initial_state = {
        "job_id": job_id,
        "genre_name": genre_name,
        "reference_artists": request.reference_artists,
        "on_progress": channel.send,
        "refine_iteration": 0,
    }

    async def run_and_close() -> None:
        try:
            await graph.ainvoke(initial_state, {"recursion_limit": 20})
        except Exception as e:
            logger.exception("Genre research failed for job %s", job_id)
            await repo.update_job(job_id, {"status": "failed", "error_message": str(e)})
            await channel.send("genre_research", {"status": "failed", "detail": str(e)})
        finally:
            await channel.close()
            _channels.pop(job_id, None)

    asyncio.create_task(run_and_close())

    return StartResearchResponse(job_id=job_id)


@router.get("/genres/research/{job_id}")
async def get_research_status(
    job_id: str,
    repo: GenreResearchRepository = Depends(get_genre_research_repo),  # noqa: B008
) -> dict[str, Any]:
    """Poll job status."""
    job = await repo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/genres/research/{job_id}/stream")
async def stream_research_progress(job_id: str) -> EventSourceResponse:
    """SSE progress stream for a research job."""
    channel = _channels.get(job_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="No active stream for this job")
    return EventSourceResponse(channel.stream())


@router.get("/genres/drafts")
async def list_pending_drafts(
    repo: GenreResearchRepository = Depends(get_genre_research_repo),  # noqa: B008
) -> DraftListResponse:
    """List all pending drafts."""
    drafts = await repo.list_pending_drafts()
    items = [
        DraftSummary(
            job_id=d["id"],
            genre_name=d.get("genre_name", ""),
            created_at=d.get("created_at", ""),
        )
        for d in drafts
    ]
    return DraftListResponse(items=items)


@router.get("/genres/drafts/{job_id}")
async def get_draft_detail(
    job_id: str,
    repo: GenreResearchRepository = Depends(get_genre_research_repo),  # noqa: B008
) -> dict[str, Any]:
    """Get full draft detail for review."""
    job = await repo.get_job(job_id)
    if job is None or job.get("status") != "pending_review":
        raise HTTPException(status_code=404, detail="Draft not found or not pending review")
    return job


@router.post("/genres/drafts/{job_id}/approve")
async def approve_draft(
    job_id: str,
    repo: GenreResearchRepository = Depends(get_genre_research_repo),  # noqa: B008
    driver: Any = Depends(get_neo4j_driver),  # noqa: B008
) -> dict[str, str]:
    """Approve a draft — writes YAML files and syncs to Neo4j."""
    import yaml

    from explorator.domain.style.service import StyleService

    job = await repo.get_job(job_id)
    if job is None or job.get("status") != "pending_review":
        raise HTTPException(status_code=404, detail="Draft not found or not pending review")

    genre_name = job["genre_name"]
    draft_yamls = job.get("draft_yamls", {})

    # Write YAML files
    files_written: list[str] = []
    try:
        profile_path = STYLE_DIR / "genres" / f"{genre_name}.yaml"
        rules_path = STYLE_DIR / "rules" / f"{genre_name}_rules.yaml"
        grammar_path = STYLE_DIR / "grammars" / f"{genre_name}_grammar.yaml"

        profile_path.write_text(yaml.dump(draft_yamls.get("profile", {}), default_flow_style=False))
        files_written.append(str(profile_path))

        rules_path.write_text(yaml.dump(draft_yamls.get("rules", {}), default_flow_style=False))
        files_written.append(str(rules_path))

        grammar_path.write_text(yaml.dump(draft_yamls.get("grammar", {}), default_flow_style=False))
        files_written.append(str(grammar_path))

        # Sync to Neo4j
        style_service = StyleService(driver)
        await style_service.sync_genres_to_neo4j()

    except Exception:
        # Clean up written files on failure
        import os
        for f in files_written:
            try:
                os.remove(f)
            except OSError:
                pass
        logger.exception("Failed to approve genre %s", genre_name)
        raise HTTPException(status_code=500, detail="Failed to write genre files")

    # Mark approved only after everything succeeds
    await repo.update_job(job_id, {"status": "approved"})
    return {"status": "approved", "genre_name": genre_name}


@router.post("/genres/drafts/{job_id}/reject")
async def reject_draft(
    job_id: str,
    request: RejectRequest,
    repo: GenreResearchRepository = Depends(get_genre_research_repo),  # noqa: B008
) -> dict[str, str]:
    """Reject a draft with optional reason."""
    job = await repo.get_job(job_id)
    if job is None or job.get("status") != "pending_review":
        raise HTTPException(status_code=404, detail="Draft not found or not pending review")

    await repo.update_job(job_id, {
        "status": "rejected",
        "rejection_reason": request.reason,
    })
    return {"status": "rejected"}
```

- [ ] **Step 2: Mount the router in app.py**

In `backend/src/explorator/api/app.py`, add the import and router mount. Find where other routers are included and add:

```python
from explorator.api.routes.genre_research import router as genre_research_router
```

And in the router mounting section:

```python
app.include_router(genre_research_router, prefix="/v1")
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/explorator/api/routes/genre_research.py backend/src/explorator/api/app.py
git commit -m "feat(m5c): add genre research API endpoints with SSE streaming"
```

---

## Task 10: Frontend — API Service & Store

**Files:**
- Modify: `frontend/src/services/api.ts`
- Create: `frontend/src/stores/genreResearchStore.ts`

- [ ] **Step 1: Add API functions**

Add to `frontend/src/services/api.ts`:

```typescript
// --- Genre Research ---

export interface GenreSummary {
  genre: string;
  display_name: string;
}

export interface GenreListResponse {
  items: GenreSummary[];
}

export interface GenreResearchJob {
  id: string;
  genre_name: string;
  reference_artists: string[];
  status: string;
  research_log: string;
  critique_trail: any[];
  draft_yamls: Record<string, any>;
  validation_errors?: string[];
  rejection_reason?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DraftSummary {
  job_id: string;
  genre_name: string;
  created_at: string;
}

export interface DraftListResponse {
  items: DraftSummary[];
}

export async function listGenres(): Promise<GenreListResponse> {
  const res = await fetch(`${API_BASE}/genres`);
  if (!res.ok) throw new Error(`Failed to list genres: ${res.status}`);
  return res.json();
}

export async function startGenreResearch(
  genreName: string,
  referenceArtists: string[] = [],
): Promise<{ job_id: string }> {
  const res = await fetch(`${API_BASE}/genres/research`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ genre_name: genreName, reference_artists: referenceArtists }),
  });
  if (res.status === 409) {
    const data = await res.json();
    throw new Error(data.detail || 'Genre already exists or research in progress');
  }
  if (!res.ok) throw new Error(`Failed to start research: ${res.status}`);
  return res.json();
}

export async function getResearchStatus(jobId: string): Promise<GenreResearchJob> {
  const res = await fetch(`${API_BASE}/genres/research/${jobId}`);
  if (!res.ok) throw new Error(`Failed to get research status: ${res.status}`);
  return res.json();
}

export function streamResearchProgress(jobId: string): EventSource {
  return new EventSource(`${API_BASE}/genres/research/${jobId}/stream`);
}

export async function listPendingDrafts(): Promise<DraftListResponse> {
  const res = await fetch(`${API_BASE}/genres/drafts`);
  if (!res.ok) throw new Error(`Failed to list drafts: ${res.status}`);
  return res.json();
}

export async function getDraftDetail(jobId: string): Promise<GenreResearchJob> {
  const res = await fetch(`${API_BASE}/genres/drafts/${jobId}`);
  if (!res.ok) throw new Error(`Failed to get draft: ${res.status}`);
  return res.json();
}

export async function approveDraft(jobId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/genres/drafts/${jobId}/approve`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to approve: ${res.status}`);
}

export async function rejectDraft(jobId: string, reason = ''): Promise<void> {
  const res = await fetch(`${API_BASE}/genres/drafts/${jobId}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) throw new Error(`Failed to reject: ${res.status}`);
}
```

- [ ] **Step 2: Create the Zustand store**

Create `frontend/src/stores/genreResearchStore.ts`:

```typescript
import { create } from 'zustand';
import {
  approveDraft,
  getDraftDetail,
  listGenres,
  listPendingDrafts,
  rejectDraft,
  startGenreResearch,
  streamResearchProgress,
  type DraftSummary,
  type GenreResearchJob,
  type GenreSummary,
} from '../services/api';

interface GenreResearchState {
  // Genre library
  genres: GenreSummary[];
  pendingDrafts: DraftSummary[];

  // Active research
  activeJobId: string | null;
  activeJobStatus: string | null;
  progressDetail: string | null;
  errorMessage: string | null;

  // Review
  reviewDraft: GenreResearchJob | null;

  // SSE cleanup
  _eventSource: EventSource | null;

  // Actions
  fetchGenres: () => Promise<void>;
  fetchDrafts: () => Promise<void>;
  startResearch: (genreName: string, referenceArtists?: string[]) => Promise<void>;
  connectProgress: (jobId: string) => void;
  disconnectProgress: () => void;
  fetchDraftDetail: (jobId: string) => Promise<void>;
  doApproveDraft: (jobId: string) => Promise<void>;
  doRejectDraft: (jobId: string, reason?: string) => Promise<void>;
  reset: () => void;
}

export const useGenreResearchStore = create<GenreResearchState>((set, get) => ({
  genres: [],
  pendingDrafts: [],
  activeJobId: null,
  activeJobStatus: null,
  progressDetail: null,
  errorMessage: null,
  reviewDraft: null,
  _eventSource: null,

  fetchGenres: async () => {
    const data = await listGenres();
    set({ genres: data.items });
  },

  fetchDrafts: async () => {
    const data = await listPendingDrafts();
    set({ pendingDrafts: data.items });
  },

  startResearch: async (genreName, referenceArtists = []) => {
    const { job_id } = await startGenreResearch(genreName, referenceArtists);
    set({ activeJobId: job_id, activeJobStatus: 'researching', progressDetail: null, errorMessage: null });
    get().connectProgress(job_id);
  },

  connectProgress: (jobId) => {
    get().disconnectProgress();
    const es = streamResearchProgress(jobId);

    es.addEventListener('genre_research', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        set({
          activeJobStatus: data.status,
          progressDetail: data.detail,
        });

        if (data.status === 'pending_review') {
          es.close();
          set({ _eventSource: null });
          get().fetchDrafts();
        }
        if (data.status === 'failed') {
          es.close();
          set({ _eventSource: null, errorMessage: data.detail });
        }
      } catch {
        // Ignore parse errors
      }
    });

    es.onerror = () => {
      es.close();
      set({ _eventSource: null });
    };

    set({ _eventSource: es });
  },

  disconnectProgress: () => {
    const es = get()._eventSource;
    if (es) {
      es.close();
      set({ _eventSource: null });
    }
  },

  fetchDraftDetail: async (jobId) => {
    const draft = await getDraftDetail(jobId);
    set({ reviewDraft: draft });
  },

  doApproveDraft: async (jobId) => {
    await approveDraft(jobId);
    set({ reviewDraft: null });
    await get().fetchGenres();
    await get().fetchDrafts();
  },

  doRejectDraft: async (jobId, reason = '') => {
    await rejectDraft(jobId, reason);
    set({ reviewDraft: null });
    await get().fetchDrafts();
  },

  reset: () => {
    get().disconnectProgress();
    set({
      activeJobId: null,
      activeJobStatus: null,
      progressDetail: null,
      errorMessage: null,
      reviewDraft: null,
    });
  },
}));
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/api.ts frontend/src/stores/genreResearchStore.ts
git commit -m "feat(m5c): add genre research API service and Zustand store"
```

---

## Task 11: Frontend — GenreManagement Component

**Files:**
- Create: `frontend/src/components/GenreManagement.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/index.css`

This is the largest frontend task. The component implements three view states: library, progress, and review. Follow the spec section 6.3-6.8 for visual details.

- [ ] **Step 1: Add CSS animations and genre accent palette**

Add to `frontend/src/index.css` before the closing comment:

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

Add to `:root` in `frontend/src/index.css`:

```css
  /* Genre accent palette for dynamically-created genres */
  --genre-accent-1: #f472b6;
  --genre-accent-2: #38bdf8;
  --genre-accent-3: #fb923c;
  --genre-accent-4: #a3e635;
  --genre-accent-5: #e879f9;
```

- [ ] **Step 2: Create GenreManagement component**

Create `frontend/src/components/GenreManagement.tsx`. This is a large component — implement it with the three view states described in spec section 6.3-6.5. Use the existing design tokens, Tailwind utilities, and component patterns from the Dashboard. Key elements:

- Genre library with cards using genre-specific left border accents
- Inline request form with genre name + reference artists inputs
- Step rail progress indicator with 5 steps and pulse animation on active step
- Review view with three-column grid for profile/rules/grammar cards
- Expandable research log and critique trail panels
- Approve/Reject action buttons

The component should use `useGenreResearchStore` for all state management and `useEffect` for initial data fetching.

- [ ] **Step 3: Add route to App.tsx**

In `frontend/src/App.tsx`, add the import and route:

```typescript
import GenreManagement from './components/GenreManagement';
```

Add inside the `<Routes>` block:

```typescript
<Route path="/genres" element={<GenreManagement />} />
```

- [ ] **Step 4: Add nav link to Dashboard**

In `frontend/src/views/Dashboard.tsx`, add a "Genres" link near the hero section subtitle. Add below the subtitle `<p>` tag:

```typescript
<div className="mt-4">
  <a
    href="/genres"
    className="text-xs tracking-wider uppercase transition-colors"
    style={{ color: 'var(--text-muted)' }}
    onMouseOver={(e) => (e.currentTarget.style.color = 'var(--accent-primary)')}
    onMouseOut={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
  >
    Manage Genres →
  </a>
</div>
```

- [ ] **Step 5: Test in browser**

Run: `cd frontend && npm run dev`

Verify:
- Navigate to `/genres` — library view loads with 3 existing genres
- Click "Research New Genre" — form appears
- Nav link from Dashboard works

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/GenreManagement.tsx frontend/src/App.tsx frontend/src/views/Dashboard.tsx frontend/src/index.css
git commit -m "feat(m5c): add GenreManagement component with library/progress/review views"
```

---

## Task 12: E2E Tests

**Files:**
- Create: `e2e/tests/genre-research.spec.ts`

- [ ] **Step 1: Create E2E test file**

Create `e2e/tests/genre-research.spec.ts`:

```typescript
import { test, expect } from '../fixtures/test-fixtures';

const API_BASE = 'http://localhost:8100/v1';

test.describe('Genre Research Agent (M5c)', () => {
  test('34: research-job-lifecycle', async ({ page }) => {
    // Navigate to genre management
    await page.goto('/genres');
    await page.waitForLoadState('networkidle');

    // Verify existing genres visible
    await expect(page.locator('text=Dream Pop')).toBeVisible({ timeout: 10_000 });

    // Start research
    await page.getByRole('button', { name: /research new genre/i }).click();
    await page.locator('input[placeholder*="lo-fi"]').fill('ambient_jazz');
    await page.getByRole('button', { name: /start research/i }).click();

    // Verify progress view appears with step indicator
    await expect(page.locator('text=Research')).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('text=Draft')).toBeVisible();

    // Wait for job to complete (pending_review)
    await expect(page.locator('text=Ready for review').or(page.locator('text=Pending Review'))).toBeVisible({ timeout: 120_000 });
  });

  test('35: review-draft-content', async ({ page }) => {
    // Start a research job via API
    const startRes = await fetch(`${API_BASE}/genres/research`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ genre_name: 'test_review_genre', reference_artists: [] }),
    });
    const { job_id } = await startRes.json();

    // Poll until pending_review
    let status = 'researching';
    for (let i = 0; i < 60 && status !== 'pending_review' && status !== 'failed'; i++) {
      await page.waitForTimeout(2000);
      const pollRes = await fetch(`${API_BASE}/genres/research/${job_id}`);
      const job = await pollRes.json();
      status = job.status;
    }
    expect(status).toBe('pending_review');

    // Fetch draft detail
    const draftRes = await fetch(`${API_BASE}/genres/drafts/${job_id}`);
    const draft = await draftRes.json();

    // Verify all three YAML structures present
    expect(draft.draft_yamls).toBeDefined();
    expect(draft.draft_yamls.profile).toBeDefined();
    expect(draft.draft_yamls.profile.genre).toBe('test_review_genre');
    expect(draft.draft_yamls.rules).toBeDefined();
    expect(draft.draft_yamls.grammar).toBeDefined();

    // Verify research log and critique trail
    expect(draft.research_log).toBeTruthy();
    expect(draft.critique_trail).toBeDefined();
  });

  test('36: approve-flow', async ({ page }) => {
    // Start and wait for a research job via API
    const startRes = await fetch(`${API_BASE}/genres/research`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ genre_name: 'test_approve_genre', reference_artists: [] }),
    });
    const { job_id } = await startRes.json();

    let status = 'researching';
    for (let i = 0; i < 60 && status !== 'pending_review' && status !== 'failed'; i++) {
      await page.waitForTimeout(2000);
      const pollRes = await fetch(`${API_BASE}/genres/research/${job_id}`);
      const job = await pollRes.json();
      status = job.status;
    }
    expect(status).toBe('pending_review');

    // Approve
    const approveRes = await fetch(`${API_BASE}/genres/drafts/${job_id}/approve`, { method: 'POST' });
    expect(approveRes.ok).toBe(true);

    // Verify genre appears in list
    const genresRes = await fetch(`${API_BASE}/genres`);
    const genres = await genresRes.json();
    const names = genres.items.map((g: any) => g.genre);
    expect(names).toContain('test_approve_genre');
  });

  test('37: new-genre-usable-in-session', async ({ page }) => {
    // Verify the approved genre from test 36 is usable
    // (relies on test_approve_genre being approved in prior test or setup)
    const genresRes = await fetch(`${API_BASE}/genres`);
    const genres = await genresRes.json();
    const hasGenre = genres.items.some((g: any) => g.genre === 'test_approve_genre');

    if (!hasGenre) {
      test.skip();
      return;
    }

    // Create a session with the new genre
    const sessionRes = await fetch(`${API_BASE}/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: 'Test approve genre in C major, 4 bars', mode: 'full_exploration' }),
    });
    expect(sessionRes.ok).toBe(true);
  });

  test('38: reject-flow', async ({ page }) => {
    const startRes = await fetch(`${API_BASE}/genres/research`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ genre_name: 'test_reject_genre', reference_artists: [] }),
    });
    const { job_id } = await startRes.json();

    let status = 'researching';
    for (let i = 0; i < 60 && status !== 'pending_review' && status !== 'failed'; i++) {
      await page.waitForTimeout(2000);
      const pollRes = await fetch(`${API_BASE}/genres/research/${job_id}`);
      const job = await pollRes.json();
      status = job.status;
    }
    expect(status).toBe('pending_review');

    // Reject with reason
    const rejectRes = await fetch(`${API_BASE}/genres/drafts/${job_id}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: 'Harmonic vocabulary too generic' }),
    });
    expect(rejectRes.ok).toBe(true);

    // Verify rejected
    const jobRes = await fetch(`${API_BASE}/genres/research/${job_id}`);
    const job = await jobRes.json();
    expect(job.status).toBe('rejected');
    expect(job.rejection_reason).toBe('Harmonic vocabulary too generic');

    // Verify not in genres list
    const genresRes = await fetch(`${API_BASE}/genres`);
    const genres = await genresRes.json();
    const names = genres.items.map((g: any) => g.genre);
    expect(names).not.toContain('test_reject_genre');
  });

  test('39: duplicate-prevention', async ({ page }) => {
    // Try to research an existing genre
    const res1 = await fetch(`${API_BASE}/genres/research`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ genre_name: 'dream_pop', reference_artists: [] }),
    });
    expect(res1.status).toBe(409);

    // Start a job, then try duplicate
    const res2 = await fetch(`${API_BASE}/genres/research`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ genre_name: 'test_dup_genre', reference_artists: [] }),
    });
    expect(res2.ok).toBe(true);

    const res3 = await fetch(`${API_BASE}/genres/research`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ genre_name: 'test_dup_genre', reference_artists: [] }),
    });
    expect(res3.status).toBe(409);
  });
});
```

- [ ] **Step 2: Run E2E tests**

Run: `cd e2e && npx playwright test tests/genre-research.spec.ts --timeout 180000`
Expected: All 6 tests PASS (requires backend + frontend running)

- [ ] **Step 3: Commit**

```bash
git add e2e/tests/genre-research.spec.ts
git commit -m "test(m5c): add E2E tests for genre research workflow"
```

---

## Summary

| Task | Description | Est. Files |
|------|-------------|-----------|
| 1 | Schema prerequisite (melodic_tendencies) | 2 |
| 2 | GenreResearchJob models | 2 |
| 3 | GenreResearchRepository + deps | 2 |
| 4 | Prompt templates + loader | 5 |
| 5 | LangGraph nodes: research + draft | 3 |
| 6 | LangGraph nodes: critique + refine | 2 |
| 7 | LangGraph nodes: validate + output | 3 |
| 8 | LangGraph graph assembly | 2 |
| 9 | API endpoints | 2 |
| 10 | Frontend API + store | 2 |
| 11 | Frontend GenreManagement component | 4 |
| 12 | E2E tests | 1 |
| **Total** | | **30 files** |
