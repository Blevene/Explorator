Neo4j/property-graph schema for the 

**Genre Chord Exploration and Realization System**.

I’ll structure it as:

1. Modeling approach
2. Node labels
3. Relationship types
4. Core subgraphs
5. Recommended properties by label
6. Example Cypher schema skeleton
7. Query patterns
8. Practical design notes

The key design choice is this:

* Use **nodes for durable semantic objects**
* Use **relationships for lineage, composition, evaluation, and provenance**
* Keep large musical event arrays either:

  * embedded as JSON-like properties when compact, or
  * exploded into event nodes when you need fine-grained querying

For this system, a **hybrid graph** is best.

---

# 1. Modeling approach

## Design principle

Use the graph for:

* session structure
* candidate lineage
* family grouping
* evaluation links
* style-rule inheritance
* retrieval and memory
* provenance and mutation tracking

Do **not** over-atomize too early. For example:

* `ProgressionCandidate` should be a node
* every individual pitch in every voicing does **not** need to be a node at MVP stage

A good rule:

* If you will query it as an entity, make it a node
* If it is mostly payload, keep it as properties
* If it participates in lineage or comparison, make it a node

---

# 2. Primary node labels

## Session / intent layer

* `Session`
* `CreativeBrief`
* `UserPreferenceProfile`
* `SessionContext`
* `SearchPlan`
* `SearchRound`
* `FinalSelection`

## Style / rule layer

* `GenreProfile`
* `HarmonicGrammar`
* `GenreRule`
* `AntiPattern`

## Musical generation layer

* `ProgressionCandidate`
* `ProgressionFamily`
* `RomanNumeralAnalysis`
* `ArrangementCandidate`
* `ArrangementFamily`
* `VoicingPlan`
* `BassLine`
* `MelodicComplement`
* `Melody`
* `InnerVoicePlan`
* `GroovePattern`
* `InstrumentRealizationPlan`

## Optional fine-grained music-event layer

Only if you need granular querying:

* `ChordEvent`
* `VoicingEvent`
* `BassNoteEvent`
* `MelodyNoteEvent`
* `PatternEvent`

## Evaluation / search layer

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
* `ParetoFrontSnapshot`

## Memory / explanation layer

* `PatternLibraryEntry`
* `UserFeedbackEvent`
* `RetrievalQuery`
* `RetrievalResult`
* `ProvenanceTrace`
* `CandidateExplanation`
* `ComparisonView`
* `RenderArtifact`
* `ExportPackage`

---

# 3. Relationship types

Here is the core relationship vocabulary.

## Session ownership

* `(:Session)-[:HAS_BRIEF]->(:CreativeBrief)`
* `(:Session)-[:HAS_CONTEXT]->(:SessionContext)`
* `(:Session)-[:USES_SEARCH_PLAN]->(:SearchPlan)`
* `(:Session)-[:USES_OBJECTIVE_WEIGHTS]->(:ObjectiveWeights)`
* `(:Session)-[:HAS_ROUND]->(:SearchRound)`
* `(:Session)-[:HAS_FINAL_SELECTION]->(:FinalSelection)`
* `(:Session)-[:HAS_PROVENANCE]->(:ProvenanceTrace)`
* `(:Session)-[:HAS_FEEDBACK]->(:UserFeedbackEvent)`

## Style associations

* `(:CreativeBrief)-[:TARGETS_GENRE]->(:GenreProfile)`
* `(:GenreProfile)-[:USES_GRAMMAR]->(:HarmonicGrammar)`
* `(:GenreProfile)-[:HAS_RULE]->(:GenreRule)`
* `(:GenreProfile)-[:HAS_ANTI_PATTERN]->(:AntiPattern)`

## Candidate generation

* `(:Session)-[:GENERATED_PROGRESSION]->(:ProgressionCandidate)`
* `(:Session)-[:GENERATED_ARRANGEMENT]->(:ArrangementCandidate)`
* `(:ProgressionFamily)-[:HAS_MEMBER]->(:ProgressionCandidate)`
* `(:ArrangementFamily)-[:HAS_MEMBER]->(:ArrangementCandidate)`
* `(:ProgressionFamily)-[:ROOT_MEMBER]->(:ProgressionCandidate)`
* `(:ArrangementFamily)-[:ROOT_MEMBER]->(:ArrangementCandidate)`

## Candidate composition

* `(:ProgressionCandidate)-[:HAS_ANALYSIS]->(:RomanNumeralAnalysis)`

* `(:ProgressionCandidate)-[:REALIZED_AS]->(:ArrangementCandidate)`

* `(:ArrangementCandidate)-[:USES_VOICING_PLAN]->(:VoicingPlan)`

* `(:ArrangementCandidate)-[:USES_BASS_LINE]->(:BassLine)`

* `(:ArrangementCandidate)-[:USES_MELODIC_COMPLEMENT]->(:MelodicComplement)`

* `(:ArrangementCandidate)-[:USES_MELODY]->(:Melody)`

* `(:ArrangementCandidate)-[:USES_INNER_VOICE_PLAN]->(:InnerVoicePlan)`

