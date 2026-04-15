"""Neo4j schema constraints, indexes, and initialization."""

from neo4j import AsyncDriver

CONSTRAINTS = [
    "CREATE CONSTRAINT session_id IF NOT EXISTS FOR (n:Session) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT session_context_id IF NOT EXISTS"
    " FOR (n:SessionContext) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT creative_brief_id IF NOT EXISTS"
    " FOR (n:CreativeBrief) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT genre_profile_id IF NOT EXISTS"
    " FOR (n:GenreProfile) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT genre_rule_id IF NOT EXISTS FOR (n:GenreRule) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT anti_pattern_id IF NOT EXISTS"
    " FOR (n:AntiPattern) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT harmonic_grammar_id IF NOT EXISTS"
    " FOR (n:HarmonicGrammar) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT search_plan_id IF NOT EXISTS FOR (n:SearchPlan) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT objective_weights_id IF NOT EXISTS"
    " FOR (n:ObjectiveWeights) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT user_preference_profile_id IF NOT EXISTS"
    " FOR (n:UserPreferenceProfile) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT progression_candidate_id IF NOT EXISTS"
    " FOR (n:ProgressionCandidate) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT progression_family_id IF NOT EXISTS"
    " FOR (n:ProgressionFamily) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT roman_numeral_analysis_id IF NOT EXISTS"
    " FOR (n:RomanNumeralAnalysis) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT arrangement_candidate_id IF NOT EXISTS"
    " FOR (n:ArrangementCandidate) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT arrangement_family_id IF NOT EXISTS"
    " FOR (n:ArrangementFamily) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT voicing_plan_id IF NOT EXISTS"
    " FOR (n:VoicingPlan) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT bass_line_id IF NOT EXISTS FOR (n:BassLine) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT groove_pattern_id IF NOT EXISTS FOR (n:GroovePattern) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT evaluation_bundle_id IF NOT EXISTS"
    " FOR (n:EvaluationBundle) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT evaluation_id IF NOT EXISTS FOR (n:Evaluation) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT aggregate_scorecard_id IF NOT EXISTS"
    " FOR (n:AggregateScorecard) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT search_round_id IF NOT EXISTS"
    " FOR (n:SearchRound) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT mutation_record_id IF NOT EXISTS"
    " FOR (n:MutationRecord) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT pareto_front_snapshot_id IF NOT EXISTS"
    " FOR (n:ParetoFrontSnapshot) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT final_selection_id IF NOT EXISTS"
    " FOR (n:FinalSelection) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT user_feedback_event_id IF NOT EXISTS"
    " FOR (n:UserFeedbackEvent) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT candidate_explanation_id IF NOT EXISTS"
    " FOR (n:CandidateExplanation) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT comparison_view_id IF NOT EXISTS"
    " FOR (n:ComparisonView) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT render_artifact_id IF NOT EXISTS"
    " FOR (n:RenderArtifact) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT export_package_id IF NOT EXISTS"
    " FOR (n:ExportPackage) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT provenance_trace_id IF NOT EXISTS"
    " FOR (n:ProvenanceTrace) REQUIRE n.id IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX genre_profile_genre IF NOT EXISTS FOR (n:GenreProfile) ON (n.genre)",
    "CREATE INDEX candidate_status IF NOT EXISTS FOR (n:Candidate) ON (n.status)",
    "CREATE INDEX scorecard_weighted_total IF NOT EXISTS"
    " FOR (n:AggregateScorecard) ON (n.weighted_total)",
    "CREATE INDEX pattern_library_genre IF NOT EXISTS"
    " FOR (n:PatternLibraryEntry) ON (n.genre)",
]


async def init_schema(driver: AsyncDriver) -> None:
    """Create all constraints and indexes."""
    async with driver.session() as session:
        for constraint in CONSTRAINTS:
            await session.run(constraint)
        for index in INDEXES:
            await session.run(index)
