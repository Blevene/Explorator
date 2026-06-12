# M5d-2 — Pattern Library Browser: Design Spec

**Date:** 2026-04-19
**Status:** Draft
**Depends on:** M5d-1 (pattern harvest, merged 2026-04-18 at commit `e703ccc`)

## 1. Overview

M5d-1 made every completed session silently harvest ~15 `PatternLibraryEntry` rows (5 pattern types × 3 finalists) into Neo4j via MERGE-on-natural-key upsert. M5d-2 makes this library **visible and curatable**: a read/delete HTTP API, a `/patterns` browser page, and UI feedback when harvest runs. No retrieval / warm-start logic — that is M5d-3.

**Key decisions from brainstorming:**

- Plan from written spec; library is empty at merge time, iterate on UX after real patterns accumulate
- Defer `WarmStartPanel` (originally Task 31) to M5d-3 — it is retrieval UX, not library UX
- Keep manual re-save endpoint + "Save finalists to library" button in `FinalistPanel`
- Filter on `genre` + `pattern_type` only; tags shown as badges, not filterable
- Sort by `weighted_total DESC` only
- Hard delete (from user perspective) via confirm dialog, implemented as soft delete behind the scenes
- Keyset cursor pagination from day one, plaintext `after_score` / `after_id` query params
- Show `source_candidate_id` as short-hash badge (no link — avoids "session no longer exists" plumbing)
- SSE toast reads `"Saved N patterns to library"` — count sourced from `HarvestReport`
- Extract `harvest_session_finalists(session_id, repos)` module-level helper; graph node + API endpoint both call it

**Deviations from the monolithic plan at `docs/design/plans/2026-04-18-m5d-retrieval-warm-starts.md`:**

- **Tag filtering deferred.** The original M5d-2 scope listed `tags` as a filter. Tag vocabulary stability has not been observed against real data, so tags ship as display-only badges. Revisit in M5d-3 or a follow-up.
- **WarmStartPanel moved to M5d-3** (task 31).

---

## 2. Architecture

Three layers; one new module in each of domain + API + frontend:

```
┌─────────────────────────────────────────────────────────┐
│ FRONTEND  /patterns page + FinalistPanel button         │
│   <PatternLibraryBrowser> composes subcomponents        │
│   patternFiltersStore + patternLibraryStore (Zustand)   │
│   Sonner toasts for node_completed(harvest_patterns)    │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP /v1/patterns, /v1/sessions/{id}/finalists/harvest
┌──────────────────────▼──────────────────────────────────┐
│ API  backend/src/explorator/api/routes/patterns.py      │
│   GET /v1/patterns  GET /v1/patterns/{id}               │
│   DELETE /v1/patterns/{id}                              │
│   POST /v1/sessions/{id}/finalists/harvest              │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│ DOMAIN                                                  │
│   PatternLibraryRepo (list_page, get, soft_delete,      │
│                       upsert — upsert clears deleted_at)│
│   harvest_session_finalists(session_id, repos) helper   │ NEW
│     ↑ called from both LangGraph node and API endpoint  │
│   cursor.py (parse_cursor, InvalidCursor)               │ NEW
└─────────────────────────────────────────────────────────┘
```

**Refactor risk on M5d-1 code:** The `harvest_patterns` LangGraph node is reduced to an SSE-emitting wrapper around the new helper. This is a *pure extraction* (no behavior change) and must land as a separate commit before any API wiring (see §9).

---

## 3. Data Model Changes

### 3.1 `PatternLibraryEntry` gains `deleted_at`

```python
@dataclass
class PatternLibraryEntry:
    ...existing fields...
    deleted_at: datetime | None = None
```

**Semantics:**