* `(:ArrangementCandidate)-[:USES_GROOVE_PATTERN]->(:GroovePattern)`

* `(:ArrangementCandidate)-[:USES_INSTRUMENT_REALIZATION]->(:InstrumentRealizationPlan)`

## Fine-grained musical event composition

Optional:

* `(:ProgressionCandidate)-[:HAS_CHORD_EVENT]->(:ChordEvent)`
* `(:VoicingPlan)-[:HAS_VOICING_EVENT]->(:VoicingEvent)`
* `(:BassLine)-[:HAS_BASS_NOTE]->(:BassNoteEvent)`
* `(:Melody)-[:HAS_NOTE]->(:MelodyNoteEvent)`
* `(:MelodicComplement)-[:HAS_NOTE]->(:MelodyNoteEvent)`
* `(:GroovePattern)-[:HAS_PATTERN_EVENT]->(:PatternEvent)`

And sequencing edges:

* `(:ChordEvent)-[:NEXT]->(:ChordEvent)`
* `(:VoicingEvent)-[:NEXT]->(:VoicingEvent)`
* `(:BassNoteEvent)-[:NEXT]->(:BassNoteEvent)`
* `(:MelodyNoteEvent)-[:NEXT]->(:MelodyNoteEvent)`

## Evaluation graph

* `(:ProgressionCandidate)-[:HAS_EVALUATION]->(:EvaluationBundle)`

* `(:ArrangementCandidate)-[:HAS_EVALUATION]->(:EvaluationBundle)`

* `(:EvaluationBundle)-[:HAS_THEORY_EVAL]->(:TheoryEvaluation)`

* `(:EvaluationBundle)-[:HAS_VOICE_LEADING_EVAL]->(:VoiceLeadingEvaluation)`

* `(:EvaluationBundle)-[:HAS_REGISTER_DENSITY_EVAL]->(:RegisterDensityEvaluation)`

* `(:EvaluationBundle)-[:HAS_PLAYABILITY_EVAL]->(:PlayabilityEvaluation)`

* `(:EvaluationBundle)-[:HAS_GROOVE_EVAL]->(:GrooveEvaluation)`

* `(:EvaluationBundle)-[:HAS_MELODY_HARMONY_EVAL]->(:MelodyHarmonyEvaluation)`

* `(:EvaluationBundle)-[:HAS_SCORECARD]->(:AggregateScorecard)`

## Lineage and mutation

* `(:MutationRecord)-[:SOURCE]->(:ProgressionCandidate|ArrangementCandidate)`
* `(:MutationRecord)-[:RESULT]->(:ProgressionCandidate|ArrangementCandidate)`
* `(:MutationRecord)-[:APPLIES_IN_ROUND]->(:SearchRound)`

Convenient direct lineage edges too:

* `(:ProgressionCandidate)-[:MUTATED_INTO]->(:ProgressionCandidate)`
* `(:ArrangementCandidate)-[:MUTATED_INTO]->(:ArrangementCandidate)`
* `(:ProgressionCandidate)-[:BELONGS_TO_FAMILY]->(:ProgressionFamily)`
* `(:ArrangementCandidate)-[:BELONGS_TO_FAMILY]->(:ArrangementFamily)`

## Search-round edges

* `(:SearchRound)-[:INPUT_CANDIDATE]->(:ProgressionCandidate|ArrangementCandidate)`
* `(:SearchRound)-[:GENERATED]->(:ProgressionCandidate|ArrangementCandidate)`
* `(:SearchRound)-[:SELECTED]->(:ProgressionCandidate|ArrangementCandidate)`
* `(:SearchRound)-[:ELIMINATED]->(:ProgressionCandidate|ArrangementCandidate)`

## Pareto / selection

* `(:ParetoFrontSnapshot)-[:INCLUDES]->(:ProgressionCandidate|ArrangementCandidate)`
* `(:FinalSelection)-[:SELECTS {role:'safest'}]->(:ArrangementCandidate)`
* `(:FinalSelection)-[:SELECTS {role:'best_loop'}]->(:ArrangementCandidate)`
* `(:FinalSelection)-[:SELECTS {role:'most_experimental_viable'}]->(:ArrangementCandidate)`

## Feedback / memory / retrieval

* `(:UserFeedbackEvent)-[:ABOUT]->(:ProgressionCandidate|ArrangementCandidate)`

* `(:UserFeedbackEvent)-[:UPDATES]->(:UserPreferenceProfile)`

* `(:PatternLibraryEntry)-[:ABSTRACTED_FROM]->(:ProgressionCandidate|ArrangementCandidate)`

* `(:RetrievalQuery)-[:SEARCHES]->(:PatternLibraryEntry)`

* `(:RetrievalResult)-[:RETURNS]->(:PatternLibraryEntry)`

* `(:Session)-[:HAS_RETRIEVAL_QUERY]->(:RetrievalQuery)`

* `(:Session)-[:HAS_RETRIEVAL_RESULT]->(:RetrievalResult)`

## Explanation / export

