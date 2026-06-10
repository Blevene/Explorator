"""Neo4j repository for AggregateScorecard nodes."""

from explorator.graph.repository import BaseRepository


class ScorecardRepo(BaseRepository):
    """CRUD for AggregateScorecard nodes."""

    label = "AggregateScorecard"
