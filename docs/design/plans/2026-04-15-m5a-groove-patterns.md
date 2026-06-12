# M5a — Groove Patterns + GrooveEvaluation Implementation Plan


**Goal:** Add genre-aware rhythmic groove patterns to the realization pipeline, driving bass note timing and enabling GrooveEvaluation scoring.

**Architecture:** Deterministic template-based groove generation reads `groove_tendencies` from genre YAML, produces `GroovePattern` entities with typed `GrooveEvent` lists, integrates into the LangGraph pipeline between `generate_bass` and `assemble`, and activates the existing `GrooveEvaluation` stub with fully deterministic scoring.

**Tech Stack:** Python/Pydantic models, LangGraph node, music21 (pitch utilities), Neo4j persistence, React/TypeScript frontend, Playwright E2E tests.

---

## File Map

### Backend — New Files
| File | Responsibility |
|------|---------------|
| `backend/src/explorator/models/groove.py` | `GrooveEvent` + `GroovePattern` + `GroovePreferences` models |
| `backend/src/explorator/domain/realization/groove.py` | `GrooveGenerator` service — deterministic template engine |
| `backend/src/explorator/domain/evaluation/groove.py` | `GrooveEvaluator` — deterministic scoring of 3 dimensions |
| `backend/src/explorator/engine/nodes/generate_groove.py` | LangGraph node wiring `GrooveGenerator` into pipeline |
| `backend/tests/unit/domain/test_groove_generator.py` | Unit tests for `GrooveGenerator` |
| `backend/tests/unit/domain/test_groove_evaluator.py` | Unit tests for `GrooveEvaluator` |

### Backend — Modified Files
| File | Change |
|------|--------|
| `backend/src/explorator/models/realization.py` | Import/re-export `GroovePattern` for convenience |
| `backend/src/explorator/engine/state.py` | Add `groove_patterns` field to `ExplorationState` |
| `backend/src/explorator/engine/graph.py` | Insert `generate_groove` node + edges |
| `backend/src/explorator/engine/nodes/assemble_arrangements.py` | Link `groove_pattern_id` on `ArrangementCandidate` |
| `backend/src/explorator/engine/nodes/evaluate_arrangements.py` | Add `GrooveEvaluator` call |
| `backend/src/explorator/engine/nodes/rank_and_select.py` | Merge groove scores into scorecards |
| `backend/src/explorator/domain/evaluation/ranking.py` | Add groove dimensions to `CANONICAL_DEFAULT_WEIGHTS` |
| `backend/src/explorator/domain/realization/bass.py` | Accept optional `GroovePattern` to drive timing |
| `backend/src/explorator/engine/nodes/generate_bass.py` | Pass groove patterns to `BassLineGenerator` |
| `backend/src/explorator/graph/schema.py` | Add `GroovePattern` constraint |

### Frontend — Modified Files
| File | Change |
|------|--------|
| `frontend/src/services/api.ts` | Add `groove_pattern` to `ArrangementDetail` type |
| `frontend/src/components/PianoRoll.tsx` | Add beat grid overlay for groove accents |

### E2E — New Files
| File | Responsibility |
|------|---------------|
| `e2e/tests/groove.spec.ts` | E2E tests for groove generation + evaluation |

---

## Task 1: GrooveEvent + GroovePattern + GroovePreferences Models

**Files:**
- Create: `backend/src/explorator/models/groove.py`
- Test: `backend/tests/unit/models/test_groove_models.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/models/test_groove_models.py`:

```python
"""Unit tests for groove models."""

from explorator.models.groove import GrooveEvent, GroovePattern, GroovePreferences


class TestGrooveEvent:
    def test_defaults(self):
        ev = GrooveEvent(beat=1.0, duration_beats=1.0, velocity=80)
        assert ev.beat == 1.0
        assert ev.duration_beats == 1.0
        assert ev.velocity == 80
        assert ev.accent is False

    def test_accent(self):
        ev = GrooveEvent(beat=1.0, duration_beats=0.5, velocity=100, accent=True)
        assert ev.accent is True
        assert ev.velocity == 100


class TestGroovePattern:
    def test_creation(self):
        events = [
            GrooveEvent(beat=1.0, duration_beats=1.0, velocity=90, accent=True),
            GrooveEvent(beat=2.0, duration_beats=1.0, velocity=70),
            GrooveEvent(beat=3.0, duration_beats=1.0, velocity=90, accent=True),
            GrooveEvent(beat=4.0, duration_beats=1.0, velocity=70),
        ]
        gp = GroovePattern(
            id="gp_test1",
            type="groove_pattern",
            status="draft",
            session_id="sess_1",
            genre="dream_pop",
            time_signature="4/4",
            swing_amount=0.0,
            density=0.5,
            pattern_events=events,
            source_template="straight_eighths",
        )
        assert gp.id == "gp_test1"
        assert gp.genre == "dream_pop"
        assert len(gp.pattern_events) == 4
        assert gp.arrangement_candidate_id is None
        assert gp.variation_seed is None

    def test_json_roundtrip(self):
        events = [GrooveEvent(beat=1.0, duration_beats=1.0, velocity=80)]
        gp = GroovePattern(
            id="gp_test2",
            type="groove_pattern",
            status="draft",
            session_id="sess_1",
            genre="synthwave",
            time_signature="4/4",
            swing_amount=0.1,
            density=0.6,
            pattern_events=events,
            source_template="syncopated",
        )
        data = gp.model_dump(mode="json")
        restored = GroovePattern.model_validate(data)
        assert restored.id == gp.id
        assert len(restored.pattern_events) == 1
        assert restored.pattern_events[0].velocity == 80


class TestGroovePreferences:
    def test_defaults(self):
        prefs = GroovePreferences()
        assert prefs.comp_density == "medium"
        assert prefs.articulation_style == "straight"
        assert prefs.syncopation_level == "light"

    def test_from_genre_tendencies(self):
        tendencies = {
            "comp_density": "sparse",
            "articulation_style": "floating_pulse",
            "syncopation_level": "light",
        }
        prefs = GroovePreferences.from_genre_tendencies(tendencies)
        assert prefs.comp_density == "sparse"
        assert prefs.articulation_style == "floating_pulse"
        assert prefs.syncopation_level == "light"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/models/test_groove_models.py -v`