* `(:CandidateExplanation)-[:EXPLAINS]->(:ProgressionCandidate|ArrangementCandidate)`
* `(:ComparisonView)-[:COMPARES]->(:ArrangementCandidate)`
* `(:RenderArtifact)-[:RENDERS]->(:ArrangementCandidate)`
* `(:ExportPackage)-[:INCLUDES]->(:RenderArtifact)`
* `(:ExportPackage)-[:INCLUDES_CANDIDATE]->(:ArrangementCandidate)`

## Provenance

* `(:ProvenanceTrace)-[:TRACE_OF]->(:Session)`
* `(:ProvenanceTrace)-[:REFERENCES]->(:ProgressionCandidate|ArrangementCandidate|MutationRecord|EvaluationBundle|UserFeedbackEvent)`

---

# 4. Core subgraphs

## A. Session subgraph

```text
(Session)-[:HAS_BRIEF]->(CreativeBrief)
(Session)-[:HAS_CONTEXT]->(SessionContext)
(Session)-[:USES_SEARCH_PLAN]->(SearchPlan)
(Session)-[:USES_OBJECTIVE_WEIGHTS]->(ObjectiveWeights)
(Session)-[:HAS_ROUND]->(SearchRound)
(Session)-[:HAS_FINAL_SELECTION]->(FinalSelection)
(Session)-[:HAS_PROVENANCE]->(ProvenanceTrace)
```

## B. Genre/style subgraph

```text
(CreativeBrief)-[:TARGETS_GENRE]->(GenreProfile)
(GenreProfile)-[:USES_GRAMMAR]->(HarmonicGrammar)
(GenreProfile)-[:HAS_RULE]->(GenreRule)
(GenreProfile)-[:HAS_ANTI_PATTERN]->(AntiPattern)
```

## C. Harmonic generation subgraph

```text
(Session)-[:GENERATED_PROGRESSION]->(ProgressionCandidate)
(ProgressionFamily)-[:HAS_MEMBER]->(ProgressionCandidate)
(ProgressionCandidate)-[:HAS_ANALYSIS]->(RomanNumeralAnalysis)
(ProgressionCandidate)-[:REALIZED_AS]->(ArrangementCandidate)
```

## D. Realization subgraph

```text
(ArrangementCandidate)-[:USES_VOICING_PLAN]->(VoicingPlan)
(ArrangementCandidate)-[:USES_BASS_LINE]->(BassLine)
(ArrangementCandidate)-[:USES_MELODIC_COMPLEMENT]->(MelodicComplement)
(ArrangementCandidate)-[:USES_INNER_VOICE_PLAN]->(InnerVoicePlan)
(ArrangementCandidate)-[:USES_GROOVE_PATTERN]->(GroovePattern)
(ArrangementCandidate)-[:USES_INSTRUMENT_REALIZATION]->(InstrumentRealizationPlan)
```

## E. Evaluation subgraph

```text
(ArrangementCandidate)-[:HAS_EVALUATION]->(EvaluationBundle)
(EvaluationBundle)-[:HAS_THEORY_EVAL]->(TheoryEvaluation)
(EvaluationBundle)-[:HAS_VOICE_LEADING_EVAL]->(VoiceLeadingEvaluation)
(EvaluationBundle)-[:HAS_SCORECARD]->(AggregateScorecard)
```

## F. Mutation / lineage subgraph

```text
(ArrangementCandidate)-[:MUTATED_INTO]->(ArrangementCandidate)
(MutationRecord)-[:SOURCE]->(ArrangementCandidate)
(MutationRecord)-[:RESULT]->(ArrangementCandidate)
(MutationRecord)-[:APPLIES_IN_ROUND]->(SearchRound)
```

## G. Memory / feedback subgraph

```text
(UserFeedbackEvent)-[:ABOUT]->(ArrangementCandidate)
(UserFeedbackEvent)-[:UPDATES]->(UserPreferenceProfile)
(PatternLibraryEntry)-[:ABSTRACTED_FROM]->(ArrangementCandidate)
```

---

# 5. Recommended properties by label

Below are the most useful graph properties.

## `Session`

```text
session_id, created_at, updated_at, status, mode
```

## `CreativeBrief`

```text
creative_brief_id, genre, subgenre, key_center, mode, meter,
tempo_hint_bpm, phrase_length_bars, complexity_target,
novelty_target, form_hint, mood_targets, instrumentation_targets
```

For arrays like `mood_targets`, `instrumentation_targets`, Neo4j list properties are fine.

## `UserPreferenceProfile`

```text
user_preference_profile_id, preferred_complexity_band,
preferred_novelty_band, voicing_preferences_json,
bass_preferences_json, melodic_preferences_json,
genre_biases_json, disliked_patterns
```

## `GenreProfile`

```text
genre_profile_id, genre, subgenre, harmonic_vocabulary,
common_devices, experimentation_envelope_json,
harmonic_tendencies_json, voicing_tendencies_json,
bass_tendencies_json, groove_tendencies_json
```

## `GenreRule`

```text
genre_rule_id, genre, rule_type, name, description,
weight, anti_rule, applicability_conditions_json
```