- `DELETE /v1/patterns/{id}` sets `deleted_at` to `utcnow()`. UI presents this as a hard delete.
- `list_page` filters `WHERE p.deleted_at IS NULL`.
- `GET /v1/patterns/{id}` returns 404 for soft-deleted rows (externally indistinguishable from "never existed").
- **Re-harvest resurrects.** MERGE on the natural key `(source_candidate_id, pattern_type)` clears `deleted_at` *unconditionally* on match. The upsert query uses `ON MATCH SET p.deleted_at = NULL` (no WHERE predicate on the SET) so non-deleted patterns also have their `deleted_at` set to NULL — a no-op in that case, but the unconditional form eliminates any ambiguity with concurrent DELETE. This preserves the existing upsert contract, requires no change to the natural key itself, and avoids tombstone accumulation. If the user deleted a pattern and then re-ran harvest on the same session, they get the pattern back with its original `id`.

Insurance value: if a future "undo delete" UI arrives, no schema migration is needed — the wiring is already there.

**Invariants (the three rules that make soft-delete consistent — all three must hold together):**

1. `list_page` and any derived query that exposes patterns to the API filters `WHERE p.deleted_at IS NULL`.
2. The upsert query unconditionally clears `deleted_at` on MATCH (`ON MATCH SET p.deleted_at = NULL`).
3. `get_by_id` returns 404 for any row where `deleted_at IS NOT NULL`; `soft_delete(id)` raises `NotFound` for missing *or* already-deleted rows.

### 3.2 Neo4j migration

New migration adds the sort index and documents the `deleted_at` property (Neo4j is schemaless; the migration is declarative for index management):

```cypher
CREATE INDEX pattern_library_sort_idx IF NOT EXISTS
  FOR (p:PatternLibraryEntry) ON (p.weighted_total, p.id);
```

Keyset pagination performance depends on this index.

### 3.3 `HarvestReport`

The helper and SSE payload both use:

```python
class SkipReason(str, Enum):
    MISSING_ABSTRACTION = "missing_abstraction"
    UNSUPPORTED_PATTERN_TYPE = "unsupported_pattern_type"
    REPO_READ_FAILED = "repo_read_failed"

@dataclass(frozen=True)
class SkipEntry:
    candidate_id: str
    pattern_type: str
    reason: SkipReason

@dataclass(frozen=True)
class HarvestReport:
    session_id: str
    upserted_count: int                 # count of successful upserts (MERGE operations)
    skipped_count: int                  # len(skipped_reasons)
    skipped_reasons: list[SkipEntry]
    upserted_pattern_ids: list[str]     # IDs of upserted entries, for tests and debugging
```

**`upserted_count` semantics:** counts every successful MERGE operation (write action), whether the row was new or an idempotent re-write. This is *not* a net-new delta against the library. The user-facing toast reads `"Saved N patterns to library"` — truthful because it describes the write action, not the library delta. Distinguishing new-vs-rewrite would require a pre-existence lookup per pattern, which is overhead for no user benefit.

**`upserted_pattern_ids` ordering:** the list is returned in whatever order the harvest loop produces. Consumers (tests, toasts) must not assume stable ordering — treat it as a set.

### 3.4 `PatternFilters` typed dataclass

Repo takes a typed filter object, not raw kwargs, to prevent the router leaking storage concerns into the repo layer:

```python
@dataclass(frozen=True)
class PatternFilters:
    genre: str | None = None
    pattern_type: str | None = None
```

---

## 4. Backend

### 4.1 `harvest_session_finalists()` helper

New module `backend/src/explorator/services/pattern_library/harvest_service.py`:

```python
@dataclass(frozen=True)
class HarvestRepos:
    pattern_library: PatternLibraryRepo
    arrangement_candidate: ArrangementCandidateRepo
    progression_candidate: ProgressionCandidateRepo
    bass_line: BassLineRepo
    voicing_plan: VoicingPlanRepo
    groove_pattern: GroovePatternRepo
    melodic_complement: MelodicComplementRepo

def harvest_session_finalists(
    session_id: str,
    repos: HarvestRepos,
) -> HarvestReport:
    """Read finalists for a session, harvest patterns, upsert. Idempotent."""
```

**Transport-free.** The helper does not emit SSE, does not talk to LangGraph state. It is pure orchestration over repos.

**LangGraph node** (`harvest_patterns` in existing `graph.py`) becomes:

```python
def harvest_patterns(state: ExplorationState) -> ExplorationState:
    emit_sse("node_started", node="harvest_patterns", session_id=state.session_id)
    report = harvest_session_finalists(state.session_id, get_harvest_repos())
    emit_sse("node_completed", node="harvest_patterns", payload=asdict(report))
    return state
```

### 4.2 Router

New file `backend/src/explorator/api/routes/patterns.py` registered in `app.py`:

| Endpoint | Request | Response | Errors |
|----------|---------|----------|--------|
| `GET /v1/patterns` | `?genre=X&pattern_type=Y&after_score=F&after_id=S&limit=N` (default 50, cap 200) | `{items: [PatternItem], next_cursor: {after_score, after_id} \| null}` | 400 on `InvalidCursor` |
| `GET /v1/patterns/{id}` | — | `PatternItem` | 404 (also for soft-deleted) |
| `DELETE /v1/patterns/{id}` | — | 204 | 404 |
| `POST /v1/sessions/{id}/finalists/harvest` | — | `HarvestReport` (200) | 404 if session missing; 200 with `upserted_count=0` if session exists but has no finalists |

### 4.3 `PatternItem` response schema

`backend/src/explorator/api/schemas/patterns.py`:

```python
class PatternItem(BaseModel):
    id: str
    pattern_type: str
    genre: str
    tags: list[str]
    source_candidate_id: str
    abstracted_pattern: dict
    success_metrics: dict[str, float]
    notes: str
    created_at: datetime
    # intentionally drops `embedding` (large, useless in browser) and `deleted_at` (404 masks it)
```

### 4.4 Repo: `list_page` + `iter_all` replace `list_all`

`list_all()` is removed. Two replacement methods:

- `list_page(filters: PatternFilters | None = None, cursor: Cursor | None = None, limit: int = 50) -> tuple[list[PatternLibraryEntry], Cursor | None]` — public, bounded, keyset-paginated. Used by the HTTP API.
- `iter_all(filters: PatternFilters | None = None) -> Iterator[PatternLibraryEntry]` — internal, unbounded generator. Used by any internal consumer that needs to stream the full library (e.g. the existing `query_for_warm_starts` helper in `pattern_library_repo.py`). Not exposed via the HTTP API.

Splitting these prevents a `limit=None` sentinel from accidentally exporting an unbounded path. `list_page` always has a bounded `limit`.

**Migration note:** `query_for_warm_starts` currently relies on `list_all()` and does in-Python grouping by `pattern_type`. It migrates to `iter_all()` for M5d-2. M5d-3 warm-start retrieval will likely want a top-K-per-type query; introduce that as a new repo method then, rather than piggybacking on `iter_all`.

**Keyset query:**

```cypher
MATCH (p:PatternLibraryEntry)
WHERE p.deleted_at IS NULL
  AND ($genre IS NULL OR p.genre = $genre)
  AND ($pattern_type IS NULL OR p.pattern_type = $pattern_type)
  AND ($after_score IS NULL
       OR p.weighted_total < $after_score
       OR (p.weighted_total = $after_score AND p.id > $after_id))
RETURN p
ORDER BY p.weighted_total DESC, p.id ASC
LIMIT $limit + 1
```

The `+1` row tells the server whether `next_cursor` should be emitted, without a separate count query. It is dropped from the response body.

**Tie handling:** the compound predicate `(wt < $score OR (wt = $score AND id > $id))` correctly paginates across rows with identical `weighted_total`. A dedicated test (§7) guards this.

### 4.5 Cursor module

`backend/src/explorator/services/pattern_library/cursor.py`:

```python
class InvalidCursor(Exception):
    """Raised when one of (after_score, after_id) is set but not the other."""

@dataclass(frozen=True)
class Cursor:
    after_score: float
    after_id: str

def parse_cursor(after_score: float | None, after_id: str | None) -> Cursor | None:
    """None if both params are None; Cursor if both set; raises InvalidCursor otherwise."""
```

Router catches `InvalidCursor` → HTTP 400. Plaintext cursor form chosen over opaque base64 because this is internal tooling with no external API consumers; DevTools-legibility > encapsulation for our context.

