"""Deterministic groove pattern generation from genre preferences."""

import random

from ulid import ULID

from explorator.models.groove import GrooveEvent, GroovePattern, GroovePreferences
from explorator.utils import utc_now

# ---------------------------------------------------------------------------
# Density ranges: comp_density label → (min_density, max_density)
# ---------------------------------------------------------------------------

_DENSITY_RANGES: dict[str, tuple[float, float]] = {
    "sparse": (0.1, 0.35),
    "low": (0.15, 0.4),
    "medium": (0.4, 0.7),
    "dense": (0.7, 0.95),
    "sparse_to_dense": (0.2, 0.6),
}
_DEFAULT_DENSITY_RANGE = (0.4, 0.7)

# ---------------------------------------------------------------------------
# Swing amounts per template
# ---------------------------------------------------------------------------

_SWING_AMOUNTS: dict[str, float] = {
    "straight_eighths": 0.0,
    "syncopated": 0.05,
    "dotted": 0.0,
    "triplet_feel": 0.55,
    "sparse": 0.0,
}

# ---------------------------------------------------------------------------
# Articulation style overrides
# ---------------------------------------------------------------------------

_ARTICULATION_TO_TEMPLATE: dict[str, str] = {
    "shuffle": "triplet_feel",
    "swing": "triplet_feel",
    "floating_pulse": "sparse",
    "sustained_swells": "sparse",
    "arpeggiated_pulse": "straight_eighths",
}

# ---------------------------------------------------------------------------
# Syncopation level fallback
# ---------------------------------------------------------------------------

_SYNCOPATION_TO_TEMPLATE: dict[str, str] = {
    "minimal": "sparse",
    "light": "straight_eighths",
    "low": "straight_eighths",
    "moderate": "dotted",
    "heavy": "syncopated",
}
_DEFAULT_TEMPLATE = "straight_eighths"


def _select_template(prefs: GroovePreferences) -> str:
    """Select the source template based on articulation style then syncopation level."""
    # 1. Articulation overrides (highest priority)
    art = prefs.articulation_style
    if art in _ARTICULATION_TO_TEMPLATE:
        return _ARTICULATION_TO_TEMPLATE[art]
    # 2. Syncopation level fallback
    return _SYNCOPATION_TO_TEMPLATE.get(prefs.syncopation_level, _DEFAULT_TEMPLATE)


def _sample_density(comp_density: str, rng: random.Random) -> float:
    """Return a density float sampled uniformly from the comp_density range."""
    lo, hi = _DENSITY_RANGES.get(comp_density, _DEFAULT_DENSITY_RANGE)
    return rng.uniform(lo, hi)


# ---------------------------------------------------------------------------
# Pattern builders — one per template archetype
# Each builder returns a list of GrooveEvent for `bars` bars (4/4 time).
# Beat positions are continuous: bar 0 → beats 1–4, bar 1 → beats 5–8, etc.
# ---------------------------------------------------------------------------


def _straight_eighths_events(
    bars: int, density: float, rng: random.Random
) -> list[GrooveEvent]:
    """Fill eighth-note slots proportional to density.

    Always include beat 1 of each bar. Accents on beats 1 and 3 of each bar.
    """
    events: list[GrooveEvent] = []
    for bar in range(bars):
        base = bar * 4.0
        # Eighth-note positions within a 4/4 bar: 0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5
        eighth_offsets = [i * 0.5 for i in range(8)]
        for offset in eighth_offsets:
            beat = base + 1.0 + offset  # beat 1 = base+1.0
            is_beat1 = offset == 0.0
            is_accent = offset in (0.0, 2.0)  # beats 1 and 3
            # Always include beat 1; include others by density probability
            if is_beat1 or rng.random() < density:
                velocity = 100 if is_accent else (70 if offset % 1.0 == 0.0 else 55)
                events.append(
                    GrooveEvent(
                        beat=beat,
                        duration_beats=0.5,
                        velocity=velocity,
                        accent=is_accent,
                    )
                )
    return events


