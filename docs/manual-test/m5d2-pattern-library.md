# M5d-2 Pattern Library — manual verification checklist

Merged to `main` as PR #5 on 2026-04-20 (merge commit `f1bcd64`). The E2E
(`e2e/tests/pattern-library.spec.ts`) covers the mocked happy path. This
checklist covers what mocks can't catch and what the E2E doesn't exercise.

**Stack prereqs**

- [ ] Neo4j container up (`docker compose up -d neo4j`) — default name `explorator-neo4j-1` on 7475/7688
- [ ] Backend running on `:8100` **without** `LLM_MOCK` (real Gemini)
- [ ] Frontend dev server on `:5173`
- [ ] `GEMINI_API_KEY` is set in the backend env
- [ ] `GET /v1/genres` returns non-empty `items` (genres live as YAML in `backend/src/explorator/domain/style/genres/`, not in Neo4j)

Neo4j only stores runtime state (sessions, patterns, arrangements, etc.). A
fresh Neo4j is fine; the 40 pre-built genre YAMLs + matching grammars + rules
are the source of truth and are served by the backend directly from disk.
`GenreProfile` nodes exist **only** for genres newly created via the genre
research flow (M5c), which is out of scope for this checklist.

## 1 · Critical — real-Gemini round trip

For each approved genre:

- [ ] Start a fresh session (prompt matching the genre, e.g. `"Dream pop in A major, wistful, 4 bars"`)
- [ ] Watch the `Saved N patterns to library` toast appear when `harvest_patterns` completes (end of the round)
- [ ] Confirm `N` is non-zero and matches the delta in `/v1/patterns?genre=<g>` before/after
- [ ] Open `/patterns` — new cards visible, correct genre, source candidate short-hash matches

