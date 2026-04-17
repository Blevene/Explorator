# Genre Draft: {genre_name}

You are synthesizing research into structured genre data for a music generation system.

## Research Summary

{research_log}

## Reference Example

Here is an existing genre profile (Dream Pop) showing the EXACT format, value vocabulary, and key ordering you must follow. Your output must use the same value labels — do NOT invent new ones.

### Profile (dream_pop)
```json
{{
  "genre": "dream_pop",
  "display_name": "Dream Pop",
  "version": 1,
  "harmonic_vocabulary": ["maj7", "add9", "sus2", "m7", "borrowed_iv", "modal_mixture"],
  "harmonic_tendencies": {{
    "functional_strength": "low_medium",
    "chromaticism_level": "moderate",
    "borrowed_chord_tolerance": "moderate_high",
    "cadence_closure_preference": "soft"
  }},
  "voicing_tendencies": {{
    "spacing": "open",
    "register_bias": "mid_high",
    "extension_density": "medium",
    "top_voice_continuity_importance": "high"
  }},
  "bass_tendencies": {{
    "root_emphasis": "medium",
    "pedal_tone_tolerance": "high",
    "rhythmic_activity": "low_medium"
  }},
  "groove_tendencies": {{
    "comp_density": "sparse",
    "articulation_style": "floating_pulse",
    "syncopation_level": "light"
  }},
  "melodic_tendencies": {{
    "motion_preference": "stepwise",
    "range_placement": "above_voicing",
    "density": "sparse",
    "phrase_length": 4,
    "strong_beat_preference": "extensions",
    "rest_between_phrases": true
  }},
  "common_devices": ["borrowed minor iv", "shimmering add9 voicings", "slow harmonic rhythm", "suspended resolutions", "major 7th color"],
  "experimentation_envelope": {{
    "harmonic_deviation_tolerance": 0.65,
    "voicing_deviation_tolerance": 0.80,
    "groove_deviation_tolerance": 0.40
  }},
  "voicing_preferences": {{
    "default_voicing_type": "open",
    "default_register": "mid_high",
    "default_density": "medium",
    "default_voice_count": 4,
    "favor_extensions": true,
    "top_voice_continuity": "high",
    "variant_voicing_types": ["open", "drop2"]
  }},
  "bass_preferences": {{
    "default_bass_mode": "supportive",
    "default_register": "low",
    "rhythmic_density": "sparse",
    "variant_bass_modes": ["supportive", "pedal"]
  }}
}}
```

### Rules (dream_pop)
```json
{{
  "rules": [
    {{
      "name": "shimmering_extensions",
      "type": "voicing",
      "weight": 0.8,
      "description": "Favor add9 and maj7 extensions in upper voicing to create dreamy shimmer",
      "applicability": {{"chord_types": ["maj7", "add9", "sus2"]}}
    }}
  ],
  "anti_patterns": [
    {{
      "name": "power_chord_stacking",
      "scope": "voicing",
      "severity": 0.7,
      "description": "Avoid parallel fifths without extensions — sounds too rock, breaks dreamy texture"
    }}
  ]
}}
```

### Grammar (dream_pop)
```json
{{
  "genre_profile_id": "genre_dream_pop_01",
  "preferred_chord_qualities": ["maj7", "add9", "sus2", "m7"],
  "allowed_borrowed_chords": ["borrowed minor iv", "modal mixture from parallel minor"],
  "cadence_archetypes": ["IV - I (plagal)", "vi - IV - I (deceptive resolve)", "IVmaj7 - Imaj7 (floating)"],
  "harmonic_rhythm_defaults": {{"4/4": 2.0}},
  "functional_motion_bias": {{"stepwise_diatonic": 0.7, "circle_of_fifths": 0.3, "chromatic": 0.2}}
}}
```

## CRITICAL: Allowed Value Vocabulary

You MUST use values from these constrained sets. Do NOT invent new labels.

**Tendency levels** (for all tendency fields): `low`, `low_medium`, `medium`, `medium_high`, `high`

**Spacing**: `open`, `closed`, `mixed`
**Register bias**: `low`, `mid`, `mid_high`, `high`
**Cadence closure preference**: `soft`, `moderate`, `strong`

**Comp density**: `sparse`, `moderate`, `busy`
**Syncopation level**: `none`, `light`, `moderate`, `heavy`
**Articulation style**: use short descriptive labels like `floating_pulse`, `driving_straight`, `swung_relaxed`, `bouncy_staccato`

**Bass mode** (must be one of): `supportive`, `pedal`, `syncopated`
**Bass register**: `low`
**Rhythmic density** (bass): `sparse`, `moderate`, `active`

**Voicing type** (must be from): `open`, `closed`, `drop2`, `quartal`, `cluster`
**Voicing register**: `low`, `mid`, `mid_high`, `high`
**Voicing density**: `sparse`, `medium`, `dense`

**Melodic motion_preference**: `stepwise`, `leaping`, `mixed`
**Melodic range_placement**: `above_voicing`, `overlapping`, `wide`
**Melodic density**: `sparse`, `moderate`, `active`
**Melodic strong_beat_preference**: `chord_tones`, `extensions`, `roots`

**Harmonic vocabulary items**: use lowercase chord symbols: `maj7`, `m7`, `add9`, `sus2`, `sus4`, `7`, `m9`, `9`, `m11`, `13`, `dim7`, `m7b5`, `aug`, `6`, `m6`, `borrowed_iv`, `modal_mixture`, etc.

## Task

Convert the research into three JSON objects matching the reference format EXACTLY:

### 1. Profile
Same field structure and key ordering as the dream_pop example above. Use the allowed value vocabulary. `melodic_tendencies` is OPTIONAL — include only if the research provides confident data.

### 2. Rules
Must include both `rules` (list) and `anti_patterns` (list). Always include at least 1 anti-pattern — every genre has patterns that break its identity.

### 3. Grammar
Same structure as the dream_pop grammar example. `genre_profile_id` must be `"genre_{genre_name}_01"`.

Return valid JSON with top-level keys: "profile", "rules", "grammar".
