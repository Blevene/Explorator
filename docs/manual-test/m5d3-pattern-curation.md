# M5d-3 Pattern Curation — manual verification checklist

Merged to `main` as PR #8 on 2026-04-24 (merge commit `f940694`). The E2E (`e2e/tests/pattern-library.spec.ts`) covers the mocked happy path: curate a pattern → toggle Curated-only filter → reload → state persists. This checklist covers what mocks can't catch and what the E2E doesn't exercise.

**Stack prereqs**

- [ ] Neo4j container up (`make neo4j-up`) — default name `explorator-neo4j-1` on 7475/7688
- [ ] Backend running on `:8000` (`make backend`) **without** `LLM_MOCK` (real LLM)
- [ ] Frontend dev server on `:5173`, pointed at that backend: `make frontend`
- [ ] LLM configured in `backend/.env` — `LLM_API_KEY` for the default Gemini provider, or your provider's `LLM_*` settings (see README → LLM providers). `backend/.env` accepts only `Settings` fields; unknown keys stop the backend at startup
- [ ] Migration `m5d3_curation_fields.py --yes` has been applied at least once against the dev Neo4j (idempotent — safe to re-run)
- [ ] You have at least one session with completed finalists in the dev DB. If not, run a fresh round before starting.

## 1 · Critical — FinalistPanel star, end-to-end

For an arrangement that has reached `pending_review` (i.e. the Finalists panel shows it):

- [ ] Outlined star renders next to the score on each finalist card
- [ ] Click the star → `Curated` toast appears, star fills (amber)
- [ ] Click again → `Removed from curated` toast, star empties
- [ ] Click does NOT trigger the card's `onSelect` handler — the card's selected state should not change (stopPropagation working)
- [ ] Backend log shows `POST /v1/arrangements/{id}/curation` returning 200; payload `affected_pattern_ids` length matches the number of facet rows for that arrangement (1–5)

**Cypher backdoor for audit-log verification:**

```cypher
MATCH (e:UserFeedbackEvent {feedback_type: 'pattern_curation', candidate_id: $arrangement_id})
RETURN e.content, e.created_at, e.session_id
ORDER BY e.created_at DESC
```

- [ ] Two events present after curate-then-uncurate, in chronological order, with content `"curated"` then `"uncurated"`
- [ ] `session_id` matches the session that produced the arrangement

**Fail-stop:** if the toggle returns 200 but no event is written, the curation service's transaction is busted. Check `curation_service.py`'s `tx.commit()` call — the read probe was moved inside the tx in commit `d8234f4`.

## 2 · Critical — PatternCard star matches FinalistPanel

After step 1's curation toggle:

- [ ] Navigate to `/patterns` and find the affected pattern row(s)
- [ ] Each of the 1–5 facet rows for that arrangement should show a **filled** star
- [ ] Toggle the star from `/patterns` → toast appears → fan-out flips all matching facet rows in the same render frame (all 5 stars update together; no stale-row flicker)
- [ ] Return to the session — the finalist's star reflects the new state

**Why it matters:** the spec mandates fan-out across all facet rows for one arrangement. If only the clicked row flips, the `is_curated` denormalization is broken.

## 3 · Critical — `Curated only` filter

- [ ] In `/patterns`, with a mix of curated and uncurated rows, toggle `Curated only`
- [ ] List narrows to only the rows with filled stars; uncurated rows disappear
- [ ] Toggle off → full list returns
- [ ] Combined with Genre + Pattern Type filters: all three filters AND together correctly
- [ ] Click `Load more` while `Curated only` is active → next page also respects the filter (no uncurated rows leak in)

## 4 · Critical — re-harvest preserves curation

- [ ] Star a pattern from a specific arrangement
- [ ] Run **another session round** that produces a finalist whose source mutation re-uses the same `source_candidate_id` (rare in practice — easier to verify via Cypher)
- [ ] After re-harvest, the row still has `is_curated = true` and `curated_at` unchanged

**Cypher backdoor:**

```cypher
MATCH (p:PatternLibraryEntry {source_candidate_id: $arrangement_id})
RETURN p.pattern_type, p.is_curated, p.curated_at, p.weighted_total
```

