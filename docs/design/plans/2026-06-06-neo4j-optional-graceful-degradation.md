# Neo4j-Optional / Graceful Degradation Implementation Plan


**Goal:** Make Neo4j **optional**. When it is reachable, behaviour is identical to today. When it is unreachable:

- **Generation fully works** — M1 progressions → M2 realization → M3 mutations — backed by a process-lifetime in-memory store.
- **Learning / preferences / recall degrade gracefully** — pattern library, feedback re-weighting, session history/provenance, lineage, genre research, curation — return empty/neutral results, never 500.
- The backend **boots without Neo4j** instead of hard-failing in `lifespan`.
- The frontend shows a **clear "limited mode" banner** and hides/disables the unavailable features, driven by a new `GET /v1/capabilities` flag.

**Architecture:**

The decoupling rests on two new pieces plus one inversion:

1. **Tolerant connection.** `graph/connection.py` gains `probe_driver()` (verify connectivity with a timeout; return `None` on failure) and `get_optional_driver()` / `neo4j_available()`. The `lifespan` probes once at startup and records `app.state.persistence_mode`.

2. **A `persistence/` package** — the single place the "which backend?" branch lives:
   - `memory_store.py` — a process-singleton dict store (`label → {id → props}`) with `create/get/query/all/update/upsert/clear`. Stores `model_dump(mode="json")` dicts, so reads match the *deserialized* shape Neo4j repos already return.
   - `protocols.py` — `typing.Protocol` contracts for the generation-path repos (keeps mypy-strict happy across both backends).
   - `memory_repos.py` — in-memory implementations with **real** behaviour for the generation path.
   - `null_repos.py` — empty/no-op implementations for the learning/recall repos (reads → empty, writes → no-op).
   - `factory.py` — `make_<repo>(driver)` helpers: `driver is None` → memory/null repo, else the existing Neo4j repo.

3. **Inversion of repo construction.** Today engine nodes and routes call `SessionRepository(driver)` directly. They will instead call `make_session_repo(driver)` and accept `driver: AsyncDriver | None`. Because the engine and API run in one process and share the `MemoryStore` singleton, engine writes (persist_*) are visible to API reads (sessions/candidates/arrangements) — exactly the M1→M2 handoff the generation path needs.

Genres are special: `StyleService.sync_genres_to_neo4j()` already reads genre YAML from disk and only *writes* to Neo4j. We extract the YAML loader and give `StyleService` a memory mode that serves `get_genre_profile` / `list_genres` straight from YAML — so generation has full genre data with no database.

**Tech Stack:** FastAPI, Pydantic v2, Neo4j (async driver), LangGraph, React + Vite, Zustand, Vitest, Playwright, ruff + mypy (strict).

**Branch:** `feature/neo4j-optional`

**Decisions (confirmed with user):**
- Fallback store: **in-memory only** (process lifetime; lost on restart). No SQLite/JSON adjunct.
- Neo4j role: **optional, auto-detect** at startup. No config flag required to run either way.
- UI: **clear "limited mode" indicator** driven by a backend capabilities flag.

**Non-goals:**
- No durable non-Neo4j persistence.
- No removal of Neo4j or the `graph/` layer; Neo4j-mode behaviour and feature set are unchanged.
- No change to the LangGraph node topology — only how repos are constructed inside nodes.

**Degradation contract (what "graceful" means per feature):**

| Feature | Neo4j present | Neo4j absent (memory mode) |
|---|---|---|
| Session create/list | full | full (in-memory) |
| M1 generation + candidates | full | full |
| M2 realization + arrangements | full | full |
| M3 mutations | full | full |
| Genre profiles / rules | from Neo4j | from YAML |
| Feedback re-weighting (load_memory) | full | canonical default weights (no learning) |
| Pattern library (browse/harvest) | full | empty list / no-op harvest |
| Curation (star/unstar) | full | disabled in UI; API 200 no-op or 409 |
| Session history / provenance | full | empty timeline (hidden in UI) |
| Lineage tree | full | derived from candidate metadata only (hidden in UI) |
| Genre research jobs | full | empty / disabled in UI |
| Export | full | works (reads in-memory arrangements) |

---

## Part 0 — Tolerant connection + lifespan + capabilities endpoint

Outcome of this part: the backend boots with Neo4j down and reports its mode. Generation may still be broken until Part 4 — that is expected; Part 0 is the foundation.

### Task 0.1: `probe_driver()` + availability state in `connection.py`

**Files:**
- Modify: `backend/src/explorator/graph/connection.py`
- Test: `backend/tests/unit/test_connection_probe.py` (new)

- [ ] **Step 1: Write failing test**

Create `backend/tests/unit/test_connection_probe.py`:

```python
import explorator.graph.connection as conn


async def test_probe_returns_none_when_unreachable(monkeypatch):
    """probe_driver returns None (not raise) when connectivity check fails."""
    class _Boom:
        async def verify_connectivity(self):
            raise OSError("refused")
        async def close(self):
            pass

    monkeypatch.setattr(
        conn.AsyncGraphDatabase, "driver", lambda *a, **k: _Boom()
    )
    await conn.close_driver()
    result = await conn.probe_driver(timeout=0.1)
    assert result is None
    assert conn.neo4j_available() is False
    assert await conn.get_optional_driver() is None


async def test_probe_returns_driver_when_reachable(monkeypatch):
    class _Ok:
        async def verify_connectivity(self):
            return None
        async def close(self):
            pass

    monkeypatch.setattr(
        conn.AsyncGraphDatabase, "driver", lambda *a, **k: _Ok()
    )
    await conn.close_driver()
    result = await conn.probe_driver(timeout=0.1)
    assert result is not None
    assert conn.neo4j_available() is True
    assert await conn.get_optional_driver() is result
    await conn.close_driver()
    assert conn.neo4j_available() is False
```

- [ ] **Step 2: Verify fail** — `cd backend && uv run pytest tests/unit/test_connection_probe.py -v` (AttributeError: no `probe_driver`).

- [ ] **Step 3: Implement.** Replace `backend/src/explorator/graph/connection.py`:

```python
"""Neo4j driver connection management.

The driver is OPTIONAL. `probe_driver()` is called once at startup; if Neo4j is
unreachable it records unavailability and the app runs in in-memory mode. The
rest of the app must use `get_optional_driver()` (may return None) — only legacy
callers that truly require Neo4j use `get_driver()`.
"""

import asyncio
import logging

from neo4j import AsyncDriver, AsyncGraphDatabase

from explorator.config import settings

logger = logging.getLogger(__name__)

_driver: AsyncDriver | None = None
_available: bool = False
_lock = asyncio.Lock()


async def probe_driver(timeout: float = 3.0) -> AsyncDriver | None:
    """Create the driver and verify connectivity. Returns None if unreachable.

    Sets module availability state. Safe to call once at startup. On failure the
    half-open driver is closed so we don't leak sockets.
    """
    global _driver, _available
    async with _lock:
        if _driver is not None and _available:
            return _driver
        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        try:
            await asyncio.wait_for(driver.verify_connectivity(), timeout=timeout)
        except (OSError, asyncio.TimeoutError, Exception) as exc:  # noqa: BLE001
            logger.warning("Neo4j unreachable (%s) — running in in-memory mode", exc)
            await driver.close()
            _driver = None
            _available = False
            return None
        _driver = driver
        _available = True
        return _driver


async def get_optional_driver() -> AsyncDriver | None:
    """Return the live driver if Neo4j is available, else None. Never connects."""
    return _driver if _available else None


def neo4j_available() -> bool:
    """Whether the last probe found a reachable Neo4j."""
    return _available


async def get_driver() -> AsyncDriver:
    """Legacy: get-or-create the driver, raising if unreachable.

    Retained for code paths that genuinely require Neo4j (migrations, the
    Neo4j-only test fixtures). Application code should prefer get_optional_driver.
    """
    global _driver, _available
    if _driver is None:
        async with _lock:
            if _driver is None:
                _driver = AsyncGraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_user, settings.neo4j_password),
                )
                _available = True
    return _driver


async def close_driver() -> None:
    """Close the Neo4j driver and reset availability."""
    global _driver, _available
    async with _lock:
        if _driver is not None:
            await _driver.close()
            _driver = None
        _available = False
```

> Note: the broad `except ... Exception` is intentional — `verify_connectivity` can raise driver-internal exceptions (`ServiceUnavailable`, `ConfigurationError`, auth errors). We want *any* failure to mean "no Neo4j", never a crashed startup. Add a `# noqa: BLE001` and a one-line comment so the lint waiver is self-documenting.

- [ ] **Step 4: Verify pass.** `cd backend && uv run pytest tests/unit/test_connection_probe.py -v`.

- [ ] **Step 5: Commit** — `feat(decouple): tolerant probe_driver + optional-driver accessors`.

---

### Task 0.2: Tolerant `lifespan` + `app.state.persistence_mode`

**Files:**
- Modify: `backend/src/explorator/api/app.py`
- Test: `backend/tests/api/test_lifespan_modes.py` (new)

- [ ] **Step 1: Write failing test**

Create `backend/tests/api/test_lifespan_modes.py`:

```python
import explorator.graph.connection as conn
from explorator.api.app import create_app
from fastapi.testclient import TestClient


def test_app_boots_in_memory_mode(monkeypatch):
    """With Neo4j unreachable, the app still starts and reports memory mode."""
    async def _no_driver(*a, **k):
        return None
    monkeypatch.setattr(conn, "probe_driver", _no_driver)
    monkeypatch.setattr(conn, "neo4j_available", lambda: False)

    app = create_app()
    with TestClient(app) as client:  # runs lifespan; must NOT raise
        assert app.state.persistence_mode == "memory"
        resp = client.get("/v1/capabilities")
        assert resp.status_code == 200
        assert resp.json()["persistence_mode"] == "memory"
```

