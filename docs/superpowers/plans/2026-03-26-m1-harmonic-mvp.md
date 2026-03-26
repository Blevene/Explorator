# M1 — Harmonic MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable a user to prompt for genre-specific chord progressions and see ranked results with Roman numeral analysis and theory scores in the UI. No voicings, bass lines, or playback — those are M2.

**Architecture:** FastAPI triggers a LangGraph partial flow (`parse_intent → load_genre → generate → evaluate_progressions → select_top_progressions → persist_round`) per round. Gemini Flash handles intent parsing and evaluation scoring. Gemini Pro handles creative progression generation. music21 provides Roman numeral analysis behind a thin adapter. The frontend shows a candidate card grid with scores and chord symbols. SSE streams round progress in real-time.

**Tech Stack:** LangGraph, google-genai (Gemini), music21, FastAPI SSE (sse-starlette), existing Pydantic models, Neo4j, React + TanStack Query

**Prerequisites:** M0 complete. Neo4j running on port 7688. Backend on port 8001. Gemini API key in `backend/.env`.

---

## File Map

### New Dependencies
- `langgraph` — LangGraph orchestration framework
- `music21` — Symbolic music analysis (Roman numeral, chord parsing)
- `sse-starlette` — Server-Sent Events for FastAPI

### Backend — Gemini Adapter (modify existing)
- `backend/src/explorator/adapters/gemini.py` — Implement actual Gemini API calls using google-genai

### Backend — music21 Adapter (new)
- `backend/src/explorator/adapters/music21_adapter.py` — Thin wrapper for Roman numeral analysis and chord parsing

### Backend — Domain Services (new)
- `backend/src/explorator/domain/intent/__init__.py`
- `backend/src/explorator/domain/intent/parser.py` — Gemini Flash prompt → CreativeBrief
- `backend/src/explorator/domain/style/service.py` — Genre profile retrieval from Neo4j
- `backend/src/explorator/domain/harmony/__init__.py`
- `backend/src/explorator/domain/harmony/generator.py` — Gemini Pro generates ProgressionCandidates
- `backend/src/explorator/domain/evaluation/__init__.py`
- `backend/src/explorator/domain/evaluation/theory.py` — Deterministic + Gemini hybrid theory scoring
- `backend/src/explorator/domain/evaluation/ranking.py` — Weighted scoring + top-K selection

### Backend — LangGraph Engine (new)
- `backend/src/explorator/engine/__init__.py`
- `backend/src/explorator/engine/state.py` — ExplorationState TypedDict
- `backend/src/explorator/engine/nodes/parse_intent.py`
- `backend/src/explorator/engine/nodes/load_genre.py`
- `backend/src/explorator/engine/nodes/generate.py`
- `backend/src/explorator/engine/nodes/evaluate_progressions.py`
- `backend/src/explorator/engine/nodes/select_top_progressions.py`
- `backend/src/explorator/engine/nodes/persist_round.py`
- `backend/src/explorator/engine/graph.py` — Graph definition and compilation

### Backend — Neo4j Repos (new)
- `backend/src/explorator/graph/candidate_repo.py` — ProgressionCandidate CRUD
- `backend/src/explorator/graph/evaluation_repo.py` — Evaluation CRUD

### Backend — API Routes (new/modify)
- `backend/src/explorator/api/routes/rounds.py` — POST /v1/sessions/:id/rounds, GET events SSE
- `backend/src/explorator/api/routes/candidates.py` — GET /v1/sessions/:id/candidates, GET /v1/candidates/:id
- `backend/src/explorator/api/sse.py` — SSE event helpers
- Modify: `backend/src/explorator/api/app.py` — Register new routes
- Modify: `backend/src/explorator/api/deps.py` — Add new dependencies

### Frontend (new/modify)
- `frontend/src/services/sse.ts` — SSE client for round progress
- `frontend/src/stores/candidateStore.ts` — Candidate state
- `frontend/src/components/CandidateCard.tsx` — Card with scores and chord symbols
- `frontend/src/components/PromptBar.tsx` — Enhanced prompt bar with generation mode toggle
- Modify: `frontend/src/views/SessionWorkspace.tsx` — Wire up round trigger, SSE, candidate grid
- Modify: `frontend/src/services/api.ts` — Add round and candidate API calls

### Tests
- `backend/tests/unit/adapters/test_music21_adapter.py`
- `backend/tests/unit/domain/test_intent_parser.py`
- `backend/tests/unit/domain/test_harmony_generator.py`
- `backend/tests/unit/domain/test_theory_evaluator.py`
- `backend/tests/unit/domain/test_ranking.py`
- `backend/tests/unit/engine/test_state.py`
- `backend/tests/integration/test_engine_flow.py`
- `backend/tests/integration/test_rounds_api.py`

---

## Task 1: Add New Dependencies

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add langgraph, music21, and sse-starlette to dependencies**

Add these to the `dependencies` list in `backend/pyproject.toml`:

```toml
    "langgraph>=0.3.0",
    "music21>=9.1.0",
    "sse-starlette>=2.0.0",
```

- [ ] **Step 2: Install**

```bash
cd /home/angel/Documents/code/Explorator/backend
uv sync --all-extras
```

- [ ] **Step 3: Verify imports work**

```bash
uv run python -c "import langgraph; import music21; import sse_starlette; print('All imports OK')"
```

- [ ] **Step 4: Commit**

```bash
cd /home/angel/Documents/code/Explorator
git add backend/pyproject.toml backend/uv.lock
git commit -m "feat(m1): add langgraph, music21, sse-starlette dependencies"
```

---

## Task 2: Implement Gemini Adapter (Real API Calls)

**Files:**
- Modify: `backend/src/explorator/adapters/gemini.py`
- Test: `backend/tests/unit/adapters/test_gemini.py`

- [ ] **Step 1: Write test for structured generation**

Add to `backend/tests/unit/adapters/test_gemini.py`:

```python
"""Tests for Gemini adapter."""

import pytest
from pydantic import BaseModel

from explorator.adapters.gemini import GeminiClient, ModelTier


def test_model_tier_routing() -> None:
    client = GeminiClient(api_key="test-key")
    assert client.get_model_name(ModelTier.PRO) == "gemini-pro-latest"
    assert client.get_model_name(ModelTier.FLASH) == "gemini-flash-latest"


def test_client_initialization() -> None:
    client = GeminiClient(api_key="test-key")
    assert client.api_key == "test-key"
    assert client.pro_model == "gemini-pro-latest"
    assert client.flash_model == "gemini-flash-latest"


class SampleResponse(BaseModel):
    name: str
    value: int


@pytest.mark.skipif(
    not _has_api_key(),
    reason="GEMINI_API_KEY not set",
)
async def test_generate_structured_returns_typed_response() -> None:
    """Integration test — requires real Gemini API key."""
    import os

    client = GeminiClient(api_key=os.environ["GEMINI_API_KEY"])
    result = await client.generate_structured(
        prompt="Return a JSON object with name='test' and value=42",
        response_model=SampleResponse,
        tier=ModelTier.FLASH,
    )
    assert isinstance(result, SampleResponse)
    assert result.name == "test"
    assert result.value == 42


def _has_api_key() -> bool:
    import os
    return bool(os.environ.get("GEMINI_API_KEY"))
```

- [ ] **Step 2: Implement Gemini client with google-genai**

Replace `backend/src/explorator/adapters/gemini.py`:

```python
"""Gemini API client with Pro/Flash model routing."""

import json
import logging
from enum import StrEnum
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ModelTier(StrEnum):
    """Gemini model tier selection."""

    PRO = "pro"
    FLASH = "flash"


class GeminiClient:
    """Client for Google Gemini API with tiered model routing."""

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
        self._client = genai.Client(api_key=api_key)

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
        """Generate a structured response validated against a Pydantic model."""
        model_name = self.get_model_name(tier)
        contents = prompt
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_model,
            system_instruction=system_prompt,
        )

        response = await self._client.aio.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )

        raw_text = response.text
        if raw_text is None:
            msg = f"Gemini returned empty response for model={model_name}"
            raise ValueError(msg)

        parsed = json.loads(raw_text)
        return response_model.model_validate(parsed)

    async def generate_text(
        self,
        prompt: str,
        tier: ModelTier = ModelTier.FLASH,
        system_prompt: str | None = None,
    ) -> str:
        """Generate a plain text response."""
        model_name = self.get_model_name(tier)
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
        )

        response = await self._client.aio.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )

        if response.text is None:
            msg = f"Gemini returned empty response for model={model_name}"
            raise ValueError(msg)

        return response.text
```

- [ ] **Step 3: Run unit tests (skip integration if no API key)**

```bash
cd /home/angel/Documents/code/Explorator/backend
uv run pytest tests/unit/adapters/test_gemini.py -v
```

- [ ] **Step 4: Run ruff and mypy**

```bash
uv run ruff check src/explorator/adapters/ && uv run mypy src/explorator/adapters/
```

- [ ] **Step 5: Commit**

```bash
cd /home/angel/Documents/code/Explorator
git add backend/src/explorator/adapters/ backend/tests/unit/adapters/
git commit -m "feat(m1): implement Gemini adapter with google-genai structured output"
```

---

## Task 3: music21 Adapter

**Files:**
- Create: `backend/src/explorator/adapters/music21_adapter.py`
- Test: `backend/tests/unit/adapters/test_music21_adapter.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/adapters/test_music21_adapter.py`:

