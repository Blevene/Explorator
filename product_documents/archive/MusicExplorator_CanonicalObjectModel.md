Below is a canonical object model for the full **Genre Chord Exploration and Realization System**.

I’ll structure it as a coherent domain model, not just a loose list of JSON blobs. The goal is to define the core entities, what each represents, how they relate, and what fields they should carry.

A useful way to think about the system is that it has six major object families:

1. **Intent and session objects**
2. **Style and rule objects**
3. **Musical generation objects**
4. **Evaluation and search objects**
5. **Memory and learning objects**
6. **Presentation and export objects**

---

# 1. Canonical modeling principles

Before the objects themselves, here are the design principles the model should follow.

## A. Separate abstract harmony from realization

A progression is not the same thing as a voiced arrangement.

* `ProgressionCandidate` = harmonic skeleton
* `ArrangementCandidate` = realized musical surface

## B. Preserve lineage

Every meaningful variant should be traceable.

* what source object it came from
* what changed
* why it changed
* which scores improved or worsened

## C. Support partial generation

The system should work even if some layers are missing.

Examples:

* only progression generation
* progression + bass
* user supplies chords, system only explores voicings
* user supplies melody, system explores reharmonization

## D. Separate constraints from preferences

“Must be in D minor” is different from “prefer darker color.”

## E. Model scores as first-class objects

Do not bury evaluation in ad hoc notes.

## F. Make everything session-addressable

Every candidate and evaluation should belong to a session.

---

# 2. Core entity map

Here is the full domain object graph.

```text
Session
 ├── CreativeBrief
 ├── UserPreferenceProfile
 ├── GenreProfile
 ├── SearchPlan
 ├── ProgressionCandidate[]
 │    ├── HarmonicAnalysis
 │    ├── MutationRecord[]
 │    └── EvaluationBundle[]
 ├── ArrangementCandidate[]
 │    ├── VoicingPlan
 │    ├── BassLine
 │    ├── MelodicComplement
 │    ├── InnerVoicePlan
 │    ├── GroovePattern
 │    ├── InstrumentRealizationPlan
 │    ├── MutationRecord[]
 │    └── EvaluationBundle[]
 ├── FinalSelection
 ├── FeedbackEvent[]
 └── ProvenanceTrace
```

And across sessions:

```text
PatternLibrary
UserPreferenceMemory
GenreRuleLibrary
SessionArtifactStore
```

---

# 3. Intent and session objects

## 3.1 Session

This is the top-level container for one exploration run.

### Purpose

Tracks the entire lifecycle of one creative exploration session.

### Canonical fields

```json
{
  "session_id": "sess_2026_03_21_001",
  "created_at": "2026-03-21T15:10:00Z",
  "updated_at": "2026-03-21T15:42:00Z",
  "status": "active",
  "creative_brief_id": "brief_01",
  "genre_profile_id": "genre_neo_soul_01",
  "search_plan_id": "search_01",
  "progression_candidate_ids": ["prog_01", "prog_02"],
  "arrangement_candidate_ids": ["arr_01", "arr_02"],
  "feedback_event_ids": ["fb_01", "fb_02"],
  "final_selection_id": "final_01",
  "provenance_trace_id": "trace_01",
  "metadata": {
    "initiated_by": "user",
    "mode": "full_exploration"
  }
}
```

### Notes

A session can be:

* active
* paused
* completed
* abandoned

---

## 3.2 CreativeBrief

This is the normalized statement of user intent.

### Purpose

Holds the user’s requested artistic direction, hard constraints, and soft preferences.

### Canonical fields

```json
{
  "creative_brief_id": "brief_01",
  "genre": "dream pop",
  "subgenre": null,
  "mood_targets": ["wistful", "haunted"],
  "energy_level": "low_medium",
  "key_center": "A",
  "mode": "major",
  "meter": "4/4",
  "tempo_hint_bpm": 82,
  "phrase_length_bars": 8,
  "form_hint": "loop",
  "complexity_target": "medium",
  "novelty_target": "moderate",
  "instrumentation_targets": ["electric piano", "pad", "bass", "guitar texture"],
  "must_have_constraints": {
    "loopable": true,
    "open_voicings": true
  },
  "avoid_constraints": {
    "strong_classical_cadence": true,
    "overly_busy_bass": true
  },
  "optional_inputs": {
    "reference_artists": [],
    "reference_tracks": [],
    "seed_progression": null,
    "seed_melody_id": null,
    "seed_bassline_id": null
  },
  "user_language_notes": [
    "slightly haunted",
    "not too jazzy"
  ]
}
```