- [ ] **Step 2: Verify fail** (lifespan raises today; `/v1/capabilities` 404).

- [ ] **Step 3: Implement.** Edit `lifespan` in `backend/src/explorator/api/app.py`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Init Neo4j schema + sync genres if reachable; else run in memory mode."""
    import logging

    from explorator.graph.connection import close_driver, probe_driver

    logger = logging.getLogger(__name__)
    driver = await probe_driver()
    if driver is not None:
        from explorator.graph.schema import init_schema
        from explorator.domain.style.service import StyleService

        await init_schema(driver)
        count = await StyleService(driver).sync_genres_to_neo4j()
        logger.info("Neo4j mode — synced %d genre profiles", count)
        app.state.persistence_mode = "neo4j"
    else:
        logger.warning("In-memory mode — long-term memory features disabled")
        app.state.persistence_mode = "memory"

    yield
    await close_driver()
```

Remove the now-unused top-level `get_driver` / `init_schema` imports from `app.py` (they move inside the branch).

- [ ] **Step 4: Verify pass** (also depends on Task 0.3 for the endpoint — implement 0.3 first if running strictly sequentially, or stub the route now).

- [ ] **Step 5: Commit** — `feat(decouple): lifespan tolerates absent Neo4j, records persistence_mode`.

---

### Task 0.3: `GET /v1/capabilities`

**Files:**
- Create: `backend/src/explorator/api/routes/capabilities.py`
- Modify: `backend/src/explorator/api/app.py` (register router)
- Test: `backend/tests/api/test_capabilities.py` (new)

- [ ] **Step 1: Write failing test**

Create `backend/tests/api/test_capabilities.py`:

```python
def test_capabilities_shape(client):
    resp = client.get("/v1/capabilities")
    assert resp.status_code == 200
    body = resp.json()
    assert body["persistence_mode"] in ("neo4j", "memory")
    feats = body["features"]
    for key in (
        "durable_persistence", "pattern_library", "feedback_learning",
        "session_history", "lineage", "genre_research", "curation",
    ):
        assert key in feats
        assert isinstance(feats[key], bool)


def test_capabilities_all_false_in_memory_mode(client_memory):
    body = client_memory.get("/v1/capabilities").json()
    assert body["persistence_mode"] == "memory"
    assert all(v is False for v in body["features"].values())
```

> `client` is the existing API fixture (Neo4j mode). Add a `client_memory` fixture to `backend/tests/api/conftest.py` that monkeypatches `probe_driver`→None before `create_app()` (mirror Task 0.2). Reuse it throughout Parts 1–4.

- [ ] **Step 2: Verify fail.**

- [ ] **Step 3: Implement.** Create `backend/src/explorator/api/routes/capabilities.py`:

```python
"""Runtime capability reporting for the frontend (limited-mode UI)."""
from fastapi import APIRouter, Request

router = APIRouter()

# Features that exist ONLY with a durable graph backend. In memory mode each is
# reported false so the UI can hide/disable the corresponding surface.
_NEO4J_ONLY = (
    "durable_persistence",
    "pattern_library",
    "feedback_learning",
    "session_history",
    "lineage",
    "genre_research",
    "curation",
)


@router.get("/capabilities")
async def get_capabilities(request: Request) -> dict[str, object]:
    mode = getattr(request.app.state, "persistence_mode", "memory")
    enabled = mode == "neo4j"
    return {
        "persistence_mode": mode,
        "features": {name: enabled for name in _NEO4J_ONLY},
    }
```

Register in `app.py` `create_app()`:

```python
from explorator.api.routes.capabilities import router as capabilities_router
...
app.include_router(capabilities_router, prefix="/v1")
```

- [ ] **Step 4: Verify pass** — `cd backend && uv run pytest tests/api/test_capabilities.py tests/api/test_lifespan_modes.py -v`.

- [ ] **Step 5: Commit** — `feat(decouple): GET /v1/capabilities reports persistence mode`.

---

## Part 1 — The `persistence/` package: store, protocols, factory

### Task 1.1: `MemoryStore` singleton

**Files:**
- Create: `backend/src/explorator/persistence/__init__.py`
- Create: `backend/src/explorator/persistence/memory_store.py`
- Test: `backend/tests/unit/test_memory_store.py` (new)

- [ ] **Step 1: Write failing test**

Create `backend/tests/unit/test_memory_store.py`:

```python
from explorator.persistence.memory_store import MemoryStore, get_memory_store


def test_create_get_roundtrip():
    s = MemoryStore()
    s.create("Session", {"id": "a", "genre": "jazz"})
    assert s.get("Session", "a") == {"id": "a", "genre": "jazz"}
    assert s.get("Session", "missing") is None


def test_get_returns_copy_not_reference():
    s = MemoryStore()
    s.create("Session", {"id": "a", "n": 1})
    got = s.get("Session", "a")
    got["n"] = 999
    assert s.get("Session", "a")["n"] == 1  # store not mutated


def test_query_by_property_and_all():
    s = MemoryStore()
    s.create("Cand", {"id": "1", "session_id": "S"})
    s.create("Cand", {"id": "2", "session_id": "S"})
    s.create("Cand", {"id": "3", "session_id": "T"})
    assert {r["id"] for r in s.query("Cand", "session_id", "S")} == {"1", "2"}
    assert len(s.all("Cand")) == 3


def test_update_and_upsert():
    s = MemoryStore()
    s.create("X", {"id": "1", "status": "new"})
    s.update("X", "1", status="done")
    assert s.get("X", "1")["status"] == "done"
    s.upsert("X", key=("scid", "ptype"),
             props={"id": "9", "scid": "c", "ptype": "p", "v": 1})
    s.upsert("X", key=("scid", "ptype"),
             props={"id": "ignored", "scid": "c", "ptype": "p", "v": 2},
             immutable_on_match=("id",))
    rows = [r for r in s.all("X") if r.get("scid") == "c"]
    assert len(rows) == 1 and rows[0]["id"] == "9" and rows[0]["v"] == 2


def test_singleton_shared():
    get_memory_store().clear()
    get_memory_store().create("S", {"id": "z"})
    assert get_memory_store().get("S", "z") is not None
    get_memory_store().clear()
    assert get_memory_store().get("S", "z") is None
```

- [ ] **Step 2: Verify fail.**

- [ ] **Step 3: Implement.** Create `backend/src/explorator/persistence/__init__.py` (empty) and `backend/src/explorator/persistence/memory_store.py`:

```python
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

    def clear(self) -> None:
        self._nodes.clear()


_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    """Return the process-singleton store (shared by engine + API)."""
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store
```

- [ ] **Step 4: Verify pass.**

- [ ] **Step 5: Commit** — `feat(decouple): in-memory MemoryStore singleton`.

---

### Task 1.2: Repository protocols

**Files:**
- Create: `backend/src/explorator/persistence/protocols.py`
- (No standalone test — exercised structurally via mypy + the repo tests in Part 2.)

- [ ] **Step 1: Implement.** Create `backend/src/explorator/persistence/protocols.py` declaring `Protocol`s for the generation-path repos so the factory's union return types are checkable. Mirror the signatures captured in the reference (BaseRepo CRUD plus the few specialized methods):

```python
"""Structural contracts shared by the Neo4j and in-memory repo implementations.

