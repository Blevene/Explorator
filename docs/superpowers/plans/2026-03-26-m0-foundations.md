# M0 — Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the MusicExplorator monorepo with all foundational infrastructure: Python backend, React frontend, Neo4j persistence, Pydantic domain models, genre YAML system, and a working session CRUD flow from frontend to database.

**Architecture:** Monorepo with `backend/` (FastAPI + Pydantic v2, managed by uv) and `frontend/` (React + Vite + Tailwind). Neo4j runs via Docker Compose. Genre profiles are YAML files validated by Pydantic and synced to Neo4j. Gemini client is configured but not heavily exercised until M1.

**Tech Stack:** Python 3.12, uv, ruff, mypy, FastAPI, Pydantic v2, Neo4j 5 Community, neo4j Python driver, python-ulid, React 18, TypeScript, Vite, Tailwind CSS, Zustand, TanStack Query

---

## File Map

### Backend — Project Config
- `backend/pyproject.toml` — uv project, dependencies, ruff + mypy config
- `backend/Dockerfile` — Python container for dev

### Backend — Pydantic Models
- `backend/src/explorator/__init__.py` — package init
- `backend/src/explorator/models/__init__.py` — re-export all models
- `backend/src/explorator/models/base.py` — BaseEntity, CandidateBase, EvaluationBase
- `backend/src/explorator/models/session.py` — Session, SessionContext, CreativeBrief
- `backend/src/explorator/models/style.py` — GenreProfile, GenreRule, AntiPattern, HarmonicGrammar
- `backend/src/explorator/models/harmony.py` — ChordEvent, ProgressionCandidate, ProgressionFamily, RomanNumeralAnalysis
- `backend/src/explorator/models/realization.py` — VoicingPlan, BassLine, ArrangementCandidate, ArrangementFamily
- `backend/src/explorator/models/evaluation.py` — EvaluationBundle, TheoryEvaluation, VoiceLeadingEvaluation, RegisterDensityEvaluation, PlayabilityEvaluation, GrooveEvaluation, MelodyHarmonyEvaluation, AggregateScorecard, ObjectiveWeights
- `backend/src/explorator/models/search.py` — SearchPlan, SearchRound, MutationRecord, ParetoFrontSnapshot, FinalSelection
- `backend/src/explorator/models/memory.py` — UserPreferenceProfile, UserFeedbackEvent, PatternLibraryEntry, RetrievalQuery, RetrievalResult
- `backend/src/explorator/models/export.py` — CandidateExplanation, ComparisonView, RenderArtifact, ExportPackage, ProvenanceTrace
- `backend/src/explorator/models/stubs.py` — Melody, InstrumentRealizationPlan (forward-compat stubs)

### Backend — Neo4j Graph Layer
- `backend/src/explorator/graph/__init__.py`
- `backend/src/explorator/graph/connection.py` — Neo4j driver singleton, connection management
- `backend/src/explorator/graph/schema.py` — Cypher constraints, indexes, schema init
- `backend/src/explorator/graph/repository.py` — Base repository (generic create/read/update by ID)
- `backend/src/explorator/graph/session_repo.py` — Session CRUD + relationships
- `backend/src/explorator/graph/style_repo.py` — GenreProfile, GenreRule, AntiPattern, HarmonicGrammar upsert/read

### Backend — Genre System
- `backend/src/explorator/domain/__init__.py`
- `backend/src/explorator/domain/style/__init__.py`
- `backend/src/explorator/domain/style/schema.py` — Pydantic models for YAML parsing (GenreProfileYAML, GenreRulesYAML, HarmonicGrammarYAML)
- `backend/src/explorator/domain/style/loader.py` — Read YAML, validate, sync to Neo4j
- `backend/src/explorator/domain/style/service.py` — Genre profile retrieval, rule lookup
- `backend/src/explorator/domain/style/genres/dream_pop.yaml`
- `backend/src/explorator/domain/style/genres/synthwave.yaml`
- `backend/src/explorator/domain/style/genres/cinematic.yaml`
- `backend/src/explorator/domain/style/rules/dream_pop_rules.yaml`
- `backend/src/explorator/domain/style/rules/synthwave_rules.yaml`
- `backend/src/explorator/domain/style/rules/cinematic_rules.yaml`
- `backend/src/explorator/domain/style/grammars/dream_pop_grammar.yaml`
- `backend/src/explorator/domain/style/grammars/synthwave_grammar.yaml`
- `backend/src/explorator/domain/style/grammars/cinematic_grammar.yaml`

### Backend — Gemini Adapter
- `backend/src/explorator/adapters/__init__.py`
- `backend/src/explorator/adapters/gemini.py` — Gemini client with Pro/Flash routing

### Backend — Settings
- `backend/src/explorator/config.py` — Pydantic Settings

### Backend — FastAPI App
- `backend/src/explorator/api/__init__.py`
- `backend/src/explorator/api/app.py` — FastAPI app factory, lifespan, CORS
- `backend/src/explorator/api/deps.py` — Dependency injection (Neo4j driver, services)
- `backend/src/explorator/api/middleware.py` — Auth stub
- `backend/src/explorator/api/routes/__init__.py`
- `backend/src/explorator/api/routes/sessions.py` — Session CRUD
- `backend/src/explorator/api/routes/genres.py` — Genre list

### Backend — Tests
- `backend/tests/__init__.py`
- `backend/tests/conftest.py` — Shared fixtures
- `backend/tests/unit/__init__.py`
- `backend/tests/unit/models/test_base.py`
- `backend/tests/unit/models/test_session.py`
- `backend/tests/unit/models/test_style.py`
- `backend/tests/unit/domain/test_genre_loader.py`
- `backend/tests/integration/__init__.py`
- `backend/tests/integration/test_session_api.py`
- `backend/tests/integration/test_genre_sync.py`

### Frontend
- `frontend/package.json`
- `frontend/tsconfig.json`
- `frontend/tsconfig.app.json`
- `frontend/tsconfig.node.json`
- `frontend/vite.config.ts`
- `frontend/tailwind.config.ts`
- `frontend/postcss.config.js`
- `frontend/index.html`
- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/index.css` — Tailwind directives + dark theme
- `frontend/src/services/api.ts` — API client
- `frontend/src/stores/sessionStore.ts` — Zustand session state
- `frontend/src/views/Dashboard.tsx` — Session list + new session
- `frontend/src/views/SessionWorkspace.tsx` — Placeholder workspace

### Root
- `docker-compose.yml` — Neo4j + backend
- `Makefile` — dev commands
- `.env.example` — env template

---

## Task 1: Backend Project Scaffold

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/src/explorator/__init__.py`
- Create: `backend/src/explorator/config.py`

- [ ] **Step 1: Initialize backend with uv**

```bash
cd <repo-root>
mkdir -p backend/src/explorator
cd backend
uv init --lib --name explorator
```

- [ ] **Step 2: Configure pyproject.toml**

Replace the generated `backend/pyproject.toml` with:

```toml
[project]
name = "explorator"
version = "0.1.0"
description = "Genre-aware musical exploration engine"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.7.0",
    "neo4j>=5.27.0",
    "python-ulid>=3.0.0",
    "pyyaml>=6.0.0",
    "google-genai>=1.0.0",
    "httpx>=0.28.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.25.0",
    "ruff>=0.9.0",
    "mypy>=1.14.0",
    "types-PyYAML>=6.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/explorator"]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "TCH"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: Install dependencies**

```bash
cd backend
uv sync --all-extras
```

- [ ] **Step 4: Create package init**

Create `backend/src/explorator/__init__.py`:

```python
"""MusicExplorator — Genre-aware musical exploration engine."""
```

- [ ] **Step 5: Create settings**

Create `backend/src/explorator/config.py`:

```python
"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "explorator_dev"

    # Gemini
    gemini_api_key: str = ""
    gemini_pro_model: str = "gemini-pro-latest"
    gemini_flash_model: str = "gemini-flash-latest"

    # Generation defaults
    default_max_rounds: int = 4
    default_target_score: float = 8.5
    default_generation_mode: str = "balanced"

    # Timeouts
    gemini_timeout_seconds: int = 30
    neo4j_query_timeout_seconds: int = 5


settings = Settings()
```

- [ ] **Step 6: Verify ruff and mypy work**

```bash
cd backend
uv run ruff check src/
uv run mypy src/
```

Expected: Both pass with no errors.

- [ ] **Step 7: Commit**

```bash
cd <repo-root>
git add backend/
git commit -m "feat(m0): scaffold backend project with uv, ruff, mypy"
```

---

## Task 2: Pydantic Base Models

**Files:**
- Create: `backend/src/explorator/models/__init__.py`
- Create: `backend/src/explorator/models/base.py`
- Test: `backend/tests/unit/models/test_base.py`

- [ ] **Step 1: Create test directory structure**

```bash
mkdir -p backend/tests/unit/models
touch backend/tests/__init__.py backend/tests/unit/__init__.py backend/tests/unit/models/__init__.py
```

- [ ] **Step 2: Write failing tests for base models**

Create `backend/tests/unit/models/test_base.py`:

```python
"""Tests for base entity models."""

from datetime import datetime, timezone

from explorator.models.base import BaseEntity, CandidateBase, EvaluationBase


def test_base_entity_creation():
    entity = BaseEntity(
        id="test_01",
        type="test",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        status="active",
    )
    assert entity.id == "test_01"
    assert entity.type == "test"
    assert entity.version == 1
    assert entity.metadata == {}
    assert entity.status == "active"


def test_base_entity_requires_id():
    try:
        BaseEntity(
            type="test",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            status="active",
        )  # type: ignore[call-arg]
        assert False, "Should have raised ValidationError"
    except Exception:
        pass


def test_candidate_base_extends_base_entity():
    candidate = CandidateBase(
        id="prog_01",
        type="progression_candidate",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        status="candidate",
        session_id="sess_01",
        family_id=None,
        rationale="Test progression",
    )
    assert candidate.session_id == "sess_01"
    assert candidate.intent_tags == []
    assert candidate.mutation_lineage_ids == []
    assert candidate.warnings == []


