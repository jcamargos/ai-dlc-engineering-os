from ._store_base import SCHEMA_VERSION, MemoryHit, MemoryStoreBase
from ._store_ops import MemoryStoreOps
from ._store_search import MemoryStoreSearch
from ._store_evolution import MemoryStoreEvolution
from .swarm import SwarmRuntimeMixin
from .vector_memory import VectorMemoryMixin

__all__ = ["SCHEMA_VERSION", "MemoryHit", "MemoryStore"]


class MemoryStore(MemoryStoreBase, MemoryStoreOps, MemoryStoreSearch, MemoryStoreEvolution, VectorMemoryMixin, SwarmRuntimeMixin):
    """Local AI-DLC Engineering OS store: governed memory, FTS5 + vector retrieval, agent evolution, swarms."""