---

## 3.3 UserPreferenceProfile

This is the long-lived taste model for the user.

### Purpose

Stores persistent user preferences that can shape future sessions.

### Canonical fields

```json
{
  "user_preference_profile_id": "user_pref_01",
  "preferred_complexity_band": "medium",
  "preferred_novelty_band": "moderate_high",
  "voicing_preferences": {
    "prefer_open_voicings": true,
    "prefer_dense_clusters": false,
    "prefer_rootless_jazz_voicings": false
  },
  "bass_preferences": {
    "prefer_supportive_bass": true,
    "prefer_busy_bass": false,
    "prefer_pedal_tones": true
  },
  "melodic_preferences": {
    "prefer_sparse_complements": true,
    "prefer_hooky_fragments": false
  },
  "genre_biases": {
    "neo_soul": 0.8,
    "dream_pop": 0.9,
    "indie_folk": 0.5
  },
  "disliked_patterns": [
    "overly rigid ii-V-I chains",
    "generic four-chord pop loop"
  ],
  "updated_at": "2026-03-21T15:39:00Z"
}
```

---

## 3.4 SessionContext

This is the current working state of a session.

### Purpose

Stores dynamic in-session control state.

### Canonical fields

```json
{
  "session_context_id": "ctx_01",
  "session_id": "sess_2026_03_21_001",
  "active_phase": "arrangement_evaluation",
  "current_round": 3,
  "selected_progression_family_ids": ["progfam_02"],
  "selected_arrangement_family_ids": ["arrfam_01"],
  "search_budget_remaining": 12,
  "stop_condition_state": {
    "quality_threshold_met": false,
    "diversity_threshold_met": true,
    "user_satisfaction_estimate": 0.71
  },
  "current_objective_weights_id": "weights_02"
}
```

---

# 4. Style and rule objects

## 4.1 GenreProfile

This is the operational representation of genre knowledge.

### Purpose

Defines genre priors and stylistic boundaries.

### Canonical fields

```json
{
  "genre_profile_id": "genre_dream_pop_01",
  "genre": "dream pop",
  "subgenre": null,
  "harmonic_vocabulary": [
    "maj7",
    "add9",
    "sus2",
    "borrowed_iv",
    "modal mixture"
  ],
  "harmonic_tendencies": {
    "functional_strength": "low_medium",
    "chromaticism_level": "moderate",
    "borrowed_chord_tolerance": "moderate_high",
    "cadence_closure_preference": "soft"
  },
  "voicing_tendencies": {
    "spacing": "open",
    "register_bias": "mid_high",
    "extension_density": "medium",
    "top_voice_continuity_importance": "high"
  },
  "bass_tendencies": {
    "root_emphasis": "medium",
    "pedal_tone_tolerance": "high",
    "rhythmic_activity": "low_medium"
  },
  "groove_tendencies": {
    "comp_density": "sparse",
    "articulation_style": "floating_pulse",
    "syncopation_level": "light"
  },
  "common_devices": [
    "borrowed minor iv",
    "shimmering add9 voicings",
    "slow harmonic rhythm"
  ],
  "anti_patterns": [
    "hard bop dominant chains",
    "aggressively walking bass",
    "dense bebop inner motion"
  ],
  "experimentation_envelope": {
    "harmonic_deviation_tolerance": 0.65,
    "voicing_deviation_tolerance": 0.80,
    "groove_deviation_tolerance": 0.40
  }
}
```

---

## 4.2 GenreRule

This is a smaller reusable rule unit.

### Purpose

Represents one genre-specific rule or prior.

### Canonical fields

```json
{
  "genre_rule_id": "rule_014",
  "genre": "neo-soul",
  "rule_type": "voicing_preference",
  "name": "Prefer smooth upper-structure continuity",
  "description": "When possible, maintain common tones in upper voices and move by semitone or whole step between extensions.",
  "weight": 0.84,
  "applicability_conditions": {
    "instrument": ["piano", "rhodes"],
    "complexity_min": "medium"
  },
  "anti_rule": false
}
```

---

## 4.3 AntiPattern

### Purpose

Represents a pattern that likely breaks stylistic coherence.

```json
{
  "anti_pattern_id": "anti_007",
  "genre": "dream pop",
  "scope": "bass_line",
  "name": "Overly active walking bass",
  "description": "Continuous quarter-note walking bass tends to pull the texture toward jazz or classic pop rather than dream pop.",
  "severity": 0.79
}
```

---

## 4.4 HarmonicGrammar

### Purpose