## `AntiPattern`

```text
anti_pattern_id, genre, scope, name, description, severity
```

## `HarmonicGrammar`

```text
harmonic_grammar_id, preferred_chord_qualities,
allowed_borrowed_chords, cadence_archetypes,
harmonic_rhythm_defaults_json, functional_motion_bias_json
```

## `ProgressionCandidate`

```text
progression_candidate_id, key_center, mode, phrase_length_bars,
generator_mode, rationale, source_type, status, intent_tags,
chord_events_json
```

Store `chord_events_json` unless you need event nodes.

## `RomanNumeralAnalysis`

```text
roman_numeral_analysis_id, analysis_events_json, analysis_notes
```

## `ArrangementCandidate`

```text
arrangement_candidate_id, rationale, status, intent_tags,
render_status, complexity_estimate, novelty_estimate
```

## `VoicingPlan`

```text
voicing_plan_id, instrument, global_strategy, density_level,
register_profile, voicing_events_json
```

## `BassLine`

```text
bass_line_id, style_mode, contour_type, rhythmic_density,
relationship_to_harmony, note_events_json
```

## `MelodicComplement`

```text
melodic_complement_id, style_mode, register_profile,
density_level, motivic_description, note_events_json
```

## `Melody`

```text
melody_id, source_type, range_low, range_high, note_events_json
```

## `InnerVoicePlan`

```text
inner_voice_plan_id, strategy, voice_paths_json, notes
```

## `GroovePattern`

```text
groove_pattern_id, meter, style_mode, syncopation_level,
density_level, pattern_events_json
```

## `InstrumentRealizationPlan`

```text
instrument_realization_plan_id, orchestration_notes,
instrument_roles_json
```

## `EvaluationBundle`

```text
evaluation_bundle_id, candidate_type, created_at
```

## `TheoryEvaluation`

```text
theory_evaluation_id, genre_fit, emotional_fit,
theoretical_coherence, cadence_quality, novelty, notes
```

## `VoiceLeadingEvaluation`

```text
voice_leading_evaluation_id, smoothness_score,
common_tone_retention_score, awkward_leap_penalty,
resolution_quality, notes
```

## `RegisterDensityEvaluation`

```text
register_density_evaluation_id, register_balance_score,
mud_risk_score, overcrowding_risk_score,
spacing_quality, notes
```

## `PlayabilityEvaluation`

```text
playability_evaluation_id, piano_playability,
guitar_playability, ensemble_playability,
simplification_recommendations
```

## `GrooveEvaluation`

```text
groove_evaluation_id, groove_authenticity,
rhythmic_coherence, style_alignment, notes
```

## `MelodyHarmonyEvaluation`

```text
melody_harmony_evaluation_id, melody_support_score,
tension_justification_score, collision_risk_score, notes
```

## `AggregateScorecard`

```text
aggregate_scorecard_id, weighted_total, rank_within_round,
pareto_tags, scores_json
```

## `ObjectiveWeights`

```text
objective_weights_id, profile_name, weights_json
```

## `MutationRecord`

```text
mutation_record_id, mutation_scope, reason,
predicted_effects, actual_score_delta_json, changes_json
```

## `SearchPlan`

```text
search_plan_id, search_strategy, initial_generation_count,
progression_selection_count, arrangement_selection_count,
max_rounds, mutation_budget_per_round, diversity_target,
stop_conditions_json
```

## `SearchRound`

```text
search_round_id, round_number, notes
```

## `ParetoFrontSnapshot`

```text
pareto_front_snapshot_id, round_number, axes
```

## `FinalSelection`

```text
final_selection_id, selection_notes
```

## `PatternLibraryEntry`

```text
pattern_library_entry_id, pattern_type, genre, tags,
abstracted_pattern_json, success_metrics_json, notes
```

## `UserFeedbackEvent`

```text
feedback_event_id, feedback_type, content,
interpreted_adjustments_json, timestamp
```

## `RetrievalQuery`

```text
retrieval_query_id, target_store, query_tags, top_k
```

## `RetrievalResult`

```text
retrieval_result_id, scores
```

## `ProvenanceTrace`

```text
provenance_trace_id, events_json
```

## `CandidateExplanation`

```text
candidate_explanation_id, summary, why_it_works,
what_is_experimental, recommended_use_cases
```

## `ComparisonView`

```text
comparison_view_id, comparison_axes, labels_json
```

## `RenderArtifact`

```text
render_artifact_id, artifact_type, path, created_at, metadata_json
```

## `ExportPackage`

```text
export_package_id, formats, notes
```

---

# 6. Suggested graph pattern: hybrid event modeling

There are two viable approaches.

## Option A: compact hybrid, recommended for MVP

Keep these as properties:

* chord event arrays
* voicing arrays
* bass note arrays
* melody note arrays
* groove pattern arrays

Make only higher-level objects nodes.

This keeps the graph readable and performant.

## Option B: fully exploded event graph, only if needed

Make `ChordEvent`, `VoicingEvent`, `BassNoteEvent`, `MelodyNoteEvent` nodes when you want queries like:

