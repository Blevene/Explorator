"""Neo4j repository for ArrangementCandidate nodes."""
from explorator.graph.repository import BaseRepository


class ArrangementCandidateRepo(BaseRepository):
    label = "ArrangementCandidate"