Represents a genre’s operational harmonic syntax.

```json
{
  "harmonic_grammar_id": "grammar_01",
  "genre_profile_id": "genre_dream_pop_01",
  "preferred_chord_qualities": ["maj7", "add9", "sus2", "m7"],
  "allowed_borrowed_chords": ["iv", "bVI", "bVII"],
  "cadence_archetypes": ["soft_plagal", "open_loop_return", "delayed_resolution"],
  "harmonic_rhythm_defaults": {
    "chords_per_bar_min": 0.5,
    "chords_per_bar_max": 1.5
  },
  "functional_motion_bias": {
    "tonic_to_submediant": 0.6,
    "subdominant_color_motion": 0.8,
    "strong_dominant_resolution": 0.3
  }
}
```

---

# 5. Musical generation objects

## 5.1 ProgressionCandidate

This is the abstract harmonic structure.

### Purpose

Represents a candidate chord progression before detailed realization.

### Canonical fields

```json
{
  "progression_candidate_id": "prog_01",
  "session_id": "sess_2026_03_21_001",
  "family_id": "progfam_01",
  "key_center": "A",
  "mode": "major",
  "phrase_length_bars": 8,
  "chord_events": [
    {
      "bar": 1,
      "beat": 1.0,
      "duration_beats": 4.0,
      "symbol": "Amaj7"
    },
    {
      "bar": 2,
      "beat": 1.0,
      "duration_beats": 4.0,
      "symbol": "C#m7"
    },
    {
      "bar": 3,
      "beat": 1.0,
      "duration_beats": 4.0,
      "symbol": "Dmaj9"
    },
    {
      "bar": 4,
      "beat": 1.0,
      "duration_beats": 4.0,
      "symbol": "Dm6"
    }
  ],
  "roman_numeral_analysis_id": "rna_01",
  "generator_mode": "balanced",
  "intent_tags": ["wistful", "loopable", "borrowed_color"],
  "rationale": "Stable opening with a wistful borrowed iv shift",
  "source_type": "generated",
  "source_reference": null,
  "mutation_lineage_ids": [],
  "status": "candidate"
}
```

---

## 5.2 ChordEvent

### Purpose

Represents one harmonic event in time.

```json
{
  "chord_event_id": "ce_001",
  "bar": 3,
  "beat": 1.0,
  "duration_beats": 2.0,
  "symbol": "F#7alt",
  "function_label": "secondary_dominant",
  "scale_context": "A_major_with_chromatic_borrowing",
  "harmonic_role_tags": ["tension", "pre_resolution"]
}
```

---

## 5.3 RomanNumeralAnalysis

### Purpose

Stores symbolic harmonic interpretation separately from the raw chord labels.

```json
{
  "roman_numeral_analysis_id": "rna_01",
  "progression_candidate_id": "prog_01",
  "analysis_events": [
    {
      "bar": 1,
      "symbol": "Imaj7",
      "confidence": 0.98
    },
    {
      "bar": 2,
      "symbol": "iii7",
      "confidence": 0.92
    },
    {
      "bar": 3,
      "symbol": "IVmaj9",
      "confidence": 0.95
    },
    {
      "bar": 4,
      "symbol": "ivm6",
      "confidence": 0.90
    }
  ],
  "analysis_notes": [
    "bar 4 is modal mixture via borrowed minor iv"
  ]
}
```

---

## 5.4 ProgressionFamily

### Purpose

Groups related harmonic variants.

```json
{
  "progression_family_id": "progfam_01",
  "session_id": "sess_2026_03_21_001",
  "root_progression_candidate_id": "prog_01",
  "member_progression_candidate_ids": ["prog_01", "prog_01b", "prog_01c"],
  "family_description": "A-major wistful family centered around borrowed iv coloration"
}
```

---

## 5.5 VoicingPlan

### Purpose

Defines how a progression is voiced.

```json
{
  "voicing_plan_id": "vp_01",
  "progression_candidate_id": "prog_01",
  "instrument": "electric_piano",
  "voicing_events": [
    {
      "bar": 1,
      "beat": 1.0,
      "pitch_classes": ["A", "C#", "E", "G#"],
      "absolute_pitches": ["E3", "G#3", "C#4", "G#4"],
      "inversion": "root",
      "voicing_tags": ["open", "top_voice_G#"]
    },
    {
      "bar": 2,
      "beat": 1.0,
      "pitch_classes": ["C#", "E", "G#", "B"],
      "absolute_pitches": ["E3", "B3", "C#4", "G#4"],
      "inversion": "first_inversion_feel",
      "voicing_tags": ["common_tone_retention"]
    }
  ],
  "global_strategy": "open mid-high spacing with top voice continuity",
  "density_level": "medium",
  "register_profile": "mid_high"
}
```

