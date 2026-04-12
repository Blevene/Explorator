"""Neo4j repository for ComparisonView entities."""

from explorator.graph.repository import BaseRepository


class ComparisonViewRepo(BaseRepository):
    """CRUD operations for ComparisonView nodes."""

    label = "ComparisonView"
