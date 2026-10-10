"""Backend selection. driver is None ⇒ memory/null repo; else Neo4j repo.

This is the single branch point for the whole decoupling. Add a make_* here for
every repo a node/route needs; never branch on driver elsewhere.

Each ``make_*`` returns a union of the two concrete classes it can construct.
Both members share the methods callers use, so the unions keep mypy --strict
happy without casts. Concrete classes are imported under ``TYPE_CHECKING`` for
the annotations and lazily inside each function body to avoid heavy/circular
imports at module load.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from explorator.persistence.memory_store import get_memory_store

if TYPE_CHECKING:
    from neo4j import AsyncDriver

    from explorator.graph.arrangement_candidate_repo import ArrangementCandidateRepo
    from explorator.graph.arrangement_family_repo import ArrangementFamilyRepo
    from explorator.graph.bass_line_repo import BassLineRepo
    from explorator.graph.candidate_explanation_repo import CandidateExplanationRepo
    from explorator.graph.comparison_view_repo import ComparisonViewRepo
    from explorator.graph.creative_brief_repo import CreativeBriefRepo
    from explorator.graph.export_package_repo import ExportPackageRepo
    from explorator.graph.feedback_repo import FeedbackEventRepo, ObjectiveWeightsRepo
    from explorator.graph.genre_research_repo import GenreResearchRepository
    from explorator.graph.groove_pattern_repo import GroovePatternRepo
    from explorator.graph.melodic_complement_repo import MelodicComplementRepo
    from explorator.graph.mutation_record_repo import MutationRecordRepo
    from explorator.graph.pattern_library_repo import PatternLibraryRepo
    from explorator.graph.provenance_trace_repo import ProvenanceTraceRepo
    from explorator.graph.render_artifact_repo import RenderArtifactRepo
    from explorator.graph.repository import ProgressionCandidateRepo
    from explorator.graph.scorecard_repo import ScorecardRepo
    from explorator.graph.search_round_repo import SearchRoundRepo
    from explorator.graph.session_repo import SessionRepository
    from explorator.graph.style_repo import StyleRepository
    from explorator.graph.voicing_plan_repo import VoicingPlanRepo
    from explorator.persistence.memory_repos import (
        MemoryArrangementCandidateRepo,
        MemoryArrangementFamilyRepo,
        MemoryBassLineRepo,
        MemoryCandidateExplanationRepo,
        MemoryCandidateRepo,
        MemoryCreativeBriefRepo,
        MemoryExportPackageRepo,
        MemoryGroovePatternRepo,
        MemoryMelodicComplementRepo,
        MemoryMutationRecordRepo,
        MemoryRenderArtifactRepo,
        MemoryScorecardRepo,
        MemorySearchRoundRepo,
        MemorySessionRepo,
        MemoryStyleRepo,
        MemoryVoicingPlanRepo,
    )
    from explorator.persistence.null_repos import (
        NullComparisonViewRepo,
        NullFeedbackEventRepo,
        NullGenreResearchRepo,
        NullObjectiveWeightsRepo,
        NullPatternLibraryRepo,
        NullProvenanceTraceRepo,
    )


# ---------------------------------------------------------------------------
# Generation-path repos: memory repo (real behaviour) when driver is None.
# ---------------------------------------------------------------------------


def make_session_repo(
    driver: AsyncDriver | None,
) -> SessionRepository | MemorySessionRepo:
    if driver is None:
        from explorator.persistence.memory_repos import MemorySessionRepo

        return MemorySessionRepo(get_memory_store())
    from explorator.graph.session_repo import SessionRepository

    return SessionRepository(driver)


def make_candidate_repo(
    driver: AsyncDriver | None,
) -> ProgressionCandidateRepo | MemoryCandidateRepo:
    if driver is None:
        from explorator.persistence.memory_repos import MemoryCandidateRepo

        return MemoryCandidateRepo(get_memory_store())
    from explorator.graph.repository import ProgressionCandidateRepo

    return ProgressionCandidateRepo(driver)


def make_arrangement_candidate_repo(
    driver: AsyncDriver | None,
) -> ArrangementCandidateRepo | MemoryArrangementCandidateRepo:
    if driver is None:
        from explorator.persistence.memory_repos import MemoryArrangementCandidateRepo

        return MemoryArrangementCandidateRepo(get_memory_store())
    from explorator.graph.arrangement_candidate_repo import ArrangementCandidateRepo

    return ArrangementCandidateRepo(driver)


def make_voicing_plan_repo(
    driver: AsyncDriver | None,
) -> VoicingPlanRepo | MemoryVoicingPlanRepo:
    if driver is None:
        from explorator.persistence.memory_repos import MemoryVoicingPlanRepo

        return MemoryVoicingPlanRepo(get_memory_store())
    from explorator.graph.voicing_plan_repo import VoicingPlanRepo

    return VoicingPlanRepo(driver)


def make_bass_line_repo(
    driver: AsyncDriver | None,
) -> BassLineRepo | MemoryBassLineRepo:
    if driver is None:
        from explorator.persistence.memory_repos import MemoryBassLineRepo

        return MemoryBassLineRepo(get_memory_store())
    from explorator.graph.bass_line_repo import BassLineRepo

    return BassLineRepo(driver)


def make_groove_pattern_repo(
    driver: AsyncDriver | None,
) -> GroovePatternRepo | MemoryGroovePatternRepo:
    if driver is None:
        from explorator.persistence.memory_repos import MemoryGroovePatternRepo

        return MemoryGroovePatternRepo(get_memory_store())
    from explorator.graph.groove_pattern_repo import GroovePatternRepo

    return GroovePatternRepo(driver)


def make_melodic_complement_repo(
    driver: AsyncDriver | None,
) -> MelodicComplementRepo | MemoryMelodicComplementRepo:
    if driver is None:
        from explorator.persistence.memory_repos import MemoryMelodicComplementRepo

        return MemoryMelodicComplementRepo(get_memory_store())
    from explorator.graph.melodic_complement_repo import MelodicComplementRepo

    return MelodicComplementRepo(driver)


def make_scorecard_repo(
    driver: AsyncDriver | None,
) -> ScorecardRepo | MemoryScorecardRepo:
    if driver is None:
        from explorator.persistence.memory_repos import MemoryScorecardRepo

        return MemoryScorecardRepo(get_memory_store())
    from explorator.graph.scorecard_repo import ScorecardRepo

    return ScorecardRepo(driver)


def make_creative_brief_repo(
    driver: AsyncDriver | None,
) -> CreativeBriefRepo | MemoryCreativeBriefRepo:
    if driver is None:
        from explorator.persistence.memory_repos import MemoryCreativeBriefRepo

        return MemoryCreativeBriefRepo(get_memory_store())
    from explorator.graph.creative_brief_repo import CreativeBriefRepo

    return CreativeBriefRepo(driver)


def make_search_round_repo(
    driver: AsyncDriver | None,
) -> SearchRoundRepo | MemorySearchRoundRepo:
    if driver is None:
        from explorator.persistence.memory_repos import MemorySearchRoundRepo

        return MemorySearchRoundRepo(get_memory_store())
    from explorator.graph.search_round_repo import SearchRoundRepo

    return SearchRoundRepo(driver)


def make_arrangement_family_repo(
    driver: AsyncDriver | None,
) -> ArrangementFamilyRepo | MemoryArrangementFamilyRepo:
    if driver is None:
        from explorator.persistence.memory_repos import MemoryArrangementFamilyRepo

        return MemoryArrangementFamilyRepo(get_memory_store())
    from explorator.graph.arrangement_family_repo import ArrangementFamilyRepo

    return ArrangementFamilyRepo(driver)


def make_mutation_record_repo(
    driver: AsyncDriver | None,
) -> MutationRecordRepo | MemoryMutationRecordRepo:
    if driver is None:
        from explorator.persistence.memory_repos import MemoryMutationRecordRepo

        return MemoryMutationRecordRepo(get_memory_store())
    from explorator.graph.mutation_record_repo import MutationRecordRepo

    return MutationRecordRepo(driver)


def make_style_repo(
    driver: AsyncDriver | None,
) -> StyleRepository | MemoryStyleRepo:
    if driver is None:
        from explorator.persistence.memory_repos import MemoryStyleRepo

        return MemoryStyleRepo(get_memory_store())
    from explorator.graph.style_repo import StyleRepository

    return StyleRepository(driver)


# ---------------------------------------------------------------------------
# Learning / recall repos: null repo (empty/no-op) when driver is None.
# ---------------------------------------------------------------------------


def make_pattern_library_repo(
    driver: AsyncDriver | None,
) -> PatternLibraryRepo | NullPatternLibraryRepo:
    if driver is None:
        from explorator.persistence.null_repos import NullPatternLibraryRepo

        return NullPatternLibraryRepo()
    from explorator.graph.pattern_library_repo import PatternLibraryRepo

    return PatternLibraryRepo(driver)


def make_feedback_event_repo(
    driver: AsyncDriver | None,
) -> FeedbackEventRepo | NullFeedbackEventRepo:
    if driver is None:
        from explorator.persistence.null_repos import NullFeedbackEventRepo

        return NullFeedbackEventRepo()
    from explorator.graph.feedback_repo import FeedbackEventRepo

    return FeedbackEventRepo(driver)


def make_objective_weights_repo(
    driver: AsyncDriver | None,
) -> ObjectiveWeightsRepo | NullObjectiveWeightsRepo:
    if driver is None:
        from explorator.persistence.null_repos import NullObjectiveWeightsRepo

        return NullObjectiveWeightsRepo()
    from explorator.graph.feedback_repo import ObjectiveWeightsRepo

    return ObjectiveWeightsRepo(driver)


def make_genre_research_repo(
    driver: AsyncDriver | None,
) -> GenreResearchRepository | NullGenreResearchRepo:
    if driver is None:
        from explorator.persistence.null_repos import NullGenreResearchRepo

        return NullGenreResearchRepo()
    from explorator.graph.genre_research_repo import GenreResearchRepository

    return GenreResearchRepository(driver)


def make_provenance_trace_repo(
    driver: AsyncDriver | None,
) -> ProvenanceTraceRepo | NullProvenanceTraceRepo:
    if driver is None:
        from explorator.persistence.null_repos import NullProvenanceTraceRepo

        return NullProvenanceTraceRepo()
    from explorator.graph.provenance_trace_repo import ProvenanceTraceRepo

    return ProvenanceTraceRepo(driver)


def make_comparison_view_repo(
    driver: AsyncDriver | None,
) -> ComparisonViewRepo | NullComparisonViewRepo:
    if driver is None:
        from explorator.persistence.null_repos import NullComparisonViewRepo

        return NullComparisonViewRepo()
    from explorator.graph.comparison_view_repo import ComparisonViewRepo

    return ComparisonViewRepo(driver)


def make_candidate_explanation_repo(
    driver: AsyncDriver | None,
) -> CandidateExplanationRepo | MemoryCandidateExplanationRepo:
    if driver is None:
        # Real within-process caching (not a null repo) so `POST /explain`
        # doesn't re-invoke pro-tier LLM on every call in memory mode.
        from explorator.persistence.memory_repos import MemoryCandidateExplanationRepo

        return MemoryCandidateExplanationRepo(get_memory_store())
    from explorator.graph.candidate_explanation_repo import CandidateExplanationRepo

    return CandidateExplanationRepo(driver)


def make_export_package_repo(
    driver: AsyncDriver | None,
) -> ExportPackageRepo | MemoryExportPackageRepo:
    if driver is None:
        # MEMORY (not Null): export is a working surface in memory mode — you
        # export the arrangements you just generated, so the package node must
        # persist for list/download to find it.
        from explorator.persistence.memory_repos import MemoryExportPackageRepo

        return MemoryExportPackageRepo(get_memory_store())
    from explorator.graph.export_package_repo import ExportPackageRepo

    return ExportPackageRepo(driver)


def make_render_artifact_repo(
    driver: AsyncDriver | None,
) -> RenderArtifactRepo | MemoryRenderArtifactRepo:
    if driver is None:
        # MEMORY (not Null): the artifact node must persist so download_artifact
        # can resolve the on-disk path written during export.
        from explorator.persistence.memory_repos import MemoryRenderArtifactRepo

        return MemoryRenderArtifactRepo(get_memory_store())
    from explorator.graph.render_artifact_repo import RenderArtifactRepo

    return RenderArtifactRepo(driver)