Only the methods actually called by engine nodes / routes are declared — these
are the surfaces that must behave identically across backends. mypy uses these
to verify make_*() factory return types.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


@runtime_checkable
class CrudRepo(Protocol):
    async def create(self, entity: BaseModel) -> None: ...
    async def get_by_id(self, entity_id: str) -> dict[str, Any] | None: ...
    async def query_by_property(self, prop: str, value: Any) -> list[dict[str, Any]]: ...
    async def update_status(self, entity_id: str, status: str) -> None: ...


@runtime_checkable
class SessionRepoProto(CrudRepo, Protocol):
    async def list_sessions(self) -> list[dict[str, Any]]: ...


@runtime_checkable
class StyleRepoProto(Protocol):
    async def get_genre_profile(self, genre: str) -> dict[str, Any] | None: ...
    async def list_genre_profiles(self) -> list[dict[str, Any]]: ...
```

Add further protocols (`CreativeBriefRepoProto.get_by_session_id`, `ScorecardRepoProto`) as the implementing tasks need them. Keep them minimal — declare a method here only when a caller depends on it.

- [ ] **Step 2: Commit** — `feat(decouple): repo protocols for dual backends`.

---

### Task 1.3: The factory

**Files:**
- Create: `backend/src/explorator/persistence/factory.py`
- Test: `backend/tests/unit/test_persistence_factory.py` (new)

> Implement this **after** Part 2's memory repos exist; listed here so the package shape is clear. The factory is the ONLY module that imports both `graph.*` repos and `persistence.memory_repos`/`null_repos`.

- [ ] **Step 1: Write failing test**

```python
from explorator.persistence.factory import make_session_repo, make_pattern_library_repo
from explorator.persistence.memory_repos import MemorySessionRepo
from explorator.persistence.null_repos import NullPatternLibraryRepo
from explorator.graph.session_repo import SessionRepository


def test_factory_returns_memory_when_no_driver():
    assert isinstance(make_session_repo(None), MemorySessionRepo)
    assert isinstance(make_pattern_library_repo(None), NullPatternLibraryRepo)


def test_factory_returns_neo4j_when_driver(fake_driver):  # AsyncMock(spec=AsyncDriver)
    assert isinstance(make_session_repo(fake_driver), SessionRepository)