def test_evaluation_base_extends_base_entity():
    evaluation = EvaluationBase(
        id="eval_01",
        type="theory_evaluation",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        status="completed",
        candidate_id="prog_01",
        evaluation_type="theory",
    )
    assert evaluation.candidate_id == "prog_01"
    assert evaluation.evaluation_type == "theory"
    assert evaluation.notes == []
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd backend
uv run pytest tests/unit/models/test_base.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'explorator.models'`

- [ ] **Step 4: Implement base models**

Create `backend/src/explorator/models/__init__.py`:

```python
"""Pydantic v2 canonical object model for MusicExplorator."""
```

Create `backend/src/explorator/models/base.py`:

```python
"""Shared base interfaces for all domain entities."""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class BaseEntity(BaseModel):
    """Base interface for all persistent domain entities.

    Every entity carries: id, type, timestamps, version, status, metadata.
    """

    id: str
    type: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    version: int = 1
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateBase(BaseEntity):
    """Shared interface for ProgressionCandidate and ArrangementCandidate."""

    session_id: str
    family_id: str | None = None
    intent_tags: list[str] = Field(default_factory=list)
    rationale: str
    mutation_lineage_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EvaluationBase(BaseEntity):
    """Shared interface for all evaluation types."""

    candidate_id: str
    evaluation_type: str
    notes: list[str] = Field(default_factory=list)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend
uv run pytest tests/unit/models/test_base.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 6: Run ruff and mypy**

```bash
cd backend
uv run ruff check src/ tests/
uv run mypy src/
```

Expected: Both pass.

- [ ] **Step 7: Commit**

```bash
cd <repo-root>
git add backend/src/explorator/models/ backend/tests/
git commit -m "feat(m0): add Pydantic base models (BaseEntity, CandidateBase, EvaluationBase)"
```

---

## Task 3: Session and Style Pydantic Models

**Files:**
- Create: `backend/src/explorator/models/session.py`
- Create: `backend/src/explorator/models/style.py`
- Create: `backend/src/explorator/models/evaluation.py`
- Create: `backend/src/explorator/models/search.py`
- Create: `backend/src/explorator/models/harmony.py`
- Create: `backend/src/explorator/models/realization.py`
- Create: `backend/src/explorator/models/memory.py`
- Create: `backend/src/explorator/models/export.py`
- Create: `backend/src/explorator/models/stubs.py`
- Test: `backend/tests/unit/models/test_session.py`
- Test: `backend/tests/unit/models/test_style.py`

- [ ] **Step 1: Write failing tests for Session and CreativeBrief**

Create `backend/tests/unit/models/test_session.py`:

```python
"""Tests for session domain models."""

from explorator.models.session import CreativeBrief, Session, SessionContext


def test_session_creation():
    session = Session(
        id="sess_01",
        type="session",
        status="active",
        mode="full_exploration",
    )
    assert session.id == "sess_01"
    assert session.mode == "full_exploration"
    assert session.creative_brief_id is None
    assert session.progression_candidate_ids == []


def test_creative_brief_creation():
    brief = CreativeBrief(
        id="brief_01",
        type="creative_brief",
        status="active",
        genre="dream_pop",
        mood_targets=["wistful", "haunted"],
        key_center="A",
        mode="major",
        phrase_length_bars=8,
        complexity_target="medium",
        novelty_target="moderate",
        generation_mode="balanced",
    )
    assert brief.genre == "dream_pop"
    assert brief.mood_targets == ["wistful", "haunted"]
    assert brief.phrase_length_bars == 8
    assert brief.generation_mode == "balanced"
    assert brief.meter == "4/4"
    assert brief.seed_melody_id is None


def test_session_context_creation():
    ctx = SessionContext(
        id="ctx_01",
        type="session_context",
        status="active",
        session_id="sess_01",
        active_phase="harmonic_generation",
        current_round=1,
        search_budget_remaining=12,
    )
    assert ctx.current_round == 1
    assert ctx.active_phase == "harmonic_generation"
```

- [ ] **Step 2: Write failing tests for GenreProfile**

Create `backend/tests/unit/models/test_style.py`:

```python
"""Tests for style domain models."""

from explorator.models.style import AntiPattern, GenreProfile, GenreRule, HarmonicGrammar


def test_genre_profile_creation():
    profile = GenreProfile(
        id="genre_dream_pop_01",
        type="genre_profile",
        status="active",
        genre="dream_pop",
        display_name="Dream Pop",
        harmonic_vocabulary=["maj7", "add9", "sus2"],
        harmonic_tendencies={
            "functional_strength": "low_medium",
            "chromaticism_level": "moderate",
        },
        voicing_tendencies={"spacing": "open", "register_bias": "mid_high"},
        bass_tendencies={"root_emphasis": "medium"},
        groove_tendencies={"comp_density": "sparse"},
        common_devices=["borrowed minor iv"],
        experimentation_envelope={
            "harmonic_deviation_tolerance": 0.65,
            "voicing_deviation_tolerance": 0.80,
            "groove_deviation_tolerance": 0.40,
        },
    )
    assert profile.genre == "dream_pop"
    assert "maj7" in profile.harmonic_vocabulary


def test_genre_rule_creation():
    rule = GenreRule(
        id="rule_01",
        type="genre_rule",
        status="active",
        genre="dream_pop",
        rule_type="voicing_preference",
        name="Prefer open voicings",
        description="Spread voicings across mid-high register.",
        weight=0.88,
    )
    assert rule.weight == 0.88
    assert not rule.anti_rule


def test_anti_pattern_creation():
    ap = AntiPattern(
        id="anti_01",
        type="anti_pattern",
        status="active",
        genre="dream_pop",
        scope="harmony",
        name="Hard bop dominant chains",
        description="Extended ii-V-I sequences break the floating quality.",
        severity=0.85,
    )
    assert ap.severity == 0.85
    assert ap.scope == "harmony"


def test_harmonic_grammar_creation():
    grammar = HarmonicGrammar(
        id="grammar_01",
        type="harmonic_grammar",
        status="active",
        genre_profile_id="genre_dream_pop_01",
        preferred_chord_qualities=["maj7", "add9", "sus2", "m7"],
        allowed_borrowed_chords=["iv", "bVI", "bVII"],
        cadence_archetypes=["soft_plagal", "open_loop_return"],
    )
    assert "iv" in grammar.allowed_borrowed_chords
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd backend
uv run pytest tests/unit/models/ -v
```

Expected: FAIL — modules not found.

- [ ] **Step 4: Implement Session models**

Create `backend/src/explorator/models/session.py`:

```python
"""Session, SessionContext, and CreativeBrief models."""

from pydantic import Field

from explorator.models.base import BaseEntity


class Session(BaseEntity):
    """Top-level container for one exploration run."""

    mode: str = "full_exploration"
    creative_brief_id: str | None = None
    genre_profile_id: str | None = None
    search_plan_id: str | None = None
    progression_candidate_ids: list[str] = Field(default_factory=list)
    arrangement_candidate_ids: list[str] = Field(default_factory=list)
    feedback_event_ids: list[str] = Field(default_factory=list)
    final_selection_id: str | None = None
    provenance_trace_id: str | None = None


class CreativeBrief(BaseEntity):
    """Normalized statement of user intent."""

    genre: str
    subgenre: str | None = None
    mood_targets: list[str] = Field(default_factory=list)
    energy_level: str | None = None
    key_center: str | None = None
    mode: str | None = "major"
    meter: str = "4/4"
    tempo_hint_bpm: int | None = None
    phrase_length_bars: int = 8
    form_hint: str | None = None
    complexity_target: str = "medium"
    novelty_target: str = "moderate"
    generation_mode: str = "balanced"
    instrumentation_targets: list[str] = Field(default_factory=list)
    must_have_constraints: dict[str, bool] = Field(default_factory=dict)
    avoid_constraints: dict[str, bool] = Field(default_factory=dict)
    seed_progression: list[str] | None = None
    seed_melody_id: str | None = None
    seed_bassline_id: str | None = None
    reference_artists: list[str] = Field(default_factory=list)
    user_language_notes: list[str] = Field(default_factory=list)


class SessionContext(BaseEntity):
    """Dynamic in-session state."""

    session_id: str
    active_phase: str = "initialized"
    current_round: int = 0
    selected_progression_family_ids: list[str] = Field(default_factory=list)
    selected_arrangement_family_ids: list[str] = Field(default_factory=list)
    search_budget_remaining: int = 12
    current_objective_weights_id: str | None = None
```

- [ ] **Step 5: Implement Style models**

Create `backend/src/explorator/models/style.py`:

```python
"""GenreProfile, GenreRule, AntiPattern, HarmonicGrammar models."""

from typing import Any

from pydantic import Field

from explorator.models.base import BaseEntity


class GenreProfile(BaseEntity):
    """Operational representation of genre knowledge."""

    genre: str
    display_name: str = ""
    subgenre: str | None = None
    harmonic_vocabulary: list[str] = Field(default_factory=list)
    harmonic_tendencies: dict[str, str] = Field(default_factory=dict)
    voicing_tendencies: dict[str, str] = Field(default_factory=dict)
    bass_tendencies: dict[str, str] = Field(default_factory=dict)
    groove_tendencies: dict[str, str] = Field(default_factory=dict)
    common_devices: list[str] = Field(default_factory=list)
    anti_patterns: list[str] = Field(default_factory=list)
    experimentation_envelope: dict[str, float] = Field(default_factory=dict)


class GenreRule(BaseEntity):
    """Individual reusable rule with weight and applicability conditions."""

    genre: str
    rule_type: str
    name: str
    description: str
    weight: float = 0.5
    applicability: dict[str, Any] = Field(default_factory=dict)
    anti_rule: bool = False


class AntiPattern(BaseEntity):
    """Pattern that breaks genre identity."""

    genre: str
    scope: str
    name: str
    description: str
    severity: float = 0.5


class HarmonicGrammar(BaseEntity):
    """Genre's operational harmonic syntax."""

    genre_profile_id: str
    preferred_chord_qualities: list[str] = Field(default_factory=list)
    allowed_borrowed_chords: list[str] = Field(default_factory=list)
    cadence_archetypes: list[str] = Field(default_factory=list)
    harmonic_rhythm_defaults: dict[str, float] = Field(default_factory=dict)
    functional_motion_bias: dict[str, float] = Field(default_factory=dict)
```

- [ ] **Step 6: Implement remaining model files**

Create `backend/src/explorator/models/harmony.py`:

```python
"""Harmonic generation models."""

from pydantic import BaseModel, Field

from explorator.models.base import BaseEntity, CandidateBase


class ChordEvent(BaseModel):
    """One harmonic event in time (embedded, not a graph node)."""

    bar: int
    beat: float = 1.0
    duration_beats: float = 4.0
    symbol: str
    function_label: str | None = None
    harmonic_role_tags: list[str] = Field(default_factory=list)


class ProgressionCandidate(CandidateBase):
    """Candidate chord progression before realization."""

    key_center: str
    mode: str = "major"
    phrase_length_bars: int = 8
    chord_events: list[ChordEvent] = Field(default_factory=list)
    roman_numeral_analysis_id: str | None = None
    generator_mode: str = "balanced"
    source_type: str = "generated"


class ProgressionFamily(BaseEntity):
    """Groups related harmonic variants."""

    session_id: str
    root_progression_candidate_id: str
    member_progression_candidate_ids: list[str] = Field(default_factory=list)
    family_description: str = ""


class RomanNumeralAnalysis(BaseEntity):
    """Symbolic harmonic interpretation."""

    progression_candidate_id: str
    analysis_events: list[dict[str, str | float]] = Field(default_factory=list)
    analysis_notes: list[str] = Field(default_factory=list)
```

Create `backend/src/explorator/models/realization.py`:

```python
"""Realization models: voicings, bass, arrangements."""

from pydantic import Field

from explorator.models.base import BaseEntity, CandidateBase


class VoicingPlan(BaseEntity):
    """How a progression is voiced."""

    progression_candidate_id: str | None = None
    instrument: str = "electric_piano"
    global_strategy: str = ""
    density_level: str = "medium"
    register_profile: str = "mid_high"
    voicing_events_json: list[dict] = Field(default_factory=list)  # type: ignore[type-arg]


class BassLine(BaseEntity):
    """Bass realization layer."""

    progression_candidate_id: str | None = None
    style_mode: str = "supportive"
    contour_type: str = "mostly_stepwise"
    rhythmic_density: str = "low"
    relationship_to_harmony: str = "stabilizing"
    note_events_json: list[dict] = Field(default_factory=list)  # type: ignore[type-arg]


class ArrangementCandidate(CandidateBase):
    """Realized musical object combining progression + realization layers."""

    progression_candidate_id: str
    voicing_plan_id: str | None = None
    bass_line_id: str | None = None
    melodic_complement_id: str | None = None
    groove_pattern_id: str | None = None
    instrument_realization_plan_id: str | None = None
    render_artifact_ids: list[str] = Field(default_factory=list)


class ArrangementFamily(BaseEntity):
    """Groups related arrangement variants."""

    session_id: str
    root_arrangement_candidate_id: str
    member_arrangement_candidate_ids: list[str] = Field(default_factory=list)
    family_description: str = ""
```

Create `backend/src/explorator/models/evaluation.py`:

```python
"""Evaluation, scoring, and objective weight models."""

from typing import Any

from pydantic import Field

from explorator.models.base import BaseEntity, EvaluationBase


class TheoryEvaluation(EvaluationBase):
    """Harmonic theory scoring."""

    genre_fit: float = 0.0
    emotional_fit: float = 0.0
    theoretical_coherence: float = 0.0
    cadence_quality: float = 0.0
    novelty: float = 0.0
    loopability: float = 0.0


class VoiceLeadingEvaluation(EvaluationBase):
    """Voice leading quality scoring."""

    smoothness_score: float = 0.0
    common_tone_retention_score: float = 0.0
    awkward_leap_penalty: float = 0.0
    resolution_quality: float = 0.0


class RegisterDensityEvaluation(EvaluationBase):
    """Register and density balance scoring."""

    register_balance_score: float = 0.0
    mud_risk_score: float = 0.0
    overcrowding_risk_score: float = 0.0
    spacing_quality: float = 0.0


class PlayabilityEvaluation(EvaluationBase):
    """Playability scoring per instrument."""

    piano_playability: float = 0.0
    guitar_playability: float = 0.0
    ensemble_playability: float = 0.0
    simplification_recommendations: list[str] = Field(default_factory=list)


class GrooveEvaluation(EvaluationBase):
    """Groove authenticity scoring. Deferred to M5."""

    groove_authenticity: float = 0.0
    rhythmic_coherence: float = 0.0
    style_alignment: float = 0.0


class MelodyHarmonyEvaluation(EvaluationBase):
    """Melody-harmony compatibility. Deferred to v1.5."""

    melody_support_score: float = 0.0
    tension_justification_score: float = 0.0
    collision_risk_score: float = 0.0


class EvaluationBundle(BaseEntity):
    """Groups all evaluations for one candidate."""

    candidate_id: str
    candidate_type: str
    theory_evaluation_id: str | None = None
    voice_leading_evaluation_id: str | None = None
    register_density_evaluation_id: str | None = None
    playability_evaluation_id: str | None = None
    groove_evaluation_id: str | None = None
    melody_harmony_evaluation_id: str | None = None
    aggregate_scorecard_id: str | None = None


class AggregateScorecard(BaseEntity):
    """Normalized final scores."""

    candidate_id: str
    scores: dict[str, float] = Field(default_factory=dict)
    weighted_total: float = 0.0
    rank_within_round: int = 0
    pareto_tags: list[str] = Field(default_factory=list)


class ObjectiveWeights(BaseEntity):
    """Configurable scoring weights per dimension."""

    profile_name: str = "default"
    weights: dict[str, float] = Field(default_factory=dict)
```

Create `backend/src/explorator/models/search.py`:

```python
"""Search plan, rounds, mutation, and selection models."""

from typing import Any

from pydantic import BaseModel, Field

from explorator.models.base import BaseEntity


class StopConditions(BaseModel):
    """Configurable stop conditions."""

    target_score: float = 8.5
    max_rounds: int = 4


class SearchPlan(BaseEntity):
    """Exploration strategy for the session."""

    session_id: str
    search_strategy: str = "beam_plus_mutation"
    initial_generation_count: int = 12
    progression_selection_count: int = 4
    arrangement_selection_count: int = 4
    max_rounds: int = 4
    mutation_budget_per_round: int = 6
    diversity_target: float = 0.65
    stop_conditions: StopConditions = Field(default_factory=StopConditions)
    random_seed: int | None = None


class SearchRound(BaseEntity):
    """One iteration of exploration."""

    session_id: str
    round_number: int
    input_candidate_ids: list[str] = Field(default_factory=list)
    generated_candidate_ids: list[str] = Field(default_factory=list)
    selected_candidate_ids: list[str] = Field(default_factory=list)
    eliminated_candidate_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class MutationChange(BaseModel):
    """One change within a mutation."""

    field: str
    operation: str
    description: str


class MutationRecord(BaseEntity):
    """Tracks a concrete transformation."""

    source_candidate_id: str
    source_candidate_type: str
    result_candidate_id: str
    result_candidate_type: str
    mutation_scope: str
    changes: list[MutationChange] = Field(default_factory=list)
    reason: str = ""
    predicted_effects: list[str] = Field(default_factory=list)
    actual_score_delta: dict[str, float] = Field(default_factory=dict)


class ParetoFrontSnapshot(BaseEntity):
    """Non-dominated candidates for a round."""

    session_id: str
    round_number: int
    candidate_ids: list[str] = Field(default_factory=list)
    axes: list[str] = Field(default_factory=list)


class FinalSelection(BaseEntity):
    """Chosen outputs."""

    session_id: str
    selected_candidate_ids: list[str] = Field(default_factory=list)
    selection_roles: dict[str, str] = Field(default_factory=dict)
    selection_notes: list[str] = Field(default_factory=list)
```

Create `backend/src/explorator/models/memory.py`:

```python
"""Memory, feedback, and user preference models."""

from typing import Any

from pydantic import Field

from explorator.models.base import BaseEntity


class UserPreferenceProfile(BaseEntity):
    """Persistent user taste model."""

    preferred_complexity_band: str = "medium"
    preferred_novelty_band: str = "moderate"
    voicing_preferences: dict[str, bool] = Field(default_factory=dict)
    bass_preferences: dict[str, bool] = Field(default_factory=dict)
    melodic_preferences: dict[str, bool] = Field(default_factory=dict)
    genre_biases: dict[str, float] = Field(default_factory=dict)
    disliked_patterns: list[str] = Field(default_factory=list)


class UserFeedbackEvent(BaseEntity):
    """Explicit user reaction."""

    session_id: str
    candidate_id: str
    feedback_type: str = "text_reaction"
    content: str = ""
    interpreted_adjustments: dict[str, Any] = Field(default_factory=dict)


class PatternLibraryEntry(BaseEntity):
    """Reusable discovered pattern. Deferred to M5."""

    pattern_type: str
    genre: str
    tags: list[str] = Field(default_factory=list)
    source_candidate_id: str | None = None
    abstracted_pattern: dict[str, Any] = Field(default_factory=dict)
    success_metrics: dict[str, float] = Field(default_factory=dict)
    notes: str = ""


class RetrievalQuery(BaseEntity):
    """Memory retrieval request. Deferred to M5."""

    session_id: str
    target_store: str = "pattern_library"
    query_tags: list[str] = Field(default_factory=list)
    top_k: int = 5


class RetrievalResult(BaseEntity):
    """Memory retrieval result. Deferred to M5."""

    retrieval_query_id: str
    matched_entry_ids: list[str] = Field(default_factory=list)
    scores: list[float] = Field(default_factory=list)
```

Create `backend/src/explorator/models/export.py`:

```python
"""Presentation and export models."""

from typing import Any

from pydantic import Field

from explorator.models.base import BaseEntity


class ProvenanceTrace(BaseEntity):
    """Full decision lineage of a session."""

    session_id: str
    events: list[dict[str, Any]] = Field(default_factory=list)


class CandidateExplanation(BaseEntity):
    """Human-readable explanation of one result."""

    candidate_id: str
    summary: str = ""
    why_it_works: list[str] = Field(default_factory=list)
    what_is_experimental: list[str] = Field(default_factory=list)
    recommended_use_cases: list[str] = Field(default_factory=list)


class ComparisonView(BaseEntity):
    """Contrasted presentation set."""

    session_id: str
    candidate_ids: list[str] = Field(default_factory=list)
    comparison_axes: list[str] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)


class RenderArtifact(BaseEntity):
    """Exported render or file."""

    candidate_id: str
    artifact_type: str
    path: str
    render_metadata: dict[str, Any] = Field(default_factory=dict)


class ExportPackage(BaseEntity):
    """Groups outputs for downstream use."""

    session_id: str
    included_candidate_ids: list[str] = Field(default_factory=list)
    included_artifact_ids: list[str] = Field(default_factory=list)
    formats: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
```

Create `backend/src/explorator/models/stubs.py`:

```python
"""Forward-compatibility stub models. Not active until v1.5/M5."""

from typing import Any

from pydantic import Field

from explorator.models.base import BaseEntity


class Melody(BaseEntity):
    """User-supplied or generated primary melody. Deferred to v1.5."""

    session_id: str
    source_type: str = "user_supplied"
    note_events_json: list[dict[str, Any]] = Field(default_factory=list)
    range_low: str | None = None
    range_high: str | None = None


class InstrumentRealizationPlan(BaseEntity):
    """Instrument role assignments. Deferred to M5."""

    arrangement_candidate_id: str
    instrument_roles: list[dict[str, str]] = Field(default_factory=list)
    orchestration_notes: list[str] = Field(default_factory=list)
```

- [ ] **Step 7: Run all model tests**

```bash
cd backend
uv run pytest tests/unit/models/ -v
```

Expected: All tests PASS.

- [ ] **Step 8: Run ruff and mypy**

```bash
cd backend
uv run ruff check src/ tests/
uv run mypy src/
```

Expected: Both pass.

- [ ] **Step 9: Commit**

```bash
cd <repo-root>
git add backend/src/explorator/models/ backend/tests/
git commit -m "feat(m0): add all Pydantic domain models (session, style, harmony, evaluation, search, memory, export)"
```

---

## Task 4: Docker Compose and Neo4j Schema

**Files:**
- Create: `docker-compose.yml`
- Create: `backend/src/explorator/graph/__init__.py`
- Create: `backend/src/explorator/graph/connection.py`
- Create: `backend/src/explorator/graph/schema.py`
- Create: `.env.example`

- [ ] **Step 1: Create docker-compose.yml**

Create `docker-compose.yml` at repo root:

```yaml
services:
  neo4j:
    image: neo4j:5-community
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      NEO4J_AUTH: neo4j/explorator_dev
      NEO4J_PLUGINS: '[]'
    volumes:
      - neo4j_data:/data
    healthcheck:
      test: ["CMD", "neo4j", "status"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  neo4j_data:
```

- [ ] **Step 2: Create .env.example**

Create `.env.example` at repo root:

```bash
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=explorator_dev

# Gemini
GEMINI_API_KEY=your-api-key-here
GEMINI_PRO_MODEL=gemini-pro-latest
GEMINI_FLASH_MODEL=gemini-flash-latest
```

- [ ] **Step 3: Create Neo4j connection manager**

Create `backend/src/explorator/graph/__init__.py`:

```python
"""Neo4j graph persistence layer."""
```

Create `backend/src/explorator/graph/connection.py`:

```python
"""Neo4j driver connection management."""

from neo4j import AsyncGraphDatabase, AsyncDriver

from explorator.config import settings


_driver: AsyncDriver | None = None


async def get_driver() -> AsyncDriver:
    """Get or create the Neo4j async driver singleton."""
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


async def close_driver() -> None:
    """Close the Neo4j driver."""
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None
```

- [ ] **Step 4: Create Neo4j schema initialization**

Create `backend/src/explorator/graph/schema.py`:

```python
"""Neo4j schema constraints, indexes, and initialization."""

from neo4j import AsyncDriver

CONSTRAINTS = [
    "CREATE CONSTRAINT session_id IF NOT EXISTS FOR (n:Session) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT session_context_id IF NOT EXISTS FOR (n:SessionContext) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT creative_brief_id IF NOT EXISTS FOR (n:CreativeBrief) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT genre_profile_id IF NOT EXISTS FOR (n:GenreProfile) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT genre_rule_id IF NOT EXISTS FOR (n:GenreRule) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT anti_pattern_id IF NOT EXISTS FOR (n:AntiPattern) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT harmonic_grammar_id IF NOT EXISTS FOR (n:HarmonicGrammar) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT search_plan_id IF NOT EXISTS FOR (n:SearchPlan) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT objective_weights_id IF NOT EXISTS FOR (n:ObjectiveWeights) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT user_preference_profile_id IF NOT EXISTS FOR (n:UserPreferenceProfile) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT progression_candidate_id IF NOT EXISTS FOR (n:ProgressionCandidate:Candidate) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT progression_family_id IF NOT EXISTS FOR (n:ProgressionFamily) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT roman_numeral_analysis_id IF NOT EXISTS FOR (n:RomanNumeralAnalysis) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT arrangement_candidate_id IF NOT EXISTS FOR (n:ArrangementCandidate:Candidate) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT arrangement_family_id IF NOT EXISTS FOR (n:ArrangementFamily) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT voicing_plan_id IF NOT EXISTS FOR (n:VoicingPlan) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT bass_line_id IF NOT EXISTS FOR (n:BassLine) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT evaluation_bundle_id IF NOT EXISTS FOR (n:EvaluationBundle) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT evaluation_id IF NOT EXISTS FOR (n:Evaluation) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT aggregate_scorecard_id IF NOT EXISTS FOR (n:AggregateScorecard) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT search_round_id IF NOT EXISTS FOR (n:SearchRound) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT mutation_record_id IF NOT EXISTS FOR (n:MutationRecord) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT pareto_front_snapshot_id IF NOT EXISTS FOR (n:ParetoFrontSnapshot) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT final_selection_id IF NOT EXISTS FOR (n:FinalSelection) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT user_feedback_event_id IF NOT EXISTS FOR (n:UserFeedbackEvent) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT candidate_explanation_id IF NOT EXISTS FOR (n:CandidateExplanation) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT comparison_view_id IF NOT EXISTS FOR (n:ComparisonView) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT render_artifact_id IF NOT EXISTS FOR (n:RenderArtifact) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT export_package_id IF NOT EXISTS FOR (n:ExportPackage) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT provenance_trace_id IF NOT EXISTS FOR (n:ProvenanceTrace) REQUIRE n.id IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX genre_profile_genre IF NOT EXISTS FOR (n:GenreProfile) ON (n.genre)",
    "CREATE INDEX candidate_status IF NOT EXISTS FOR (n:Candidate) ON (n.status)",
    "CREATE INDEX scorecard_weighted_total IF NOT EXISTS FOR (n:AggregateScorecard) ON (n.weighted_total)",
    "CREATE INDEX pattern_library_genre IF NOT EXISTS FOR (n:PatternLibraryEntry) ON (n.genre)",
]


async def init_schema(driver: AsyncDriver) -> None:
    """Create all constraints and indexes."""
    async with driver.session() as session:
        for constraint in CONSTRAINTS:
            await session.run(constraint)
        for index in INDEXES:
            await session.run(index)
```

- [ ] **Step 5: Start Neo4j and verify**

```bash
cd <repo-root>
docker compose up -d neo4j
# Wait for healthcheck
sleep 10
docker compose ps
```

Expected: neo4j service is healthy.

- [ ] **Step 6: Commit**

```bash
cd <repo-root>
git add docker-compose.yml .env.example backend/src/explorator/graph/
git commit -m "feat(m0): add Docker Compose with Neo4j and graph schema initialization"
```

---

## Task 5: Neo4j Base Repository and Session Repository

**Files:**
- Create: `backend/src/explorator/graph/repository.py`
- Create: `backend/src/explorator/graph/session_repo.py`
- Test: `backend/tests/integration/test_session_repo.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Create test conftest with Neo4j fixture**

Create `backend/tests/conftest.py`:

```python
"""Shared test fixtures."""

import asyncio
from collections.abc import AsyncGenerator

import pytest
from neo4j import AsyncDriver, AsyncGraphDatabase

from explorator.graph.schema import init_schema


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def neo4j_driver() -> AsyncGenerator[AsyncDriver, None]:
    """Connect to test Neo4j instance."""
    driver = AsyncGraphDatabase.driver(
        "bolt://localhost:7687",
        auth=("neo4j", "explorator_dev"),
    )
    await init_schema(driver)
    yield driver
    await driver.close()


@pytest.fixture(autouse=True)
async def clean_db(neo4j_driver: AsyncDriver) -> AsyncGenerator[None, None]:
    """Clean all nodes between tests."""
    yield
    async with neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
```

- [ ] **Step 2: Write failing integration tests**

Create `backend/tests/integration/__init__.py`:

```python
```

Create `backend/tests/integration/test_session_repo.py`:

```python
"""Integration tests for session repository."""

from neo4j import AsyncDriver

from explorator.graph.session_repo import SessionRepository
from explorator.models.session import Session


async def test_create_and_read_session(neo4j_driver: AsyncDriver):
    repo = SessionRepository(neo4j_driver)
    session = Session(
        id="sess_test_01",
        type="session",
        status="active",
        mode="full_exploration",
    )
    await repo.create(session)
    result = await repo.get_by_id("sess_test_01")
    assert result is not None
    assert result["id"] == "sess_test_01"
    assert result["status"] == "active"
    assert result["mode"] == "full_exploration"


async def test_list_sessions(neo4j_driver: AsyncDriver):
    repo = SessionRepository(neo4j_driver)
    for i in range(3):
        session = Session(
            id=f"sess_list_{i}",
            type="session",
            status="active",
            mode="full_exploration",
        )
        await repo.create(session)
    results = await repo.list_sessions()
    assert len(results) == 3


async def test_update_session_status(neo4j_driver: AsyncDriver):
    repo = SessionRepository(neo4j_driver)
    session = Session(
        id="sess_update_01",
        type="session",
        status="active",
        mode="full_exploration",
    )
    await repo.create(session)
    await repo.update_status("sess_update_01", "completed")
    result = await repo.get_by_id("sess_update_01")
    assert result is not None
    assert result["status"] == "completed"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd backend
uv run pytest tests/integration/test_session_repo.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'explorator.graph.session_repo'`

- [ ] **Step 4: Implement base repository**

Create `backend/src/explorator/graph/repository.py`:

```python
"""Base Neo4j repository with generic CRUD operations."""

from datetime import datetime, timezone
from typing import Any

from neo4j import AsyncDriver
from pydantic import BaseModel