### 4.6 DI wiring

`deps.py` additions:

- `get_pattern_library_repo()` — singleton repo instance.
- `get_harvest_repos() -> HarvestRepos` — composes the 7 existing `get_*_repo` dependencies into the bundle dataclass. Kept in `deps.py` (composition root) rather than the service package so the composition is visible at the API edge.

---

## 5. Frontend

### 5.1 Routing + navigation

- New route `/patterns` registered in the React Router v7 tree → `PatternLibraryBrowser`.
- Sidebar gets a **Library** nav item linking to `/patterns`.

### 5.2 Stores (split into two)

Pagination and filter state have different reset semantics — changing a filter must reset cursor + items, while `loadMore` must not. Two stores makes the boundary explicit.

**`frontend/src/stores/patternFiltersStore.ts`:**

```ts
interface PatternFiltersStore {
  filters: { genre?: string; pattern_type?: PatternType };
  setFilter: (patch: Partial<Filters>) => void;
}
```

**`frontend/src/stores/patternLibraryStore.ts`:**

```ts
interface PatternLibraryStore {
  items: PatternItem[];
  cursor: { after_score: number; after_id: string } | null;
  hasMore: boolean;
  loading: boolean;
  error: string | null;

  loadMore: (filters: Filters) => Promise<void>;   // appends; no-ops when !hasMore
  removePattern: (id: string) => Promise<void>;    // optimistic with rollback
  reset: () => void;
}
```

`PatternLibraryBrowser` subscribes to `patternFiltersStore`; on change, calls `patternLibraryStore.reset()` then `loadMore(filters)`.

### 5.3 Components

`PatternLibraryBrowser.tsx` is a thin composition:

```tsx
<PatternLibraryBrowser>
  <PatternFilters />                    // reads/writes patternFiltersStore
  <PatternList>                         // renders cards from patternLibraryStore
    {items.map(p => <PatternCard ... />)}
  </PatternList>
  <LoadMoreButton />                    // wired to hasMore + loadMore
  <EmptyState />                        // shown when items.length === 0 && !loading
</PatternLibraryBrowser>
```

`PatternCard` shows, per row: `type` badge · `genre` · score (2 decimal) · short-hash `source_candidate_id` badge · tags row · collapsed `abstracted_pattern` JSON (click to expand) · notes · delete button. Delete triggers a confirm dialog; on confirm, `patternLibraryStore.removePattern(id)` does optimistic splice + `DELETE /v1/patterns/{id}` with rollback on error (Sonner error toast).

### 5.4 API client

`frontend/src/api/patterns.ts`:

```ts
listPatterns(filters, cursor?): Promise<{items: PatternItem[], next_cursor: Cursor | null}>
getPattern(id): Promise<PatternItem>
deletePattern(id): Promise<void>
harvestSessionFinalists(sessionId): Promise<HarvestReport>
```

Function names mirror the backend service (`harvest_session_finalists`) for cross-stack grep parity.

### 5.5 SSE contract

`frontend/src/api/types.ts` mirrors the backend `HarvestReport` shape (hand-maintained; source of truth is the Python dataclass — comment at the top of the TS interface):

```ts
// Source of truth: backend/src/explorator/services/pattern_library/harvest_service.py
export type SkipReason = "missing_abstraction" | "unsupported_pattern_type" | "repo_read_failed";
export interface SkipEntry { candidate_id: string; pattern_type: string; reason: SkipReason; }
export interface HarvestReport {
  session_id: string;
  upserted_count: number;
  skipped_count: number;
  skipped_reasons: SkipEntry[];
  upserted_pattern_ids: string[];
}
```

`useRealizationFlow` adds a `node_completed` case for `node === "harvest_patterns"`:

```ts
case "harvest_patterns": {
  const report = payload as HarvestReport;
  toast.success(`Saved ${report.upserted_count} patterns to library`);
  break;
}
```

### 5.6 FinalistPanel button