```

- [ ] **Step 2/3: Implement** `backend/src/explorator/persistence/factory.py`:

```python
"""Backend selection. driver is None ⇒ memory/null repo; else Neo4j repo.

This is the single branch point for the whole decoupling. Add a make_* here for
every repo a node/route needs; never branch on driver elsewhere.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from explorator.persistence.memory_store import get_memory_store

if TYPE_CHECKING:
    from neo4j import AsyncDriver


def make_session_repo(driver: "AsyncDriver | None"):
    if driver is None:
        from explorator.persistence.memory_repos import MemorySessionRepo
        return MemorySessionRepo(get_memory_store())
    from explorator.graph.session_repo import SessionRepository
    return SessionRepository(driver)


# ... one make_* per repo: candidate, arrangement_candidate, voicing_plan,
# bass_line, groove_pattern, melodic_complement, scorecard, creative_brief,
# search_round, arrangement_family, mutation_record, style,
# pattern_library, feedback_event, objective_weights, genre_research,
# provenance_trace, comparison_view, candidate_explanation, export_package,
# render_artifact.
```

- [ ] **Step 4: Verify pass.**

- [ ] **Step 5: Commit** — `feat(decouple): repo factory keyed on driver availability`.

---

## Part 2 — In-memory generation-path repos (the heart of "generation works")

All memory repos live in `backend/src/explorator/persistence/memory_repos.py`, constructed with a `MemoryStore`. They return the **same dict shape** as the Neo4j repos (deserialized — nested dicts/lists, ISO datetime strings), achieved by storing `entity.model_dump(mode="json")`.

A shared base eliminates boilerplate:

```python
class _MemoryCrud:
    label = "Node"
    def __init__(self, store: MemoryStore) -> None:
        self._store = store
    async def create(self, entity: BaseModel) -> None:
        self._store.create(self.label, entity.model_dump(mode="json"))
    async def get_by_id(self, entity_id: str) -> dict[str, Any] | None:
        return self._store.get(self.label, entity_id)
    async def query_by_property(self, prop, value) -> list[dict[str, Any]]:
        return self._store.query(self.label, prop, value)
    async def update_status(self, entity_id: str, status: str) -> None:
        self._store.update(self.label, entity_id,
                           status=status, updated_at=utc_now().isoformat())
```

### Task 2.1: Memory CRUD repos (the BaseRepository family)

**Files:** Modify `persistence/memory_repos.py`; Test `backend/tests/unit/test_memory_repos.py` (new).

- [ ] Implement `_MemoryCrud` plus thin subclasses setting `label`:
  `MemoryCandidateRepo("ProgressionCandidate")`, `MemoryArrangementCandidateRepo("ArrangementCandidate")`,
  `MemoryVoicingPlanRepo`, `MemoryBassLineRepo`, `MemoryGroovePatternRepo`, `MemoryMelodicComplementRepo`,
  `MemoryScorecardRepo("AggregateScorecard")`, `MemorySearchRoundRepo`, `MemoryArrangementFamilyRepo`,
  `MemoryMutationRecordRepo`.
- [ ] `MemorySessionRepo` adds `list_sessions()` → `self._store.all("Session")` sorted by `created_at` desc.
- [ ] `MemoryArrangementCandidateRepo` adds:
  - `list_finalists_for_session(session_id)` → `query("ArrangementCandidate","session_id",sid)` filtered to rows whose `metadata` dict has a `role` key, sorted by `weighted_total` desc.
  - `get_progression_candidate(pc_id)` → `store.get("ProgressionCandidate", pc_id)`.
  - `fetch_curation_state(ids)` → `{i: (None, None) for i in ids}` (no curation in memory mode).
- [ ] `MemoryCreativeBriefRepo` adds `get_by_session_id(sid)` → first `query("CreativeBrief","session_id",sid)` or None.
- [ ] **Tests:** roundtrip create/get for each; `list_finalists_for_session` role filtering; `list_sessions` ordering; `get_by_session_id`. Use the real Pydantic models from the reference (`models/session.py`, `models/harmony.py`, `models/realization.py`, etc.) so the dict shapes are exact.
- [ ] **Commit** — `feat(decouple): in-memory generation-path repos`.

### Task 2.2: Memory style repo from YAML + StyleService memory mode

**Files:** Modify `domain/style/service.py`, `graph/style_repo.py` (extract YAML loader); add `MemoryStyleRepo` to `persistence/memory_repos.py`; Test `backend/tests/unit/test_memory_style.py`.

- [ ] Extract the genre-YAML loading currently inside `StyleService.sync_genres_to_neo4j()` into a pure function `load_genre_profiles_from_yaml() -> list[dict]` (in `domain/style/service.py` or a `loader.py`). `sync_genres_to_neo4j` calls it then upserts.
- [ ] `MemoryStyleRepo` loads via that function (cache on first use) and serves `get_genre_profile(genre)` / `list_genre_profiles()` from the in-memory list — matching `StyleRepository`'s return shape.
- [ ] `StyleService.__init__(self, driver: AsyncDriver | None)` selects the repo via `make_style_repo(driver)`. `get_genre_profile` / `list_genres` work in both modes. `sync_genres_to_neo4j` becomes a no-op returning 0 when `driver is None` (it's only called from the Neo4j branch of lifespan anyway).
- [ ] **Tests:** `MemoryStyleRepo.get_genre_profile("dream_pop")` returns the YAML profile with the same keys the Neo4j path yields; unknown genre → None.
- [ ] **Commit** — `feat(decouple): YAML-backed genre profiles for memory mode`.

---

## Part 3 — Null learning/recall repos (graceful empties)

**Files:** Create `backend/src/explorator/persistence/null_repos.py`; Test `backend/tests/unit/test_null_repos.py`.

These satisfy the same call surfaces but do nothing (writes) and return empties (reads), so learning/recall endpoints return 200 with neutral data instead of 500.

### Task 3.1: Null repos

- [ ] `NullPatternLibraryRepo`: `upsert`→no-op; `get_by_id`→None; `delete_by_id`/`soft_delete`→no-op/False; `query_for_warm_starts(...)`→`{}`; `list_page(...)`→`([], None)`; `iter_all(...)`→empty async generator; `toggle_curation(...)`→`[]`.
- [ ] `NullFeedbackEventRepo`: `create_with_relationships`→no-op; `list_by_session`→`[]`.
- [ ] `NullObjectiveWeightsRepo`: `get_latest_for_session`→`None` (load_memory already falls back to `CANONICAL_DEFAULT_WEIGHTS`).
- [ ] `NullGenreResearchRepo`: `create_job`/`update_job`→no-op; `get_job`→None; `list_pending_drafts`→`[]`; `job_exists_for_genre`→False.
- [ ] `NullProvenanceTraceRepo`: `append_events`→no-op; `get_by_session_id`→None.
- [ ] `NullComparisonViewRepo`, `NullCandidateExplanationRepo` (`get_by_candidate_id`→None), `NullExportPackageRepo`, `NullRenderArtifactRepo`: CRUD no-ops / None.
- [ ] **Tests:** assert each read returns the documented empty and each write is a no-op (no raise).
- [ ] **Commit** — `feat(decouple): null learning/recall repos for graceful degradation`.

---

## Part 4 — Wire the engine, deps, and routes through the factory

This is where generation actually starts working in memory mode. After each task, run the relevant tests in **both** modes (Neo4j up, and with the `client_memory`/monkeypatched-`probe_driver` path).

### Task 4.1: Engine graph accepts `driver: AsyncDriver | None`

**Files:** Modify `engine/graph.py`, `engine/genre_research_graph.py`; Test `backend/tests/unit/test_graph_build_no_driver.py`.

- [ ] Change `build_exploration_graph(gemini, driver)`, `build_realization_subgraph(...)`, `_add_m2_nodes(...)`, and `build` in `genre_research_graph.py` to type `driver: AsyncDriver | None`.
- [ ] Replace `PatternLibraryRepo(driver)` at `graph.py:105` with `make_pattern_library_repo(driver)`.
- [ ] No other change here — nodes receive `driver` (possibly None) via `partial`.
- [ ] **Test:** `build_exploration_graph(fake_gemini, None)` compiles without raising.
- [ ] **Commit** — `refactor(decouple): engine graphs accept optional driver`.

### Task 4.2: Engine nodes resolve repos via factory

**Files:** Modify `engine/nodes/{load_genre,load_context,load_memory,persist_round,persist_realization}.py`; Tests: extend existing node unit tests + new memory-mode tests.

- [ ] `load_genre`: `StyleService(driver)` already works for both modes after Task 2.2 — no change beyond `driver: AsyncDriver | None` typing.
- [ ] `load_context`: replace the four inline repo constructions with `make_candidate_repo`, `make_session_repo`, `make_style_repo` (use `StyleService` for the genre read to share the YAML path), `make_creative_brief_repo`. Type `driver` optional.
- [ ] `load_memory`: `make_feedback_event_repo`, `make_objective_weights_repo`. Existing timeout fallbacks remain; with null repos they return empty fast.
- [ ] `persist_round`: `make_candidate_repo`, `make_search_round_repo`, `make_mutation_record_repo`, `make_provenance_trace_repo`. Keep the per-item `Neo4jError` try/except for Neo4j mode; memory repos won't raise.
- [ ] `persist_realization`: route node writes (`voicing_plan`/`bass_line`/`groove_pattern`/`melodic_complement`/`arrangement_candidate`/`arrangement_family`) and the **AggregateScorecard** write through factory repos (use `make_scorecard_repo`). Guard the **direct-Cypher** blocks (`_create_relationship`, Session `final_selection` update) with `if driver is not None:` — relationships/provenance are learning/lineage concerns that degrade. Add `SessionRepository`/`MemorySessionRepo.set_final_selection(session_id, payload)` so the final-selection write works in both modes (arrangements still need to be readable; the session field is optional UI sugar — acceptable to no-op in memory if simpler, but prefer storing it).
  - **Critical:** the AggregateScorecard write MUST go through the factory because `realization_rounds.list_arrangements` reads scorecards back (`ScorecardRepo.query_by_property("candidate_id", ...)`) to populate `weighted_total`/`rank_within_round`. If it stayed direct-Cypher, ranking would vanish in memory mode.
- [ ] **Tests:**
  - Memory-mode `persist_realization` → arrangements + scorecards retrievable from the store.
  - Memory-mode `load_context` after `persist_round` returns the persisted candidates (the M1→M2 handoff).
- [ ] **Commit** — `refactor(decouple): engine nodes construct repos via factory`.

### Task 4.3: `deps.py` + inline route repos via factory

**Files:** Modify `api/deps.py`, `api/routes/{candidates,realization_rounds,exports,feedback,patterns,sessions,genres,genre_research,mutations,rounds,explanations,comparisons}.py`; Tests: new memory-mode API tests.

- [ ] `api/deps.py`: every `get_*` swaps `await get_driver()` for `await get_optional_driver()` and returns `make_*_repo(driver)`. `get_neo4j_driver` becomes `get_optional_driver` (rename the dep or keep the name but return `AsyncDriver | None`). `get_harvest_repos` builds its bundle from factory calls (null repos in memory mode → harvest is a clean no-op).
- [ ] Replace inline repo classes in routes with factory calls:
  - `candidates.py` `CandidateRepo` → `make_candidate_repo(driver)`.
  - `realization_rounds.py` `ArrangementCandidateRepo`/`ScorecardRepo` → `make_arrangement_candidate_repo`/`make_scorecard_repo`. `fetch_curation_state` already returns `(None, None)` per id in memory mode.
  - `exports.py` `ArrangementCandidateRepo`/`CreativeBriefRepo` → factory.
  - Routes taking a raw driver dependency now get `AsyncDriver | None`; anywhere they construct a repo, go through the factory.
- [ ] The genre-research, feedback, patterns, comparisons, explanations routes already get repos from `deps.py`; once `deps.py` returns null repos they degrade automatically. Verify each returns 200 (empty) rather than 500 in memory mode — add a small guard where a route assumed a non-null result.
- [ ] **Tests (memory mode):**
  - `POST /v1/sessions` → 201; `GET /v1/sessions` lists it.
  - Full generation round endpoint → candidates present; realization → arrangements with `weighted_total`.
  - `GET /v1/patterns` → `{items: [], next_cursor: null}` 200.
  - `POST` feedback → 200/204 no-op; provenance/genre-research/explanations/comparisons → empty 200.
  - Export of an in-memory arrangement → succeeds.
- [ ] **Commit** — `refactor(decouple): API deps + routes use optional driver via factory`.

### Task 4.4: Harvest + curation services no-op cleanly

**Files:** Modify `engine/nodes/harvest_patterns.py` (already takes a repo — null repo handles it), `services/pattern_library/curation_service.py`; Tests.

- [ ] `harvest_patterns`: with a `NullPatternLibraryRepo`, `upsert` is a no-op — confirm the node still returns a valid state (no crash, harvest report shows 0).
- [ ] `curate_arrangement`: add an early branch — when `driver is None`, raise `PatternsNotHarvested` (frontend already disables the star in memory mode, so this is defence-in-depth) OR return a no-op `CurationResult`. Prefer raising `PatternsNotHarvested` → route maps to 409, consistent with "nothing to curate". Document the choice in a docstring line.
- [ ] **Tests:** memory-mode harvest node returns 0 harvested; `curate_arrangement(driver=None, ...)` raises `PatternsNotHarvested`.
- [ ] **Commit** — `feat(decouple): harvest/curation degrade cleanly without Neo4j`.

---

## Part 5 — Frontend "limited mode"

### Task 5.1: `getCapabilities()` + `capabilitiesStore`

**Files:** Modify `frontend/src/services/api.ts`; Create `frontend/src/stores/capabilitiesStore.ts`; Test `frontend/src/stores/__tests__/capabilitiesStore.test.ts`.

- [ ] Add to `api.ts`:

```typescript
export interface Capabilities {
  persistence_mode: 'neo4j' | 'memory';
  features: Record<string, boolean>;
}

export async function getCapabilities(): Promise<Capabilities> {
  const res = await fetch(`${API_BASE}/capabilities`);
  if (!res.ok) throw new Error(`Failed to fetch capabilities: ${res.status}`);
  return res.json();
}
```

- [ ] Create `capabilitiesStore.ts` (Zustand, matching the `patternLibraryStore` shape): state `{ capabilities, loading, error }`, action `fetch()`, selectors `isMemoryMode()` and `can(feature: string): boolean` (defaults to `true` until loaded, so nothing flickers-hidden on first paint — except the banner, which keys off `persistence_mode === 'memory'` only after load).
- [ ] **Test:** mock `getCapabilities`; assert store populates and `isMemoryMode()` reflects it.
- [ ] **Commit** — `feat(decouple-ui): capabilities store + getCapabilities`.

### Task 5.2: Fetch on boot + global banner

**Files:** Modify `frontend/src/components/AppShell.tsx` (and/or `App.tsx` for the initial fetch).

- [ ] Call `useCapabilitiesStore.getState().fetch()` once on app mount (in `App.tsx` `useEffect`, or `AppShell`).
- [ ] In `AppShell`, render a banner directly under the header (before `<Outlet/>` at ~line 46) when `persistence_mode === 'memory'`: "Limited mode — long-term memory is off (pattern library, history, lineage, and learning are disabled). Generation works normally." Style with existing design tokens (`var(--warning-*)` / `var(--accent-secondary)`); keep it dismissible-optional but visible by default.
- [ ] **Commit** — `feat(decouple-ui): limited-mode banner in AppShell`.

### Task 5.3: Gate the degradable surfaces

**Files:** `AppShell.tsx` (nav), `App.tsx` (routes), `SessionWorkspace.tsx`, `StarButton.tsx` call sites (`FinalistPanel.tsx`, `PatternCard.tsx`), `GenreManagement.tsx`.

- [ ] **Nav:** hide the `Patterns` `NAV_ITEMS` entry when `!can('pattern_library')`. Hide/disable the `Genres` research affordances when `!can('genre_research')` (keep the genre *library* visible — it's served from YAML and works).
- [ ] **Routes:** when memory mode, either drop the `/patterns` route or render a small "unavailable in limited mode" placeholder (prefer placeholder so a bookmarked URL doesn't 404 in-app).
- [ ] **SessionWorkspace:** wrap `<SessionHistory .../>` (mount ~line 422) in `{can('session_history') && ...}` and `<LineageTree .../>` (mount ~line 355) in `{can('lineage') && ...}`.
- [ ] **StarButton:** pass `disabled={!can('curation')}` at both call sites (`FinalistPanel.tsx:85`, `PatternCard.tsx:58`) with a title tooltip "Curation requires the database (limited mode)".
- [ ] **GenreManagement:** gate the "Research New Genre" button + form + pending-drafts list (lines ~383–488) on `can('genre_research')`.
- [ ] **Tests:** component tests asserting each surface hides/disables when the store reports memory mode (mock the store). Reuse the `StarButton.test.tsx` pattern.
- [ ] **Commit** — `feat(decouple-ui): gate pattern library, history, lineage, curation, research`.

---

## Part 6 — Tests, lint, docs

### Task 6.1: End-to-end memory-mode test pass

**Files:** `backend/tests/...` (memory-mode suite), `frontend/...`.

- [ ] Add a backend memory-mode integration test that drives a full session through the API with `probe_driver`→None: create session → generate → realize → read arrangements → confirm `/v1/capabilities` memory + learning endpoints empty. (Gate the LLM call with `GEMINI_MOCK=true`, per existing convention.)
- [ ] Confirm the existing Neo4j-mode suites still pass unchanged (run `make test`, which starts the test container on :7689 — see `project_test_neo4j_port` memory).
- [ ] Frontend: `cd frontend && npm run test:unit` green.
- [ ] **Commit** — `test(decouple): memory-mode end-to-end coverage`.

### Task 6.2: Lint / type gate

- [ ] `make lint` (ruff + **mypy strict**) clean. Expect to add a few `AsyncDriver | None` annotations and possibly `cast`s where a route narrowed to a concrete repo type; prefer the Protocol return types from Task 1.2 over `cast`.
- [ ] **Commit** — `chore(decouple): lint + mypy strict clean`.

### Task 6.3: Docs

**Files:** `README.md`, `docs/ARCHITECTURE.md`.

- [ ] README: note Neo4j is now **optional** — generation runs without it via in-memory mode; `make neo4j-up` is required only for durable storage + learning/recall features. Document the limited-mode banner.
- [ ] ARCHITECTURE: add a short "Persistence backends" section describing `probe_driver` auto-detect, the `persistence/` package (store + factory + memory/null repos), and the degradation contract table from this plan.
- [ ] **Commit** — `docs(decouple): document optional Neo4j + limited mode`.

---

## Manual verification (after all parts)

1. **Memory mode:** stop Neo4j (`docker compose stop neo4j` or just don't start it). `make backend` → starts, logs "In-memory mode". Open the UI: limited-mode banner shows; Patterns nav hidden; run a full generate → realize; arrangements render with scores; star buttons disabled; history/lineage hidden. Restart backend → prior session gone (expected, in-memory).
2. **Neo4j mode:** `make neo4j-up`, `make backend` → logs "Neo4j mode — synced N genre profiles"; no banner; all features present; behaviour identical to pre-change. Restart → data persists.
3. `/v1/capabilities` returns the correct `persistence_mode` and feature flags in each mode.

## Review (filled in after implementation)
- _pending_