---

## 5.6 VoicingEvent

### Purpose

Represents one realized chord voicing.

```json
{
  "voicing_event_id": "ve_01",
  "bar": 4,
  "beat": 1.0,
  "chord_symbol": "Dm6",
  "absolute_pitches": ["D3", "A3", "B3", "F4"],
  "top_voice": "F4",
  "lowest_voice": "D3",
  "spacing_type": "open",
  "playability_notes": ["comfortable for piano", "awkward for closed-position guitar"]
}
```

---

## 5.7 BassLine

### Purpose

Represents the bass realization layer.

```json
{
  "bass_line_id": "bass_01",
  "progression_candidate_id": "prog_01",
  "style_mode": "supportive_pedal_mix",
  "note_events": [
    {
      "bar": 1,
      "beat": 1.0,
      "pitch": "A2",
      "duration_beats": 4.0,
      "role": "root_anchor"
    },
    {
      "bar": 2,
      "beat": 1.0,
      "pitch": "G#2",
      "duration_beats": 4.0,
      "role": "stepwise_support"
    }
  ],
  "contour_type": "mostly_stepwise",
  "rhythmic_density": "low",
  "relationship_to_harmony": "stabilizing"
}
```

---

## 5.8 BassNoteEvent

```json
{
  "bass_note_event_id": "bn_01",
  "bar": 3,
  "beat": 3.0,
  "pitch": "C#3",
  "duration_beats": 1.0,
  "role": "approach_tone",
  "target_harmonic_event_id": "ce_004"
}
```

---

## 5.9 MelodicComplement

### Purpose

Represents a non-primary melodic supporting line.

```json
{
  "melodic_complement_id": "mc_01",
  "progression_candidate_id": "prog_01",
  "style_mode": "sparse_counterline",
  "note_events": [
    {
      "bar": 1,
      "beat": 3.0,
      "pitch": "C#5",
      "duration_beats": 1.0,
      "function": "color_tone"
    },
    {
      "bar": 2,
      "beat": 4.0,
      "pitch": "B4",
      "duration_beats": 1.0,
      "function": "neighbor_motion"
    }
  ],
  "register_profile": "upper_mid",
  "density_level": "sparse",
  "motivic_description": "descending reflective fragments"
}
```

---

## 5.10 Melody

This is for user-supplied or generated primary melody.

```json
{
  "melody_id": "mel_01",
  "session_id": "sess_2026_03_21_001",
  "source_type": "user_supplied",
  "note_events": [
    {
      "bar": 1,
      "beat": 1.0,
      "pitch": "E4",
      "duration_beats": 2.0
    }
  ],
  "range": {
    "lowest": "C4",
    "highest": "A5"
  }
}
```

---

## 5.11 InnerVoicePlan

### Purpose

Represents designed inner motion between bass and top voices.

```json
{
  "inner_voice_plan_id": "iv_01",
  "progression_candidate_id": "prog_01",
  "strategy": "common_tone_retention_with_semitone_resolutions",
  "voice_paths": [
    {
      "voice_label": "alto_like",
      "events": ["E4", "E4", "F#4", "F4"]
    },
    {
      "voice_label": "tenor_like",
      "events": ["C#4", "C#4", "D4", "D4"]
    }
  ],
  "notes": [
    "Preserve shimmer through common-tone anchoring"
  ]
}
```

---

## 5.12 GroovePattern

### Purpose

Represents rhythmic realization behavior.

```json
{
  "groove_pattern_id": "groove_01",
  "meter": "4/4",
  "style_mode": "floating_broken_chords",
  "pattern_events": [
    {
      "bar": 1,
      "beat": 1.0,
      "action": "bass_attack"
    },
    {
      "bar": 1,
      "beat": 1.5,
      "action": "upper_voicing_pulse"
    },
    {
      "bar": 1,
      "beat": 3.0,
      "action": "light_rearticulation"
    }
  ],
  "syncopation_level": "light",
  "density_level": "sparse_medium"
}
```

---

## 5.13 InstrumentRealizationPlan

### Purpose

Adapts arrangement to specific instruments or ensembles.