def _sparse_events(bars: int, rng: random.Random) -> list[GrooveEvent]:
    """Half notes on beats 1 and 3, occasional ghost note on beat 2 or 4."""
    events: list[GrooveEvent] = []
    for bar in range(bars):
        base = bar * 4.0
        # Beat 1
        events.append(
            GrooveEvent(beat=base + 1.0, duration_beats=2.0, velocity=95, accent=True)
        )
        # Beat 3
        events.append(
            GrooveEvent(beat=base + 3.0, duration_beats=2.0, velocity=90, accent=True)
        )
        # Occasional ghost note on beat 2 or 4 (~30% chance each)
        if rng.random() < 0.3:
            ghost_beat = base + rng.choice([2.0, 4.0])
            events.append(
                GrooveEvent(beat=ghost_beat, duration_beats=0.5, velocity=40, accent=False)
            )
    return events


def _syncopated_events(bars: int, rng: random.Random) -> list[GrooveEvent]:
    """Accents on off-beats (1.5, 2.5, 4.5 within a bar).

    Must have at least one off-beat accent per bar.
    """
    events: list[GrooveEvent] = []
    # Primary off-beat accent positions (bar-relative, 0-indexed: beat 1 = 0.0)
    off_beat_offsets = [0.5, 1.5, 3.5]  # = beats 1.5, 2.5, 4.5 in 1-indexed
    on_beat_offsets = [0.0, 1.0, 2.0, 3.0]  # beats 1–4

    for bar in range(bars):
        base = bar * 4.0

        # Always include at least one guaranteed off-beat accent
        guaranteed_off = rng.choice(off_beat_offsets)
        guaranteed_beat = base + 1.0 + guaranteed_off

        added_offbeats: set[float] = {guaranteed_off}

        # Add more off-beat accents stochastically
        for offset in off_beat_offsets:
            if offset not in added_offbeats and rng.random() < 0.5:
                events.append(
                    GrooveEvent(
                        beat=base + 1.0 + offset,
                        duration_beats=0.5,
                        velocity=95,
                        accent=True,
                    )
                )
                added_offbeats.add(offset)

        # Guaranteed off-beat accent (appended after to preserve order, then sort)
        events.append(
            GrooveEvent(
                beat=guaranteed_beat,
                duration_beats=0.5,
                velocity=100,
                accent=True,
            )
        )

        # Some on-beat notes for context
        for offset in on_beat_offsets:
            if rng.random() < 0.4:
                is_accent = offset in (0.0, 2.0)
                events.append(
                    GrooveEvent(
                        beat=base + 1.0 + offset,
                        duration_beats=0.5,
                        velocity=80 if is_accent else 60,
                        accent=is_accent,
                    )
                )

    # Sort by beat position
    events.sort(key=lambda e: e.beat)
    return events


def _dotted_events(bars: int, _rng: random.Random) -> list[GrooveEvent]:
    """Long-short pattern using 1.5 + 0.5 beat pairs."""
    events: list[GrooveEvent] = []
    for bar in range(bars):
        base = bar * 4.0
        # Two dotted-quarter + eighth pairs per bar:
        # pair 1: beat 1 (dotted quarter = 1.5 beats) + beat 2.5 (eighth = 0.5 beats)
        # pair 2: beat 3 (dotted quarter = 1.5 beats) + beat 4.5 (eighth = 0.5 beats)
        pairs = [(1.0, 1.5, True), (2.5, 0.5, False), (3.0, 1.5, True), (4.5, 0.5, False)]
        for offset, dur, is_long in pairs:
            beat = base + offset
            is_accent = is_long
            velocity = 95 if is_accent else 65
            events.append(
                GrooveEvent(
                    beat=beat,
                    duration_beats=dur,
                    velocity=velocity,
                    accent=is_accent,
                )
            )
    return events