* find all arrangements where bass approaches borrowed iv by semitone
* find all voicing events with top voice held across 3 consecutive chord changes
* find patterns where altered dominant resolves by contrary motion in inner voices

That is powerful, but heavier.

My recommendation:

* Start with Option A
* Promote specific event types to nodes only when query pressure justifies it

---

# 7. Example graph sketch

```text
(:Session {session_id:'sess_01'})
  -[:HAS_BRIEF]->
(:CreativeBrief {genre:'dream pop', key_center:'A'})

(:CreativeBrief)-[:TARGETS_GENRE]->
(:GenreProfile {genre:'dream pop'})

(:GenreProfile)-[:HAS_RULE]->
(:GenreRule {name:'Prefer open voicings'})

(:Session)-[:GENERATED_PROGRESSION]->
(:ProgressionCandidate {progression_candidate_id:'prog_01'})

(:ProgressionCandidate)-[:HAS_ANALYSIS]->
(:RomanNumeralAnalysis {roman_numerals:['Imaj7','iii7','IVmaj9','ivm6']})

(:ProgressionCandidate)-[:REALIZED_AS]->
(:ArrangementCandidate {arrangement_candidate_id:'arr_01'})

(:ArrangementCandidate)-[:USES_VOICING_PLAN]->
(:VoicingPlan {global_strategy:'open mid-high spacing'})

(:ArrangementCandidate)-[:USES_BASS_LINE]->
(:BassLine {style_mode:'supportive_pedal_mix'})

(:ArrangementCandidate)-[:HAS_EVALUATION]->
(:EvaluationBundle)

(:EvaluationBundle)-[:HAS_SCORECARD]->
(:AggregateScorecard {weighted_total:8.19})

(:ArrangementCandidate)-[:MUTATED_INTO]->
(:ArrangementCandidate {arrangement_candidate_id:'arr_01b'})

(:MutationRecord)-[:SOURCE]->
(:ArrangementCandidate {arrangement_candidate_id:'arr_01'})

(:MutationRecord)-[:RESULT]->
(:ArrangementCandidate {arrangement_candidate_id:'arr_01b'})
```

---

# 8. Neo4j schema skeleton in Cypher

Here is a practical starting schema.

```cypher
// ---------- Constraints ----------
CREATE CONSTRAINT session_id IF NOT EXISTS
FOR (n:Session) REQUIRE n.session_id IS UNIQUE;

CREATE CONSTRAINT creative_brief_id IF NOT EXISTS
FOR (n:CreativeBrief) REQUIRE n.creative_brief_id IS UNIQUE;

CREATE CONSTRAINT genre_profile_id IF NOT EXISTS
FOR (n:GenreProfile) REQUIRE n.genre_profile_id IS UNIQUE;

CREATE CONSTRAINT progression_candidate_id IF NOT EXISTS
FOR (n:ProgressionCandidate) REQUIRE n.progression_candidate_id IS UNIQUE;

CREATE CONSTRAINT arrangement_candidate_id IF NOT EXISTS
FOR (n:ArrangementCandidate) REQUIRE n.arrangement_candidate_id IS UNIQUE;

CREATE CONSTRAINT progression_family_id IF NOT EXISTS
FOR (n:ProgressionFamily) REQUIRE n.progression_family_id IS UNIQUE;

CREATE CONSTRAINT arrangement_family_id IF NOT EXISTS
FOR (n:ArrangementFamily) REQUIRE n.arrangement_family_id IS UNIQUE;

CREATE CONSTRAINT evaluation_bundle_id IF NOT EXISTS
FOR (n:EvaluationBundle) REQUIRE n.evaluation_bundle_id IS UNIQUE;

CREATE CONSTRAINT aggregate_scorecard_id IF NOT EXISTS
FOR (n:AggregateScorecard) REQUIRE n.aggregate_scorecard_id IS UNIQUE;

CREATE CONSTRAINT mutation_record_id IF NOT EXISTS
FOR (n:MutationRecord) REQUIRE n.mutation_record_id IS UNIQUE;

CREATE CONSTRAINT search_plan_id IF NOT EXISTS
FOR (n:SearchPlan) REQUIRE n.search_plan_id IS UNIQUE;

CREATE CONSTRAINT search_round_id IF NOT EXISTS
FOR (n:SearchRound) REQUIRE n.search_round_id IS UNIQUE;

CREATE CONSTRAINT final_selection_id IF NOT EXISTS
FOR (n:FinalSelection) REQUIRE n.final_selection_id IS UNIQUE;

CREATE CONSTRAINT pattern_library_entry_id IF NOT EXISTS
FOR (n:PatternLibraryEntry) REQUIRE n.pattern_library_entry_id IS UNIQUE;

CREATE CONSTRAINT feedback_event_id IF NOT EXISTS
FOR (n:UserFeedbackEvent) REQUIRE n.feedback_event_id IS UNIQUE;

CREATE CONSTRAINT render_artifact_id IF NOT EXISTS
FOR (n:RenderArtifact) REQUIRE n.render_artifact_id IS UNIQUE;
```