```json
{
  "instrument_realization_plan_id": "irp_01",
  "arrangement_candidate_id": "arr_01",
  "instrument_roles": [
    {
      "instrument": "electric_piano",
      "role": "primary_harmonic_carrier"
    },
    {
      "instrument": "bass",
      "role": "foundation"
    },
    {
      "instrument": "pad",
      "role": "sustain_texture"
    }
  ],
  "orchestration_notes": [
    "Pad doubles upper chord tones lightly",
    "Guitar only enters on bars 5-8"
  ]
}
```

---

## 5.14 ArrangementCandidate

This is the central realized musical object.

### Purpose

Combines progression plus realization layers into one candidate arrangement.

### Canonical fields

```json
{
  "arrangement_candidate_id": "arr_01",
  "session_id": "sess_2026_03_21_001",
  "family_id": "arrfam_01",
  "progression_candidate_id": "prog_01",
  "voicing_plan_id": "vp_01",
  "bass_line_id": "bass_01",
  "melodic_complement_id": "mc_01",
  "inner_voice_plan_id": "iv_01",
  "groove_pattern_id": "groove_01",
  "instrument_realization_plan_id": "irp_01",
  "render_artifact_ids": [],
  "intent_tags": ["wistful", "floating", "loopable"],
  "rationale": "Preserves harmonic simplicity while adding shimmer and motion",
  "mutation_lineage_ids": [],
  "status": "candidate"
}
```

---

## 5.15 ArrangementFamily

### Purpose

Groups related realized arrangement variants.

```json
{
  "arrangement_family_id": "arrfam_01",
  "session_id": "sess_2026_03_21_001",
  "root_arrangement_candidate_id": "arr_01",
  "member_arrangement_candidate_ids": ["arr_01", "arr_01b", "arr_01c"],
  "family_description": "Open-voiced floating realizations of progression family 01"
}
```

---

# 6. Evaluation and search objects

## 6.1 EvaluationBundle

### Purpose

Groups all evaluations for one candidate.

```json
{
  "evaluation_bundle_id": "eval_01",
  "candidate_id": "arr_01",
  "candidate_type": "arrangement",
  "theory_evaluation_id": "theory_01",
  "voice_leading_evaluation_id": "vl_01",
  "register_density_evaluation_id": "rd_01",
  "playability_evaluation_id": "play_01",
  "groove_evaluation_id": "grv_01",
  "melody_harmony_evaluation_id": null,
  "aggregate_scorecard_id": "score_01"
}
```

---

## 6.2 TheoryEvaluation

```json
{
  "theory_evaluation_id": "theory_01",
  "candidate_id": "arr_01",
  "genre_fit": 8.8,
  "emotional_fit": 8.5,
  "theoretical_coherence": 8.9,
  "cadence_quality": 7.9,
  "novelty": 6.8,
  "notes": [
    "Borrowed iv is stylistically effective",
    "Cadential closure remains soft and loop-friendly"
  ]
}
```

---

## 6.3 VoiceLeadingEvaluation

```json
{
  "voice_leading_evaluation_id": "vl_01",
  "candidate_id": "arr_01",
  "smoothness_score": 8.7,
  "common_tone_retention_score": 8.9,
  "awkward_leap_penalty": 0.4,
  "resolution_quality": 8.2,
  "notes": [
    "Upper voices move elegantly from IVmaj9 to ivm6"
  ]
}
```

---

## 6.4 RegisterDensityEvaluation

```json
{
  "register_density_evaluation_id": "rd_01",
  "candidate_id": "arr_01",
  "register_balance_score": 8.1,
  "mud_risk_score": 1.9,
  "overcrowding_risk_score": 2.3,
  "spacing_quality": 8.6,
  "notes": [
    "Texture remains airy",
    "No low-mid accumulation problems"
  ]
}
```

---

## 6.5 PlayabilityEvaluation

```json
{
  "playability_evaluation_id": "play_01",
  "candidate_id": "arr_01",
  "piano_playability": 8.9,
  "guitar_playability": 5.8,
  "ensemble_playability": 8.2,
  "simplification_recommendations": [
    "Guitar version should omit one color tone in bar 4"
  ]
}
```

---

## 6.6 GrooveEvaluation

```json
{
  "groove_evaluation_id": "grv_01",
  "candidate_id": "arr_01",
  "groove_authenticity": 8.0,
  "rhythmic_coherence": 8.3,
  "style_alignment": 8.4,
  "notes": [
    "Sparse broken-chord pulse supports the genre well"
  ]
}
```

---

## 6.7 MelodyHarmonyEvaluation

```json
{
  "melody_harmony_evaluation_id": "mh_01",
  "candidate_id": "arr_02",
  "melody_support_score": 8.5,
  "tension_justification_score": 7.9,
  "collision_risk_score": 2.1,
  "notes": [
    "Melodic E over Dm6 creates a pleasing 9th-like color implication in context"
  ]
}
```

