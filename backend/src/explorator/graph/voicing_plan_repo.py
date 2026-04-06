"""Neo4j repository for VoicingPlan nodes."""
from explorator.graph.repository import BaseRepository


class VoicingPlanRepo(BaseRepository):
    label = "VoicingPlan"
