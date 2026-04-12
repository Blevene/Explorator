"""JSON sidecar renderer — human-readable export for DAW reference."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from explorator.models.realization import ArrangementCandidate, BassLine, VoicingPlan
from explorator.models.session import CreativeBrief, Session
from explorator.models.harmony import ProgressionCandidate

_VERSION = "0.4.0"


@dataclass
class JsonRenderContext:
    """All data needed to render a JSON sidecar for one candidate."""

    session: Session
    creative_brief: CreativeBrief
    candidate: ProgressionCandidate
    arrangement: ArrangementCandidate
    voicing_plan: VoicingPlan
    bass_line: BassLine
    scores: dict[str, float]
    mutation_summaries: list[str]


def render_json(ctx: JsonRenderContext) -> str:
    """Produce a human-readable JSON sidecar string."""
    from explorator.utils import utc_now

    doc: dict[str, Any] = {
        "explorator_version": _VERSION,
        "exported_at": utc_now().isoformat(),
        "session": {
            "id": ctx.session.id,
            "prompt": ctx.session.metadata.get("prompt", ""),
            "genre": ctx.creative_brief.genre,
            "bpm": ctx.creative_brief.tempo_hint_bpm,
            "key": f"{ctx.creative_brief.key_center or 'C'} {ctx.creative_brief.mode or 'major'}",
            "meter": ctx.creative_brief.meter,
        },
        "candidate": {
            "id": ctx.candidate.id,
            "label": ctx.candidate.metadata.get("label", ""),
            "role": ctx.candidate.metadata.get("role", ""),
            "chords": ctx.candidate.chord_symbols,
            "roman_numerals": ctx.candidate.roman_numerals,
            "scores": ctx.scores,
            "voicings": [
                {
                    "bar": ev.bar,
                    "beat": ev.beat,
                    "chord": ev.chord_symbol,
                    "pitches": ev.pitches,
                    "duration_beats": ev.duration_beats,
                }
                for ev in ctx.voicing_plan.voicing_events
            ],
            "bass_line": [
                {
                    "bar": ev.bar,
                    "beat": ev.beat,
                    "pitch": ev.pitch,
                    "velocity": ev.velocity,
                    "duration_beats": ev.duration_beats,
                }
                for ev in ctx.bass_line.note_events
            ],
            "lineage": {
                "origin_round": ctx.candidate.metadata.get("origin_round", 1),
                "mutations": ctx.mutation_summaries,
            },
        },
    }
    return json.dumps(doc, indent=2)