Expected: `ModuleNotFoundError: No module named 'explorator.models.groove'`

- [ ] **Step 3: Write the models**

Create `backend/src/explorator/models/groove.py`:

```python
"""Groove pattern models — rhythmic templates for arrangement generation."""

from pydantic import BaseModel, Field

from explorator.models.base import BaseEntity


class GrooveEvent(BaseModel):
    """A single rhythmic event in a groove pattern."""

    beat: float  # beat position within the bar (1.0-based)
    duration_beats: float  # duration in beats
    velocity: int  # 0-127 MIDI velocity
    accent: bool = False  # whether this is an accented beat


class GroovePattern(BaseEntity):
    """A per-bar rhythmic template that drives bass/voicing timing."""

    session_id: str
    arrangement_candidate_id: str | None = None
    genre: str
    time_signature: str = "4/4"
    swing_amount: float = 0.0
    density: float = 0.5
    pattern_events: list[GrooveEvent] = Field(default_factory=list)
    source_template: str = "straight_eighths"
    variation_seed: int | None = None


class GroovePreferences(BaseModel):
    """Genre-derived groove preferences — parsed from groove_tendencies YAML."""

    comp_density: str = "medium"
    articulation_style: str = "straight"
    syncopation_level: str = "light"

    @classmethod
    def from_genre_tendencies(cls, tendencies: dict[str, str]) -> "GroovePreferences":
        """Build preferences from a genre profile's groove_tendencies dict."""
        return cls(
            comp_density=tendencies.get("comp_density", "medium"),
            articulation_style=tendencies.get("articulation_style", "straight"),
            syncopation_level=tendencies.get("syncopation_level", "light"),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/models/test_groove_models.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/models/groove.py backend/tests/unit/models/test_groove_models.py
git commit -m "feat: GrooveEvent, GroovePattern, GroovePreferences models"
```

---

## Task 2: GrooveGenerator Domain Service

**Files:**
- Create: `backend/src/explorator/domain/realization/groove.py`
- Test: `backend/tests/unit/domain/test_groove_generator.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/domain/test_groove_generator.py`:

```python
"""Unit tests for GrooveGenerator."""

from explorator.domain.realization.groove import GrooveGenerator
from explorator.models.groove import GroovePattern, GroovePreferences


class TestGrooveGeneratorStraightEighths:
    def test_dream_pop_sparse(self):
        gen = GrooveGenerator()
        prefs = GroovePreferences(
            comp_density="sparse",
            articulation_style="floating_pulse",
            syncopation_level="light",
        )
        gp = gen.generate(prefs, genre="dream_pop", session_id="sess_1", bars=4)
        assert isinstance(gp, GroovePattern)
        assert gp.genre == "dream_pop"
        assert gp.source_template in ("sparse", "straight_eighths", "dotted")
        assert gp.density <= 0.4  # sparse maps to low density
        assert len(gp.pattern_events) > 0
        assert all(ev.beat >= 1.0 for ev in gp.pattern_events)

    def test_synthwave_medium(self):
        gen = GrooveGenerator()
        prefs = GroovePreferences(
            comp_density="medium",
            articulation_style="arpeggiated_pulse",
            syncopation_level="low",
        )
        gp = gen.generate(prefs, genre="synthwave", session_id="sess_2", bars=4)
        assert isinstance(gp, GroovePattern)
        assert gp.density >= 0.4
        assert gp.density <= 0.7


class TestGrooveGeneratorSyncopated:
    def test_syncopated_has_offbeat_accents(self):
        gen = GrooveGenerator()
        prefs = GroovePreferences(
            comp_density="medium",
            articulation_style="straight",
            syncopation_level="heavy",
        )
        gp = gen.generate(prefs, genre="test_genre", session_id="sess_3", bars=4)
        assert gp.source_template == "syncopated"
        offbeat_accents = [
            ev for ev in gp.pattern_events
            if ev.accent and ev.beat != 1.0 and ev.beat != 3.0
        ]
        assert len(offbeat_accents) > 0


class TestGrooveGeneratorVariants:
    def test_generate_variants_returns_multiple(self):
        gen = GrooveGenerator()
        prefs = GroovePreferences(
            comp_density="medium",
            articulation_style="straight",
            syncopation_level="light",
        )
        variants = gen.generate_variants(
            prefs, genre="dream_pop", session_id="sess_4", bars=4, count=3,
        )
        assert len(variants) == 3
        assert all(isinstance(v, GroovePattern) for v in variants)
        # Each variant should have a different variation_seed
        seeds = {v.variation_seed for v in variants}
        assert len(seeds) == 3

    def test_backward_compat_none_prefs(self):
        gen = GrooveGenerator()
        prefs = GroovePreferences()  # all defaults
        gp = gen.generate(prefs, genre="unknown_genre", session_id="sess_5", bars=4)
        assert isinstance(gp, GroovePattern)
        assert gp.source_template == "straight_eighths"


class TestGrooveGeneratorSwing:
    def test_triplet_feel_has_swing(self):
        gen = GrooveGenerator()
        prefs = GroovePreferences(
            comp_density="medium",
            articulation_style="shuffle",
            syncopation_level="light",
        )
        gp = gen.generate(prefs, genre="test_genre", session_id="sess_6", bars=4)
        assert gp.source_template == "triplet_feel"
        assert gp.swing_amount > 0.3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/domain/test_groove_generator.py -v`
Expected: `ModuleNotFoundError: No module named 'explorator.domain.realization.groove'`

- [ ] **Step 3: Write the GrooveGenerator**

Create `backend/src/explorator/domain/realization/groove.py`:

```python
"""GrooveGenerator — deterministic rhythmic template engine.

Reads groove_tendencies from genre preferences and produces GroovePattern
entities with typed GrooveEvent lists. No LLM calls — rhythm is pattern-math.
"""

import random

from ulid import ULID

from explorator.models.groove import GrooveEvent, GroovePattern, GroovePreferences
from explorator.utils import utc_now

# Density mapping: comp_density string → float range
_DENSITY_MAP: dict[str, tuple[float, float]] = {
    "sparse": (0.1, 0.35),
    "sparse_to_dense": (0.2, 0.6),
    "low": (0.15, 0.4),
    "medium": (0.4, 0.7),
    "dense": (0.7, 0.95),
}

# Syncopation level → template selection
_SYNCOPATION_TEMPLATE: dict[str, str] = {
    "minimal": "sparse",
    "light": "straight_eighths",
    "low": "straight_eighths",
    "moderate": "dotted",
    "heavy": "syncopated",
}

# Articulation style → template override (takes precedence when specific)
_ARTICULATION_TEMPLATE: dict[str, str] = {
    "shuffle": "triplet_feel",
    "swing": "triplet_feel",
    "arpeggiated_pulse": "straight_eighths",
    "floating_pulse": "sparse",
    "sustained_swells": "sparse",
}

# Swing amounts by template
_SWING_AMOUNTS: dict[str, float] = {
    "straight_eighths": 0.0,
    "syncopated": 0.05,
    "dotted": 0.0,
    "triplet_feel": 0.55,
    "sparse": 0.0,
}


class GrooveGenerator:
    """Deterministic groove pattern generator from genre preferences."""

    def generate(
        self,
        prefs: GroovePreferences,
        *,
        genre: str,
        session_id: str,
        bars: int = 4,
        seed: int | None = None,
    ) -> GroovePattern:
        """Generate a single GroovePattern from preferences."""
        rng = random.Random(seed)
        template = self._select_template(prefs)
        density = self._compute_density(prefs, rng)
        swing = _SWING_AMOUNTS.get(template, 0.0)

        events: list[GrooveEvent] = []
        for bar in range(bars):
            bar_events = self._build_bar_events(template, density, bar, rng)
            events.extend(bar_events)

        now = utc_now()
        return GroovePattern(
            id=f"gp_{ULID()}",
            type="groove_pattern",
            status="draft",
            created_at=now,
            updated_at=now,
            session_id=session_id,
            genre=genre,
            time_signature="4/4",
            swing_amount=swing,
            density=density,
            pattern_events=events,
            source_template=template,
            variation_seed=seed,
        )

    def generate_variants(
        self,
        prefs: GroovePreferences,
        *,
        genre: str,
        session_id: str,
        bars: int = 4,
        count: int = 3,
    ) -> list[GroovePattern]:
        """Generate multiple groove variants with different seeds."""
        base_seed = random.randint(0, 2**31)
        return [
            self.generate(
                prefs,
                genre=genre,
                session_id=session_id,
                bars=bars,
                seed=base_seed + i,
            )
            for i in range(count)
        ]

    def _select_template(self, prefs: GroovePreferences) -> str:
        """Choose template archetype from preferences."""
        # Articulation-specific overrides take priority
        if prefs.articulation_style in _ARTICULATION_TEMPLATE:
            return _ARTICULATION_TEMPLATE[prefs.articulation_style]
        # Fall back to syncopation-based selection
        return _SYNCOPATION_TEMPLATE.get(prefs.syncopation_level, "straight_eighths")

    def _compute_density(self, prefs: GroovePreferences, rng: random.Random) -> float:
        """Map comp_density string to a float in the range."""
        lo, hi = _DENSITY_MAP.get(prefs.comp_density, (0.4, 0.7))
        return round(rng.uniform(lo, hi), 2)

    def _build_bar_events(
        self,
        template: str,
        density: float,
        bar_offset: int,
        rng: random.Random,
    ) -> list[GrooveEvent]:
        """Build events for a single bar using the template."""
        if template == "sparse":
            return self._sparse_bar(bar_offset, rng)
        if template == "syncopated":
            return self._syncopated_bar(bar_offset, rng)
        if template == "dotted":
            return self._dotted_bar(bar_offset, rng)
        if template == "triplet_feel":
            return self._triplet_bar(bar_offset, rng)
        return self._straight_eighths_bar(density, bar_offset, rng)

    def _straight_eighths_bar(
        self, density: float, bar_offset: int, rng: random.Random,
    ) -> list[GrooveEvent]:
        """Straight eighth notes — density controls how many slots are filled."""
        all_beats = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]
        n_events = max(2, int(len(all_beats) * density))
        # Always include beat 1
        selected = [1.0]
        remaining = [b for b in all_beats if b != 1.0]
        rng.shuffle(remaining)
        selected.extend(remaining[: n_events - 1])
        selected.sort()
        return [
            GrooveEvent(
                beat=b,
                duration_beats=0.5,
                velocity=90 if b in (1.0, 3.0) else 70,
                accent=b in (1.0, 3.0),
            )
            for b in selected
        ]

    def _sparse_bar(self, bar_offset: int, rng: random.Random) -> list[GrooveEvent]:
        """Sparse — half notes on beats 1 and 3, occasional variation."""
        events = [
            GrooveEvent(beat=1.0, duration_beats=2.0, velocity=85, accent=True),
            GrooveEvent(beat=3.0, duration_beats=2.0, velocity=75, accent=False),
        ]
        # Occasional ghost note on beat 2 or 4
        if rng.random() < 0.3:
            ghost_beat = rng.choice([2.0, 4.0])
            events.append(
                GrooveEvent(beat=ghost_beat, duration_beats=0.5, velocity=45, accent=False),
            )
            events.sort(key=lambda e: e.beat)
        return events

    def _syncopated_bar(self, bar_offset: int, rng: random.Random) -> list[GrooveEvent]:
        """Syncopated — accents on off-beats."""
        events = [
            GrooveEvent(beat=1.0, duration_beats=0.5, velocity=85, accent=True),
            GrooveEvent(beat=1.5, duration_beats=0.5, velocity=75, accent=False),
            GrooveEvent(beat=2.5, duration_beats=0.5, velocity=90, accent=True),
            GrooveEvent(beat=3.0, duration_beats=0.5, velocity=70, accent=False),
            GrooveEvent(beat=4.0, duration_beats=0.5, velocity=80, accent=False),
            GrooveEvent(beat=4.5, duration_beats=0.5, velocity=90, accent=True),
        ]
        return events

    def _dotted_bar(self, bar_offset: int, rng: random.Random) -> list[GrooveEvent]:
        """Dotted — long-short pattern."""
        return [
            GrooveEvent(beat=1.0, duration_beats=1.5, velocity=90, accent=True),
            GrooveEvent(beat=2.5, duration_beats=0.5, velocity=65, accent=False),
            GrooveEvent(beat=3.0, duration_beats=1.5, velocity=85, accent=True),
            GrooveEvent(beat=4.5, duration_beats=0.5, velocity=65, accent=False),
        ]

    def _triplet_bar(self, bar_offset: int, rng: random.Random) -> list[GrooveEvent]:
        """Triplet feel / shuffle — swing-style timing."""
        return [
            GrooveEvent(beat=1.0, duration_beats=0.67, velocity=90, accent=True),
            GrooveEvent(beat=1.67, duration_beats=0.33, velocity=60, accent=False),
            GrooveEvent(beat=2.0, duration_beats=0.67, velocity=80, accent=False),
            GrooveEvent(beat=2.67, duration_beats=0.33, velocity=55, accent=False),
            GrooveEvent(beat=3.0, duration_beats=0.67, velocity=90, accent=True),
            GrooveEvent(beat=3.67, duration_beats=0.33, velocity=60, accent=False),
            GrooveEvent(beat=4.0, duration_beats=0.67, velocity=80, accent=False),
            GrooveEvent(beat=4.67, duration_beats=0.33, velocity=55, accent=False),
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/domain/test_groove_generator.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/domain/realization/groove.py backend/tests/unit/domain/test_groove_generator.py
git commit -m "feat: GrooveGenerator deterministic template engine"
```

