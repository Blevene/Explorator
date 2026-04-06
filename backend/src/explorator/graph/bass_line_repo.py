"""Neo4j repository for BassLine nodes."""
from explorator.graph.repository import BaseRepository


class BassLineRepo(BaseRepository):
    label = "BassLine"