```python
"""Tests for music21 adapter."""

from explorator.adapters.music21_adapter import (
    ChordInfo,
    RomanNumeralResult,
    analyze_roman_numerals,
    parse_chord_symbol,
)


def test_parse_chord_symbol_major_seventh() -> None:
    info = parse_chord_symbol("Cmaj7")
    assert isinstance(info, ChordInfo)
    assert info.root == "C"
    assert "major" in info.quality.lower() or "maj" in info.quality.lower()


def test_parse_chord_symbol_minor_seventh() -> None:
    info = parse_chord_symbol("Am7")
    assert info.root == "A"


def test_parse_chord_symbol_dominant() -> None:
    info = parse_chord_symbol("G7")
    assert info.root == "G"


def test_parse_chord_symbol_sus2() -> None:
    info = parse_chord_symbol("Dsus2")
    assert info.root == "D"


def test_analyze_roman_numerals_major_key() -> None:
    result = analyze_roman_numerals(
        key="C",
        mode="major",
        chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
    )
    assert isinstance(result, list)
    assert len(result) == 4
    assert all(isinstance(r, RomanNumeralResult) for r in result)
    # C in C major should be I
    assert "I" in result[0].roman_numeral


def test_analyze_roman_numerals_minor_key() -> None:
    result = analyze_roman_numerals(
        key="A",
        mode="minor",
        chord_symbols=["Am", "Dm", "E7", "Am"],
    )
    assert len(result) == 4
    # Am in A minor should be i
    assert "i" in result[0].roman_numeral.lower()


def test_parse_invalid_chord_returns_unknown() -> None:
    info = parse_chord_symbol("Xqz123")
    assert info.root == "unknown"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/angel/Documents/code/Explorator/backend
uv run pytest tests/unit/adapters/test_music21_adapter.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement music21 adapter**

Create `backend/src/explorator/adapters/music21_adapter.py`:

```python
"""Thin music21 adapter for symbolic music analysis.

music21 objects are created transiently and converted to Pydantic types.
No music21 types leak outside this module.
"""

import logging

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ChordInfo(BaseModel):
    """Parsed chord information."""

    root: str
    quality: str
    bass_note: str | None = None
    pitch_classes: list[str] = []


class RomanNumeralResult(BaseModel):
    """Roman numeral analysis for one chord."""

    chord_symbol: str
    roman_numeral: str
    confidence: float = 1.0


def parse_chord_symbol(symbol: str) -> ChordInfo:
    """Parse a chord symbol string into structured info."""
    try:
        from music21 import harmony

        chord = harmony.ChordSymbol(symbol)
        root = chord.root().name if chord.root() else "unknown"
        quality = chord.chordKind or "unknown"
        bass = chord.bass().name if chord.bass() and chord.bass() != chord.root() else None
        pitches = [p.name for p in chord.pitches]

        return ChordInfo(
            root=root,
            quality=quality,
            bass_note=bass,
            pitch_classes=pitches,
        )
    except Exception:
        logger.warning("Failed to parse chord symbol: %s", symbol)
        return ChordInfo(root="unknown", quality="unknown")


def analyze_roman_numerals(
    key: str,
    mode: str,
    chord_symbols: list[str],
) -> list[RomanNumeralResult]:
    """Analyze chord symbols as Roman numerals in a given key."""
    from music21 import key as m21_key
    from music21 import roman

    try:
        if mode == "minor":
            analysis_key = m21_key.Key(key, "minor")
        else:
            analysis_key = m21_key.Key(key, "major")
    except Exception:
        logger.warning("Failed to create key: %s %s", key, mode)
        return [
            RomanNumeralResult(chord_symbol=s, roman_numeral="?", confidence=0.0)
            for s in chord_symbols
        ]

    results: list[RomanNumeralResult] = []
    for symbol in chord_symbols:
        try:
            rn = roman.romanNumeralFromChord(
                _symbol_to_chord(symbol),
                analysis_key,
            )
            results.append(
                RomanNumeralResult(
                    chord_symbol=symbol,
                    roman_numeral=rn.romanNumeralAlone + _quality_suffix(rn),
                    confidence=0.9,
                )
            )
        except Exception:
            logger.warning("Failed to analyze %s in %s %s", symbol, key, mode)
            results.append(
                RomanNumeralResult(
                    chord_symbol=symbol,
                    roman_numeral="?",
                    confidence=0.0,
                )
            )

    return results


def _symbol_to_chord(symbol: str):
    """Convert a chord symbol string to a music21 Chord object."""
    from music21 import harmony

    return harmony.ChordSymbol(symbol)


def _quality_suffix(rn) -> str:
    """Extract quality suffix from a Roman numeral object."""
    figure = rn.figure
    numeral = rn.romanNumeralAlone
    # Return everything after the numeral (e.g., "7", "maj7", "m7")
    if figure.startswith(numeral):
        return figure[len(numeral):]
    return ""
```

- [ ] **Step 4: Run tests**

```bash
cd /home/angel/Documents/code/Explorator/backend
uv run pytest tests/unit/adapters/test_music21_adapter.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 5: Run ruff and mypy**

```bash
uv run ruff check src/explorator/adapters/ tests/unit/adapters/
uv run mypy src/explorator/adapters/
```

- [ ] **Step 6: Commit**

```bash
cd /home/angel/Documents/code/Explorator
git add backend/src/explorator/adapters/music21_adapter.py backend/tests/unit/adapters/test_music21_adapter.py
git commit -m "feat(m1): add music21 adapter for Roman numeral analysis and chord parsing"
```

---

## Task 4: Intent Parser Service

**Files:**
- Create: `backend/src/explorator/domain/intent/__init__.py`
- Create: `backend/src/explorator/domain/intent/parser.py`
- Test: `backend/tests/unit/domain/test_intent_parser.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/unit/domain/test_intent_parser.py`:

```python
"""Tests for intent parser service."""

import pytest

from explorator.domain.intent.parser import (
    IntentParser,
    extract_deterministic_constraints,
)
from explorator.models.session import CreativeBrief


def test_extract_key_from_prompt() -> None:
    constraints = extract_deterministic_constraints(
        "Dream pop in A major, wistful and haunted, 8 bars"
    )
    assert constraints["key_center"] == "A"
    assert constraints["mode"] == "major"


def test_extract_bars_from_prompt() -> None:
    constraints = extract_deterministic_constraints(
        "Give me 16 bars of synthwave in C minor"
    )
    assert constraints["phrase_length_bars"] == 16


def test_extract_genre_from_prompt() -> None:
    constraints = extract_deterministic_constraints(
        "Dream pop in A major, 8 bars"
    )
    assert constraints["genre"] == "dream_pop"


def test_extract_mode_minor() -> None:
    constraints = extract_deterministic_constraints(
        "Synthwave in C minor, dark and driving"
    )
    assert constraints["mode"] == "minor"
    assert constraints["key_center"] == "C"


def test_defaults_when_not_specified() -> None:
    constraints = extract_deterministic_constraints(
        "Something dark and moody"
    )
    assert constraints.get("phrase_length_bars") is None
    assert constraints.get("key_center") is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/angel/Documents/code/Explorator/backend
uv run pytest tests/unit/domain/test_intent_parser.py -v
```

- [ ] **Step 3: Implement intent parser**

Create `backend/src/explorator/domain/intent/__init__.py`:

```python
"""Intent interpretation domain service."""
```

Create `backend/src/explorator/domain/intent/parser.py`:

```python
"""Parse user prompts into structured CreativeBrief.

Uses hybrid approach:
- Deterministic regex extraction for explicit constraints (key, bars, genre)
- Gemini Flash for soft preferences (mood, complexity, aesthetic interpretation)
"""

import re
from typing import Any

from pydantic import BaseModel, Field

from explorator.adapters.gemini import GeminiClient, ModelTier
from explorator.models.session import CreativeBrief
from explorator.utils import utc_now

# Known genres (normalized to snake_case)
KNOWN_GENRES = {
    "dream pop": "dream_pop",
    "dreampop": "dream_pop",
    "synthwave": "synthwave",
    "synth wave": "synthwave",
    "cinematic": "cinematic",
    "film score": "cinematic",
}

# Key pattern: matches "in A major", "in C minor", "in Bb", "in F# minor"
KEY_PATTERN = re.compile(
    r"\bin\s+([A-G][b#]?)\s*(major|minor|maj|min)?\b",
    re.IGNORECASE,
)

# Bars pattern: matches "8 bars", "16 bars", "4-bar"
BARS_PATTERN = re.compile(r"(\d+)\s*[-\s]?bars?", re.IGNORECASE)


class SoftPreferences(BaseModel):
    """LLM-extracted soft preferences from a prompt."""

    mood_targets: list[str] = Field(default_factory=list)
    energy_level: str | None = None
    complexity_target: str = "medium"
    novelty_target: str = "moderate"
    instrumentation_targets: list[str] = Field(default_factory=list)
    user_language_notes: list[str] = Field(default_factory=list)


def extract_deterministic_constraints(prompt: str) -> dict[str, Any]:
    """Extract explicit constraints from prompt using regex."""
    constraints: dict[str, Any] = {}

    # Extract key/mode
    key_match = KEY_PATTERN.search(prompt)
    if key_match:
        constraints["key_center"] = key_match.group(1)
        mode_str = (key_match.group(2) or "").lower()
        if mode_str in ("minor", "min"):
            constraints["mode"] = "minor"
        else:
            constraints["mode"] = "major"

    # Extract bars
    bars_match = BARS_PATTERN.search(prompt)
    if bars_match:
        constraints["phrase_length_bars"] = int(bars_match.group(1))

    # Extract genre
    prompt_lower = prompt.lower()
    for genre_phrase, genre_key in KNOWN_GENRES.items():
        if genre_phrase in prompt_lower:
            constraints["genre"] = genre_key
            break

    return constraints


class IntentParser:
    """Parses user prompts into CreativeBrief using hybrid extraction."""

    def __init__(self, gemini: GeminiClient) -> None:
        self.gemini = gemini

    async def parse(self, prompt: str, session_id: str) -> CreativeBrief:
        """Parse a prompt into a structured CreativeBrief."""
        # Step 1: Deterministic extraction
        constraints = extract_deterministic_constraints(prompt)

        # Step 2: LLM-assisted soft preference extraction
        soft = await self._extract_soft_preferences(prompt)

        # Step 3: Merge into CreativeBrief
        from ulid import ULID

        brief_id = f"brief_{ULID()}"

        return CreativeBrief(
            id=brief_id,
            type="creative_brief",
            status="active",
            created_at=utc_now(),
            updated_at=utc_now(),
            genre=constraints.get("genre", "dream_pop"),
            key_center=constraints.get("key_center"),
            mode=constraints.get("mode", "major"),
            phrase_length_bars=constraints.get("phrase_length_bars", 8),
            mood_targets=soft.mood_targets,
            energy_level=soft.energy_level,
            complexity_target=soft.complexity_target,
            novelty_target=soft.novelty_target,
            instrumentation_targets=soft.instrumentation_targets,
            user_language_notes=soft.user_language_notes + [prompt],
        )

    async def _extract_soft_preferences(self, prompt: str) -> SoftPreferences:
        """Use Gemini Flash to extract mood, complexity, and aesthetic preferences."""
        system = (
            "You are a music analysis assistant. Extract soft preferences from "
            "the user's creative prompt. Return structured JSON with mood_targets "
            "(list of mood words), energy_level (low/low_medium/medium/medium_high/high), "
            "complexity_target (low/medium/medium_high/high), novelty_target "
            "(low/moderate/moderate_high/high), instrumentation_targets (list of "
            "instrument names), and user_language_notes (notable phrases from the prompt)."
        )
        try:
            return await self.gemini.generate_structured(
                prompt=f"Extract preferences from this music prompt: {prompt}",
                response_model=SoftPreferences,
                tier=ModelTier.FLASH,
                system_prompt=system,
            )
        except Exception:
            # Fallback: return minimal defaults if Gemini fails
            return SoftPreferences(user_language_notes=[prompt])
```