---

## 6.8 AggregateScorecard

### Purpose

Holds normalized final scores.

```json
{
  "aggregate_scorecard_id": "score_01",
  "candidate_id": "arr_01",
  "scores": {
    "genre_fit": 8.8,
    "emotional_fit": 8.5,
    "theoretical_coherence": 8.9,
    "cadence_quality": 7.9,
    "novelty": 6.8,
    "loopability": 8.7,
    "voicing_quality": 8.6,
    "bass_line_quality": 7.8,
    "melodic_complement_quality": 7.5,
    "inner_voice_quality": 8.3,
    "groove_authenticity": 8.0,
    "playability": 8.2,
    "density_balance": 8.4
  },
  "weighted_total": 8.19,
  "pareto_tags": ["high_genre_fit", "high_loopability"],
  "rank_within_round": 2
}
```

---

## 6.9 ObjectiveWeights

### Purpose

Defines the current weighting scheme.

```json
{
  "objective_weights_id": "weights_02",
  "profile_name": "dream_pop_loop_focused",
  "weights": {
    "genre_fit": 0.18,
    "emotional_fit": 0.14,
    "theoretical_coherence": 0.10,
    "novelty": 0.08,
    "loopability": 0.12,
    "voicing_quality": 0.10,
    "bass_line_quality": 0.07,
    "melodic_complement_quality": 0.05,
    "inner_voice_quality": 0.05,
    "groove_authenticity": 0.05,
    "playability": 0.03,
    "density_balance": 0.03
  }
}
```

---

## 6.10 MutationRecord

### Purpose

Tracks a concrete transformation.

```json
{
  "mutation_record_id": "mut_01",
  "source_candidate_id": "arr_01",
  "source_candidate_type": "arrangement",
  "result_candidate_id": "arr_01b",
  "result_candidate_type": "arrangement",
  "mutation_scope": "voicing_and_bass",
  "changes": [
    {
      "field": "voicing_plan",
      "operation": "increase_openness",
      "description": "Raise top voice by octave in bars 3-4"
    },
    {
      "field": "bass_line",
      "operation": "introduce_pedal",
      "description": "Hold A in bar 1-2 instead of descending to G#"
    }
  ],
  "reason": "Increase floating quality and reduce directed motion",
  "predicted_effects": [
    "more ambient",
    "less tonal pull"
  ],
  "actual_score_delta": {
    "genre_fit": 0.2,
    "loopability": 0.4,
    "novelty": -0.1
  }
}
```

---

## 6.11 SearchPlan

### Purpose

Represents the exploration strategy for the session.

```json
{
  "search_plan_id": "search_01",
  "session_id": "sess_2026_03_21_001",
  "search_strategy": "beam_plus_mutation",
  "initial_generation_count": 16,
  "progression_selection_count": 6,
  "arrangement_selection_count": 4,
  "max_rounds": 4,
  "mutation_budget_per_round": 6,
  "diversity_target": 0.65,
  "stop_conditions": {
    "target_score": 8.4,
    "max_rounds": 4
  }
}
```

---

## 6.12 SearchRound

### Purpose

Tracks one iteration of exploration.

```json
{
  "search_round_id": "round_02",
  "session_id": "sess_2026_03_21_001",
  "round_number": 2,
  "input_candidate_ids": ["prog_01", "prog_02"],
  "generated_candidate_ids": ["arr_01", "arr_01b", "arr_02"],
  "selected_candidate_ids": ["arr_01b", "arr_02"],
  "eliminated_candidate_ids": ["arr_01"],
  "notes": [
    "Round focused on voicing openness and bass simplification"
  ]
}
```

---

## 6.13 ParetoFrontSnapshot

### Purpose

Captures the non-dominated candidates for a round.

```json
{
  "pareto_front_snapshot_id": "pareto_02",
  "session_id": "sess_2026_03_21_001",
  "round_number": 2,
  "candidate_ids": ["arr_01b", "arr_03", "arr_04"],
  "axes": ["genre_fit", "novelty", "loopability", "playability"]
}
```

---

## 6.14 FinalSelection

### Purpose

Represents the chosen outputs.

```json
{
  "final_selection_id": "final_01",
  "session_id": "sess_2026_03_21_001",
  "selected_candidate_ids": ["arr_01b", "arr_03", "arr_04"],
  "selection_roles": {
    "safest": "arr_01b",
    "most_experimental_viable": "arr_03",
    "best_loop": "arr_04"
  },
  "selection_notes": [
    "Selected to preserve diversity across emotional and textural interpretations"
  ]
}
```