class BaseRepository:
    """Generic Neo4j node CRUD. Subclasses set `label`."""

    label: str = "Node"

    def __init__(self, driver: AsyncDriver) -> None:
        self.driver = driver

    async def create(self, entity: BaseModel) -> None:
        """Create a node from a Pydantic model."""
        data = entity.model_dump(mode="json")
        query = f"CREATE (n:{self.label} $props) SET n.id = $props.id"
        async with self.driver.session() as session:
            await session.run(query, props=data)

    async def get_by_id(self, entity_id: str) -> dict[str, Any] | None:
        """Read a node by ID."""
        query = f"MATCH (n:{self.label} {{id: $id}}) RETURN properties(n) AS props"
        async with self.driver.session() as session:
            result = await session.run(query, id=entity_id)
            record = await result.single()
            if record is None:
                return None
            return dict(record["props"])

    async def update_status(self, entity_id: str, status: str) -> None:
        """Update a node's status."""
        query = f"""
            MATCH (n:{self.label} {{id: $id}})
            SET n.status = $status, n.updated_at = $now
        """
        async with self.driver.session() as session:
            await session.run(
                query,
                id=entity_id,
                status=status,
                now=datetime.now(timezone.utc).isoformat(),
            )
```

- [ ] **Step 5: Implement session repository**

Create `backend/src/explorator/graph/session_repo.py`:

```python
"""Session-specific Neo4j repository."""

from typing import Any

from explorator.graph.repository import BaseRepository


class SessionRepository(BaseRepository):
    """CRUD operations for Session nodes."""

    label = "Session"

    async def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions ordered by creation time."""
        query = """
            MATCH (n:Session)
            RETURN properties(n) AS props
            ORDER BY n.created_at DESC
        """
        async with self.driver.session() as session:
            result = await session.run(query)
            records = await result.data()
            return [dict(r["props"]) for r in records]
```

- [ ] **Step 6: Run integration tests**

```bash
cd backend
uv run pytest tests/integration/test_session_repo.py -v
```

Expected: All 3 tests PASS (requires Neo4j running via Docker Compose).

- [ ] **Step 7: Commit**

```bash
cd <repo-root>
git add backend/src/explorator/graph/ backend/tests/
git commit -m "feat(m0): add Neo4j base repository and session repository with integration tests"
```

---

## Task 6: Genre YAML Files and Loader

**Files:**
- Create: `backend/src/explorator/domain/__init__.py`
- Create: `backend/src/explorator/domain/style/__init__.py`
- Create: `backend/src/explorator/domain/style/schema.py`
- Create: `backend/src/explorator/domain/style/loader.py`
- Create: 9 YAML files (3 genres x 3 file types)
- Create: `backend/src/explorator/graph/style_repo.py`
- Test: `backend/tests/unit/domain/test_genre_loader.py`
- Test: `backend/tests/integration/test_genre_sync.py`

- [ ] **Step 1: Write failing test for YAML parsing**

```bash
mkdir -p backend/tests/unit/domain
touch backend/tests/unit/domain/__init__.py
```

Create `backend/tests/unit/domain/test_genre_loader.py`:

```python
"""Tests for genre YAML loader."""

from pathlib import Path

from explorator.domain.style.loader import load_genre_from_yaml
from explorator.domain.style.schema import GenreProfileYAML


def test_load_dream_pop_profile():
    genres_dir = Path(__file__).parents[3] / "src" / "explorator" / "domain" / "style" / "genres"
    profile = load_genre_from_yaml(genres_dir / "dream_pop.yaml")
    assert isinstance(profile, GenreProfileYAML)
    assert profile.genre == "dream_pop"
    assert profile.display_name == "Dream Pop"
    assert "maj7" in profile.harmonic_vocabulary
    assert profile.version == 1


def test_load_synthwave_profile():
    genres_dir = Path(__file__).parents[3] / "src" / "explorator" / "domain" / "style" / "genres"
    profile = load_genre_from_yaml(genres_dir / "synthwave.yaml")
    assert profile.genre == "synthwave"


def test_load_cinematic_profile():
    genres_dir = Path(__file__).parents[3] / "src" / "explorator" / "domain" / "style" / "genres"
    profile = load_genre_from_yaml(genres_dir / "cinematic.yaml")
    assert profile.genre == "cinematic"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
uv run pytest tests/unit/domain/test_genre_loader.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create YAML schema models**

Create `backend/src/explorator/domain/__init__.py`:

```python
"""Domain services — pure business logic."""
```

Create `backend/src/explorator/domain/style/__init__.py`:

```python
"""Genre/style domain service."""
```

Create `backend/src/explorator/domain/style/schema.py`:

```python
"""Pydantic models for validating genre YAML files."""

from pydantic import BaseModel, Field


class GenreProfileYAML(BaseModel):
    """Schema for genre profile YAML files."""

    genre: str
    display_name: str
    version: int = 1

    harmonic_vocabulary: list[str] = Field(default_factory=list)
    harmonic_tendencies: dict[str, str] = Field(default_factory=dict)
    voicing_tendencies: dict[str, str] = Field(default_factory=dict)
    bass_tendencies: dict[str, str] = Field(default_factory=dict)
    groove_tendencies: dict[str, str] = Field(default_factory=dict)
    common_devices: list[str] = Field(default_factory=list)
    experimentation_envelope: dict[str, float] = Field(default_factory=dict)


class RuleEntryYAML(BaseModel):
    """One rule within a rules YAML file."""

    name: str
    type: str
    weight: float = 0.5
    description: str = ""
    applicability: dict[str, list[str]] = Field(default_factory=dict)


class AntiPatternEntryYAML(BaseModel):
    """One anti-pattern within a rules YAML file."""

    name: str
    scope: str
    severity: float = 0.5
    description: str = ""


class GenreRulesYAML(BaseModel):
    """Schema for genre rules YAML files."""

    rules: list[RuleEntryYAML] = Field(default_factory=list)
    anti_patterns: list[AntiPatternEntryYAML] = Field(default_factory=list)


class HarmonicGrammarYAML(BaseModel):
    """Schema for harmonic grammar YAML files."""

    genre_profile_id: str
    preferred_chord_qualities: list[str] = Field(default_factory=list)
    allowed_borrowed_chords: list[str] = Field(default_factory=list)
    cadence_archetypes: list[str] = Field(default_factory=list)
    harmonic_rhythm_defaults: dict[str, float] = Field(default_factory=dict)
    functional_motion_bias: dict[str, float] = Field(default_factory=dict)
```

- [ ] **Step 4: Create the YAML loader**

Create `backend/src/explorator/domain/style/loader.py`:

```python
"""Read genre YAML files and validate against Pydantic schemas."""

from pathlib import Path

import yaml

from explorator.domain.style.schema import (
    GenreProfileYAML,
    GenreRulesYAML,
    HarmonicGrammarYAML,
)


def load_genre_from_yaml(path: Path) -> GenreProfileYAML:
    """Load and validate a genre profile YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return GenreProfileYAML.model_validate(data)


def load_rules_from_yaml(path: Path) -> GenreRulesYAML:
    """Load and validate a genre rules YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return GenreRulesYAML.model_validate(data)


def load_grammar_from_yaml(path: Path) -> HarmonicGrammarYAML:
    """Load and validate a harmonic grammar YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return HarmonicGrammarYAML.model_validate(data)


def discover_genres(style_dir: Path) -> list[str]:
    """Discover available genre names from the genres/ directory."""
    genres_dir = style_dir / "genres"
    if not genres_dir.exists():
        return []
    return [p.stem for p in genres_dir.glob("*.yaml")]
```

- [ ] **Step 5: Create the 3 genre profile YAMLs**

Create `backend/src/explorator/domain/style/genres/dream_pop.yaml`:

```yaml
genre: dream_pop
display_name: Dream Pop
version: 1

harmonic_vocabulary:
  - maj7
  - add9
  - sus2
  - m7
  - borrowed_iv
  - modal_mixture

harmonic_tendencies:
  functional_strength: low_medium
  chromaticism_level: moderate
  borrowed_chord_tolerance: moderate_high
  cadence_closure_preference: soft

voicing_tendencies:
  spacing: open
  register_bias: mid_high
  extension_density: medium
  top_voice_continuity_importance: high

bass_tendencies:
  root_emphasis: medium
  pedal_tone_tolerance: high
  rhythmic_activity: low_medium

groove_tendencies:
  comp_density: sparse
  articulation_style: floating_pulse
  syncopation_level: light

common_devices:
  - borrowed minor iv
  - shimmering add9 voicings
  - slow harmonic rhythm
  - suspended resolutions
  - major 7th color

experimentation_envelope:
  harmonic_deviation_tolerance: 0.65
  voicing_deviation_tolerance: 0.80
  groove_deviation_tolerance: 0.40
```

Create `backend/src/explorator/domain/style/genres/synthwave.yaml`:

```yaml
genre: synthwave
display_name: Synthwave
version: 1

harmonic_vocabulary:
  - minor
  - m7
  - maj7
  - sus4
  - power_chords
  - add9

harmonic_tendencies:
  functional_strength: medium
  chromaticism_level: low_medium
  borrowed_chord_tolerance: moderate
  cadence_closure_preference: medium

voicing_tendencies:
  spacing: mid_spread
  register_bias: mid
  extension_density: low_medium
  top_voice_continuity_importance: medium

bass_tendencies:
  root_emphasis: high
  pedal_tone_tolerance: medium
  rhythmic_activity: medium_high

groove_tendencies:
  comp_density: medium
  articulation_style: arpeggiated_pulse
  syncopation_level: low

common_devices:
  - minor key center
  - octave bass movement
  - arpeggiated synth patterns
  - vi-IV-I-V progressions in minor
  - suspended fourths resolving

experimentation_envelope:
  harmonic_deviation_tolerance: 0.45
  voicing_deviation_tolerance: 0.55
  groove_deviation_tolerance: 0.35
```

Create `backend/src/explorator/domain/style/genres/cinematic.yaml`:

```yaml
genre: cinematic
display_name: Cinematic
version: 1

harmonic_vocabulary:
  - maj7
  - m7
  - sus2
  - sus4
  - add9
  - dim7
  - aug
  - modal_interchange
  - borrowed_chords

harmonic_tendencies:
  functional_strength: medium_high
  chromaticism_level: moderate_high
  borrowed_chord_tolerance: high
  cadence_closure_preference: varies

voicing_tendencies:
  spacing: wide
  register_bias: full_range
  extension_density: medium_high
  top_voice_continuity_importance: high

bass_tendencies:
  root_emphasis: medium_high
  pedal_tone_tolerance: high
  rhythmic_activity: low

groove_tendencies:
  comp_density: sparse_to_dense
  articulation_style: sustained_swells
  syncopation_level: minimal

common_devices:
  - pedal tones under moving harmony
  - deceptive cadences
  - modal interchange (bVI, bVII)
  - chromatic mediants
  - suspended resolutions over long durations
  - crescendo through harmonic density