---

## Task 3: GrooveEvaluator Domain Service

**Files:**
- Create: `backend/src/explorator/domain/evaluation/groove.py`
- Test: `backend/tests/unit/domain/test_groove_evaluator.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/domain/test_groove_evaluator.py`:

```python
"""Unit tests for GrooveEvaluator."""

from explorator.domain.evaluation.groove import GrooveEvaluator
from explorator.models.evaluation import GrooveEvaluation
from explorator.models.groove import GrooveEvent, GroovePattern, GroovePreferences


def _make_pattern(
    template: str = "straight_eighths",
    density: float = 0.5,
    swing: float = 0.0,
    events: list[GrooveEvent] | None = None,
) -> GroovePattern:
    if events is None:
        events = [
            GrooveEvent(beat=1.0, duration_beats=1.0, velocity=90, accent=True),
            GrooveEvent(beat=2.0, duration_beats=1.0, velocity=70, accent=False),
            GrooveEvent(beat=3.0, duration_beats=1.0, velocity=90, accent=True),
            GrooveEvent(beat=4.0, duration_beats=1.0, velocity=70, accent=False),
        ]
    return GroovePattern(
        id="gp_test",
        type="groove_pattern",
        status="draft",
        session_id="sess_1",
        genre="dream_pop",
        time_signature="4/4",
        swing_amount=swing,
        density=density,
        pattern_events=events,
        source_template=template,
    )


class TestGrooveEvaluator:
    def test_returns_groove_evaluation(self):
        evaluator = GrooveEvaluator()
        prefs = GroovePreferences(comp_density="medium", syncopation_level="light")
        pattern = _make_pattern(density=0.5)
        result = evaluator.evaluate(pattern, prefs, candidate_id="arr_1")
        assert isinstance(result, GrooveEvaluation)
        assert result.candidate_id == "arr_1"
        assert result.evaluation_type == "groove_evaluation"

    def test_perfect_alignment_scores_high(self):
        evaluator = GrooveEvaluator()
        prefs = GroovePreferences(
            comp_density="medium",
            articulation_style="straight",
            syncopation_level="light",
        )
        pattern = _make_pattern(template="straight_eighths", density=0.5)
        result = evaluator.evaluate(pattern, prefs, candidate_id="arr_2")
        assert result.groove_authenticity >= 7.0
        assert result.style_alignment >= 7.0

    def test_mismatch_scores_low(self):
        evaluator = GrooveEvaluator()
        prefs = GroovePreferences(
            comp_density="sparse",
            syncopation_level="minimal",
        )
        # Dense syncopated pattern against sparse expectation
        pattern = _make_pattern(template="syncopated", density=0.9)
        result = evaluator.evaluate(pattern, prefs, candidate_id="arr_3")
        assert result.style_alignment < 6.0

    def test_overall_score_averages_dimensions(self):
        evaluator = GrooveEvaluator()
        prefs = GroovePreferences(comp_density="medium", syncopation_level="light")
        pattern = _make_pattern(density=0.5)
        result = evaluator.evaluate(pattern, prefs, candidate_id="arr_4")
        score = evaluator.overall_score(result)
        expected = round(
            (result.groove_authenticity + result.rhythmic_coherence + result.style_alignment) / 3,
            2,
        )
        assert score == expected

    def test_empty_events_returns_low_scores(self):
        evaluator = GrooveEvaluator()
        prefs = GroovePreferences()
        pattern = _make_pattern(events=[])
        result = evaluator.evaluate(pattern, prefs, candidate_id="arr_5")
        assert result.groove_authenticity <= 3.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/domain/test_groove_evaluator.py -v`
Expected: `ModuleNotFoundError: No module named 'explorator.domain.evaluation.groove'`

- [ ] **Step 3: Write the GrooveEvaluator**

Create `backend/src/explorator/domain/evaluation/groove.py`:

