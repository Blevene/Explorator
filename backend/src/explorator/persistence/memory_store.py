"""Process-lifetime in-memory node store — the Neo4j stand-in for memory mode.

Stores plain dicts (the `model_dump(mode="json")` shape) keyed by label then id.
Reads return deep copies so callers can't mutate stored state, matching the
"fresh dict per read" semantics of the Neo4j repos. NOT durable: data is lost on
process restart, by design (see plan decisions).
"""
from __future__ import annotations

import copy
from collections import defaultdict
from typing import Any


class MemoryStore:
    """Unbounded in-memory node store. Known limitation: it grows for the
    process lifetime with no eviction — every created node stays resident until
    the process exits or ``clear()`` is called. ``MemorySessionRepo.list_sessions``
    therefore returns *every* session created this process. This is acceptable
    because memory mode is ephemeral (single-user, restart loses everything);
    add eviction only if memory mode ever needs to be long-lived.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)

    def create(self, label: str, props: dict[str, Any]) -> None:
        self._nodes[label][props["id"]] = copy.deepcopy(props)

    def get(self, label: str, node_id: str) -> dict[str, Any] | None:
        node = self._nodes[label].get(node_id)
        return copy.deepcopy(node) if node is not None else None

    def query(self, label: str, prop: str, value: Any) -> list[dict[str, Any]]:
        return [
            copy.deepcopy(n)
            for n in self._nodes[label].values()
            if n.get(prop) == value
        ]

    def all(self, label: str) -> list[dict[str, Any]]:
        return [copy.deepcopy(n) for n in self._nodes[label].values()]

    def update(self, label: str, node_id: str, **changes: Any) -> None:
        node = self._nodes[label].get(node_id)
        if node is not None:
            node.update(copy.deepcopy(changes))

    def upsert(
        self,
        label: str,
        *,
        key: tuple[str, ...],
        props: dict[str, Any],
        immutable_on_match: tuple[str, ...] = (),
    ) -> None:
        """MERGE-by-natural-key. On match, fields in immutable_on_match are kept."""
        key_vals = tuple(props.get(k) for k in key)
        for existing in self._nodes[label].values():
            if tuple(existing.get(k) for k in key) == key_vals:
                incoming = {
                    k: v for k, v in props.items() if k not in immutable_on_match
                }
                existing.update(copy.deepcopy(incoming))
                return
        self.create(label, props)

    def delete(self, label: str, node_id: str) -> bool:
        """Remove a node by label+id. Returns True if it existed."""
        return self._nodes[label].pop(node_id, None) is not None

    def clear(self) -> None:
        self._nodes.clear()


_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    """Return the process-singleton store (shared by engine + API).

    This is a single process-lifetime instance with no eviction (see
    :class:`MemoryStore`). It is never cleared automatically — tests call
    ``.clear()`` for isolation; in production it accumulates for the process
    lifetime.
    """
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store