**Fail-stop:** if the toast never fires or `N === 0`, halt. Check backend logs
for the `harvest_patterns` node — density coercion (PR #5 `eaef3b3`) should
have fixed the `float("low")` crash but real Gemini may return novel edge cases.

## 2 · Critical — soft-delete resurrection

- [ ] Delete one pattern via the Delete button (confirm dialog accept)
- [ ] Run another round whose finalist would reuse the same `source_candidate_id` + `pattern_type`
- [ ] Refresh `/patterns` — the deleted pattern should reappear, with `deleted_at = NULL`
- [ ] Cypher backdoor:
  `MATCH (p:PatternLibraryEntry {source_candidate_id: $scid, pattern_type: $pt}) RETURN p.deleted_at`

## 3 · Critical — filter combinations

Filters live at the top of `/patterns`.

- [ ] Filter by genre alone → only that genre's patterns visible
- [ ] Filter by pattern_type alone (try each of `progression`, `voicing`, `bass`, `groove`, `melody`)
- [ ] Both filters combined
- [ ] Clear filters → full list returns
- [ ] Filter → Load More → change filter → confirm no stale rows from previous page leak

## 4 · Worth checking — pagination past first page

Requires >50 patterns total. Build up via repeated rounds or harvest multiple sessions.

- [ ] Click "Load More" at least once
- [ ] DevTools Network: cursor params (`after_score`, `after_id`) on page 2 look plausible
- [ ] No duplicate pattern IDs across pages
- [ ] At end of data, Load More disappears or becomes inactive

## 5 · Worth checking — FinalistPanel manual save button

The auto-harvest via SSE is the primary path; the manual button is a redundant UX.

- [ ] After a round, click "Save to library" in the FinalistPanel
- [ ] Confirm toast fires with same `Saved N patterns to library` format
- [ ] Click twice quickly — idempotent (upsert semantics should dedupe, no double rows)

## 6 · Worth checking — empty states

- [ ] Filter to an impossible combo (`genre=nonexistent` via URL manipulation, or type an unknown genre if the UI allows) → EmptyState renders, not an error
- [ ] Fresh DB (before any harvest) → `/patterns` shows EmptyState, not spinner-forever

## 7 · Worth checking — delete cancel

- [ ] Click Delete → hit **Cancel** on confirm dialog → row remains, no toast, no list flicker
- [ ] Check backend logs — no DELETE request should have fired

## 8 · Polish — visuals

- [ ] Narrow viewport (~375px) — cards don't overflow, delete button still reachable
- [ ] Very long tag lists wrap cleanly without pushing the delete button off-screen
- [ ] `abstracted_pattern` `<details>` expand/collapse — no layout jank
- [ ] Toast stacking — fire two rounds back-to-back; multiple toasts stack cleanly (Sonner default)

## 9 · Polish — navigation

- [ ] Dashboard → "Pattern Library" link lands on `/patterns`
- [ ] `← Dashboard` link returns home
- [ ] Direct-load `/patterns` (browser URL, no dashboard detour) renders correctly on cold load
- [ ] Browser back/forward preserves filter state (nit if broken)

## 10 · Regression sanity — M5d-1 warm-starts

Task 10 migrated `query_for_warm_starts` from `list_all` → `iter_all`.

- [ ] After harvesting patterns for a genre, run a **new** session on that same genre
- [ ] Backend log should show `load_memory` node picking up warm-start patterns
- [ ] Eyeball first-round candidates — should feel "primed" vs. cold-start diversity

## 11 · Regression sanity — density coercion fix

- [ ] Run rounds that produce each of bass / groove / melody finalists (most rounds will)
- [ ] Backend logs: no `ValueError: could not convert string to float` stack traces
- [ ] `/patterns?pattern_type=bass`, `groove`, `melody` all have entries (not just `progression` / `voicing`)

---

## Findings during verification

- **Manual `Save to library` button silently harvests 0 patterns** (discovered 2026-04-20).
  Backend log shows `harvest_session_finalists: no genre in state for session ...; skipping`;
  the endpoint returns 200 with `upserted_count: 0`. Only the auto-harvest LangGraph node
  path populates `state.genre`; the API path at
  `POST /v1/sessions/{id}/finalists/harvest` doesn't reconstruct the genre from the
  arrangement and falls through to the skip branch. Auto-harvest is unaffected.
  **Resolution:** the button is slated for removal in M5d-3 (pattern curation) which
  replaces it with per-finalist star toggles. Not worth a separate fix.

- **Every harvest facet reads from the wrong field paths on its source node** —
  M5d-1 data-integrity issue (discovered 2026-04-20). The extractor code in
  `backend/src/explorator/domain/memory/pattern_harvesting.py` was written against
  a schema that didn't match (or stopped matching) the actual stored shape of
  `ProgressionCandidate`, `BassLine`, `MelodicComplement`, `GroovePattern`, and
  `VoicingPlan`. Every `abstracted_pattern` in the current library is partly or
  mostly default-filled, making the library noise.

  | Facet | Harvest reads | Actual source field | Effect |
  |---|---|---|---|
  | Progression | `chord_symbols`, `metadata.roman_numerals` | `chord_events[*].symbol`, `metadata.roman_numeral_analysis.analysis_events[*].symbol` | both `[]`; `cadence:*` tag never fires; `complexity:low` uniformly |
  | Bass | `mode` → `"root"` | `style_mode`; also missing `contour_type`, `relationship_to_harmony`, `note_events` | meaningless 2-field abstract |
  | Melody | `strategy.contour_type`, `strategy.range_semitones`, `strategy.rhythmic_density` | flat `contour_type` (e.g. `"Descending wave"`), `range_low`/`range_high`, `note_events` | `contour_type=""`, 12-semitone default, 0.5 density default |
  | Groove | `swing_level`, `syncopation_level`, `density`, `template_name` | `swing_amount`, (no syncopation_level on node), `density`, `source_template` | field-name drift + missing data |
  | Voicing | `strategy.density`, `strategy.voice_count` | `density_level`; `voice_count` doesn't exist on node | mostly defaults |

  **Resolution:** dedicated follow-up PR — `fix(m5d-1): align harvest extractors
  with actual source node schemas`. One extractor per facet; include a backfill
  migration that re-harvests all existing library rows from live source nodes.
  Orthogonal to M5d-2 and M5d-3; don't fold in, but blocker for the library
  having actual signal value.

- **`PatternCard` exposes no human-visible pattern ID and no pivot link back to the
  source arrangement** — UX gap (discovered 2026-04-20). The `pl_01...` ULID is only
  in the `data-testid` DOM attribute; the displayed `src:` short-hash is the last 8
  chars of `source_candidate_id` (the arrangement ID) with no click/hover to navigate
  to that arrangement. Users can't reference a specific pattern conversationally nor
  pivot from "interesting pattern" to "what song did this come from." **Resolution:**
  fold into M5d-3 scope *or* a separate post-M5d-3 polish PR — add a small monospace
  pattern-ID badge on each card (with click-to-copy) and make the `src:` hash a link
  that opens `/session/{session_id}` (or `/arrangements/{arrangement_id}` if we add
  such a route). Discuss before deciding.


## Suggested order

Highest-signal sweep (~20–30 min): §1 → §2 → §3 → §10 → §11.
If those pass, §4–§9 for completeness.
If §1 or §2 fails, stop and triage — everything downstream depends on the
harvest+library round trip working end-to-end.
