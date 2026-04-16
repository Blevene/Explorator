"""Export orchestrator — coordinates rendering and file writing."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from explorator.domain.export.json_renderer import JsonRenderContext, render_json
from explorator.domain.export.midi_renderer import (
    render_combined_midi,
    render_separate_midi,
)
from explorator.models.melody import MelodicComplement
from explorator.models.realization import BassLine, VoicingPlan


_FILENAME_MAP = {
    "midi_combined": "candidate-{label}-{sid}-chords-bass-melody.mid",
    "midi_separate_chords": "candidate-{label}-{sid}-chords.mid",
    "midi_separate_bass": "candidate-{label}-{sid}-bass.mid",
    "midi_separate_melody": "candidate-{label}-{sid}-melody.mid",
    "json": "candidate-{label}-{sid}.json",
}


def build_filename(label: str, short_id: str, artifact_type: str) -> str:
    """Build the export filename for a given artifact type."""
    template = _FILENAME_MAP[artifact_type]
    return template.format(label=label, sid=short_id)


@dataclass
class ExportRequest:
    """All data needed to render artifacts for one candidate."""

    label: str
    short_id: str
    voicing_plan: VoicingPlan
    bass_line: BassLine
    melodic_complement: MelodicComplement | None
    bpm: float
    beats_per_bar: int
    formats: list[str]
    output_dir: str
    json_context: JsonRenderContext | None = None


def render_and_write_artifacts(req: ExportRequest) -> list[dict[str, Any]]:
    """Render requested formats and write to disk. Returns artifact metadata list."""
    os.makedirs(req.output_dir, exist_ok=True)
    artifacts: list[dict[str, Any]] = []

    for fmt in req.formats:
        if fmt == "midi_combined":
            data = render_combined_midi(
                req.voicing_plan, req.bass_line, req.bpm, req.beats_per_bar,
                melodic_complement=req.melodic_complement,
            )
            fname = build_filename(req.label, req.short_id, "midi_combined")
            path = os.path.join(req.output_dir, fname)
            with open(path, "wb") as f:
                f.write(data)
            artifacts.append({"artifact_type": "midi_combined", "path": path, "filename": fname})

        elif fmt == "midi_separate":
            separate = render_separate_midi(
                req.voicing_plan, req.bass_line, req.bpm, req.beats_per_bar,
                melodic_complement=req.melodic_complement,
            )
            for voice, key in [("chords", "chords"), ("bass", "bass"), ("melody", "melody")]:
                if key not in separate:
                    continue
                fname = build_filename(req.label, req.short_id, f"midi_separate_{voice}")
                path = os.path.join(req.output_dir, fname)
                with open(path, "wb") as f:
                    f.write(separate[key])
                artifacts.append({"artifact_type": f"midi_separate_{voice}", "path": path, "filename": fname})

        elif fmt == "json":
            if req.json_context is None:
                continue
            data_str = render_json(req.json_context)
            fname = build_filename(req.label, req.short_id, "json")
            path = os.path.join(req.output_dir, fname)
            with open(path, "w") as f:
                f.write(data_str)
            artifacts.append({"artifact_type": "json", "path": path, "filename": fname})

    return artifacts
