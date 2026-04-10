"""Neo4j repository for MutationRecord entities."""

from explorator.graph.repository import BaseRepository


class MutationRecordRepo(BaseRepository):
    """CRUD operations for MutationRecord nodes."""

    label = "MutationRecord"