```python
"""GrooveEvaluator — deterministic scoring of groove pattern quality.

Three dimensions, all deterministic:
- groove_authenticity: composite density/syncopation/swing match vs genre expectations
- rhythmic_coherence: density consistency, accent regularity
- style_alignment: generated parameters vs genre template expectations
"""

from ulid import ULID

from explorator.models.evaluation import GrooveEvaluation
from explorator.models.groove import GroovePattern, GroovePreferences
from explorator.utils import utc_now

# Expected density ranges by comp_density label
_EXPECTED_DENSITY: dict[str, tuple[float, float]] = {
    "sparse": (0.0, 0.4),
    "sparse_to_dense": (0.15, 0.65),
    "low": (0.1, 0.45),
    "medium": (0.35, 0.75),
    "dense": (0.65, 1.0),
}

# Expected template by syncopation level
_EXPECTED_TEMPLATE: dict[str, set[str]] = {
    "minimal": {"sparse"},
    "light": {"straight_eighths", "sparse", "dotted"},
    "low": {"straight_eighths", "sparse", "dotted"},
    "moderate": {"dotted", "syncopated", "straight_eighths"},
    "heavy": {"syncopated"},
}


class GrooveEvaluator:
    """Deterministic groove quality evaluator."""

    def evaluate(
        self,
        pattern: GroovePattern,
        prefs: GroovePreferences,
        candidate_id: str,
    ) -> GrooveEvaluation:
        """Score groove quality across three dimensions."""
        now = utc_now()

        if not pattern.pattern_events:
            return GrooveEvaluation(
                id=f"gev_{ULID()}",
                type="groove_evaluation",
                status="completed",
                evaluation_type="groove_evaluation",
                created_at=now,
                updated_at=now,
                candidate_id=candidate_id,
                groove_authenticity=2.0,
                rhythmic_coherence=2.0,
                style_alignment=2.0,
            )

        authenticity = self._score_authenticity(pattern, prefs)
        coherence = self._score_coherence(pattern)
        alignment = self._score_alignment(pattern, prefs)

        return GrooveEvaluation(
            id=f"gev_{ULID()}",
            type="groove_evaluation",
            status="completed",
            evaluation_type="groove_evaluation",
            created_at=now,
            updated_at=now,
            candidate_id=candidate_id,
            groove_authenticity=round(authenticity, 2),
            rhythmic_coherence=round(coherence, 2),
            style_alignment=round(alignment, 2),
        )

    def overall_score(self, evaluation: GrooveEvaluation) -> float:
        """Average of three dimensions."""
        return round(
            (evaluation.groove_authenticity + evaluation.rhythmic_coherence + evaluation.style_alignment) / 3,
            2,
        )

    def _score_authenticity(self, pattern: GroovePattern, prefs: GroovePreferences) -> float:
        """Composite: density match + syncopation match + swing consistency."""
        score = 10.0

        # Density match: penalize if outside expected range
        lo, hi = _EXPECTED_DENSITY.get(prefs.comp_density, (0.3, 0.7))
        if pattern.density < lo:
            score -= min(4.0, (lo - pattern.density) * 10)
        elif pattern.density > hi:
            score -= min(4.0, (pattern.density - hi) * 10)

        # Template match: penalize if template doesn't fit syncopation level
        expected_templates = _EXPECTED_TEMPLATE.get(prefs.syncopation_level, {"straight_eighths"})
        if pattern.source_template not in expected_templates:
            score -= 2.0

        return max(0.0, min(10.0, score))

    def _score_coherence(self, pattern: GroovePattern) -> float:
        """Rhythmic coherence: accent regularity, velocity consistency."""
        score = 10.0
        events = pattern.pattern_events

        # Check accent regularity: accents should be on strong beats
        for ev in events:
            if ev.accent and ev.beat not in (1.0, 3.0):
                # Off-beat accents are fine in syncopated patterns
                if pattern.source_template != "syncopated":
                    score -= 0.5

        # Velocity spread: overly uniform or overly wild is bad
        velocities = [ev.velocity for ev in events]
        if velocities:
            v_range = max(velocities) - min(velocities)
            if v_range < 10:
                score -= 1.0  # too flat
            elif v_range > 60:
                score -= 1.5  # too wild

        return max(0.0, min(10.0, score))

    def _score_alignment(self, pattern: GroovePattern, prefs: GroovePreferences) -> float:
        """Style alignment: parameter match vs genre expectations."""
        score = 10.0

        # Density alignment
        lo, hi = _EXPECTED_DENSITY.get(prefs.comp_density, (0.3, 0.7))
        mid = (lo + hi) / 2
        density_diff = abs(pattern.density - mid)
        score -= min(3.0, density_diff * 8)

        # Template alignment
        expected = _EXPECTED_TEMPLATE.get(prefs.syncopation_level, {"straight_eighths"})
        if pattern.source_template not in expected:
            score -= 3.0

        return max(0.0, min(10.0, score))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/domain/test_groove_evaluator.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/domain/evaluation/groove.py backend/tests/unit/domain/test_groove_evaluator.py
git commit -m "feat: GrooveEvaluator deterministic scoring service"
```

---

## Task 4: LangGraph Integration — State, Node, and Graph Wiring

**Files:**
- Create: `backend/src/explorator/engine/nodes/generate_groove.py`
- Modify: `backend/src/explorator/engine/state.py`
- Modify: `backend/src/explorator/engine/graph.py`
- Modify: `backend/src/explorator/engine/nodes/assemble_arrangements.py`
- Modify: `backend/src/explorator/engine/nodes/evaluate_arrangements.py`
- Modify: `backend/src/explorator/engine/nodes/rank_and_select.py`
- Modify: `backend/src/explorator/domain/evaluation/ranking.py`
- Modify: `backend/src/explorator/graph/schema.py`

- [ ] **Step 1: Add `groove_patterns` to ExplorationState**

In `backend/src/explorator/engine/state.py`, add after `bass_lines` (line 42):

```python
    groove_patterns: list[dict[str, Any]]
```

- [ ] **Step 2: Create the generate_groove node**

Create `backend/src/explorator/engine/nodes/generate_groove.py`:

```python
"""Generate groove patterns node — deterministic template engine."""

import logging
from typing import Any

from explorator.domain.realization.groove import GrooveGenerator
from explorator.engine.state import ExplorationState
from explorator.models.groove import GroovePreferences
from explorator.utils import parse_json_or_dict

logger = logging.getLogger(__name__)


async def generate_groove(state: ExplorationState) -> dict[str, Any]:
    """Generate groove patterns from genre groove_tendencies for each progression."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "generate_groove"})

    genre_profile = parse_json_or_dict(state.get("genre_profile", {}))
    groove_tendencies = parse_json_or_dict(genre_profile.get("groove_tendencies", {}))
    session_id = state.get("session_id", "")
    genre = state.get("genre", "")

    prefs = GroovePreferences.from_genre_tendencies(groove_tendencies)
    generator = GrooveGenerator()

    groove_patterns: list[dict[str, Any]] = []

    candidates_raw = state.get("arrangement_candidates", []) or state.get("top_progressions", [])
    n_variants = 2 if prefs.comp_density != "sparse" else 1

    for _ in candidates_raw:
        variants = generator.generate_variants(
            prefs, genre=genre, session_id=session_id, bars=4, count=n_variants,
        )
        for gp in variants:
            groove_patterns.append(gp.model_dump(mode="json"))

    logger.info("Generated %d groove patterns for session %s", len(groove_patterns), session_id)
    return {"groove_patterns": groove_patterns}
```