- [ ] `is_curated = true`, `curated_at` is the original timestamp
- [ ] `weighted_total` may have updated (that's OK — the metric is mutable; curation is not)

**Fail-stop:** if curation flips back to `false` after re-harvest, the `immutable_on_match` tuple in `pattern_library_repo.py` lost its `is_curated`/`curated_at` entries. Test `test_upsert_on_match_preserves_curation_fields` would catch this in CI.

## 5 · Critical — disabled star for non-harvested arrangement

This path is hard to hit naturally because finalists are surfaced *after* `harvest_patterns` runs. To force the state:

**Option A — programmatic:** Create an `ArrangementCandidate` via Cypher that has no matching `PatternLibraryEntry` rows, then load the SessionWorkspace pointing at it.

**Option B — cleanup:** Delete all `PatternLibraryEntry` rows for an arrangement, leaving the arrangement intact:

```cypher
MATCH (p:PatternLibraryEntry {source_candidate_id: $arrangement_id}) DETACH DELETE p
```

Then refresh the SessionWorkspace.

- [ ] Star renders **disabled** (~35% opacity), `aria-disabled` set, native `disabled` attribute set (not just ARIA — keyboard users can't tab to it)
- [ ] Hover shows tooltip: `Available after the round completes`
- [ ] Click does nothing — no API call, no toast, no error

If you bypass the disabled UI (e.g. force a click via DevTools), the API should respond with **HTTP 409** `arrangement not yet harvested` and **NO** event should be written. Verify with the audit-log Cypher above.

## 6 · Worth checking — debounce

- [ ] Click the star rapidly (4–5 times in <1 second)
- [ ] Only ONE event is written per 300ms window — confirm via audit-log Cypher
- [ ] Final visual state matches the last click (last-write-wins)

## 7 · Worth checking — optimistic rollback

Force a backend failure by stopping the backend mid-session and clicking a star.

- [ ] Star flips immediately (optimistic)
- [ ] After the API call times out / fails, star reverts and `Failed to update curation` error toast appears
- [ ] No durable state changed in Neo4j (audit log unchanged)
- [ ] Restore the backend; clicking again works normally

## 8 · Worth checking — selectedDetail rollback

- [ ] In SessionWorkspace, select an arrangement so its detail panel is open
- [ ] Stop the backend
- [ ] Click the finalist's star
- [ ] Optimistic flip occurs in BOTH the FinalistPanel card AND the detail panel
- [ ] On rollback, both revert to the original state

## 9 · Worth checking — soft-delete + curation interplay

- [ ] Curate a pattern
- [ ] Soft-delete it via the Delete button on `/patterns`
- [ ] Cypher backdoor: `is_curated = true` (preserved on the tombstoned row), `deleted_at != NULL`
- [ ] Re-harvest the source arrangement → row resurrects with curation intact

## 10 · Worth checking — session deletion cascade

The `DELETE /v1/sessions/{id}` endpoint cascades to `PatternLibraryEntry` rows whose source arrangement belongs to the session (added in commit `397503f`, hardened to use a transaction in commit `d654712`).

- [ ] Note the `source_candidate_id` of one of a session's pattern entries
- [ ] Delete the session via the API (there is no delete button in the UI): `curl -X DELETE localhost:8000/v1/sessions/<id>` (expect 204)
- [ ] Cypher backdoor: no `PatternLibraryEntry` rows survive with that `source_candidate_id`
- [ ] Cypher backdoor: no `ArrangementCandidate`, `Session`, etc. for that session id
- [ ] No orphans of any kind

## 11 · Worth checking — accessibility

- [ ] Tab through the SessionWorkspace — focus lands on each enabled star button, **skips** disabled stars
- [ ] On a focused star, Enter and Space both toggle (native `<button>` behavior)
- [ ] Screen reader announces `aria-label` correctly: `Mark as curated` for outlined, `Remove from curated` for filled
- [ ] `aria-pressed` reflects the boolean state (`true` / `false`)

## 12 · Polish — visuals

- [ ] Star icon size + spacing reads cleanly next to the score and Delete button on `PatternCard`
- [ ] Star icon on FinalistPanel doesn't overlap the role badge or score
- [ ] Filled star uses `--accent-primary` (#f0b429); outlined star uses `currentColor` from the same token via stroke
- [ ] Toast text matches spec: `Curated` (no period) on curate; `Removed from curated` on uncurate
- [ ] No flicker between optimistic flip and server reconciliation in normal operation

## 13 · Regression sanity — M5d-2 surfaces still work

- [ ] Genre + Pattern Type filters still work alongside the new `Curated only` filter
- [ ] Pagination via Load more still works under all filter combinations
- [ ] Delete button still shows confirm dialog and persists soft-delete
- [ ] Backend logs show no warnings about the now-removed `Save to library` button
- [ ] Routing: `/patterns` still loads cleanly on cold-load (no SessionWorkspace dependency)

## 14 · Regression sanity — non-curation flows untouched

- [ ] New session → generate → View Arrangements → finalists panel: classic flow works without involving any star
- [ ] Mutation flow (M3a) still produces children; their stars start outlined (uncurated by default)
- [ ] Comparison view (M4c) still loads and plays — adding curation didn't accidentally affect arrangement audio loading
- [ ] Export flow (M4a/b) still works — exported MIDI/JSON sidecars are unaffected by curation state

---

## Findings during verification

*(Populate during the verification pass. Format: discovery date, brief description, resolution path / ticket reference.)*

---

## Suggested order

Highest-signal sweep (~20–30 min): §1 → §2 → §3 → §4 → §13.

Then §5 (mid-session disabled state) and §10 (cascade delete) for the M5d-3-specific safety nets.

§6–§9, §11, §12, §14 round out polish and regression coverage; do them if §1–§5 pass cleanly.

If §1, §2, or §4 fails, stop and triage — those are the load-bearing invariants the entire feature depends on (atomicity, fan-out, ON MATCH preservation).