experimentation_envelope:
  harmonic_deviation_tolerance: 0.75
  voicing_deviation_tolerance: 0.70
  groove_deviation_tolerance: 0.50
```

- [ ] **Step 6: Create the 3 rules YAMLs**

Create `backend/src/explorator/domain/style/rules/dream_pop_rules.yaml`:

```yaml
rules:
  - name: Prefer open voicings
    type: voicing_preference
    weight: 0.88
    description: Spread voicings across mid-high register with air between voices.
    applicability:
      instruments: [electric_piano, pad, guitar]

  - name: Soft cadential closure
    type: harmonic_preference
    weight: 0.82
    description: Avoid strong V-I resolutions. Prefer plagal, deceptive, or open-loop returns.

  - name: Slow harmonic rhythm
    type: harmonic_preference
    weight: 0.75
    description: Prefer one chord per bar or slower. Avoid rapid chord changes.

anti_patterns:
  - name: Hard bop dominant chains
    scope: harmony
    severity: 0.85
    description: Extended ii-V-I sequences break the floating quality.

  - name: Aggressively walking bass
    scope: bass_line
    severity: 0.79
    description: Continuous quarter-note walking bass pulls toward jazz.

  - name: Dense bebop inner motion
    scope: voicing
    severity: 0.72
    description: Rapid chromatic inner voice movement is too busy for dream pop.
```

Create `backend/src/explorator/domain/style/rules/synthwave_rules.yaml`:

```yaml
rules:
  - name: Strong rhythmic pulse
    type: groove_preference
    weight: 0.90
    description: Maintain steady eighth or sixteenth note pulse in accompaniment.

  - name: Root-heavy bass
    type: bass_preference
    weight: 0.85
    description: Bass should emphasize root notes with octave movement.

  - name: Minor key center
    type: harmonic_preference
    weight: 0.78
    description: Prefer minor keys for authentic synthwave feel.

anti_patterns:
  - name: Jazz extensions on every chord
    scope: harmony
    severity: 0.80
    description: Dense 9ths, 11ths, 13ths sound too sophisticated for synthwave.

  - name: Rubato or free time
    scope: groove
    severity: 0.88
    description: Synthwave requires metronomic pulse.
```

Create `backend/src/explorator/domain/style/rules/cinematic_rules.yaml`:

```yaml
rules:
  - name: Dynamic range through harmony
    type: harmonic_preference
    weight: 0.85
    description: Build tension through harmonic density and release through simplification.

  - name: Pedal tone foundation
    type: bass_preference
    weight: 0.80
    description: Use sustained pedal tones to anchor moving upper harmony.

  - name: Wide voicing spread
    type: voicing_preference
    weight: 0.82
    description: Use full register for orchestral depth.

anti_patterns:
  - name: Repetitive pop loops
    scope: harmony
    severity: 0.70
    description: Simple 4-bar loops feel too static for cinematic contexts.

  - name: Thin single-instrument texture
    scope: voicing
    severity: 0.65
    description: Cinematic needs layered texture, not sparse single-voice lines.
```

- [ ] **Step 7: Create the 3 grammar YAMLs**

Create `backend/src/explorator/domain/style/grammars/dream_pop_grammar.yaml`:

```yaml
genre_profile_id: genre_dream_pop_01
preferred_chord_qualities: [maj7, add9, sus2, m7]
allowed_borrowed_chords: [iv, bVI, bVII]
cadence_archetypes: [soft_plagal, open_loop_return, delayed_resolution]
harmonic_rhythm_defaults:
  chords_per_bar_min: 0.5
  chords_per_bar_max: 1.5
functional_motion_bias:
  tonic_to_submediant: 0.6
  subdominant_color_motion: 0.8
  strong_dominant_resolution: 0.3
```

Create `backend/src/explorator/domain/style/grammars/synthwave_grammar.yaml`:

```yaml
genre_profile_id: genre_synthwave_01
preferred_chord_qualities: [minor, m7, sus4, power_chord]
allowed_borrowed_chords: [bVI, bVII, bIII]
cadence_archetypes: [minor_plagal, deceptive_to_bVI, loop_return]
harmonic_rhythm_defaults:
  chords_per_bar_min: 0.5
  chords_per_bar_max: 2.0
functional_motion_bias:
  tonic_to_submediant: 0.7
  subdominant_color_motion: 0.5
  strong_dominant_resolution: 0.5
```

Create `backend/src/explorator/domain/style/grammars/cinematic_grammar.yaml`:

```yaml
genre_profile_id: genre_cinematic_01
preferred_chord_qualities: [maj7, m7, sus2, sus4, dim7, aug]
allowed_borrowed_chords: [bVI, bVII, bIII, iv, bII]
cadence_archetypes: [deceptive, plagal, chromatic_mediant, half_cadence, delayed_resolution]
harmonic_rhythm_defaults:
  chords_per_bar_min: 0.25
  chords_per_bar_max: 2.0
functional_motion_bias:
  tonic_to_submediant: 0.5
  subdominant_color_motion: 0.7
  strong_dominant_resolution: 0.6
```

- [ ] **Step 8: Run YAML loading tests**

```bash
cd backend
uv run pytest tests/unit/domain/test_genre_loader.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 9: Create style repository for Neo4j sync**

Create `backend/src/explorator/graph/style_repo.py`:

```python
"""Genre/style Neo4j repository — upsert genre profiles, rules, grammars."""

from typing import Any

from neo4j import AsyncDriver


class StyleRepository:
    """CRUD for genre-related nodes."""

    def __init__(self, driver: AsyncDriver) -> None:
        self.driver = driver

    async def upsert_genre_profile(self, genre_id: str, data: dict[str, Any]) -> None:
        """Create or update a GenreProfile node."""
        query = """
            MERGE (n:GenreProfile {id: $id})
            SET n += $props
        """
        async with self.driver.session() as session:
            await session.run(query, id=genre_id, props=data)

    async def upsert_genre_rule(
        self, rule_id: str, genre_id: str, data: dict[str, Any]
    ) -> None:
        """Create or update a GenreRule and link to GenreProfile."""
        query = """
            MERGE (r:GenreRule:Rule {id: $rule_id})
            SET r += $props
            WITH r
            MATCH (g:GenreProfile {id: $genre_id})
            MERGE (g)-[:HAS_RULE]->(r)
        """
        async with self.driver.session() as session:
            await session.run(query, rule_id=rule_id, genre_id=genre_id, props=data)

    async def upsert_anti_pattern(
        self, ap_id: str, genre_id: str, data: dict[str, Any]
    ) -> None:
        """Create or update an AntiPattern and link to GenreProfile."""
        query = """
            MERGE (a:AntiPattern:Rule {id: $ap_id})
            SET a += $props
            WITH a
            MATCH (g:GenreProfile {id: $genre_id})
            MERGE (g)-[:HAS_ANTI_PATTERN]->(a)
        """
        async with self.driver.session() as session:
            await session.run(query, ap_id=ap_id, genre_id=genre_id, props=data)

    async def upsert_harmonic_grammar(
        self, grammar_id: str, genre_id: str, data: dict[str, Any]
    ) -> None:
        """Create or update a HarmonicGrammar and link to GenreProfile."""
        query = """
            MERGE (h:HarmonicGrammar {id: $grammar_id})
            SET h += $props
            WITH h
            MATCH (g:GenreProfile {id: $genre_id})
            MERGE (g)-[:USES_GRAMMAR]->(h)
        """
        async with self.driver.session() as session:
            await session.run(query, grammar_id=grammar_id, genre_id=genre_id, props=data)

    async def list_genre_profiles(self) -> list[dict[str, Any]]:
        """List all genre profiles."""
        query = "MATCH (n:GenreProfile) RETURN properties(n) AS props ORDER BY n.genre"
        async with self.driver.session() as session:
            result = await session.run(query)
            records = await result.data()
            return [dict(r["props"]) for r in records]

    async def get_genre_profile(self, genre: str) -> dict[str, Any] | None:
        """Get a genre profile by genre name."""
        query = "MATCH (n:GenreProfile {genre: $genre}) RETURN properties(n) AS props"
        async with self.driver.session() as session:
            result = await session.run(query, genre=genre)
            record = await result.single()
            if record is None:
                return None
            return dict(record["props"])
```

- [ ] **Step 10: Write integration test for genre sync**

Create `backend/tests/integration/test_genre_sync.py`:

```python
"""Integration tests for genre YAML → Neo4j sync."""

from pathlib import Path

from neo4j import AsyncDriver

from explorator.domain.style.loader import load_genre_from_yaml
from explorator.graph.style_repo import StyleRepository


async def test_sync_dream_pop_to_neo4j(neo4j_driver: AsyncDriver):
    genres_dir = Path(__file__).parents[2] / "src" / "explorator" / "domain" / "style" / "genres"
    profile = load_genre_from_yaml(genres_dir / "dream_pop.yaml")
    repo = StyleRepository(neo4j_driver)

    genre_id = f"genre_{profile.genre}_01"
    data = profile.model_dump(mode="json")
    data["id"] = genre_id
    data["type"] = "genre_profile"
    data["status"] = "active"

    await repo.upsert_genre_profile(genre_id, data)

    result = await repo.get_genre_profile("dream_pop")
    assert result is not None
    assert result["genre"] == "dream_pop"
    assert result["display_name"] == "Dream Pop"


async def test_list_genres_after_sync(neo4j_driver: AsyncDriver):
    genres_dir = Path(__file__).parents[2] / "src" / "explorator" / "domain" / "style" / "genres"
    repo = StyleRepository(neo4j_driver)

    for genre_name in ["dream_pop", "synthwave", "cinematic"]:
        profile = load_genre_from_yaml(genres_dir / f"{genre_name}.yaml")
        genre_id = f"genre_{profile.genre}_01"
        data = profile.model_dump(mode="json")
        data["id"] = genre_id
        data["type"] = "genre_profile"
        data["status"] = "active"
        await repo.upsert_genre_profile(genre_id, data)

    results = await repo.list_genre_profiles()
    assert len(results) == 3
    genres = [r["genre"] for r in results]
    assert "dream_pop" in genres
    assert "synthwave" in genres
    assert "cinematic" in genres
```

- [ ] **Step 11: Run integration tests**

```bash
cd backend
uv run pytest tests/integration/ -v
```

Expected: All integration tests PASS.

- [ ] **Step 12: Commit**

```bash
cd <repo-root>
git add backend/src/explorator/domain/ backend/src/explorator/graph/style_repo.py backend/tests/
git commit -m "feat(m0): add genre YAML system with 3 curated profiles and Neo4j sync"
```