"Save finalists to library" button on each FinalistPanel. Disabled while in flight. On success → `toast.success("Saved N patterns to library")` (same copy as the SSE toast; N from `HarvestReport.upserted_count`). On error → `toast.error("Failed to save finalists")`.

### 5.7 Sonner

- `pnpm add sonner` (or equivalent).
- Mount `<Toaster position="bottom-right" />` in `App.tsx`.
- Thin wrapper `frontend/src/lib/toast.ts`:

```ts
export const toast = {
  success: (message: string, opts?: ToastOptions) => ...,
  error:   (message: string, opts?: ToastOptions) => ...,
  info:    (message: string, opts?: ToastOptions) => ...,
};
```

All other files import from `lib/toast`, never from `sonner` directly, so a future toast-library swap is a one-file change.

---

## 6. Error Handling

- **400:** `InvalidCursor` (e.g. only one of `after_score`/`after_id` supplied).
- **404:** pattern not found (including soft-deleted); session not found for harvest endpoint.
- **DELETE idempotency:** `DELETE /v1/patterns/{id}` returns 204 on first delete of a live row; subsequent DELETEs on the same id return 404 (soft-deleted rows are treated as "not found" at the API boundary, mirroring `GET /v1/patterns/{id}` behavior). Explicit non-idempotent contract: the HTTP spec permits either 204 or 404 for already-deleted resources; this API picks 404 to keep DELETE and GET consistent.
- **5xx:** unhandled exceptions (bubble up to existing FastAPI error middleware).
- **Optimistic delete failure:** frontend rolls back by re-inserting the pattern at its prior index; surfaces Sonner error toast. Does not refetch page (keeps cursor stable).
- **Harvest on empty session:** returns 200 with `upserted_count=0` — not an error. Toast says `"Saved 0 patterns to library"` (explicit, honest feedback).

---

## 7. Testing

### 7.1 Backend (pytest + Neo4j test container)

**TDD, tests before implementation.**

- **`test_harvest_service.py`** — unit tests for `harvest_session_finalists`:
  - Happy path: 3 finalists → 15 pattern upserts, `HarvestReport` fields populated.
  - Idempotence: running twice on the same session yields identical `upserted_pattern_ids` (as sets, MERGE on natural key).
  - Session without finalists: returns `upserted_count=0`, `skipped_reasons=[]`, `upserted_pattern_ids=[]`.
  - Missing-abstraction row: recorded in `skipped_reasons` with correct enum.
  - Resurrection: soft-deleted pattern is re-harvested, `deleted_at` cleared unconditionally, same `id`.

- **`test_pattern_library_repo_pagination.py`**:
  - First page: N rows inserted, `limit=5`, assert 5 items + `next_cursor` set.
  - Follow-up page: cursor round-trip returns next 5.
  - Terminal page: exactly `limit` rows remaining → `next_cursor=None` (off-by-one guard).
  - **Tiebreaker:** 3 rows with identical `weighted_total`, `limit=2`, assert no dupes across pages and no skips.
  - Filter combinations: `genre` only, `pattern_type` only, both, neither.
  - Soft-delete filter: deleted rows never returned.
  - Tests assert *behavior* (ordering, no dupes, terminal cursor), not byte-level cursor encoding.

- **`test_cursor.py`**:
  - `parse_cursor(None, None)` → `None`.
  - `parse_cursor(0.5, "01J...")` → `Cursor(0.5, "01J...")`.
  - `parse_cursor(0.5, None)` and `parse_cursor(None, "01J...")` both raise `InvalidCursor`.

- **`test_patterns_router.py`** (FastAPI TestClient):
  - One test per endpoint covering happy path + 404 + 400 (for cursor).
  - `DELETE` then `GET` → 404; `DELETE` then `DELETE` → 404.
  - `POST harvest` on missing session → 404; on empty session → 200 + `upserted_count=0`.