---

# 7. Memory and learning objects

## 7.1 PatternLibraryEntry

### Purpose

Stores a reusable discovered pattern.

```json
{
  "pattern_library_entry_id": "pat_01",
  "pattern_type": "progression_plus_voicing",
  "genre": "dream pop",
  "tags": ["wistful", "borrowed_iv", "open_voicing", "loopable"],
  "source_candidate_id": "arr_01b",
  "abstracted_pattern": {
    "roman": ["Imaj7", "iii7", "IVmaj9", "ivm6"],
    "voicing_strategy": "open_mid_high_with_common_tone_top_voice",
    "bass_strategy": "root_then_stepwise_support"
  },
  "success_metrics": {
    "average_weighted_score": 8.31,
    "user_rating": 9.0
  },
  "notes": "Useful for ambient wistful contexts with light melancholy"
}
```

---

## 7.2 UserFeedbackEvent

### Purpose

Stores explicit user reaction.

```json
{
  "feedback_event_id": "fb_01",
  "session_id": "sess_2026_03_21_001",
  "candidate_id": "arr_01",
  "feedback_type": "text_reaction",
  "content": "I like this but the bass is still too directed",
  "interpreted_adjustments": {
    "reduce_bass_motion": true,
    "increase_pedal_probability": true
  },
  "timestamp": "2026-03-21T15:26:10Z"
}
```

---

## 7.3 RetrievalQuery

### Purpose

Represents a memory retrieval request.

```json
{
  "retrieval_query_id": "rq_01",
  "session_id": "sess_2026_03_21_001",
  "target_store": "pattern_library",
  "query_tags": ["dream pop", "wistful", "open voicings", "loopable"],
  "top_k": 5
}
```

---

## 7.4 RetrievalResult

```json
{
  "retrieval_result_id": "rr_01",
  "retrieval_query_id": "rq_01",
  "matched_entry_ids": ["pat_01", "pat_09"],
  "scores": [0.91, 0.84]
}
```

---

## 7.5 ProvenanceTrace

### Purpose

Stores the full explanation lineage of the session.

```json
{
  "provenance_trace_id": "trace_01",
  "session_id": "sess_2026_03_21_001",
  "events": [
    {
      "step": 1,
      "action": "creative_brief_normalized",
      "object_id": "brief_01"
    },
    {
      "step": 2,
      "action": "genre_profile_loaded",
      "object_id": "genre_dream_pop_01"
    },
    {
      "step": 3,
      "action": "progression_generated",
      "object_id": "prog_01"
    },
    {
      "step": 4,
      "action": "arrangement_mutated",
      "object_id": "arr_01b"
    }
  ]
}
```

---

# 8. Presentation and export objects

## 8.1 CandidateExplanation

### Purpose

Human-readable explanation of one result.

```json
{
  "candidate_explanation_id": "exp_01",
  "candidate_id": "arr_01b",
  "summary": "A floating dream-pop loop with a wistful borrowed iv and restrained bass motion.",
  "why_it_works": [
    "The borrowed iv adds melancholy without breaking tonal identity",
    "Open voicings preserve shimmer and air",
    "The simplified bass avoids over-directing the phrase"
  ],
  "what_is_experimental": [
    "Reduced dominant pull in favor of color continuity"
  ],
  "recommended_use_cases": [
    "intro loop",
    "verse bed",
    "ambient interlude"
  ]
}
```

---

## 8.2 ComparisonView

### Purpose

Represents a contrasted presentation set.

```json
{
  "comparison_view_id": "cmp_01",
  "session_id": "sess_2026_03_21_001",
  "candidate_ids": ["arr_01b", "arr_03", "arr_04"],
  "comparison_axes": [
    "genre_fit",
    "novelty",
    "bass_activity",
    "voicing_openness"
  ],
  "labels": {
    "arr_01b": "Safest",
    "arr_03": "Most Experimental Viable",
    "arr_04": "Best Loop"
  }
}
```

---

## 8.3 RenderArtifact

### Purpose

Represents an exported render or file.

```json
{
  "render_artifact_id": "render_01",
  "candidate_id": "arr_01b",
  "artifact_type": "midi",
  "path": "/artifacts/arr_01b.mid",
  "created_at": "2026-03-21T15:40:01Z",
  "metadata": {
    "tempo_bpm": 82,
    "meter": "4/4"
  }
}
```

---

## 8.4 ExportPackage

### Purpose