def _triplet_feel_events(bars: int, rng: random.Random) -> list[GrooveEvent]:
    """Shuffle/swing timing using 0.67 + 0.33 beat pairs."""
    events: list[GrooveEvent] = []
    # Triplet subdivision: 1 beat = 3 triplet eighths (0.333... each)
    # Swing pair: long (2/3 beat = 0.667) + short (1/3 beat = 0.333)
    long_dur = 2.0 / 3.0
    short_dur = 1.0 / 3.0

    for bar in range(bars):
        base = bar * 4.0
        # 4 beats per bar, each beat split into long+short pair
        for beat_idx in range(4):
            beat_start = base + 1.0 + beat_idx
            is_downbeat = beat_idx in (0, 2)  # beats 1 and 3

            # Long note (downbeat of the beat)
            velocity = 100 if is_downbeat else 75
            events.append(
                GrooveEvent(
                    beat=beat_start,
                    duration_beats=long_dur,
                    velocity=velocity,
                    accent=is_downbeat,
                )
            )

            # Short note (upbeat of the beat) — stochastic ~60% chance
            if rng.random() < 0.6:
                events.append(
                    GrooveEvent(
                        beat=beat_start + long_dur,
                        duration_beats=short_dur,
                        velocity=55,
                        accent=False,
                    )
                )

    return events


# ---------------------------------------------------------------------------
# Template dispatch table
# ---------------------------------------------------------------------------

def _build_events(
    template: str, bars: int, density: float, rng: random.Random
) -> list[GrooveEvent]:
    """Dispatch to the correct pattern builder."""
    if template == "straight_eighths":
        return _straight_eighths_events(bars, density, rng)
    elif template == "sparse":
        return _sparse_events(bars, rng)
    elif template == "syncopated":
        return _syncopated_events(bars, rng)
    elif template == "dotted":
        return _dotted_events(bars, rng)
    elif template == "triplet_feel":
        return _triplet_feel_events(bars, rng)
    else:
        # Unknown template — fall back to straight eighths
        return _straight_eighths_events(bars, density, rng)


# ---------------------------------------------------------------------------
# Public service class
# ---------------------------------------------------------------------------


class GrooveGenerator:
    """Generates GroovePattern entities from GroovePreferences using template archetypes.

    Purely deterministic — no LLM calls.
    """

    def generate(
        self,
        prefs: GroovePreferences,
        *,
        genre: str,
        session_id: str,
        bars: int = 4,
        seed: int | None = None,
    ) -> GroovePattern:
        """Generate a GroovePattern for the given preferences.

        Parameters
        ----------
        prefs:      GroovePreferences specifying density, articulation, and syncopation.
        genre:      Genre label stored on the pattern (informational).
        session_id: Session this pattern belongs to.
        bars:       Number of bars to generate (default 4).
        seed:       Optional RNG seed for deterministic output.

        Returns
        -------
        A draft GroovePattern entity.
        """
        effective_seed = seed if seed is not None else random.randint(0, 2**31 - 1)
        rng = random.Random(effective_seed)

        template = _select_template(prefs)
        density = _sample_density(prefs.comp_density, rng)
        swing = _SWING_AMOUNTS.get(template, 0.0)
        events = _build_events(template, bars, density, rng)

        now = utc_now()
        return GroovePattern(
            id=f"gp_{ULID()}",
            type="groove_pattern",
            status="draft",
            created_at=now,
            updated_at=now,
            session_id=session_id,
            genre=genre,
            swing_amount=swing,
            density=density,
            pattern_events=events,
            source_template=template,
            variation_seed=effective_seed,
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
        """Generate `count` GroovePattern variants using different seeds.

        Parameters
        ----------
        prefs:      GroovePreferences specifying density, articulation, and syncopation.
        genre:      Genre label stored on the patterns.
        session_id: Session these patterns belong to.
        bars:       Number of bars per pattern (default 4).
        count:      Number of variants to generate (default 3).

        Returns
        -------
        A list of `count` draft GroovePattern entities with unique variation_seeds.
        """
        variants: list[GroovePattern] = []
        used_seeds: set[int] = set()
        base_seed = random.randint(0, 2**31 - 1)

        for i in range(count):
            # Derive a distinct seed for each variant
            candidate_seed = (base_seed + i * 7919) % (2**31)
            while candidate_seed in used_seeds:
                candidate_seed = (candidate_seed + 1) % (2**31)
            used_seeds.add(candidate_seed)
            variants.append(
                self.generate(
                    prefs,
                    genre=genre,
                    session_id=session_id,
                    bars=bars,
                    seed=candidate_seed,
                )
            )

        return variants