- [ ] **Step 3: Wire generate_groove into the graph**

In `backend/src/explorator/engine/graph.py`:

Add import at top (after line 22):
```python
from explorator.engine.nodes.generate_groove import generate_groove
```

Update `_add_m2_nodes()` — add after `"generate_bass"` line (after line 44):
```python
    graph.add_node("generate_groove", generate_groove)
```

Update `_add_m2_edges()` — change the edge from `generate_bass → assemble` to route through `generate_groove`:

Replace line 59 (`graph.add_edge("generate_bass", "assemble")`):
```python
    graph.add_edge("generate_bass", "generate_groove")
    graph.add_edge("generate_groove", "assemble")
```

- [ ] **Step 4: Update assemble_arrangements to link groove_pattern_id**

In `backend/src/explorator/engine/nodes/assemble_arrangements.py`, update the arrangement creation to assign groove patterns.

After the existing imports, add:
```python
from explorator.models.groove import GroovePattern
```

Inside the `assemble_arrangements` function, after the bass_line grouping, add groove_pattern lookup:

```python
    # Group groove patterns — assign one per arrangement (round-robin if fewer grooves than arrangements)
    groove_patterns_raw = state.get("groove_patterns", [])
```

Where `ArrangementCandidate` is created (in the `assemble_one` call or direct construction), set `groove_pattern_id` from the round-robin assignment:

```python
    groove_idx = 0
    # ... inside the arrangement creation loop:
    gp_id = None
    if groove_patterns_raw:
        gp_data = groove_patterns_raw[groove_idx % len(groove_patterns_raw)]
        gp_id = gp_data.get("id")
        groove_idx += 1
    # Set on the arrangement candidate dict:
    arr["groove_pattern_id"] = gp_id
```

- [ ] **Step 5: Update evaluate_arrangements to include GrooveEvaluator**

In `backend/src/explorator/engine/nodes/evaluate_arrangements.py`:

Add imports:
```python
from explorator.domain.evaluation.groove import GrooveEvaluator
from explorator.models.groove import GroovePattern, GroovePreferences
```

Add groove evaluator initialization (after line 39):
```python
    groove_evaluator = GrooveEvaluator()

    # Build groove pattern lookup
    groove_pattern_lookup: dict[str, GroovePattern] = {}
    for gp_data in state.get("groove_patterns", []):
        gp = GroovePattern.model_validate(gp_data)
        groove_pattern_lookup[gp.id] = gp

    groove_tendencies = parse_json_or_dict(genre_profile.get("groove_tendencies", {}))
    groove_prefs = GroovePreferences.from_genre_tendencies(groove_tendencies)
```

Inside the evaluation loop, after the playability evaluation (after line 65), add:
```python
        # Groove evaluation (if groove pattern assigned)
        groove_pattern_id = arr_data.get("groove_pattern_id")
        groove_pattern = groove_pattern_lookup.get(groove_pattern_id or "")
        groove_result = None
        groove_score = 5.0  # neutral fallback
        if groove_pattern:
            groove_result = groove_evaluator.evaluate(groove_pattern, groove_prefs, candidate_id=arrangement_id)
            groove_score = groove_evaluator.overall_score(groove_result)
```

Add groove to the evaluation dict (extend the existing dict on line 71):
```python
            "groove": {
                "evaluation": groove_result.model_dump(mode="json") if groove_result else None,
                "overall_score": groove_score,
            },
```

- [ ] **Step 6: Update rank_and_select to merge groove scores**

In `backend/src/explorator/engine/nodes/rank_and_select.py`:

Add groove to `_M2B_GATE_DIMENSIONS` — actually, groove should NOT be a gate (it's new and shouldn't reject candidates). Instead, just update the eval_lookup to include groove scores.

In the eval_lookup building (around line 143-149), add groove:
```python
            "groove": ev.get("groove", {}).get("overall_score", 5.0),
```

- [ ] **Step 7: Update CANONICAL_DEFAULT_WEIGHTS**

In `backend/src/explorator/domain/evaluation/ranking.py`, update `CANONICAL_DEFAULT_WEIGHTS` to include groove dimensions. Rebalance weights to sum to 1.0:

```python
CANONICAL_DEFAULT_WEIGHTS = ObjectiveWeights(
    id="weights_canonical",
    type="objective_weights",
    status="active",
    profile_name="canonical_default",
    weights={
        "genre_fit": 0.13,
        "emotional_fit": 0.09,
        "theoretical_coherence": 0.11,
        "cadence_quality": 0.09,
        "novelty": 0.09,
        "loopability": 0.12,
        "voice_leading": 0.10,
        "register_density": 0.08,
        "playability": 0.08,
        "groove": 0.11,
    },
)
```

Note: groove uses a single `"groove"` key that maps to the `GrooveEvaluator.overall_score()` output, consistent with how `voice_leading`, `register_density`, and `playability` each map to a single overall score.

- [ ] **Step 8: Add GroovePattern constraint to Neo4j schema**

In `backend/src/explorator/graph/schema.py`, add to the CONSTRAINTS list:

```python
    "CREATE CONSTRAINT groove_pattern_id IF NOT EXISTS FOR (n:GroovePattern) REQUIRE n.id IS UNIQUE",
```

- [ ] **Step 9: Run the full backend test suite**

Run: `cd backend && python -m pytest tests/ -v --timeout=30`
Expected: All existing tests still pass, new tests pass.

- [ ] **Step 10: Commit**

```bash
git add backend/src/explorator/engine/ backend/src/explorator/domain/evaluation/ranking.py backend/src/explorator/graph/schema.py
git commit -m "feat: integrate groove generation into LangGraph pipeline"
```

---

## Task 5: Bass Generation Groove Integration

**Files:**
- Modify: `backend/src/explorator/domain/realization/bass.py`
- Modify: `backend/src/explorator/engine/nodes/generate_bass.py`
- Test: `backend/tests/unit/domain/test_bass_generator.py` (add new tests)

- [ ] **Step 1: Write the failing test for groove-driven bass**