Groups outputs for downstream use.

```json
{
  "export_package_id": "export_01",
  "session_id": "sess_2026_03_21_001",
  "included_candidate_ids": ["arr_01b", "arr_03", "arr_04"],
  "included_artifact_ids": ["render_01", "render_02"],
  "formats": ["json", "midi", "musicxml"],
  "notes": [
    "Includes comparative explanations and scorecards"
  ]
}
```

---

# 9. Recommended inheritance / interface model

If you were implementing this in code, I would avoid deep inheritance trees. Prefer composition with a few shared interfaces.

## Shared base interface: `BaseEntity`

```json
{
  "id": "string",
  "created_at": "datetime",
  "updated_at": "datetime",
  "metadata": {}
}
```

## Shared interface: `Candidate`

For both progression and arrangement candidates:

```json
{
  "candidate_id": "string",
  "session_id": "string",
  "family_id": "string",
  "intent_tags": [],
  "rationale": "string",
  "mutation_lineage_ids": [],
  "status": "candidate|selected|rejected|archived"
}
```

## Shared interface: `Evaluation`

```json
{
  "evaluation_id": "string",
  "candidate_id": "string",
  "notes": []
}
```

This gives consistency without forcing unnatural class hierarchies.

---

# 10. Relationship summary

Here is the most important relationship map.

```text
CreativeBrief
  -> GenreProfile
  -> SearchPlan
  -> ProgressionCandidate*
       -> RomanNumeralAnalysis
       -> VoicingPlan*
       -> BassLine*
       -> MelodicComplement*
       -> InnerVoicePlan*
       -> GroovePattern*
       -> ArrangementCandidate*
            -> EvaluationBundle*
                 -> TheoryEvaluation
                 -> VoiceLeadingEvaluation
                 -> RegisterDensityEvaluation
                 -> PlayabilityEvaluation
                 -> GrooveEvaluation
                 -> AggregateScorecard
  -> FinalSelection
  -> ProvenanceTrace
```

---

# 11. Minimal canonical subset for MVP

If you wanted to avoid overbuilding the first version, the minimum useful object model is:

* `Session`
* `CreativeBrief`
* `GenreProfile`
* `ProgressionCandidate`
* `VoicingPlan`
* `BassLine`
* `ArrangementCandidate`
* `EvaluationBundle`
* `AggregateScorecard`
* `MutationRecord`
* `FinalSelection`
* `UserFeedbackEvent`

That is enough to support:

* structured intent
* harmonic generation
* arrangement realization
* evaluation
* refinement
* explainability

---

# 12. Practical implementation note

For storage, I would split the model into:

* **document-style objects** for session artifacts and candidates
* **relational or graph links** for lineage, family grouping, and provenance
* **vector retrieval** for pattern and style memory if you want similarity search over prior results and explanations

A strong practical mapping would be:

* Postgres or document DB for canonical entities
* graph edges for mutation/provenance/family relationships
* vector store for retrieval over descriptions, tags, and abstracted patterns

---

# 13. Compact canonical schema index

Here is the final index of canonical entities.

**Intent/session**

* `Session`
* `CreativeBrief`
* `UserPreferenceProfile`
* `SessionContext`

**Style/rules**

* `GenreProfile`
* `GenreRule`
* `AntiPattern`
* `HarmonicGrammar`

**Musical generation**

* `ProgressionCandidate`
* `ChordEvent`
* `RomanNumeralAnalysis`
* `ProgressionFamily`
* `VoicingPlan`
* `VoicingEvent`
* `BassLine`
* `BassNoteEvent`
* `Melody`
* `MelodicComplement`
* `InnerVoicePlan`
* `GroovePattern`
* `InstrumentRealizationPlan`
* `ArrangementCandidate`
* `ArrangementFamily`

**Evaluation/search**

* `EvaluationBundle`
* `TheoryEvaluation`
* `VoiceLeadingEvaluation`
* `RegisterDensityEvaluation`
* `PlayabilityEvaluation`
* `GrooveEvaluation`
* `MelodyHarmonyEvaluation`
* `AggregateScorecard`
* `ObjectiveWeights`
* `MutationRecord`
* `SearchPlan`
* `SearchRound`
* `ParetoFrontSnapshot`
* `FinalSelection`

**Memory/learning**

* `PatternLibraryEntry`
* `UserFeedbackEvent`
* `RetrievalQuery`
* `RetrievalResult`
* `ProvenanceTrace`

**Presentation/export**

* `CandidateExplanation`
* `ComparisonView`
* `RenderArtifact`
* `ExportPackage`
