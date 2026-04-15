"""Neo4j repository for GroovePattern nodes."""
from explorator.graph.repository import BaseRepository


class GroovePatternRepo(BaseRepository):
    label = "GroovePattern"