- [ ] **Step 4: Run tests**

```bash
cd /home/angel/Documents/code/Explorator/backend
uv run pytest tests/unit/domain/test_intent_parser.py -v
```

Expected: All 5 tests PASS (deterministic extraction tests don't need Gemini).

- [ ] **Step 5: Commit**

```bash
cd /home/angel/Documents/code/Explorator
git add backend/src/explorator/domain/intent/ backend/tests/unit/domain/test_intent_parser.py
git commit -m "feat(m1): add intent parser with hybrid regex + Gemini extraction"
```

---

## Task 5: Genre Style Service + Genre Sync on Startup

**Files:**
- Create: `backend/src/explorator/domain/style/service.py`
- Modify: `backend/src/explorator/api/app.py` — Sync genres on startup

- [ ] **Step 1: Create genre style service**

Create `backend/src/explorator/domain/style/service.py`:

```python
"""Genre profile retrieval and rule lookup service."""

from pathlib import Path
from typing import Any

from neo4j import AsyncDriver

from explorator.domain.style.loader import (
    discover_genres,
    load_genre_from_yaml,
    load_grammar_from_yaml,
    load_rules_from_yaml,
)
from explorator.graph.style_repo import StyleRepository
from explorator.models.style import GenreProfile, HarmonicGrammar


STYLE_DIR = Path(__file__).parent


class StyleService:
    """Retrieves genre profiles, rules, and grammars from Neo4j."""

    def __init__(self, driver: AsyncDriver) -> None:
        self.repo = StyleRepository(driver)

    async def get_genre_profile(self, genre: str) -> dict[str, Any] | None:
        """Get a genre profile by genre name."""
        return await self.repo.get_genre_profile(genre)

    async def list_genres(self) -> list[dict[str, Any]]:
        """List all available genre profiles."""
        return await self.repo.list_genre_profiles()

    async def sync_genres_to_neo4j(self) -> int:
        """Load all genre YAML files and sync to Neo4j. Returns count synced."""
        genre_names = discover_genres(STYLE_DIR)
        count = 0

        for genre_name in genre_names:
            genre_id = f"genre_{genre_name}_01"

            # Load and sync profile
            profile = load_genre_from_yaml(STYLE_DIR / "genres" / f"{genre_name}.yaml")
            profile_data = profile.model_dump(mode="json")
            profile_data["id"] = genre_id
            profile_data["type"] = "genre_profile"
            profile_data["status"] = "active"
            await self.repo.upsert_genre_profile(genre_id, profile_data)

            # Load and sync rules
            rules_path = STYLE_DIR / "rules" / f"{genre_name}_rules.yaml"
            if rules_path.exists():
                rules = load_rules_from_yaml(rules_path)
                for i, rule in enumerate(rules.rules):
                    rule_id = f"rule_{genre_name}_{i:03d}"
                    rule_data = rule.model_dump(mode="json")
                    rule_data["id"] = rule_id
                    rule_data["type"] = "genre_rule"
                    rule_data["status"] = "active"
                    rule_data["genre"] = genre_name
                    await self.repo.upsert_genre_rule(rule_id, genre_id, rule_data)

                for i, ap in enumerate(rules.anti_patterns):
                    ap_id = f"anti_{genre_name}_{i:03d}"
                    ap_data = ap.model_dump(mode="json")
                    ap_data["id"] = ap_id
                    ap_data["type"] = "anti_pattern"
                    ap_data["status"] = "active"
                    ap_data["genre"] = genre_name
                    await self.repo.upsert_anti_pattern(ap_id, genre_id, ap_data)

            # Load and sync grammar
            grammar_path = STYLE_DIR / "grammars" / f"{genre_name}_grammar.yaml"
            if grammar_path.exists():
                grammar = load_grammar_from_yaml(grammar_path)
                grammar_id = f"grammar_{genre_name}_01"
                grammar_data = grammar.model_dump(mode="json")
                grammar_data["id"] = grammar_id
                grammar_data["type"] = "harmonic_grammar"
                grammar_data["status"] = "active"
                grammar_data["genre_profile_id"] = genre_id
                await self.repo.upsert_harmonic_grammar(grammar_id, genre_id, grammar_data)

            count += 1

        return count
```

- [ ] **Step 2: Update app.py to sync genres on startup**

In `backend/src/explorator/api/app.py`, update the lifespan to sync genres:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: init Neo4j schema and sync genres on startup."""
    import logging

    logger = logging.getLogger(__name__)
    driver = await get_driver()
    await init_schema(driver)

    # Sync genre YAML files to Neo4j
    from explorator.domain.style.service import StyleService

    style_service = StyleService(driver)
    count = await style_service.sync_genres_to_neo4j()
    logger.info("Synced %d genre profiles to Neo4j", count)

    yield
    await close_driver()
```

- [ ] **Step 3: Verify genres now appear in API**

Restart the backend and test:

```bash
curl -s http://localhost:8001/v1/genres | python3 -m json.tool
```

Expected: Returns 3 genres (dream_pop, synthwave, cinematic).

- [ ] **Step 4: Commit**

```bash
cd /home/angel/Documents/code/Explorator
git add backend/src/explorator/domain/style/service.py backend/src/explorator/api/app.py
git commit -m "feat(m1): add style service with genre YAML → Neo4j sync on startup"
```

---

## Task 6: Harmony Generator Service

**Files:**
- Create: `backend/src/explorator/domain/harmony/__init__.py`
- Create: `backend/src/explorator/domain/harmony/generator.py`
- Test: `backend/tests/unit/domain/test_harmony_generator.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/unit/domain/test_harmony_generator.py`:

```python
"""Tests for harmony generator service."""

from explorator.domain.harmony.generator import (
    build_generation_prompt,
)


def test_build_generation_prompt_includes_genre() -> None:
    prompt = build_generation_prompt(
        genre="dream_pop",
        key_center="A",
        mode="major",
        bars=8,
        generation_mode="balanced",
        harmonic_vocabulary=["maj7", "add9", "sus2"],
        common_devices=["borrowed minor iv"],
        cadence_archetypes=["soft_plagal", "open_loop_return"],
        mood_targets=["wistful", "haunted"],
    )
    assert "dream_pop" in prompt or "dream pop" in prompt.lower()
    assert "A major" in prompt or "A" in prompt
    assert "8 bars" in prompt or "8" in prompt
    assert "balanced" in prompt


def test_build_generation_prompt_conservative_mode() -> None:
    prompt = build_generation_prompt(
        genre="synthwave",
        key_center="C",
        mode="minor",
        bars=4,
        generation_mode="conservative",
        harmonic_vocabulary=["minor", "m7"],
        common_devices=["octave bass movement"],
        cadence_archetypes=["minor_plagal"],
        mood_targets=["dark"],
    )
    assert "conservative" in prompt.lower() or "close to archetype" in prompt.lower()
```

- [ ] **Step 2: Implement harmony generator**

Create `backend/src/explorator/domain/harmony/__init__.py`:

```python
"""Harmony generation domain service."""
```

Create `backend/src/explorator/domain/harmony/generator.py`:

```python
"""Generate chord progressions using Gemini Pro + genre constraints."""

import json

from pydantic import BaseModel, Field
from ulid import ULID

from explorator.adapters.gemini import GeminiClient, ModelTier
from explorator.adapters.music21_adapter import analyze_roman_numerals
from explorator.models.harmony import ChordEvent, ProgressionCandidate, RomanNumeralAnalysis
from explorator.utils import utc_now


class GeneratedProgression(BaseModel):
    """Schema for Gemini's structured output."""

    chord_symbols: list[str]
    rationale: str
    intent_tags: list[str] = Field(default_factory=list)


class GeneratedProgressionSet(BaseModel):
    """Multiple progressions from a single generation call."""

    progressions: list[GeneratedProgression]


def build_generation_prompt(
    genre: str,
    key_center: str,
    mode: str,
    bars: int,
    generation_mode: str,
    harmonic_vocabulary: list[str],
    common_devices: list[str],
    cadence_archetypes: list[str],
    mood_targets: list[str],
) -> str:
    """Build the prompt for Gemini Pro progression generation."""
    mode_instruction = {
        "conservative": "Stay close to genre archetypes. Prioritize genre fit and familiarity.",
        "balanced": "Mix archetypal progressions with moderately adventurous options.",
        "exploratory": "Push toward the edges of the genre's boundaries. Prioritize novelty.",
    }.get(generation_mode, "Mix archetypal and adventurous options.")

    return f"""Generate chord progressions for the following creative brief:

Genre: {genre.replace('_', ' ')}
Key: {key_center} {mode}
Length: {bars} bars (one chord per bar unless otherwise noted)
Mood: {', '.join(mood_targets) if mood_targets else 'not specified'}
Generation mode: {generation_mode} — {mode_instruction}

Genre harmonic vocabulary: {', '.join(harmonic_vocabulary)}
Common devices: {', '.join(common_devices)}
Cadence archetypes: {', '.join(cadence_archetypes)}

Return multiple distinct progressions. Each progression should:
- Use chord symbols (e.g., Cmaj7, Am7, Fmaj7, G7)
- Be {bars} chords long (one per bar)
- Fit the genre and mood
- Include a rationale explaining the harmonic choices
- Include intent_tags (short descriptive words)

Make each progression meaningfully different from the others."""


class HarmonyGenerator:
    """Generates chord progressions using Gemini Pro."""

    def __init__(self, gemini: GeminiClient) -> None:
        self.gemini = gemini

    async def generate(
        self,
        session_id: str,
        genre: str,
        key_center: str,
        mode: str,
        bars: int,
        generation_mode: str,
        n_candidates: int,
        harmonic_vocabulary: list[str],
        common_devices: list[str],
        cadence_archetypes: list[str],
        mood_targets: list[str],
    ) -> list[ProgressionCandidate]:
        """Generate N progression candidates using Gemini Pro."""
        prompt = build_generation_prompt(
            genre=genre,
            key_center=key_center or "C",
            mode=mode or "major",
            bars=bars,
            generation_mode=generation_mode,
            harmonic_vocabulary=harmonic_vocabulary,
            common_devices=common_devices,
            cadence_archetypes=cadence_archetypes,
            mood_targets=mood_targets,
        )

        system_prompt = (
            f"You are a music theory expert specializing in {genre.replace('_', ' ')}. "
            f"Generate exactly {n_candidates} distinct chord progressions. "
            "Return valid JSON matching the schema."
        )

        result = await self.gemini.generate_structured(
            prompt=prompt,
            response_model=GeneratedProgressionSet,
            tier=ModelTier.PRO,
            system_prompt=system_prompt,
        )

        candidates: list[ProgressionCandidate] = []
        for prog in result.progressions[:n_candidates]:
            candidate_id = f"prog_{ULID()}"

            # Build chord events
            chord_events = [
                ChordEvent(
                    bar=i + 1,
                    beat=1.0,
                    duration_beats=4.0,
                    symbol=symbol,
                )
                for i, symbol in enumerate(prog.chord_symbols[:bars])
            ]

            # Analyze Roman numerals via music21
            rna_id = f"rna_{ULID()}"
            rn_results = analyze_roman_numerals(
                key=key_center or "C",
                mode=mode or "major",
                chord_symbols=prog.chord_symbols[:bars],
            )
            rna = RomanNumeralAnalysis(
                id=rna_id,
                type="roman_numeral_analysis",
                status="completed",
                progression_candidate_id=candidate_id,
                analysis_events=[
                    {"bar": i + 1, "symbol": r.roman_numeral, "confidence": r.confidence}
                    for i, r in enumerate(rn_results)
                ],
            )

            candidate = ProgressionCandidate(
                id=candidate_id,
                type="progression_candidate",
                status="candidate",
                session_id=session_id,
                rationale=prog.rationale,
                intent_tags=prog.intent_tags,
                key_center=key_center or "C",
                mode=mode or "major",
                phrase_length_bars=bars,
                chord_events=chord_events,
                roman_numeral_analysis_id=rna_id,
                generator_mode=generation_mode,
                source_type="generated",
            )

            # Attach RNA as metadata for now (persisted in persist_round)
            candidate.metadata["roman_numeral_analysis"] = rna.model_dump(mode="json")
            candidates.append(candidate)

        return candidates
```

- [ ] **Step 3: Run tests**

```bash
cd /home/angel/Documents/code/Explorator/backend
uv run pytest tests/unit/domain/test_harmony_generator.py -v
```

- [ ] **Step 4: Commit**

```bash
cd /home/angel/Documents/code/Explorator
git add backend/src/explorator/domain/harmony/ backend/tests/unit/domain/test_harmony_generator.py
git commit -m "feat(m1): add harmony generator with Gemini Pro progression generation"
```

---

## Task 7: Theory Evaluator + Ranking

**Files:**
- Create: `backend/src/explorator/domain/evaluation/__init__.py`
- Create: `backend/src/explorator/domain/evaluation/theory.py`
- Create: `backend/src/explorator/domain/evaluation/ranking.py`
- Test: `backend/tests/unit/domain/test_theory_evaluator.py`
- Test: `backend/tests/unit/domain/test_ranking.py`

- [ ] **Step 1: Write tests for deterministic theory checks**

Create `backend/tests/unit/domain/test_theory_evaluator.py`:

```python
"""Tests for theory evaluator."""

from explorator.domain.evaluation.theory import (
    check_cadence_quality,
    check_loopability,
    check_theoretical_coherence,
)


def test_loopability_same_start_end() -> None:
    """Progression that starts and ends on same chord is highly loopable."""
    score = check_loopability(["Cmaj7", "Am7", "Fmaj7", "Cmaj7"])
    assert score >= 8.0


def test_loopability_different_start_end() -> None:
    """Progression with different start/end is less loopable."""
    score = check_loopability(["Cmaj7", "Am7", "Fmaj7", "G7"])
    assert score < 8.0


def test_cadence_quality_strong_resolution() -> None:
    """V-I cadence should score well."""
    score = check_cadence_quality(["Am7", "Dm7", "G7", "Cmaj7"], key="C", mode="major")
    assert score >= 7.0


def test_theoretical_coherence_diatonic() -> None:
    """Fully diatonic progression should score high coherence."""
    score = check_theoretical_coherence(
        ["Cmaj7", "Dm7", "Em7", "Fmaj7"],
        key="C",
        mode="major",
    )
    assert score >= 7.0
```

- [ ] **Step 2: Write tests for ranking**

Create `backend/tests/unit/domain/test_ranking.py`:

```python
"""Tests for candidate ranking."""

from explorator.domain.evaluation.ranking import select_top_k, weighted_score
from explorator.models.evaluation import AggregateScorecard, ObjectiveWeights


def test_weighted_score_calculation() -> None:
    weights = ObjectiveWeights(
        id="w1", type="weights", status="active",
        weights={"genre_fit": 0.5, "novelty": 0.5},
    )
    scorecard = AggregateScorecard(
        id="s1", type="scorecard", status="active", candidate_id="c1",
        scores={"genre_fit": 8.0, "novelty": 6.0},
    )
    result = weighted_score(scorecard, weights)
    assert abs(result - 7.0) < 0.01  # (8.0*0.5 + 6.0*0.5)


def test_select_top_k_returns_k_items() -> None:
    scorecards = [
        AggregateScorecard(
            id=f"s{i}", type="scorecard", status="active",
            candidate_id=f"c{i}", scores={"genre_fit": float(i)},
            weighted_total=float(i),
        )
        for i in range(10)
    ]
    top = select_top_k(scorecards, k=3)
    assert len(top) == 3
    # Highest scores first
    assert top[0].weighted_total == 9.0
    assert top[1].weighted_total == 8.0
    assert top[2].weighted_total == 7.0


def test_select_top_k_with_fewer_than_k() -> None:
    scorecards = [
        AggregateScorecard(
            id="s1", type="scorecard", status="active",
            candidate_id="c1", scores={}, weighted_total=5.0,
        )
    ]
    top = select_top_k(scorecards, k=5)
    assert len(top) == 1
```

- [ ] **Step 3: Implement theory evaluator**

Create `backend/src/explorator/domain/evaluation/__init__.py`:

```python
"""Evaluation domain service."""
```

Create `backend/src/explorator/domain/evaluation/theory.py`:

```python
"""Theory evaluation — deterministic checks + Gemini hybrid scoring.

Deterministic checks run first. Gemini Flash scores softer dimensions.
LLM is never the sole scoring authority.
"""

from pydantic import BaseModel, Field
from ulid import ULID

from explorator.adapters.gemini import GeminiClient, ModelTier
from explorator.adapters.music21_adapter import parse_chord_symbol
from explorator.models.evaluation import AggregateScorecard, EvaluationBundle, TheoryEvaluation
from explorator.models.harmony import ProgressionCandidate
from explorator.utils import utc_now


def check_loopability(chord_symbols: list[str]) -> float:
    """Score how well a progression loops (0-10). Same start/end = high score."""
    if not chord_symbols:
        return 5.0
    if chord_symbols[0] == chord_symbols[-1]:
        return 9.0
    # Check if roots are the same even with different extensions
    first = parse_chord_symbol(chord_symbols[0])
    last = parse_chord_symbol(chord_symbols[-1])
    if first.root == last.root:
        return 8.0
    return 5.5


def check_cadence_quality(
    chord_symbols: list[str], key: str, mode: str
) -> float:
    """Score cadence quality based on the last two chords (0-10)."""
    if len(chord_symbols) < 2:
        return 5.0

    last = parse_chord_symbol(chord_symbols[-1])
    penult = parse_chord_symbol(chord_symbols[-2])

    # V-I or V-i is a strong cadence
    if last.root == key and penult.root is not None:
        return 8.5

    # IV-I plagal cadence
    return 6.5


def check_theoretical_coherence(
    chord_symbols: list[str], key: str, mode: str
) -> float:
    """Score how well chords fit the key (0-10). More diatonic = higher."""
    if not chord_symbols:
        return 5.0

    # Simple heuristic: count how many chords parse successfully
    parsed = [parse_chord_symbol(s) for s in chord_symbols]
    valid = sum(1 for p in parsed if p.root != "unknown")
    ratio = valid / len(chord_symbols) if chord_symbols else 0
    return 5.0 + (ratio * 5.0)  # 5-10 range


class GeminiScores(BaseModel):
    """Schema for Gemini's evaluation output."""

    genre_fit: float = Field(ge=0, le=10)
    emotional_fit: float = Field(ge=0, le=10)
    novelty: float = Field(ge=0, le=10)


class TheoryEvaluator:
    """Hybrid theory evaluator: deterministic + Gemini Flash."""

    def __init__(self, gemini: GeminiClient) -> None:
        self.gemini = gemini

    async def evaluate(
        self,
        candidate: ProgressionCandidate,
        genre: str,
        mood_targets: list[str],
    ) -> tuple[TheoryEvaluation, AggregateScorecard]:
        """Evaluate a progression candidate. Returns evaluation + scorecard."""
        chord_symbols = [e.symbol for e in candidate.chord_events]

        # Deterministic scores
        loopability = check_loopability(chord_symbols)
        cadence = check_cadence_quality(
            chord_symbols, candidate.key_center, candidate.mode
        )
        coherence = check_theoretical_coherence(
            chord_symbols, candidate.key_center, candidate.mode
        )

        # Gemini-assisted scores
        gemini_scores = await self._gemini_evaluate(
            chord_symbols, genre, mood_targets, candidate.key_center, candidate.mode
        )

        eval_id = f"eval_{ULID()}"
        now = utc_now()

        theory_eval = TheoryEvaluation(
            id=eval_id,
            type="theory_evaluation",
            status="completed",
            created_at=now,
            updated_at=now,
            candidate_id=candidate.id,
            evaluation_type="theory",
            genre_fit=gemini_scores.genre_fit,
            emotional_fit=gemini_scores.emotional_fit,
            theoretical_coherence=coherence,
            cadence_quality=cadence,
            novelty=gemini_scores.novelty,
            loopability=loopability,
        )

        # Build aggregate scorecard
        scores = {
            "genre_fit": gemini_scores.genre_fit,
            "emotional_fit": gemini_scores.emotional_fit,
            "theoretical_coherence": coherence,
            "cadence_quality": cadence,
            "novelty": gemini_scores.novelty,
            "loopability": loopability,
        }
        avg = sum(scores.values()) / len(scores) if scores else 0

        scorecard_id = f"score_{ULID()}"
        scorecard = AggregateScorecard(
            id=scorecard_id,
            type="aggregate_scorecard",
            status="completed",
            created_at=now,
            updated_at=now,
            candidate_id=candidate.id,
            scores=scores,
            weighted_total=round(avg, 2),
        )

        return theory_eval, scorecard

    async def _gemini_evaluate(
        self,
        chord_symbols: list[str],
        genre: str,
        mood_targets: list[str],
        key: str,
        mode: str,
    ) -> GeminiScores:
        """Get Gemini Flash scores for soft dimensions."""
        prompt = f"""Rate this chord progression on a scale of 0-10:

Progression: {' → '.join(chord_symbols)}
Key: {key} {mode}
Target genre: {genre.replace('_', ' ')}
Target mood: {', '.join(mood_targets) if mood_targets else 'not specified'}

Score these dimensions:
- genre_fit: How well does this progression fit the target genre? (0-10)
- emotional_fit: How well does it match the target mood? (0-10)
- novelty: How creative/unexpected is this progression for the genre? (0-10)"""

        try:
            return await self.gemini.generate_structured(
                prompt=prompt,
                response_model=GeminiScores,
                tier=ModelTier.FLASH,
                system_prompt="You are a music theory critic. Score honestly and precisely.",
            )
        except Exception:
            # Fallback: neutral scores if Gemini fails
            return GeminiScores(genre_fit=6.0, emotional_fit=6.0, novelty=5.0)
```

- [ ] **Step 4: Implement ranking**

Create `backend/src/explorator/domain/evaluation/ranking.py`:

```python
"""Candidate ranking — weighted scoring + top-K selection."""

from explorator.models.evaluation import AggregateScorecard, ObjectiveWeights


# Default M1 weights (equal weighting across theory dimensions)
DEFAULT_THEORY_WEIGHTS = ObjectiveWeights(
    id="weights_default",
    type="objective_weights",
    status="active",
    profile_name="default_theory",
    weights={
        "genre_fit": 0.20,
        "emotional_fit": 0.15,
        "theoretical_coherence": 0.20,
        "cadence_quality": 0.15,
        "novelty": 0.10,
        "loopability": 0.20,
    },
)


def weighted_score(
    scorecard: AggregateScorecard,
    weights: ObjectiveWeights,
) -> float:
    """Compute weighted total from scorecard and weights."""
    total = 0.0
    for dim, weight in weights.weights.items():
        total += scorecard.scores.get(dim, 0.0) * weight
    return round(total, 3)


def select_top_k(
    scorecards: list[AggregateScorecard],
    k: int,
) -> list[AggregateScorecard]:
    """Select top K scorecards by weighted_total, highest first."""
    sorted_cards = sorted(scorecards, key=lambda s: s.weighted_total, reverse=True)
    return sorted_cards[:k]
```

- [ ] **Step 5: Run all tests**

```bash
cd /home/angel/Documents/code/Explorator/backend
uv run pytest tests/unit/domain/test_theory_evaluator.py tests/unit/domain/test_ranking.py -v
```

- [ ] **Step 6: Commit**

```bash
cd /home/angel/Documents/code/Explorator
git add backend/src/explorator/domain/evaluation/ backend/tests/unit/domain/test_theory_evaluator.py backend/tests/unit/domain/test_ranking.py
git commit -m "feat(m1): add theory evaluator (hybrid deterministic + Gemini) and ranking service"
```

---

## Task 8: LangGraph Engine — State + Nodes

**Files:**
- Create: `backend/src/explorator/engine/__init__.py`
- Create: `backend/src/explorator/engine/state.py`
- Create: `backend/src/explorator/engine/nodes/parse_intent.py`
- Create: `backend/src/explorator/engine/nodes/load_genre.py`
- Create: `backend/src/explorator/engine/nodes/generate.py`
- Create: `backend/src/explorator/engine/nodes/evaluate_progressions.py`
- Create: `backend/src/explorator/engine/nodes/select_top_progressions.py`
- Create: `backend/src/explorator/engine/nodes/persist_round.py`
- Create: `backend/src/explorator/engine/nodes/__init__.py`
- Test: `backend/tests/unit/engine/test_state.py`

- [ ] **Step 1: Create engine state**

Create `backend/src/explorator/engine/__init__.py`:

```python
"""LangGraph exploration engine."""
```

Create `backend/src/explorator/engine/nodes/__init__.py`:

```python
"""LangGraph node functions."""
```

Create `backend/src/explorator/engine/state.py`:

```python
"""LangGraph exploration state definition."""

from typing import Any, TypedDict


class ExplorationState(TypedDict, total=False):
    """Shared state passed through all LangGraph nodes.

    Uses total=False so nodes can incrementally populate fields.
    """

    # Session context
    session_id: str
    prompt: str
    genre: str
    generation_mode: str

    # Parsed intent
    creative_brief: dict[str, Any]

    # Genre data (loaded from Neo4j)
    genre_profile: dict[str, Any]
    harmonic_grammar: dict[str, Any]
    genre_rules: list[dict[str, Any]]

    # Generation outputs
    progression_candidates: list[dict[str, Any]]
    top_progressions: list[dict[str, Any]]

    # Evaluation outputs
    evaluations: list[dict[str, Any]]
    scorecards: list[dict[str, Any]]

    # Search control
    round_number: int
    n_candidates: int
    k_selection: int

    # Progress callback
    on_progress: Any  # Callable for SSE events
```

- [ ] **Step 2: Write test for state**

```bash
mkdir -p backend/tests/unit/engine
touch backend/tests/unit/engine/__init__.py
```

Create `backend/tests/unit/engine/test_state.py`:

```python
"""Tests for LangGraph state."""

from explorator.engine.state import ExplorationState


def test_exploration_state_creation() -> None:
    state: ExplorationState = {
        "session_id": "sess_01",
        "prompt": "Dream pop in A major",
        "genre": "dream_pop",
        "generation_mode": "balanced",
        "round_number": 1,
        "n_candidates": 12,
        "k_selection": 4,
    }
    assert state["session_id"] == "sess_01"
    assert state["round_number"] == 1


def test_exploration_state_partial() -> None:
    """State can be partially populated."""
    state: ExplorationState = {
        "session_id": "sess_01",
        "prompt": "test",
    }
    assert "genre_profile" not in state
```

- [ ] **Step 3: Implement all 6 nodes**

Create `backend/src/explorator/engine/nodes/parse_intent.py`:

```python
"""Parse intent node — extract constraints from prompt."""

from explorator.adapters.gemini import GeminiClient
from explorator.domain.intent.parser import IntentParser
from explorator.engine.state import ExplorationState


async def parse_intent(state: ExplorationState, *, gemini: GeminiClient) -> dict:
    """Extract structured creative brief from user prompt."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "parse_intent"})

    parser = IntentParser(gemini)
    brief = await parser.parse(state["prompt"], state["session_id"])

    # Update state with parsed intent
    result = {
        "creative_brief": brief.model_dump(mode="json"),
        "genre": brief.genre,
    }

    if callback:
        await callback("node_completed", {"node": "parse_intent", "genre": brief.genre})

    return result
```

Create `backend/src/explorator/engine/nodes/load_genre.py`:

```python
"""Load genre node — fetch genre profile from Neo4j."""

import json

from neo4j import AsyncDriver

from explorator.domain.style.service import StyleService
from explorator.engine.state import ExplorationState


async def load_genre(state: ExplorationState, *, driver: AsyncDriver) -> dict:
    """Load genre profile, grammar, and rules from Neo4j."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "load_genre"})

    service = StyleService(driver)
    genre = state.get("genre", "dream_pop")

    profile = await service.get_genre_profile(genre)
    if profile is None:
        profile = {"genre": genre, "harmonic_vocabulary": [], "common_devices": []}

    # Parse JSON string fields back to dicts/lists
    for field in ["harmonic_tendencies", "voicing_tendencies", "bass_tendencies",
                   "groove_tendencies", "experimentation_envelope"]:
        if field in profile and isinstance(profile[field], str):
            try:
                profile[field] = json.loads(profile[field])
            except (json.JSONDecodeError, TypeError):
                pass

    result = {
        "genre_profile": profile,
    }

    if callback:
        await callback("node_completed", {"node": "load_genre", "genre": genre})

    return result
```

Create `backend/src/explorator/engine/nodes/generate.py`:

```python
"""Generate node — produce progression candidates using Gemini Pro."""

from explorator.adapters.gemini import GeminiClient
from explorator.domain.harmony.generator import HarmonyGenerator
from explorator.engine.state import ExplorationState


async def generate(state: ExplorationState, *, gemini: GeminiClient) -> dict:
    """Generate N progression candidates."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "generate"})

    generator = HarmonyGenerator(gemini)
    brief = state.get("creative_brief", {})
    profile = state.get("genre_profile", {})

    candidates = await generator.generate(
        session_id=state["session_id"],
        genre=state.get("genre", "dream_pop"),
        key_center=brief.get("key_center", "C"),
        mode=brief.get("mode", "major"),
        bars=brief.get("phrase_length_bars", 8),
        generation_mode=state.get("generation_mode", "balanced"),
        n_candidates=state.get("n_candidates", 12),
        harmonic_vocabulary=profile.get("harmonic_vocabulary", []),
        common_devices=profile.get("common_devices", []),
        cadence_archetypes=profile.get("cadence_archetypes", []),
        mood_targets=brief.get("mood_targets", []),
    )

    serialized = [c.model_dump(mode="json") for c in candidates]

    if callback:
        await callback("candidates_preview", {
            "count": len(serialized), "type": "progression"
        })

    return {"progression_candidates": serialized}
```

Create `backend/src/explorator/engine/nodes/evaluate_progressions.py`:

```python
"""Evaluate progressions node — hybrid theory scoring."""

from explorator.adapters.gemini import GeminiClient
from explorator.domain.evaluation.theory import TheoryEvaluator
from explorator.engine.state import ExplorationState
from explorator.models.harmony import ProgressionCandidate


async def evaluate_progressions(
    state: ExplorationState, *, gemini: GeminiClient
) -> dict:
    """Score all progression candidates on theory dimensions."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "evaluate_progressions"})

    evaluator = TheoryEvaluator(gemini)
    brief = state.get("creative_brief", {})
    genre = state.get("genre", "dream_pop")
    mood_targets = brief.get("mood_targets", [])

    evaluations = []
    scorecards = []

    for candidate_data in state.get("progression_candidates", []):
        candidate = ProgressionCandidate.model_validate(candidate_data)

        theory_eval, scorecard = await evaluator.evaluate(
            candidate, genre, mood_targets
        )

        evaluations.append(theory_eval.model_dump(mode="json"))
        scorecards.append(scorecard.model_dump(mode="json"))

    if callback:
        top_score = max((s["weighted_total"] for s in scorecards), default=0)
        await callback("node_completed", {
            "node": "evaluate_progressions", "top_score": top_score
        })

    return {"evaluations": evaluations, "scorecards": scorecards}
```

Create `backend/src/explorator/engine/nodes/select_top_progressions.py`:

```python
"""Select top progressions node — filter by score + diversity."""

from explorator.domain.evaluation.ranking import select_top_k
from explorator.engine.state import ExplorationState
from explorator.models.evaluation import AggregateScorecard


async def select_top_progressions(state: ExplorationState) -> dict:
    """Select top K progressions by score."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "select_top_progressions"})

    scorecards_data = state.get("scorecards", [])
    scorecards = [AggregateScorecard.model_validate(s) for s in scorecards_data]
    k = state.get("k_selection", 4)

    top = select_top_k(scorecards, k)
    top_candidate_ids = {s.candidate_id for s in top}

    # Filter progression candidates to top K
    candidates = state.get("progression_candidates", [])
    top_progressions = [c for c in candidates if c.get("id") in top_candidate_ids]

    if callback:
        await callback("node_completed", {
            "node": "select_top_progressions", "top_count": len(top_progressions)
        })

    return {"top_progressions": top_progressions}
```

Create `backend/src/explorator/engine/nodes/persist_round.py`:

```python
"""Persist round node — save results to Neo4j."""

from neo4j import AsyncDriver

from explorator.engine.state import ExplorationState
from explorator.graph.repository import BaseRepository


class ProgressionCandidateRepo(BaseRepository):
    label = "ProgressionCandidate"


async def persist_round(state: ExplorationState, *, driver: AsyncDriver) -> dict:
    """Save all candidates and evaluations to Neo4j."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "persist_round"})

    from explorator.models.harmony import ProgressionCandidate

    repo = ProgressionCandidateRepo(driver)

    for candidate_data in state.get("top_progressions", []):
        candidate = ProgressionCandidate.model_validate(candidate_data)
        try:
            await repo.create(candidate)
        except Exception:
            pass  # May already exist from a previous round

    if callback:
        top_count = len(state.get("top_progressions", []))
        top_score = 0.0
        for s in state.get("scorecards", []):
            if s.get("weighted_total", 0) > top_score:
                top_score = s["weighted_total"]

        await callback("round_completed", {
            "round": state.get("round_number", 1),
            "candidates_count": top_count,
            "top_score": round(top_score, 2),
            "stop_met": True,  # M1 is single-round
        })

    return {}
```

- [ ] **Step 4: Run tests**

```bash
cd /home/angel/Documents/code/Explorator/backend
uv run pytest tests/unit/engine/ -v
```

- [ ] **Step 5: Commit**

```bash
cd /home/angel/Documents/code/Explorator
git add backend/src/explorator/engine/ backend/tests/unit/engine/
git commit -m "feat(m1): add LangGraph engine state and all M1 nodes"
```

---

## Task 9: LangGraph Graph Definition

**Files:**
- Create: `backend/src/explorator/engine/graph.py`
- Test: `backend/tests/integration/test_engine_flow.py`

- [ ] **Step 1: Implement graph definition**

Create `backend/src/explorator/engine/graph.py`:

```python
"""LangGraph graph definition and compilation for M1 partial flow.

M1 flow: parse_intent → load_genre → generate → evaluate_progressions
         → select_top_progressions → persist_round
"""

from functools import partial

from langgraph.graph import StateGraph, END

from explorator.adapters.gemini import GeminiClient
from explorator.engine.nodes.evaluate_progressions import evaluate_progressions
from explorator.engine.nodes.generate import generate
from explorator.engine.nodes.load_genre import load_genre
from explorator.engine.nodes.parse_intent import parse_intent
from explorator.engine.nodes.persist_round import persist_round
from explorator.engine.nodes.select_top_progressions import select_top_progressions
from explorator.engine.state import ExplorationState
from neo4j import AsyncDriver


def build_m1_graph(gemini: GeminiClient, driver: AsyncDriver):
    """Build and compile the M1 LangGraph exploration flow."""
    graph = StateGraph(ExplorationState)

    # Add nodes with injected dependencies
    graph.add_node("parse_intent", partial(parse_intent, gemini=gemini))
    graph.add_node("load_genre", partial(load_genre, driver=driver))
    graph.add_node("generate", partial(generate, gemini=gemini))
    graph.add_node("evaluate_progressions", partial(evaluate_progressions, gemini=gemini))
    graph.add_node("select_top_progressions", select_top_progressions)
    graph.add_node("persist_round", partial(persist_round, driver=driver))

    # Define edges (linear flow for M1)
    graph.set_entry_point("parse_intent")
    graph.add_edge("parse_intent", "load_genre")
    graph.add_edge("load_genre", "generate")
    graph.add_edge("generate", "evaluate_progressions")
    graph.add_edge("evaluate_progressions", "select_top_progressions")
    graph.add_edge("select_top_progressions", "persist_round")
    graph.add_edge("persist_round", END)

    return graph.compile()
```

- [ ] **Step 2: Write integration test**

Create `backend/tests/integration/test_engine_flow.py`:

```python
"""Integration test for the full M1 engine flow.

Requires: Neo4j running, Gemini API key set.
"""

import os

import pytest
from neo4j import AsyncDriver

from explorator.adapters.gemini import GeminiClient
from explorator.domain.style.service import StyleService
from explorator.engine.graph import build_m1_graph


def _has_api_key() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


@pytest.mark.skipif(not _has_api_key(), reason="GEMINI_API_KEY not set")
async def test_m1_full_flow(neo4j_driver: AsyncDriver) -> None:
    """Run the full M1 flow: parse → genre → generate → evaluate → select → persist."""
    # Sync genres first
    style = StyleService(neo4j_driver)
    await style.sync_genres_to_neo4j()

    gemini = GeminiClient(api_key=os.environ["GEMINI_API_KEY"])
    graph = build_m1_graph(gemini, neo4j_driver)

    initial_state = {
        "session_id": "sess_test_m1",
        "prompt": "Dream pop in A major, wistful and haunted, 8 bars",
        "generation_mode": "conservative",
        "round_number": 1,
        "n_candidates": 4,  # Small for testing
        "k_selection": 2,
    }

    result = await graph.ainvoke(initial_state)

    # Verify outputs
    assert "creative_brief" in result
    assert result["creative_brief"]["genre"] == "dream_pop"
    assert "genre_profile" in result
    assert "progression_candidates" in result
    assert len(result["progression_candidates"]) > 0
    assert "top_progressions" in result
    assert len(result["top_progressions"]) <= 2
    assert "scorecards" in result

    # Verify candidates have chord events
    for candidate in result["top_progressions"]:
        assert "chord_events" in candidate
        assert len(candidate["chord_events"]) > 0
```

- [ ] **Step 3: Run integration test (requires API key)**

```bash
cd /home/angel/Documents/code/Explorator/backend
GEMINI_API_KEY=$(grep GEMINI_API_KEY .env | cut -d= -f2) uv run pytest tests/integration/test_engine_flow.py -v -s
```

- [ ] **Step 4: Commit**

```bash
cd /home/angel/Documents/code/Explorator
git add backend/src/explorator/engine/graph.py backend/tests/integration/test_engine_flow.py
git commit -m "feat(m1): add LangGraph M1 graph definition with full flow integration test"
```

---

## Task 10: Rounds API + SSE

**Files:**
- Create: `backend/src/explorator/api/sse.py`
- Create: `backend/src/explorator/api/routes/rounds.py`
- Create: `backend/src/explorator/api/routes/candidates.py`
- Modify: `backend/src/explorator/api/app.py`
- Modify: `backend/src/explorator/api/deps.py`
- Test: `backend/tests/integration/test_rounds_api.py`

- [ ] **Step 1: Create SSE helpers**

Create `backend/src/explorator/api/sse.py`:

```python
"""Server-Sent Events helpers for round progress."""

import asyncio
import json
from collections.abc import AsyncGenerator


class SSEChannel:
    """A channel that collects SSE events during a round."""

    def __init__(self) -> None:
        self.events: list[dict] = []
        self._queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def send(self, event_type: str, data: dict) -> None:
        """Push an event to the channel."""
        event = {"event": event_type, "data": data}
        self.events.append(event)
        await self._queue.put(event)

    async def close(self) -> None:
        """Signal end of stream."""
        await self._queue.put(None)

    async def stream(self) -> AsyncGenerator[str, None]:
        """Yield SSE-formatted strings."""
        while True:
            event = await self._queue.get()
            if event is None:
                break
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
```

- [ ] **Step 2: Create rounds route**

Create `backend/src/explorator/api/routes/rounds.py`:

```python
"""Round triggering and SSE progress endpoints."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from explorator.adapters.gemini import GeminiClient
from explorator.api.deps import get_gemini_client, get_neo4j_driver
from explorator.api.sse import SSEChannel
from explorator.engine.graph import build_m1_graph
from explorator.graph.session_repo import SessionRepository

router = APIRouter(tags=["rounds"])

# Generation mode → (n_candidates, k_selection)
MODE_PARAMS = {
    "conservative": (8, 3),
    "balanced": (12, 4),
    "exploratory": (16, 6),
}


class TriggerRoundRequest(BaseModel):
    prompt: str | None = None
    generation_mode: str = "balanced"


class RoundResponse(BaseModel):
    round_id: str
    status: str


@router.post("/sessions/{session_id}/rounds")
async def trigger_round(
    session_id: str,
    request: TriggerRoundRequest,
    gemini: GeminiClient = Depends(get_gemini_client),  # noqa: B008
    driver=Depends(get_neo4j_driver),  # noqa: B008
) -> EventSourceResponse:
    """Trigger a generation round and stream progress via SSE."""
    # Verify session exists
    repo = SessionRepository(driver)
    session = await repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    channel = SSEChannel()
    graph = build_m1_graph(gemini, driver)

    n, k = MODE_PARAMS.get(request.generation_mode, (12, 4))

    initial_state = {
        "session_id": session_id,
        "prompt": request.prompt or session.get("metadata", {}).get("prompt", ""),
        "generation_mode": request.generation_mode,
        "round_number": 1,
        "n_candidates": n,
        "k_selection": k,
        "on_progress": channel.send,
    }

    async def run_and_close():
        try:
            await graph.ainvoke(initial_state)
        except Exception as e:
            await channel.send("round_error", {"error": str(e)})
        finally:
            await channel.close()

    # Start the round in the background
    asyncio.create_task(run_and_close())

    return EventSourceResponse(channel.stream())
```

- [ ] **Step 3: Create candidates route**

Create `backend/src/explorator/api/routes/candidates.py`:

```python
"""Candidate listing and detail endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from explorator.api.deps import get_neo4j_driver
from explorator.graph.repository import BaseRepository

router = APIRouter(tags=["candidates"])


class CandidateRepo(BaseRepository):
    label = "ProgressionCandidate"


class ChordEventResponse(BaseModel):
    bar: int
    beat: float
    duration_beats: float
    symbol: str


class CandidateSummary(BaseModel):
    candidate_id: str
    type: str
    status: str
    key_center: str = ""
    mode: str = ""
    chord_symbols: list[str] = Field(default_factory=list)
    roman_numerals: list[str] = Field(default_factory=list)
    rationale: str = ""
    intent_tags: list[str] = Field(default_factory=list)
    weighted_total: float = 0.0
    scores: dict[str, float] = Field(default_factory=dict)


class CandidateListResponse(BaseModel):
    items: list[CandidateSummary]


def _parse_json_field(value: str | list | None) -> list:
    """Parse a field that may be a JSON string or already a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


@router.get("/sessions/{session_id}/candidates")
async def list_candidates(
    session_id: str,
    driver=Depends(get_neo4j_driver),  # noqa: B008
) -> CandidateListResponse:
    """List all progression candidates for a session."""
    repo = CandidateRepo(driver)
    candidates = await repo.query_by_property("session_id", session_id)

    items = []
    for c in candidates:
        chord_events = _parse_json_field(c.get("chord_events"))
        chord_symbols = [e.get("symbol", "") for e in chord_events if isinstance(e, dict)]

        # Try to get Roman numeral analysis from metadata
        metadata = c.get("metadata", "{}")
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}

        rna = metadata.get("roman_numeral_analysis", {})
        rna_events = rna.get("analysis_events", []) if isinstance(rna, dict) else []
        roman_numerals = [e.get("symbol", "?") for e in rna_events if isinstance(e, dict)]

        items.append(CandidateSummary(
            candidate_id=c.get("id", ""),
            type=c.get("type", "progression_candidate"),
            status=c.get("status", "candidate"),
            key_center=c.get("key_center", ""),
            mode=c.get("mode", ""),
            chord_symbols=chord_symbols,
            roman_numerals=roman_numerals,
            rationale=c.get("rationale", ""),
            intent_tags=_parse_json_field(c.get("intent_tags")),
            weighted_total=0.0,  # Will come from scorecard in future
        ))

    return CandidateListResponse(items=items)


@router.get("/candidates/{candidate_id}")
async def get_candidate(
    candidate_id: str,
    driver=Depends(get_neo4j_driver),  # noqa: B008
) -> CandidateSummary:
    """Get a single candidate by ID."""
    repo = CandidateRepo(driver)
    c = await repo.get_by_id(candidate_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    chord_events = _parse_json_field(c.get("chord_events"))
    chord_symbols = [e.get("symbol", "") for e in chord_events if isinstance(e, dict)]

    return CandidateSummary(
        candidate_id=c.get("id", ""),
        type=c.get("type", "progression_candidate"),
        status=c.get("status", "candidate"),
        key_center=c.get("key_center", ""),
        mode=c.get("mode", ""),
        chord_symbols=chord_symbols,
        rationale=c.get("rationale", ""),
        intent_tags=_parse_json_field(c.get("intent_tags")),
    )
```

- [ ] **Step 4: Update app.py and deps.py**

Add to `backend/src/explorator/api/app.py` — register new routes:

```python
from explorator.api.routes import sessions, genres, rounds, candidates

# In create_app():
app.include_router(rounds.router, prefix="/v1")
app.include_router(candidates.router, prefix="/v1")
```

Add to `backend/src/explorator/api/deps.py`:

```python
async def get_neo4j_driver():
    """Get Neo4j driver dependency."""
    return await get_driver()
```

- [ ] **Step 5: Commit**

```bash
cd /home/angel/Documents/code/Explorator
git add backend/src/explorator/api/
git commit -m "feat(m1): add rounds API with SSE progress and candidates endpoints"
```

---

## Task 11: Frontend — Candidate Cards + Round Triggering

**Files:**
- Create: `frontend/src/services/sse.ts`
- Create: `frontend/src/components/CandidateCard.tsx`
- Create: `frontend/src/components/PromptBar.tsx`
- Create: `frontend/src/stores/candidateStore.ts`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/views/SessionWorkspace.tsx`

- [ ] **Step 1: Add SSE client and API functions**

Create `frontend/src/services/sse.ts`:

```typescript
export interface SSEEvent {
  event: string;
  data: Record<string, unknown>;
}

export function connectSSE(
  url: string,
  onEvent: (event: SSEEvent) => void,
  onDone: () => void,
  onError: (error: Event) => void,
): EventSource {
  const source = new EventSource(url);

  const eventTypes = [
    'node_started', 'node_completed', 'candidates_preview',
    'round_completed', 'round_error',
  ];

  for (const type of eventTypes) {
    source.addEventListener(type, (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        onEvent({ event: type, data });
        if (type === 'round_completed' || type === 'round_error') {
          source.close();
          onDone();
        }
      } catch {
        console.error('Failed to parse SSE event', e.data);
      }
    });
  }

  source.onerror = (e) => {
    source.close();
    onError(e);
  };

  return source;
}
```

Add to `frontend/src/services/api.ts`:

```typescript
export interface CandidateSummary {
  candidate_id: string;
  type: string;
  status: string;
  key_center: string;
  mode: string;
  chord_symbols: string[];
  roman_numerals: string[];
  rationale: string;
  intent_tags: string[];
  weighted_total: number;
  scores: Record<string, number>;
}

export interface CandidateListResponse {
  items: CandidateSummary[];
}

export async function listCandidates(sessionId: string): Promise<CandidateListResponse> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/candidates`);
  if (!res.ok) throw new Error(`Failed to list candidates: ${res.status}`);
  return res.json();
}

export function triggerRoundSSE(
  sessionId: string,
  prompt?: string,
  generationMode = 'balanced',
): string {
  const params = new URLSearchParams();
  if (prompt) params.set('prompt', prompt);
  params.set('generation_mode', generationMode);
  return `${API_BASE}/sessions/${sessionId}/rounds?${params}`;
}
```

- [ ] **Step 2: Create candidate store**

Create `frontend/src/stores/candidateStore.ts`:

```typescript
import { create } from 'zustand';
import type { CandidateSummary } from '../services/api';

interface CandidateState {
  candidates: CandidateSummary[];
  loading: boolean;
  progress: string;
  setCandidates: (candidates: CandidateSummary[]) => void;
  setLoading: (loading: boolean) => void;
  setProgress: (progress: string) => void;
}

export const useCandidateStore = create<CandidateState>((set) => ({
  candidates: [],
  loading: false,
  progress: '',
  setCandidates: (candidates) => set({ candidates }),
  setLoading: (loading) => set({ loading }),
  setProgress: (progress) => set({ progress }),
}));
```

- [ ] **Step 3: Create CandidateCard component**

Create `frontend/src/components/CandidateCard.tsx`:

```tsx
import type { CandidateSummary } from '../services/api';

interface Props {
  candidate: CandidateSummary;
}

export default function CandidateCard({ candidate }: Props) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 hover:border-gray-600 transition-colors">
      <div className="flex justify-between items-center mb-2">
        <span className="text-purple-400 font-semibold text-sm">
          {candidate.candidate_id.slice(0, 12)}...
        </span>
        <span className="bg-green-900/30 text-green-400 text-xs px-2 py-0.5 rounded-full">
          {candidate.weighted_total.toFixed(1)}
        </span>
      </div>

      <div className="text-gray-300 text-sm mb-2 font-mono">
        {candidate.chord_symbols.join(' → ')}
      </div>

      {candidate.roman_numerals.length > 0 && (
        <div className="text-gray-500 text-xs mb-2 font-mono">
          {candidate.roman_numerals.join(' → ')}
        </div>
      )}

      <p className="text-gray-400 text-xs mb-2 line-clamp-2">
        {candidate.rationale}
      </p>

      <div className="flex gap-1 flex-wrap">
        {candidate.intent_tags.map((tag) => (
          <span
            key={tag}
            className="bg-gray-800 text-gray-400 text-[10px] px-1.5 py-0.5 rounded"
          >
            {tag}
          </span>
        ))}
        <span className="bg-gray-800 text-gray-500 text-[10px] px-1.5 py-0.5 rounded">
          {candidate.key_center} {candidate.mode}
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create PromptBar component**

Create `frontend/src/components/PromptBar.tsx`:

```tsx
import { useState } from 'react';

interface Props {
  onSubmit: (prompt: string, mode: string) => void;
  loading: boolean;
  progress: string;
}

const MODES = ['conservative', 'balanced', 'exploratory'] as const;

export default function PromptBar({ onSubmit, loading, progress }: Props) {
  const [prompt, setPrompt] = useState('');
  const [mode, setMode] = useState<string>('balanced');

  const handleSubmit = () => {
    if (!prompt.trim() || loading) return;
    onSubmit(prompt, mode);
  };

  return (
    <div className="p-4 bg-gray-900 rounded-lg border border-gray-800 mb-6">
      <div className="flex gap-3 mb-3">
        <input
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          placeholder="Describe the music you want to explore..."
          className="flex-1 bg-gray-800 border border-gray-700 rounded-md px-4 py-2 text-gray-100 placeholder-gray-500 focus:outline-none focus:border-purple-500"
          disabled={loading}
        />
        <button
          onClick={handleSubmit}
          disabled={loading || !prompt.trim()}
          className="px-6 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-700 rounded-md font-medium transition-colors"
        >
          {loading ? 'Generating...' : 'Generate'}
        </button>
      </div>

      <div className="flex gap-2 items-center">
        <span className="text-xs text-gray-500">Mode:</span>
        {MODES.map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`text-xs px-3 py-1 rounded-full transition-colors ${
              mode === m
                ? 'bg-purple-600 text-white'
                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            {m}
          </button>
        ))}
      </div>

      {loading && progress && (
        <div className="mt-3 text-xs text-purple-400 animate-pulse">
          {progress}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Update SessionWorkspace**

Replace `frontend/src/views/SessionWorkspace.tsx`:

```tsx
import { useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { listCandidates } from '../services/api';
import { connectSSE } from '../services/sse';
import { useCandidateStore } from '../stores/candidateStore';
import CandidateCard from '../components/CandidateCard';
import PromptBar from '../components/PromptBar';

export default function SessionWorkspace() {
  const { id } = useParams<{ id: string }>();
  const { candidates, loading, progress, setCandidates, setLoading, setProgress } = useCandidateStore();

  useEffect(() => {
    if (id) {
      listCandidates(id).then((data) => setCandidates(data.items)).catch(console.error);
    }
  }, [id, setCandidates]);

  const handleGenerate = (prompt: string, mode: string) => {
    if (!id) return;
    setLoading(true);
    setProgress('Starting round...');

    const url = `/v1/sessions/${id}/rounds`;

    // POST to trigger the round, which returns an SSE stream
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, generation_mode: mode }),
    }).then(async (response) => {
      if (!response.ok || !response.body) {
        setLoading(false);
        setProgress('Error starting round');
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value);
        const lines = text.split('\n');

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            const eventType = line.slice(7).trim();
            setProgress(eventType.replace(/_/g, ' '));
          }
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.node) {
                setProgress(`${data.node.replace(/_/g, ' ')}...`);
              }
            } catch { /* ignore parse errors */ }
          }
        }
      }

      // Reload candidates after round completes
      const data = await listCandidates(id);
      setCandidates(data.items);
      setLoading(false);
      setProgress('');
    }).catch(() => {
      setLoading(false);
      setProgress('Error');
    });
  };

  return (
    <div className="max-w-6xl mx-auto p-8">
      <Link to="/" className="text-purple-400 hover:text-purple-300 text-sm mb-4 inline-block">
        &larr; Back to Dashboard
      </Link>
      <h1 className="text-2xl font-bold mb-4">Session: {id?.slice(0, 16)}...</h1>

      <PromptBar onSubmit={handleGenerate} loading={loading} progress={progress} />

      {candidates.length > 0 ? (
        <div>
          <h2 className="text-lg font-semibold mb-3">Candidates ({candidates.length})</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {candidates.map((c) => (
              <CandidateCard key={c.candidate_id} candidate={c} />
            ))}
          </div>
        </div>
      ) : !loading ? (
        <p className="text-gray-500">No candidates yet. Enter a prompt above to generate progressions.</p>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 6: Build frontend**

```bash
cd /home/angel/Documents/code/Explorator/frontend
npm run build
```

- [ ] **Step 7: Commit**

```bash
cd /home/angel/Documents/code/Explorator
git add frontend/
git commit -m "feat(m1): add candidate card grid, prompt bar with mode toggle, SSE progress"
```

---

## Task 12: End-to-End Verification

- [ ] **Step 1: Run full test suite**

```bash
cd /home/angel/Documents/code/Explorator
make test
make lint
```

- [ ] **Step 2: Start backend and frontend**

```bash
# Terminal 1: Backend
make backend  # or uvicorn on port 8001

# Terminal 2: Frontend
make frontend
```

- [ ] **Step 3: Verify genres load**

```bash
curl -s http://localhost:8001/v1/genres | python3 -m json.tool
```

Expected: 3 genres listed.

- [ ] **Step 4: Create session and trigger round via frontend**

1. Open http://localhost:5173
2. Create a new session (or open existing)
3. In the workspace, type "Dream pop in A major, wistful, 8 bars"
4. Select "balanced" mode
5. Click "Generate"
6. Watch progress indicators as SSE events arrive
7. See candidate cards appear with chord symbols, Roman numerals, and scores

- [ ] **Step 5: Verify candidates via API**

```bash
curl -s http://localhost:8001/v1/sessions/<session_id>/candidates | python3 -m json.tool
```

Expected: Progression candidates with chord_symbols and roman_numerals.

- [ ] **Step 6: Final commit**

```bash
cd /home/angel/Documents/code/Explorator
git add -A
git commit -m "feat(m1): complete M1 Harmonic MVP — end-to-end verified"
```

---

## Exit Criteria Checklist

- [ ] User can prompt for genre-specific progressions
- [ ] System generates multiple ranked progression candidates
- [ ] Each candidate shows chord symbols and Roman numeral analysis
- [ ] Theory scores (genre fit, coherence, cadence, novelty, loopability, emotional fit) displayed
- [ ] Generation mode control (conservative/balanced/exploratory) works
- [ ] SSE progress stream shows real-time node execution
- [ ] Candidates persist to Neo4j
- [ ] Genre profiles load from YAML on startup
- [ ] All tests pass, lint clean
- [ ] No voicings, bass lines, or playback (those are M2)