---

## Task 7: Gemini Adapter

**Files:**
- Create: `backend/src/explorator/adapters/__init__.py`
- Create: `backend/src/explorator/adapters/gemini.py`
- Test: `backend/tests/unit/adapters/test_gemini.py`

- [ ] **Step 1: Write failing test**

```bash
mkdir -p backend/tests/unit/adapters
touch backend/tests/unit/adapters/__init__.py
```

Create `backend/tests/unit/adapters/test_gemini.py`:

```python
"""Tests for Gemini adapter."""

from explorator.adapters.gemini import GeminiClient, ModelTier


def test_model_tier_routing():
    client = GeminiClient(api_key="test-key")
    assert client.get_model_name(ModelTier.PRO) == "gemini-pro-latest"
    assert client.get_model_name(ModelTier.FLASH) == "gemini-flash-latest"


def test_client_initialization():
    client = GeminiClient(api_key="test-key")
    assert client.api_key == "test-key"
    assert client.pro_model == "gemini-pro-latest"
    assert client.flash_model == "gemini-flash-latest"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/unit/adapters/test_gemini.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement Gemini adapter**

Create `backend/src/explorator/adapters/__init__.py`:

```python
"""External service adapters."""
```

Create `backend/src/explorator/adapters/gemini.py`:

```python
"""Gemini API client with Pro/Flash model routing."""

from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel


class ModelTier(str, Enum):
    """Gemini model tier selection."""

    PRO = "pro"
    FLASH = "flash"


T = TypeVar("T", bound=BaseModel)


class GeminiClient:
    """Client for Google Gemini API with tiered model routing.

    Uses Pro for creative/nuanced tasks, Flash for structured extraction
    and high-volume scoring.
    """

    def __init__(
        self,
        api_key: str,
        pro_model: str = "gemini-pro-latest",
        flash_model: str = "gemini-flash-latest",
        timeout_seconds: int = 30,
    ) -> None:
        self.api_key = api_key
        self.pro_model = pro_model
        self.flash_model = flash_model
        self.timeout_seconds = timeout_seconds

    def get_model_name(self, tier: ModelTier) -> str:
        """Get the model name for a given tier."""
        if tier == ModelTier.PRO:
            return self.pro_model
        return self.flash_model

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        tier: ModelTier = ModelTier.FLASH,
        system_prompt: str | None = None,
    ) -> T:
        """Generate a structured response using Gemini.

        This is a placeholder that will be fully implemented in M1
        when we need actual LLM calls. For M0, this establishes
        the interface contract.
        """
        raise NotImplementedError(
            "Gemini structured generation will be implemented in M1. "
            f"Would use model: {self.get_model_name(tier)}"
        )

    async def generate_text(
        self,
        prompt: str,
        tier: ModelTier = ModelTier.FLASH,
        system_prompt: str | None = None,
    ) -> str:
        """Generate a text response using Gemini.

        Placeholder for M1 implementation.
        """
        raise NotImplementedError(
            "Gemini text generation will be implemented in M1. "
            f"Would use model: {self.get_model_name(tier)}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend
uv run pytest tests/unit/adapters/test_gemini.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd <repo-root>
git add backend/src/explorator/adapters/ backend/tests/unit/adapters/
git commit -m "feat(m0): add Gemini adapter with Pro/Flash model routing interface"
```

---

## Task 8: FastAPI Application and Session API

**Files:**
- Create: `backend/src/explorator/api/__init__.py`
- Create: `backend/src/explorator/api/app.py`
- Create: `backend/src/explorator/api/deps.py`
- Create: `backend/src/explorator/api/middleware.py`
- Create: `backend/src/explorator/api/routes/__init__.py`
- Create: `backend/src/explorator/api/routes/sessions.py`
- Create: `backend/src/explorator/api/routes/genres.py`
- Test: `backend/tests/integration/test_session_api.py`

- [ ] **Step 1: Write failing API test**

Create `backend/tests/integration/test_session_api.py`:

```python
"""Integration tests for session API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from explorator.api.app import create_app


@pytest.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_create_session(client: AsyncClient):
    response = await client.post(
        "/v1/sessions",
        json={
            "mode": "full_exploration",
            "prompt": "Dream pop in A major, wistful and haunted, 8 bars",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "session_id" in data
    assert data["status"] == "active"


async def test_list_sessions(client: AsyncClient):
    # Create two sessions
    await client.post(
        "/v1/sessions",
        json={"mode": "full_exploration", "prompt": "Dream pop test 1"},
    )
    await client.post(
        "/v1/sessions",
        json={"mode": "full_exploration", "prompt": "Synthwave test 2"},
    )
    response = await client.get("/v1/sessions")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 2


async def test_get_session(client: AsyncClient):
    create_resp = await client.post(
        "/v1/sessions",
        json={"mode": "full_exploration", "prompt": "Cinematic test"},
    )
    session_id = create_resp.json()["session_id"]
    response = await client.get(f"/v1/sessions/{session_id}")
    assert response.status_code == 200
    assert response.json()["session_id"] == session_id


async def test_list_genres(client: AsyncClient):
    response = await client.get("/v1/genres")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/integration/test_session_api.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create FastAPI app factory**

Create `backend/src/explorator/api/__init__.py`:

```python
"""FastAPI API layer."""
```

Create `backend/src/explorator/api/middleware.py`:

```python
"""Auth and middleware stubs."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


class AuthStubMiddleware(BaseHTTPMiddleware):
    """Stub auth middleware. v1 is single-user, no auth required.

    TODO: Implement auth for multi-user support.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        return await call_next(request)
```

Create `backend/src/explorator/api/deps.py`:

```python
"""FastAPI dependency injection."""

from functools import lru_cache

from neo4j import AsyncDriver

from explorator.adapters.gemini import GeminiClient
from explorator.config import settings
from explorator.graph.connection import get_driver
from explorator.graph.session_repo import SessionRepository
from explorator.graph.style_repo import StyleRepository


async def get_neo4j_driver() -> AsyncDriver:
    """Get Neo4j driver dependency."""
    return await get_driver()


async def get_session_repo() -> SessionRepository:
    """Get session repository dependency."""
    driver = await get_driver()
    return SessionRepository(driver)


async def get_style_repo() -> StyleRepository:
    """Get style repository dependency."""
    driver = await get_driver()
    return StyleRepository(driver)


@lru_cache
def get_gemini_client() -> GeminiClient:
    """Get Gemini client singleton."""
    return GeminiClient(
        api_key=settings.gemini_api_key,
        pro_model=settings.gemini_pro_model,
        flash_model=settings.gemini_flash_model,
        timeout_seconds=settings.gemini_timeout_seconds,
    )
```

Create `backend/src/explorator/api/app.py`:

```python
"""FastAPI application factory."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from explorator.api.middleware import AuthStubMiddleware
from explorator.api.routes import sessions, genres
from explorator.graph.connection import get_driver, close_driver
from explorator.graph.schema import init_schema


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: init Neo4j schema on startup, close on shutdown."""
    driver = await get_driver()
    await init_schema(driver)
    yield
    await close_driver()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="MusicExplorator",
        description="Genre-aware musical exploration engine",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AuthStubMiddleware)

    app.include_router(sessions.router, prefix="/v1")
    app.include_router(genres.router, prefix="/v1")

    return app
```

- [ ] **Step 4: Create session routes**

Create `backend/src/explorator/api/routes/__init__.py`:

```python
"""API route modules."""
```

Create `backend/src/explorator/api/routes/sessions.py`:

```python
"""Session CRUD endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from ulid import ULID

from explorator.graph.session_repo import SessionRepository
from explorator.models.session import Session
from explorator.api.deps import get_session_repo

router = APIRouter(tags=["sessions"])


class CreateSessionRequest(BaseModel):
    """Request body for creating a session."""

    mode: str = "full_exploration"
    prompt: str


class SessionResponse(BaseModel):
    """Response for a single session."""

    session_id: str
    status: str
    mode: str
    created_at: str
    prompt: str


class SessionListResponse(BaseModel):
    """Response for listing sessions."""

    items: list[SessionResponse]


@router.post("/sessions", status_code=201)
async def create_session(
    request: CreateSessionRequest,
    repo: SessionRepository = Depends(get_session_repo),
) -> SessionResponse:
    """Create a new exploration session."""
    session_id = f"sess_{ULID()}"
    now = datetime.now(timezone.utc)

    session = Session(
        id=session_id,
        type="session",
        status="active",
        mode=request.mode,
        created_at=now,
        updated_at=now,
        metadata={"prompt": request.prompt},
    )
    await repo.create(session)

    return SessionResponse(
        session_id=session_id,
        status="active",
        mode=request.mode,
        created_at=now.isoformat(),
        prompt=request.prompt,
    )


@router.get("/sessions")
async def list_sessions(
    repo: SessionRepository = Depends(get_session_repo),
) -> SessionListResponse:
    """List all sessions."""
    sessions = await repo.list_sessions()
    items = [
        SessionResponse(
            session_id=s["id"],
            status=s.get("status", "unknown"),
            mode=s.get("mode", "unknown"),
            created_at=s.get("created_at", ""),
            prompt=s.get("metadata", {}).get("prompt", "") if isinstance(s.get("metadata"), dict) else "",
        )
        for s in sessions
    ]
    return SessionListResponse(items=items)


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    repo: SessionRepository = Depends(get_session_repo),
) -> SessionResponse:
    """Get a single session by ID."""
    session = await repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    metadata = session.get("metadata", {})
    if isinstance(metadata, str):
        metadata = {}
    return SessionResponse(
        session_id=session["id"],
        status=session.get("status", "unknown"),
        mode=session.get("mode", "unknown"),
        created_at=session.get("created_at", ""),
        prompt=metadata.get("prompt", ""),
    )