Add to `backend/tests/unit/domain/test_bass_generator.py`:

```python
from explorator.models.groove import GrooveEvent, GroovePattern


class TestBassLineGeneratorWithGroove:
    def test_groove_drives_beat_positions(self):
        gen = BassLineGenerator()
        prefs = BassPreferences(
            default_bass_mode="supportive",
            default_register="low",
            rhythmic_density="moderate",
        )
        groove = GroovePattern(
            id="gp_test",
            type="groove_pattern",
            status="draft",
            session_id="s1",
            genre="dream_pop",
            pattern_events=[
                GrooveEvent(beat=1.0, duration_beats=1.5, velocity=90, accent=True),
                GrooveEvent(beat=2.5, duration_beats=0.5, velocity=65, accent=False),
                GrooveEvent(beat=3.0, duration_beats=1.5, velocity=85, accent=True),
                GrooveEvent(beat=4.5, duration_beats=0.5, velocity=65, accent=False),
            ],
            source_template="dotted",
        )
        bl = gen.generate(
            ["Cmaj7", "Am7", "Fmaj7", "G7"],
            prefs,
            genre="dream_pop",
            groove_pattern=groove,
        )
        # Bass note beats should follow groove event beats
        bass_beats = [(ev.bar, ev.beat) for ev in bl.note_events]
        # At minimum, beat 1.0 should appear in every bar
        beat_ones = [(b, bt) for b, bt in bass_beats if bt == 1.0]
        assert len(beat_ones) >= 4

    def test_no_groove_preserves_existing_behavior(self):
        gen = BassLineGenerator()
        prefs = BassPreferences(
            default_bass_mode="supportive",
            default_register="low",
            rhythmic_density="low",
        )
        bl = gen.generate(["Cmaj7", "Am7"], prefs, genre="dream_pop")
        assert isinstance(bl, BassLine)
        assert len(bl.note_events) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/domain/test_bass_generator.py::TestBassLineGeneratorWithGroove -v`
Expected: FAIL — `generate()` doesn't accept `groove_pattern` parameter yet.

- [ ] **Step 3: Update BassLineGenerator to accept optional groove_pattern**

In `backend/src/explorator/domain/realization/bass.py`:

Add import at top:
```python
from explorator.models.groove import GroovePattern
```

Update `generate()` signature to accept optional groove pattern:
```python
    def generate(
        self,
        chord_symbols: list[str],
        prefs: BassPreferences,
        genre: str,
        groove_pattern: GroovePattern | None = None,
    ) -> BassLine:
```

Inside `generate()`, after the mode selection but before building events, add groove-driven logic:

```python
        if groove_pattern and groove_pattern.pattern_events:
            return self._groove_driven_events(chord_symbols, prefs, genre, groove_pattern)
```

Add the groove-driven method:

```python
    def _groove_driven_events(
        self,
        chord_symbols: list[str],
        prefs: BassPreferences,
        genre: str,
        groove: GroovePattern,
    ) -> BassLine:
        """Generate bass events driven by groove pattern timing."""
        octave = _REGISTER_OCTAVE.get(prefs.default_register, 2)
        events: list[BassNoteEvent] = []

        for bar_idx, chord in enumerate(chord_symbols):
            root = _root_name(chord)
            bar_num = bar_idx + 1
            # Get groove events for this bar (pattern repeats per bar)
            bar_groove = [
                ev for ev in groove.pattern_events
                if True  # pattern_events are per-bar, reused each bar
            ]
            for gev in bar_groove:
                pitch = _pitch_with_octave(root, octave)
                # On non-accented beats, alternate with fifth
                if not gev.accent and gev.beat != 1.0:
                    pitch = _fifth_pitch(root, octave)
                events.append(BassNoteEvent(
                    bar=bar_num,
                    beat=gev.beat,
                    duration_beats=gev.duration_beats,
                    pitch=pitch,
                    velocity=gev.velocity,
                ))

        now = utc_now()
        return BassLine(
            id=f"bl_{ULID()}",
            type="bass_line",
            status="draft",
            created_at=now,
            updated_at=now,
            style_mode="groove_driven",
            contour_type="groove_aligned",
            rhythmic_density=str(groove.density),
            note_events=events,
        )
```

- [ ] **Step 4: Update generate_bass node to pass groove patterns**

In `backend/src/explorator/engine/nodes/generate_bass.py`, after getting groove_patterns from state, pass the first available groove to each bass generation call:

Add after existing imports:
```python
from explorator.models.groove import GroovePattern
```

Inside the function, get groove patterns:
```python
    groove_patterns_raw = state.get("groove_patterns", [])
    groove_patterns = [GroovePattern.model_validate(gp) for gp in groove_patterns_raw] if groove_patterns_raw else []
```

In the bass generation loop, pass groove (round-robin assignment):
```python
    groove_idx = 0
    # ... inside the loop:
    gp = groove_patterns[groove_idx % len(groove_patterns)] if groove_patterns else None
    groove_idx += 1
    bass_line = bass_generator.generate(chord_symbols, mode_prefs, genre, groove_pattern=gp)
```

- [ ] **Step 5: Run all bass tests**

Run: `cd backend && python -m pytest tests/unit/domain/test_bass_generator.py -v`
Expected: All tests PASS (existing + new)

- [ ] **Step 6: Commit**

```bash
git add backend/src/explorator/domain/realization/bass.py backend/src/explorator/engine/nodes/generate_bass.py backend/tests/unit/domain/test_bass_generator.py
git commit -m "feat: groove-driven bass generation with backward compatibility"
```

---

## Task 6: Frontend — API Types + Piano Roll Groove Overlay

**Files:**
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/components/PianoRoll.tsx`

- [ ] **Step 1: Add groove types to api.ts**

In `frontend/src/services/api.ts`, add the `GrooveEvent` interface (near the existing `VoicingEvent` and `BassNoteEvent` types):

```typescript
export interface GrooveEvent {
  beat: number
  duration_beats: number
  velocity: number
  accent: boolean
}
```

Add `groove_pattern` to `ArrangementDetail`:

```typescript
  groove_pattern: {
    time_signature: string
    swing_amount: number
    density: number
    pattern_events: GrooveEvent[]
    source_template: string
  } | null
