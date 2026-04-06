"""Neo4j repository for ArrangementFamily nodes."""
from explorator.graph.repository import BaseRepository


class ArrangementFamilyRepo(BaseRepository):
    label = "ArrangementFamily"