### Useful indexes

```cypher
CREATE INDEX genre_profile_genre IF NOT EXISTS
FOR (n:GenreProfile) ON (n.genre);

CREATE INDEX progression_candidate_status IF NOT EXISTS
FOR (n:ProgressionCandidate) ON (n.status);

CREATE INDEX arrangement_candidate_status IF NOT EXISTS
FOR (n:ArrangementCandidate) ON (n.status);

CREATE INDEX pattern_library_genre IF NOT EXISTS
FOR (n:PatternLibraryEntry) ON (n.genre);

CREATE INDEX scorecard_weighted_total IF NOT EXISTS
FOR (n:AggregateScorecard) ON (n.weighted_total);
```

---

# 9. Example node and edge creation

```cypher
MERGE (s:Session {session_id:'sess_01'})
SET s.status = 'active',
    s.mode = 'full_exploration',
    s.created_at = datetime()

MERGE (b:CreativeBrief {creative_brief_id:'brief_01'})
SET b.genre = 'dream pop',
    b.key_center = 'A',
    b.mode = 'major',
    b.phrase_length_bars = 8,
    b.complexity_target = 'medium',
    b.novelty_target = 'moderate',
    b.mood_targets = ['wistful','haunted'],
    b.instrumentation_targets = ['electric piano','pad','bass']

MERGE (g:GenreProfile {genre_profile_id:'genre_dream_pop_01'})
SET g.genre = 'dream pop',
    g.harmonic_vocabulary = ['maj7','add9','sus2','borrowed_iv','modal_mixture'],
    g.common_devices = ['borrowed minor iv','slow harmonic rhythm','shimmering add9 voicings']

MERGE (s)-[:HAS_BRIEF]->(b)
MERGE (b)-[:TARGETS_GENRE]->(g);
```

```cypher
MERGE (p:ProgressionCandidate {progression_candidate_id:'prog_01'})
SET p.key_center = 'A',
    p.mode = 'major',
    p.phrase_length_bars = 8,
    p.generator_mode = 'balanced',
    p.intent_tags = ['wistful','loopable','borrowed_color'],
    p.status = 'candidate',
    p.chord_events_json = [
      {bar:1, beat:1.0, duration_beats:4.0, symbol:'Amaj7'},
      {bar:2, beat:1.0, duration_beats:4.0, symbol:'C#m7'},
      {bar:3, beat:1.0, duration_beats:4.0, symbol:'Dmaj9'},
      {bar:4, beat:1.0, duration_beats:4.0, symbol:'Dm6'}
    ]

MERGE (rna:RomanNumeralAnalysis {roman_numeral_analysis_id:'rna_01'})
SET rna.analysis_events_json = [
      {bar:1, symbol:'Imaj7', confidence:0.98},
      {bar:2, symbol:'iii7', confidence:0.92},
      {bar:3, symbol:'IVmaj9', confidence:0.95},
      {bar:4, symbol:'ivm6', confidence:0.90}
    ]

MERGE (s:Session {session_id:'sess_01'})
MERGE (s)-[:GENERATED_PROGRESSION]->(p)
MERGE (p)-[:HAS_ANALYSIS]->(rna);
```

```cypher
MERGE (a:ArrangementCandidate {arrangement_candidate_id:'arr_01'})
SET a.status = 'candidate',
    a.intent_tags = ['wistful','floating','loopable'],
    a.rationale = 'Preserves harmonic simplicity while adding shimmer and motion'

MERGE (vp:VoicingPlan {voicing_plan_id:'vp_01'})
SET vp.instrument = 'electric_piano',
    vp.global_strategy = 'open mid-high spacing with top voice continuity',
    vp.density_level = 'medium',
    vp.register_profile = 'mid_high'

MERGE (bl:BassLine {bass_line_id:'bass_01'})
SET bl.style_mode = 'supportive_pedal_mix',
    bl.contour_type = 'mostly_stepwise',
    bl.rhythmic_density = 'low',
    bl.relationship_to_harmony = 'stabilizing'

MERGE (p:ProgressionCandidate {progression_candidate_id:'prog_01'})
MERGE (p)-[:REALIZED_AS]->(a)
MERGE (a)-[:USES_VOICING_PLAN]->(vp)
MERGE (a)-[:USES_BASS_LINE]->(bl);
```

```cypher
MERGE (eb:EvaluationBundle {evaluation_bundle_id:'eval_01'})
MERGE (sc:AggregateScorecard {aggregate_scorecard_id:'score_01'})
SET sc.weighted_total = 8.19,
    sc.rank_within_round = 2,
    sc.pareto_tags = ['high_genre_fit','high_loopability'],
    sc.scores_json = {
      genre_fit: 8.8,
      emotional_fit: 8.5,
      theoretical_coherence: 8.9,
      loopability: 8.7,
      voicing_quality: 8.6
    }

MERGE (te:TheoryEvaluation {theory_evaluation_id:'theory_01'})
SET te.genre_fit = 8.8,
    te.emotional_fit = 8.5,
    te.theoretical_coherence = 8.9,
    te.cadence_quality = 7.9,
    te.novelty = 6.8

MERGE (a:ArrangementCandidate {arrangement_candidate_id:'arr_01'})
MERGE (a)-[:HAS_EVALUATION]->(eb)
MERGE (eb)-[:HAS_THEORY_EVAL]->(te)
MERGE (eb)-[:HAS_SCORECARD]->(sc);
```