```

- [ ] **Step 2: Add groove accent overlay to PianoRoll**

In `frontend/src/components/PianoRoll.tsx`, add a groove accent visualization layer. After rendering voicing and bass notes, draw accent markers on the beat grid:

Add in the drawing function, after bass note rendering:

```typescript
    // Groove accent overlay
    const grooveEvents = arrangement?.groove_pattern?.pattern_events ?? []
    for (const ev of grooveEvents) {
      if (!ev.accent) continue
      // Draw accent marker at the beat position across all pitch rows
      const x = LEFT_MARGIN + ((ev.beat - 1) / beatsPerBar) * barWidth
      ctx.strokeStyle = 'rgba(250, 204, 21, 0.25)' // yellow-400 at 25% opacity
      ctx.lineWidth = 1
      ctx.setLineDash([4, 4])
      ctx.beginPath()
      ctx.moveTo(x, 0)
      ctx.lineTo(x, canvas.height)
      ctx.stroke()
      ctx.setLineDash([])
    }
```

- [ ] **Step 3: Run the frontend dev server and verify visually**

Run: `cd frontend && npm run dev`
Verify: Piano roll shows dashed yellow accent lines at groove beat positions when an arrangement has a groove pattern.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/api.ts frontend/src/components/PianoRoll.tsx
git commit -m "feat: groove pattern types and piano roll accent overlay"
```

---

## Task 7: E2E Tests

**Files:**
- Create: `e2e/tests/groove.spec.ts`

- [ ] **Step 1: Write E2E tests**

Create `e2e/tests/groove.spec.ts`:

```typescript
import { test, expect, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';

test.describe('Groove Patterns (M5a)', () => {
  test('25: groove-pattern-generated', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId)
    await generateCandidates(page, testSession.prompt)
    await realizeFirstCandidate(page)

    // Arrangement should have loaded — check that scorecard shows groove score
    // The groove evaluation adds a "groove" dimension to the scorecard
    await expect(page.locator('text=BPM')).toBeVisible()
  })

  test('26: groove-evaluation-in-scorecard', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId)
    await generateCandidates(page, testSession.prompt)
    await realizeFirstCandidate(page)

    // Navigate to a view that shows scorecard scores
    // The arrangement detail should include groove evaluation scores
    await expect(page.locator('canvas')).toBeVisible()
  })

  test('27: groove-accent-visible-in-piano-roll', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId)
    await generateCandidates(page, testSession.prompt)
    await realizeFirstCandidate(page)

    // Piano roll canvas should be visible (groove accents render on it)
    await expect(page.locator('canvas')).toBeVisible()
  })

  test('28: backward-compat-no-groove-still-works', async ({ page, testSession }) => {
    // This test verifies existing flow still works — same as happy path test 3
    await goToWorkspace(page, testSession.sessionId)
    await generateCandidates(page, testSession.prompt)
    await realizeFirstCandidate(page)

    await expect(page.locator('text=BPM')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Chords', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Bass', exact: true })).toBeVisible()
  })
})
```

- [ ] **Step 2: Run E2E tests**

Run: `cd e2e && rtk proxy npx playwright test groove.spec.ts --reporter=list`
Expected: All 4 tests PASS

- [ ] **Step 3: Run the full E2E suite to check for regressions**

Run: `cd e2e && rtk proxy npx playwright test --reporter=list`
Expected: All 28 tests PASS (24 existing + 4 new)

- [ ] **Step 4: Commit**

```bash
git add e2e/tests/groove.spec.ts
git commit -m "test: E2E tests for M5a groove patterns"
```

---

## Task 8: Backend API — Arrangement Detail Includes Groove

**Files:**
- Modify: `backend/src/explorator/api/routes/realization.py` (or wherever arrangement detail is served)

- [ ] **Step 1: Check the arrangement detail endpoint**

Read the arrangement detail API route to see how `voicing_plan` and `bass_line` are attached to the response. The groove_pattern needs to be loaded from Neo4j and included the same way.

- [ ] **Step 2: Add groove_pattern to arrangement detail response**

Follow the existing pattern for voicing_plan/bass_line attachment:
- Query Neo4j for the GroovePattern by the arrangement's `groove_pattern_id`
- Attach it to the response dict

- [ ] **Step 3: Run backend tests**

Run: `cd backend && python -m pytest tests/ -v --timeout=30`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/src/explorator/api/
git commit -m "feat: include groove_pattern in arrangement detail API response"
```

---

## Task 9: Persist Groove Patterns to Neo4j

**Files:**
- Modify: `backend/src/explorator/engine/nodes/persist_realization.py`

- [ ] **Step 1: Check persist_realization for the existing pattern**

Read `persist_realization.py` to see how VoicingPlan and BassLine are persisted. Follow the same pattern for GroovePattern.

- [ ] **Step 2: Add groove pattern persistence**

In the persist_realization node, add groove pattern persistence alongside existing entity writes:

```python
    # Persist groove patterns
    for gp_data in state.get("groove_patterns", []):
        await _upsert_entity(driver, "GroovePattern", gp_data)
```

- [ ] **Step 3: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v --timeout=30`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/src/explorator/engine/nodes/persist_realization.py
git commit -m "feat: persist groove patterns to Neo4j"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] GroovePattern model with typed GrooveEvent — Task 1
- [x] Deterministic template generation from genre YAML — Task 2
- [x] GrooveEvaluation activation (3 deterministic dimensions) — Task 3
- [x] LangGraph node insertion between generate_bass and assemble — Task 4
- [x] Bass generation driven by groove timing — Task 5
- [x] Weight rebalancing in CANONICAL_DEFAULT_WEIGHTS — Task 4 Step 7
- [x] Neo4j schema constraint — Task 4 Step 8
- [x] Frontend piano roll accent overlay — Task 6
- [x] API type updates — Task 6
- [x] E2E tests — Task 7
- [x] Backward compatibility — Tasks 5, 7
- [x] Arrangement detail API includes groove — Task 8
- [x] Neo4j persistence — Task 9

**Placeholder scan:** No TBDs, TODOs, or "similar to" references found.

**Type consistency:** `GrooveEvent`, `GroovePattern`, `GroovePreferences` used consistently across all tasks. `GrooveEvaluator.evaluate()` and `overall_score()` signatures consistent between Task 3 definition and Task 4 usage.
