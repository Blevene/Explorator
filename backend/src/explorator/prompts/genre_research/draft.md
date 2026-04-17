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
