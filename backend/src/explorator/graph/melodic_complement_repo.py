"""Neo4j repository for MelodicComplement nodes."""
from explorator.graph.repository import BaseRepository


class MelodicComplementRepo(BaseRepository):
    label = "MelodicComplement"