```

Create `backend/src/explorator/api/routes/genres.py`:

```python
"""Genre profile endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from explorator.graph.style_repo import StyleRepository
from explorator.api.deps import get_style_repo

router = APIRouter(tags=["genres"])


class GenreSummary(BaseModel):
    """Summary of a genre profile."""

    genre: str
    display_name: str


class GenreListResponse(BaseModel):
    """Response for listing genres."""

    items: list[GenreSummary]


@router.get("/genres")
async def list_genres(
    repo: StyleRepository = Depends(get_style_repo),
) -> GenreListResponse:
    """List available genre profiles."""
    profiles = await repo.list_genre_profiles()
    items = [
        GenreSummary(
            genre=p.get("genre", "unknown"),
            display_name=p.get("display_name", p.get("genre", "unknown")),
        )
        for p in profiles
    ]
    return GenreListResponse(items=items)
```

- [ ] **Step 5: Run API integration tests**

```bash
cd backend
uv run pytest tests/integration/test_session_api.py -v
```

Expected: All 4 tests PASS (requires Neo4j running).

- [ ] **Step 6: Commit**

```bash
cd <repo-root>
git add backend/src/explorator/api/ backend/tests/integration/test_session_api.py
git commit -m "feat(m0): add FastAPI app with session CRUD and genre list endpoints"
```

---

## Task 9: Makefile and Dev Workflow

**Files:**
- Create: `Makefile`
- Create: `backend/.env`

- [ ] **Step 1: Create Makefile**

Create `Makefile` at repo root:

```makefile
.PHONY: dev test lint neo4j-up neo4j-down sync-genres backend frontend

# Infrastructure
neo4j-up:
	docker compose up -d neo4j

neo4j-down:
	docker compose down

# Backend
backend:
	cd backend && uv run uvicorn explorator.api.app:create_app --factory --host 0.0.0.0 --port 8000 --reload

test:
	cd backend && uv run pytest tests/ -v

test-unit:
	cd backend && uv run pytest tests/unit/ -v

test-integration:
	cd backend && uv run pytest tests/integration/ -v

lint:
	cd backend && uv run ruff check src/ tests/
	cd backend && uv run mypy src/

# Genre sync (placeholder — will be a CLI command)
sync-genres:
	@echo "Genre sync will be implemented as a CLI command. For now, genres load on app startup."

# Frontend (placeholder for Task 10)
frontend:
	cd frontend && npm run dev
```

- [ ] **Step 2: Create backend .env**

Create `backend/.env`:

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=explorator_dev
GEMINI_API_KEY=placeholder-replace-with-real-key
```

- [ ] **Step 3: Verify full workflow**

```bash
cd <repo-root>
make neo4j-up
sleep 10
make test
make lint
```

Expected: All tests pass, lint is clean.

- [ ] **Step 4: Commit**

```bash
cd <repo-root>
git add Makefile backend/.env
git commit -m "feat(m0): add Makefile with dev workflow commands"
```

---

## Task 10: Frontend Scaffold

**Files:**
- Create: All frontend files listed in File Map (frontend section)

- [ ] **Step 1: Initialize Vite + React + TypeScript project**

```bash
cd <repo-root>
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install -D tailwindcss @tailwindcss/vite
npm install @tanstack/react-query zustand react-router-dom
```

- [ ] **Step 2: Configure Tailwind**

Replace `frontend/vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/v1': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

Replace `frontend/src/index.css`:

```css
@import "tailwindcss";

:root {
  color-scheme: dark;
}

body {
  @apply bg-gray-950 text-gray-100 min-h-screen;
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
}
```

- [ ] **Step 3: Create API client**

Create `frontend/src/services/api.ts`:

```typescript
const API_BASE = '/v1';

export interface SessionSummary {
  session_id: string;
  status: string;
  mode: string;
  created_at: string;
  prompt: string;
}

export interface SessionListResponse {
  items: SessionSummary[];
}

export interface GenreSummary {
  genre: string;
  display_name: string;
}

export interface GenreListResponse {
  items: GenreSummary[];
}

export async function createSession(prompt: string, mode = 'full_exploration'): Promise<SessionSummary> {
  const res = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, mode }),
  });
  if (!res.ok) throw new Error(`Failed to create session: ${res.status}`);
  return res.json();
}

export async function listSessions(): Promise<SessionListResponse> {
  const res = await fetch(`${API_BASE}/sessions`);
  if (!res.ok) throw new Error(`Failed to list sessions: ${res.status}`);
  return res.json();
}

export async function getSession(sessionId: string): Promise<SessionSummary> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`);
  if (!res.ok) throw new Error(`Failed to get session: ${res.status}`);
  return res.json();
}

export async function listGenres(): Promise<GenreListResponse> {
  const res = await fetch(`${API_BASE}/genres`);
  if (!res.ok) throw new Error(`Failed to list genres: ${res.status}`);
  return res.json();
}
```

- [ ] **Step 4: Create Zustand session store**

Create `frontend/src/stores/` directory and `frontend/src/stores/sessionStore.ts`:

```typescript
import { create } from 'zustand';
import type { SessionSummary } from '../services/api';

interface SessionState {
  sessions: SessionSummary[];
  currentSession: SessionSummary | null;
  setSessions: (sessions: SessionSummary[]) => void;
  setCurrentSession: (session: SessionSummary | null) => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  sessions: [],
  currentSession: null,
  setSessions: (sessions) => set({ sessions }),
  setCurrentSession: (session) => set({ currentSession: session }),
}));
```

- [ ] **Step 5: Create Dashboard view**

Create `frontend/src/views/` directory and `frontend/src/views/Dashboard.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createSession, listSessions } from '../services/api';
import { useSessionStore } from '../stores/sessionStore';

export default function Dashboard() {
  const { sessions, setSessions } = useSessionStore();
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    listSessions().then((data) => setSessions(data.items)).catch(console.error);
  }, [setSessions]);

  const handleCreate = async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    try {
      const session = await createSession(prompt);
      navigate(`/session/${session.session_id}`);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-8">
      <h1 className="text-3xl font-bold mb-2">MusicExplorator</h1>
      <p className="text-gray-400 mb-8">Genre-aware musical exploration engine</p>

      <div className="mb-8 p-6 bg-gray-900 rounded-lg border border-gray-800">
        <h2 className="text-lg font-semibold mb-3">New Exploration</h2>
        <div className="flex gap-3">
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            placeholder="Dream pop in A major, wistful and haunted, 8 bars..."
            className="flex-1 bg-gray-800 border border-gray-700 rounded-md px-4 py-2 text-gray-100 placeholder-gray-500 focus:outline-none focus:border-purple-500"
          />
          <button
            onClick={handleCreate}
            disabled={loading || !prompt.trim()}
            className="px-6 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-700 rounded-md font-medium transition-colors"
          >
            {loading ? 'Creating...' : 'Explore'}
          </button>
        </div>
      </div>

      <h2 className="text-lg font-semibold mb-3">Sessions</h2>
      {sessions.length === 0 ? (
        <p className="text-gray-500">No sessions yet. Start a new exploration above.</p>
      ) : (
        <div className="space-y-2">
          {sessions.map((s) => (
            <div
              key={s.session_id}
              onClick={() => navigate(`/session/${s.session_id}`)}
              className="p-4 bg-gray-900 rounded-lg border border-gray-800 hover:border-gray-600 cursor-pointer transition-colors"
            >
              <div className="flex justify-between items-center">
                <span className="text-gray-200">{s.prompt || 'Untitled session'}</span>
                <span className="text-xs text-gray-500">{s.status}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

Create `frontend/src/views/SessionWorkspace.tsx`:

```tsx
import { useParams, Link } from 'react-router-dom';

export default function SessionWorkspace() {
  const { id } = useParams<{ id: string }>();

  return (
    <div className="max-w-6xl mx-auto p-8">
      <Link to="/" className="text-purple-400 hover:text-purple-300 text-sm mb-4 inline-block">
        ← Back to Dashboard
      </Link>
      <h1 className="text-2xl font-bold mb-4">Session: {id}</h1>
      <div className="p-6 bg-gray-900 rounded-lg border border-gray-800">
        <p className="text-gray-400">
          Workspace will be implemented in M1. This session is ready for exploration rounds.
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Wire up App with router**

Replace `frontend/src/App.tsx`:

```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Dashboard from './views/Dashboard';
import SessionWorkspace from './views/SessionWorkspace';

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/session/:id" element={<SessionWorkspace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
```

Replace `frontend/src/main.tsx`:

```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

- [ ] **Step 7: Delete Vite boilerplate files**

```bash
cd frontend
rm -f src/App.css src/assets/react.svg public/vite.svg
```

- [ ] **Step 8: Verify frontend builds**

```bash
cd frontend
npm run build
```

Expected: Build succeeds with no errors.

- [ ] **Step 9: Commit**

```bash
cd <repo-root>
git add frontend/ Makefile
git commit -m "feat(m0): scaffold React frontend with Dashboard, session creation, and dark theme"
```

---

## Task 11: End-to-End Verification

- [ ] **Step 1: Start all services**

```bash
cd <repo-root>
make neo4j-up
sleep 10
```

In one terminal:
```bash
make backend
```

In another terminal:
```bash
make frontend
```

- [ ] **Step 2: Verify backend health**

```bash
curl http://localhost:8000/v1/genres
```

Expected: `{"items":[]}` (genres not synced yet — they'll load when we add the sync-on-startup logic, which is already in the lifespan but needs the full sync function).

- [ ] **Step 3: Create a session via API**

```bash
curl -X POST http://localhost:8000/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"mode":"full_exploration","prompt":"Dream pop test"}'
```

Expected: `{"session_id":"sess_...","status":"active","mode":"full_exploration",...}`

- [ ] **Step 4: Open frontend**

Open `http://localhost:5173` in browser. Verify:
- Dashboard loads with dark theme
- "New Exploration" input is visible
- Creating a session navigates to workspace placeholder

- [ ] **Step 5: Run full test suite**

```bash
cd <repo-root>
make test
make lint
```

Expected: All tests pass, lint is clean.

- [ ] **Step 6: Final commit**

```bash
cd <repo-root>
git add -A
git commit -m "feat(m0): complete M0 foundations — end-to-end session CRUD verified"
```

---

## Exit Criteria Checklist

- [ ] Monorepo scaffold with uv, ruff, mypy (backend) and Vite + Tailwind (frontend)
- [ ] Docker Compose with Neo4j running locally
- [ ] All Pydantic canonical models defined (BaseEntity, CandidateBase, EvaluationBase + all families)
- [ ] Neo4j schema initialized with constraints and indexes
- [ ] 3 curated genre profiles as YAML (dream pop, synthwave, cinematic) with rules and grammars
- [ ] Genre YAML loader validates against Pydantic and syncs to Neo4j
- [ ] FastAPI skeleton with session CRUD and genre list endpoints
- [ ] Gemini client with Pro/Flash routing interface
- [ ] React SPA with Dashboard, session creation, and dark theme
- [ ] Can create a session, persist to Neo4j, see it in the frontend