---

# 10. Query patterns you will actually want

## Find best arrangement candidates for a session

```cypher
MATCH (:Session {session_id:'sess_01'})-[:GENERATED_ARRANGEMENT]->(a:ArrangementCandidate)
MATCH (a)-[:HAS_EVALUATION]->(:EvaluationBundle)-[:HAS_SCORECARD]->(s:AggregateScorecard)
RETURN a.arrangement_candidate_id, s.weighted_total, s.scores_json
ORDER BY s.weighted_total DESC
LIMIT 10;
```

## Find all mutations descending from one arrangement

```cypher
MATCH path = (a:ArrangementCandidate {arrangement_candidate_id:'arr_01'})-[:MUTATED_INTO*]->(desc)
RETURN path;
```

## Find dream-pop patterns with borrowed iv and strong user scores

```cypher
MATCH (p:PatternLibraryEntry {genre:'dream pop'})
WHERE 'borrowed_iv' IN p.tags
  AND p.success_metrics_json.user_rating >= 8.5
RETURN p.pattern_library_entry_id, p.abstracted_pattern_json, p.success_metrics_json;
```

## Find candidates criticized for overcrowding

```cypher
MATCH (a:ArrangementCandidate)-[:HAS_EVALUATION]->(:EvaluationBundle)-[:HAS_REGISTER_DENSITY_EVAL]->(r:RegisterDensityEvaluation)
WHERE r.overcrowding_risk_score > 6.0
RETURN a.arrangement_candidate_id, r.overcrowding_risk_score, r.notes
ORDER BY r.overcrowding_risk_score DESC;
```

## Retrieve all user feedback affecting bass motion

```cypher
MATCH (f:UserFeedbackEvent)-[:ABOUT]->(a:ArrangementCandidate)
WHERE f.interpreted_adjustments_json.reduce_bass_motion = true
RETURN f.feedback_event_id, a.arrangement_candidate_id, f.content, f.timestamp
ORDER BY f.timestamp DESC;
```

## Compare finalists with their explanations

```cypher
MATCH (:Session {session_id:'sess_01'})-[:HAS_FINAL_SELECTION]->(fs:FinalSelection)-[sel:SELECTS]->(a:ArrangementCandidate)
OPTIONAL MATCH (e:CandidateExplanation)-[:EXPLAINS]->(a)
RETURN sel.role, a.arrangement_candidate_id, e.summary
ORDER BY sel.role;
```

---

# 11. Recommended node categories for Neo4j labels

For clarity, you may want multi-label nodes.

Examples:

* `(:ArrangementCandidate:Candidate)`
* `(:ProgressionCandidate:Candidate)`
* `(:TheoryEvaluation:Evaluation)`
* `(:VoiceLeadingEvaluation:Evaluation)`
* `(:GenreRule:Rule)`
* `(:AntiPattern:Rule)`

This lets you do broader queries:

```cypher
MATCH (c:Candidate) RETURN count(c);
MATCH (e:Evaluation) RETURN labels(e), count(e);
```

A useful multi-label pattern:

* `Session`, `Intent`, `Style`, `Candidate`, `Evaluation`, `Memory`, `Export`, `Rule`

Examples:

* `(:CreativeBrief:Intent)`
* `(:GenreProfile:Style)`
* `(:PatternLibraryEntry:Memory)`
* `(:RenderArtifact:Export)`

---

# 12. Relationship properties worth using

Some relationships should carry properties.

## `SELECTS`

```text
role: 'safest' | 'best_loop' | 'most_experimental_viable'
```

## `MUTATED_INTO`

```text
scope, round_number, reason
```

## `HAS_MEMBER`

```text
position, is_root
```

## `REALIZED_AS`

```text
realization_mode, instrument_focus
```

## `ABOUT`

```text
feedback_strength, sentiment
```

## `COMPARES`

```text
label, display_order
```

---

# 13. What should be nodes vs properties

## Definitely nodes

* sessions
* briefs
* genre profiles
* rules
* candidates
* evaluations
* mutation records
* families
* feedback
* pattern library entries
* exports

## Usually properties

* chord event arrays
* voicing arrays
* melody note arrays
* groove event arrays
* orchestration notes
* score maps
* adjustment maps

## Promote to nodes later if needed

* individual chord events
* individual notes
* individual voicing events
* phrase sections
* reusable motif fragments

---

# 14. Recommended MVP graph schema

For a first real Neo4j implementation, I would keep just these labels:

* `Session`
* `CreativeBrief`
* `GenreProfile`
* `GenreRule`
* `ProgressionCandidate`
* `ProgressionFamily`
* `ArrangementCandidate`
* `ArrangementFamily`
* `VoicingPlan`
* `BassLine`
* `MelodicComplement`
* `GroovePattern`
* `EvaluationBundle`
* `TheoryEvaluation`
* `VoiceLeadingEvaluation`
* `AggregateScorecard`
* `MutationRecord`
* `SearchRound`
* `FinalSelection`
* `PatternLibraryEntry`
* `UserFeedbackEvent`
* `CandidateExplanation`
* `RenderArtifact`

That is enough to support:

* search
* ranking
* lineage
* memory
* explainability

without making the graph unwieldy.

---

# 15. Compact canonical property-graph schema

Here is the concise version.

```text
(Session)-[:HAS_BRIEF]->(CreativeBrief)-[:TARGETS_GENRE]->(GenreProfile)
(GenreProfile)-[:HAS_RULE]->(GenreRule)
(GenreProfile)-[:HAS_ANTI_PATTERN]->(AntiPattern)
(GenreProfile)-[:USES_GRAMMAR]->(HarmonicGrammar)

(Session)-[:GENERATED_PROGRESSION]->(ProgressionCandidate)
(ProgressionCandidate)-[:BELONGS_TO_FAMILY]->(ProgressionFamily)
(ProgressionCandidate)-[:HAS_ANALYSIS]->(RomanNumeralAnalysis)
(ProgressionCandidate)-[:REALIZED_AS]->(ArrangementCandidate)

(ArrangementCandidate)-[:BELONGS_TO_FAMILY]->(ArrangementFamily)
(ArrangementCandidate)-[:USES_VOICING_PLAN]->(VoicingPlan)
(ArrangementCandidate)-[:USES_BASS_LINE]->(BassLine)
(ArrangementCandidate)-[:USES_MELODIC_COMPLEMENT]->(MelodicComplement)
(ArrangementCandidate)-[:USES_MELODY]->(Melody)
(ArrangementCandidate)-[:USES_INNER_VOICE_PLAN]->(InnerVoicePlan)
(ArrangementCandidate)-[:USES_GROOVE_PATTERN]->(GroovePattern)
(ArrangementCandidate)-[:USES_INSTRUMENT_REALIZATION]->(InstrumentRealizationPlan)

(ProgressionCandidate)-[:HAS_EVALUATION]->(EvaluationBundle)
(ArrangementCandidate)-[:HAS_EVALUATION]->(EvaluationBundle)
(EvaluationBundle)-[:HAS_THEORY_EVAL]->(TheoryEvaluation)
(EvaluationBundle)-[:HAS_VOICE_LEADING_EVAL]->(VoiceLeadingEvaluation)
(EvaluationBundle)-[:HAS_REGISTER_DENSITY_EVAL]->(RegisterDensityEvaluation)
(EvaluationBundle)-[:HAS_PLAYABILITY_EVAL]->(PlayabilityEvaluation)
(EvaluationBundle)-[:HAS_GROOVE_EVAL]->(GrooveEvaluation)
(EvaluationBundle)-[:HAS_MELODY_HARMONY_EVAL]->(MelodyHarmonyEvaluation)
(EvaluationBundle)-[:HAS_SCORECARD]->(AggregateScorecard)

(ArrangementCandidate)-[:MUTATED_INTO]->(ArrangementCandidate)
(ProgressionCandidate)-[:MUTATED_INTO]->(ProgressionCandidate)
(MutationRecord)-[:SOURCE]->(ArrangementCandidate|ProgressionCandidate)
(MutationRecord)-[:RESULT]->(ArrangementCandidate|ProgressionCandidate)

(Session)-[:HAS_ROUND]->(SearchRound)
(SearchRound)-[:INPUT_CANDIDATE]->(ArrangementCandidate|ProgressionCandidate)
(SearchRound)-[:GENERATED]->(ArrangementCandidate|ProgressionCandidate)
(SearchRound)-[:SELECTED]->(ArrangementCandidate|ProgressionCandidate)
(SearchRound)-[:ELIMINATED]->(ArrangementCandidate|ProgressionCandidate)

(Session)-[:HAS_FINAL_SELECTION]->(FinalSelection)
(FinalSelection)-[:SELECTS]->(ArrangementCandidate)

(UserFeedbackEvent)-[:ABOUT]->(ArrangementCandidate|ProgressionCandidate)
(UserFeedbackEvent)-[:UPDATES]->(UserPreferenceProfile)

(PatternLibraryEntry)-[:ABSTRACTED_FROM]->(ArrangementCandidate|ProgressionCandidate)

(CandidateExplanation)-[:EXPLAINS]->(ArrangementCandidate|ProgressionCandidate)
(RenderArtifact)-[:RENDERS]->(ArrangementCandidate)
(ExportPackage)-[:INCLUDES]->(RenderArtifact)
(ExportPackage)-[:INCLUDES_CANDIDATE]->(ArrangementCandidate)
```

If you want, the next best step is to turn this into a **Neo4j DDL + seed Cypher file**, or a **Mermaid/Graphviz ER-style diagram** for documentation.
