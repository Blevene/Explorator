# M5d-3: Pattern Curation — design spec

**Date:** 2026-04-20
**Status:** draft, awaiting user review
**Depends on:** M5d-2 Pattern Library Browser (PR #5, merged `f1bcd64`)

## Context

M5d-2 introduced the pattern library with automatic harvest: every finalist
arrangement from every session is saved to `PatternLibraryEntry`, and the user
can delete entries they don't want. In the shipped UX, the `FinalistPanel` also
carries a redundant "Save to library" header button that re-runs the same
auto-harvest operation. There is no way for the user to tell the system *which*
finalists they actually liked — all 3 finalists per session are treated
equivalently regardless of user reaction.

This feature adds an explicit user-curation signal to the library. Curation is
a **positive-only** boolean that layers on top of the existing auto-harvested
corpus: the user stars a finalist (or a pattern in the library), and the system
records that explicit preference. In V1 the signal surfaces as a visual badge
and a "Curated only" filter. In future PRs it will feed warm-start retrieval
and the taste model — but that integration is explicitly out of scope here.

## Design decisions, recorded

The following decisions were locked in during brainstorming before this spec
was written. Each is worth preserving because it closes a door that would
otherwise re-open during implementation review.

1. **Signal polarity: positive only.** Non-selected finalists still auto-harvest.
   Curation adds a flag on top; it does not reject siblings.
2. **Granularity: arrangement-level.** One star toggles `is_curated` on all
   1–5 facet rows for the selected arrangement (progression / voicing / bass /
   groove / melody). Facet-level curation was considered and rejected as too
   fiddly for V1.
3. **Surfaces: both.** User can curate from the `FinalistPanel` during a
   session AND from `PatternCard` in the library browser.
4. **Reversibility: toggleable, with full event history preserved.** Every
   toggle writes a `UserFeedbackEvent`. The event log is append-only and is
   the authoritative audit trail; denormalized state on `PatternLibraryEntry`
   is a cache for fast reads.
5. **Data model: reuse `UserFeedbackEvent`.** No new Neo4j label. New
   `feedback_type = "pattern_curation"` discriminator with `content = "curated"
   | "uncurated"`.
6. **Denormalize current state.** `PatternLibraryEntry` gains
   `is_curated: bool` + `curated_at: datetime | None` for fast list-page reads.
   Dual-write inside a single transaction.
7. **Library-browser curation resolves session from provenance.** When the
   user curates from `/patterns`, the event's `session_id` is looked up via
   `source_candidate_id` → `arrangement.session_id`, preserving the
   "which session's pattern is this" signal.
8. **V1 consumers: display + filter only.** Curation produces: a star badge on
   patterns/finalists, and a "Curated only" checkbox in `PatternFilters`.
   Warm-start retrieval and `UserPreferenceProfile` updates are deferred.

## UX & flow

**`FinalistPanel` (session-time curation).**

- Remove the existing `Save to library` header button. It's now redundant
  (auto-harvest always runs at end-of-round) and the user confusion surfaced
  during M5d-2 manual testing confirmed it reads as "select-and-save" when the
  actual behavior is a bulk op.
- Add a star icon to each finalist card's top-right corner, next to the
  weighted-total score. Outlined star = not curated, filled star = curated.
- Click = toggle. Fires the curation API, updates the denormalized flag on all
  matching facet rows in the library, flashes a subtle toast
  (`"Curated"` / `"Removed from curated"`).
- No loading spinner — optimistic UI. On API failure, revert the flip and show
  an error toast (`"Failed to update curation"`).

**Library browser (`/patterns`).**

- Add the same star icon to every `PatternCard`, next to the existing Delete
  button. Same toggle semantics.
- Add a `Curated only` checkbox to `PatternFilters` (in the existing filter row,
  alongside genre + pattern_type). Off by default. When on, the list applies
  `WHERE p.is_curated = true` as an additional filter predicate.

**Net change vs. today:** the manual Save button disappears, per-finalist and
per-pattern stars replace it, and the library gets a curated-only filter. No
bulk curate; no multi-select.

## Data model

### `PatternLibraryEntry` additions

```python
is_curated: bool = False
curated_at: datetime | None = None
```

Follow the same storage pattern as the existing `deleted_at`. Upsert semantics:

- `ON CREATE` — both default to `false` / `NULL`.
- `ON MATCH` — **exclude these fields from the `$props` overwrite.** Unlike
  `deleted_at` (which clears on match to resurrect soft-deleted patterns),
  curation state must survive re-harvest. A user's "I liked this" should not
  be reset when the ranker happens to re-select the same arrangement in a
  later round.

### `UserFeedbackEvent` reused, not extended

New discriminator values:

| Field | Value |
|---|---|
| `feedback_type` | `"pattern_curation"` |
| `content` | `"curated"` or `"uncurated"` |
| `candidate_id` | `arrangement_id` (the finalist's arrangement ID — one event per arrangement-level toggle) |
| `session_id` | Originating session: current session for `FinalistPanel`; looked up via `source_candidate_id` → `arrangement.session_id` for library-browser curation |
| `interpreted_adjustments` | `{}` — unused for curation |
| `weight_deltas` | `{}` — unused for curation |

The two unused fields are a minor awkwardness of reusing an event shape that
was originally designed for LLM-interpreted feedback. A comment on
`UserFeedbackEvent` will flag the convention ("pattern_curation events use
empty adjustments/deltas — state is carried by content").

### Arrangement → facet fan-out

A single curation event maps to an update across all matching facet rows:

```cypher
MATCH (p:PatternLibraryEntry {source_candidate_id: $arrangement_id})
WHERE p.deleted_at IS NULL
SET p.is_curated = $is_curated, p.curated_at = $curated_at
RETURN p.id
```

The update happens inside the same transaction as the `UserFeedbackEvent`
write. Neo4j multi-statement transaction guarantees atomicity.

### Migration

New script `backend/scripts/migrations/m5d3_curation_fields.py`, parallel to
the M5d-2 index migration. Idempotent:

- `MATCH (p:PatternLibraryEntry) WHERE p.is_curated IS NULL SET p.is_curated = false`.
- `CREATE INDEX user_feedback_event_type IF NOT EXISTS FOR (n:UserFeedbackEvent) ON (n.feedback_type, n.candidate_id)` — helps future analytics that filter by feedback type.

No new Neo4j labels.

## API surface

### `POST /v1/arrangements/{arrangement_id}/curation`

**Request body:**
```json
{ "curated": true }
```

**Response (200):**
```json
{
  "arrangement_id": "arr_01KP...",
  "is_curated": true,
  "curated_at": "2026-04-20T18:43:12.557Z",
  "affected_pattern_ids": ["pat_01...", "pat_02...", "..."]
}
```

**Errors:**
- `404 "arrangement not found"` — no `ArrangementCandidate` with that id.
- `404 "no curatable patterns for this arrangement"` — arrangement exists but
  no non-deleted `PatternLibraryEntry` rows match. **No event is written in
  this case** — we don't log intent against empty state.
- `422` — body validation (missing/malformed `curated`).

**Internal flow:**

1. Resolve the arrangement and its originating `session_id`. 404 if missing.
2. Find all non-deleted `PatternLibraryEntry` rows with matching
   `source_candidate_id`. 404 if empty.
3. In one transaction: write a `UserFeedbackEvent`, then update `is_curated`
   + `curated_at` on the affected rows.
4. Return the affected IDs and new state.

**Idempotency:** two rapid toggles in the same direction write two events but
result in the same denormalized state. No dedup in V1.

### `GET /v1/patterns` — two additions

- New query parameter `curated_only: bool = false`. When true, `list_page`
  appends `AND p.is_curated = true` to its WHERE clause. The keyset cursor
  remains stable across pages.
- `PatternItem` response schema gains `is_curated: bool` and `curated_at:
  datetime | None`. The library UI uses these to render each star.

### `GET` on arrangement endpoints — add `is_curated` + `curated_at`

For the `FinalistPanel` to render stars without a second round-trip, the
`ArrangementSummary` response must carry curation state. Derivation:
`p.is_curated` on any non-deleted `PatternLibraryEntry` with matching
`source_candidate_id`. Since fan-out keeps all facet rows in sync, any one row
can be the source of truth.

This is the one deliberate out-of-scope backend touch (arrangement endpoints
are not part of the pattern library subsystem). Justified by the UX cost
avoided.

### Why not reuse `POST /sessions/{sid}/feedback`?

The input is arrangement-scoped and must work without the caller knowing
`session_id` (library-browser case). Reusing `/feedback` would force the
frontend to look up the arrangement's session on every library-browser
curate. The backend is better-placed to do that lookup.

## Frontend components & stores

### New API client function

`frontend/src/api/patterns.ts`:

```ts
export async function toggleCuration(
  arrangementId: string,
  curated: boolean,
): Promise<{
  arrangement_id: string;
  is_curated: boolean;
  curated_at: string | null;
  affected_pattern_ids: string[];
}>;
```

### Store changes

- **`patternFiltersStore`** gains `curated_only: boolean` field and
  `setCuratedOnly(value: boolean)` action. The filter is applied via
  `patternLibraryStore.loadMore(filters)` which already passes filters into
  the API call.
- **`patternLibraryStore`** gains `toggleCuration(arrangementId, nextState)`:
  1. Flip `is_curated` on every item in `items` with matching
     `source_candidate_id` (optimistic).
  2. Call API.
  3. On success: reconcile timestamps from `response.affected_pattern_ids`.
  4. On failure: revert the flip, show error toast.
- **`arrangementStore`** gains `toggleCuration(arrangementId, nextState)` with
  the same optimistic/rollback pattern, applied to its `arrangements` slice.

### Component changes

- **`PatternCard.tsx`** — star icon button next to Delete. State from
  `pattern.is_curated`. OnClick calls `patternLibraryStore.toggleCuration`.
- **`FinalistPanel.tsx`** — remove the header `Save to library` button
  entirely. Add a star to each finalist card's top-right corner, using
  `arrangement.is_curated`. OnClick calls `arrangementStore.toggleCuration`.
- **`PatternFilters.tsx`** — add a `Curated only` checkbox to the existing
  filter row.

### Visual treatment

- Inline SVG `<svg>` with a 5-pointed star path. No new icon library
  dependency — the frontend currently uses inline SVG and text for visual
  elements, and the `public/icons.svg` sprite is not wired up, so introducing
  a separate icon pipeline for a single new glyph isn't justified.
- **Uncurated:** `stroke="currentColor"` + `fill="none"` + `strokeWidth="1.5"`
  (outlined).
- **Curated:** `fill="currentColor"` + no stroke (filled).
- Color: `currentColor` resolves to `var(--accent-primary)` (`#f0b429`, the
  existing amber accent used for score highlights) applied on the button.
- No animation; pure state change.

## Error handling & edge cases

**Concurrency.** The event log is append-only and ordered by `created_at`.
Two rapid toggles write two events; denormalized state is last-write-wins.
Frontend doesn't debounce.

**Re-harvest after curation.** Upsert's `ON MATCH` excludes `is_curated` +
`curated_at` from `$props`, preserving user intent across re-harvest.

**Soft-deleted facet rebound.** If a pattern is curated, then soft-deleted,
`is_curated=true` persists as stale metadata on the invisible row. Resurrection
via re-harvest reactivates it with the flag intact — matches last-expressed
user intent.

**Optimistic UI rollback path.** Both stores flip local state immediately, fire
API, reconcile on success, revert on failure. Error toast: `"Failed to update
curation"`. No retry.

**Accessibility on star buttons:**
- `aria-label={is_curated ? "Remove from curated" : "Mark as curated"}`
- `aria-pressed={is_curated}`
- Keyboard: native `<button>` handles Enter / Space.

## Testing approach

### Backend

- **Unit — `PatternLibraryRepo`:**
  - `toggle_curation(arrangement_id, is_curated, now)` returns affected IDs,
    only touches non-deleted rows, sets/clears both fields correctly.
  - Re-run upsert after curation: `ON CREATE` defaults curation fields;
    `ON MATCH` preserves them (regression test for the invariant).
- **Unit — cursor + filter:** `list_page` with `PatternFilters(curated_only=True)`
  filters correctly; keyset cursor remains stable.
- **Integration — repo against Neo4j:**
  - Curate 5-facet arrangement → all 5 flipped in one transaction + one event.
  - Curate then uncurate → two events in log, final state correct.
  - Arrangement with some deleted facets → only non-deleted updated.
- **API — `POST /v1/arrangements/{id}/curation`:**
  - 200 happy path (curate + uncurate).
  - 404 for unknown arrangement.
  - 404 when no non-deleted library rows exist — **and verify no event was
    written.**
  - Body validation.
- **API — `GET /v1/patterns`:**
  - `curated_only=true` filters response.
  - Response items include `is_curated` + `curated_at`.
- **`UserFeedbackEvent` repo:** `feedback_type="pattern_curation"` roundtrips
  cleanly; `session_id` is the arrangement's session.

### Frontend (vitest)

- **API client:** `toggleCuration()` calls correct URL + body; response parsed.
- **`patternLibraryStore.toggleCuration`:** optimistic fan-out across siblings,
  success reconciliation, failure rollback + error toast.
- **`arrangementStore.toggleCuration`:** same semantics on the arrangements slice.
- **`patternFiltersStore`:** `curated_only` state + action.
- **`PatternCard`:** star renders correct state, click fires store action.
- **`FinalistPanel`:** old `Save to library` button is absent; star renders
  per finalist; click fires store action.
- **`PatternFilters`:** `Curated only` checkbox renders; onChange fires action.

### E2E — extend `e2e/tests/pattern-library.spec.ts`

New test case in the existing spec:

```
test('curate a pattern, filter to curated-only, persist across reload', ...)
```

Flow: run a session to seed patterns → navigate to `/patterns` → click star
on the first card → toggle `Curated only` filter → assert only the starred
item is visible → reload → filter still active, starred item visible with
filled star.

### Explicitly not tested

- Cross-tab live sync.
- Concurrent-event edge cases under load (accepted last-write-wins).
- Migration rollback paths (we're forward-only).

## Out of scope

Consolidated from the discussion; preserved so reviewers can tell what's
intentional omission vs. oversight:

1. **Warm-start retrieval boost.** `query_for_warm_starts` will not favor
   curated patterns in this PR. Separate design required.
2. **Taste-model auto-update.** `UserPreferenceProfile.genre_biases` /
   `voicing_preferences` stay untouched. Those fields are consumed by other
   pipelines and deserve deliberate integration, not a drive-by change.
3. **Bulk curate / multi-select.** No "Curate all 3 finalists" shortcut; one
   star per finalist.
4. **Negative signal (dislike).** `UserPreferenceProfile.disliked_patterns`
   exists but is unaffected by curation. Curation is positive-only.
5. **Facet-level granularity.** Arrangement-level only.
6. **Cross-tab live sync.** Accepted staleness; next refresh reconciles.
7. **Curation analytics / dashboard UI.** Event log is preserved for future
   ML/training but has no user-facing visualization.
8. **Batch backfill of `is_curated` from event log.** No reconciliation job;
   event log and denormalized state are trusted to stay in sync via
   transactional dual-write.
9. **Auto-curation of finalists.** Being selected as a finalist by the ranker
   does NOT implicitly curate the arrangement. "Finalist" (a system signal
   from the ranker) and "curated" (an explicit user signal) are distinct.

## Open questions / follow-ups

None blocking V1. The warm-start retrieval boost (item 1 above) is the most
natural follow-up PR, once there's a body of curated data to tune against.