- **Regression guard:** existing `test_m5d1_harvest.py` runs **unchanged** after Commit A. Its assertions against the `harvest_patterns` node must still pass. Additive fields on `HarvestReport` (e.g. `skipped_reasons`) and renames (`harvested_count` → `upserted_count`, `pattern_ids` → `upserted_pattern_ids`) are permitted only if existing assertions are field-subset or attribute-wise, not exhaustive dict/dataclass equality. Commit A's first step audits the current file: if any assertion does exhaustive equality, narrow it to field-subset in a precursor commit *before* the extraction lands, so Commit A itself can still be "no behavior change."

### 7.2 Frontend (Vitest + React Testing Library)

- **`patternLibraryStore.test.ts`**:
  - `loadMore` appends items and updates cursor.
  - `loadMore` no-ops when `hasMore === false`.
  - `removePattern` optimistic splice + rollback on API error.
  - `reset` clears items and cursor.

- **`patternFiltersStore.test.ts`** — `setFilter` merges patch.

- **`PatternLibraryBrowser.test.tsx`**:
  - Renders cards for items in store.
  - Empty state visible when items empty and not loading.
  - Filter change calls `reset` + `loadMore`.
  - "Load more" button hidden when `hasMore` is false.
  - Delete button → confirm dialog → store action.

- **`FinalistPanel.test.tsx`** — "Save finalists to library" button fires API call, shows toast, disables during flight.

### 7.3 E2E (Playwright, one new spec)

`e2e/tests/pattern-library.spec.ts`:

1. Create + complete a session (reuse existing helpers).
2. Wait for the `harvest_patterns` node-completed toast (reuses the existing SSE helper from `e2e/tests/realization.spec.ts`, which handles `\r\n` SSE framing per project convention); assert count equals expected finalist count × 5.
3. Navigate to `/patterns`; filter by the session's genre.
4. Assert N cards rendered with source-candidate-id values matching expected finalists.
5. Click delete on one card; confirm dialog; assert it disappears and list length decrements.
6. Reload page; assert deleted card does not reappear (soft-delete persisted).

---

## 8. Out of Scope (M5d-3 and beyond)

- Retrieval of patterns for warm-starting new sessions (`load_warm_starts` LangGraph node).
- Generation-node strategy-level pattern injection.
- `WarmStartPanel` component in `SessionWorkspace`.
- Tag filtering (add when tag vocabulary stability is observed against real data).
- Free-text search over `notes`.
- Sort dropdown (only `weighted_total DESC` ships in M5d-2).
- Bulk delete.
- Undo toast for delete (schema is ready; UI wiring deferred).
- Clickable provenance link from pattern back to source session/candidate view.
- Embedding exposure through any API surface.
- Admin-only purge of soft-deleted rows.

---

## 9. Migration + Rollout

1. **Commit A — pure extraction (no behavior change).** Move harvest orchestration from `harvest_patterns` LangGraph node to `harvest_session_finalists()` helper. Node becomes ~10-line wrapper that emits SSE. Existing `test_m5d1_harvest.py` passes unchanged.
   - **Preflight (before Commit A lands):** audit `test_m5d1_harvest.py` and any other existing assertion against `HarvestReport` for exhaustive dict/dataclass equality checks. Narrow any such assertions to field-subset / attribute-wise in a precursor commit. Without this, the Commit B rename (`harvested_count` → `upserted_count`, `pattern_ids` → `upserted_pattern_ids`) will break the "unchanged" regression guard.
2. **Commit B — library API + frontend.** Adds the patterns router, Neo4j migration (index + `deleted_at` semantics), Pydantic schemas, cursor module, frontend stores/views/toast wrapper, SSE handler, FinalistPanel button. Includes the `HarvestReport` field renames.

Splitting the commits keeps the M5d-1 refactor reviewable in isolation and reduces regression surface on merge.

---

## 10. Task Numbering

The monolithic plan at `docs/design/plans/2026-04-18-m5d-retrieval-warm-starts.md` numbered tasks 20, 21, 22, 27, 28, 29, 30, 31, 32, 34 plus one E2E for M5d-2. Task 31 (WarmStartPanel) is deferred to M5d-3. The writing-plans skill will produce the concrete implementation plan from this spec; exact task numbering is up to that plan and does not need to match the monolithic plan.
