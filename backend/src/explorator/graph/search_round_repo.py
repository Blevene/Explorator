"""Neo4j repository for SearchRound entities."""

from explorator.graph.repository import BaseRepository


class SearchRoundRepo(BaseRepository):
    """CRUD operations for SearchRound nodes."""

    label = "SearchRound"
