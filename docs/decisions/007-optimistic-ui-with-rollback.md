# ADR 007 — Optimistic UI with server reconciliation and rollback

**Status:** Accepted

## Context

Several user actions in the frontend need a backend round-trip but should *feel* instant:

- Toggling a curation star
- Deleting a pattern from the library
- Submitting feedback (less critical — a slight delay is acceptable here)

Three ways to handle this:

1. **Loading spinners.** Click → spinner → wait → result appears. Honest but feels slow on actions that are 99% likely to succeed.
2. **Pessimistic UI with disabled state.** Disable the affected control while waiting. Same problem.
3. **Optimistic UI with rollback.** Flip local state immediately; call the server in the background; reconcile on success or revert on failure.

For actions where the server-side work is well-understood, deterministic, and almost always succeeds, the third option is the right UX. But it requires a consistent pattern across stores so the rollback logic doesn't drift.

## Decision

**Optimistic UI with server reconciliation and rollback** is the standard pattern for any user-action store method that hits the backend. Implementation across all relevant Zustand stores follows the same three-phase shape:

```typescript
async someAction(args) {
  // 1. Snapshot the affected slice of state
  const prev = get().items;

  // 2. Optimistic update
  set({ items: prev.map(item => /* apply expected change */) });

  try {
    // 3. Backend call
    const response = await api.someAction(args);

    // 4. Reconcile — usually means swapping authoritative server-derived
    //    fields (timestamps, ids) into our optimistic state
    set((state) => ({
      items: state.items.map(item =>
        affected(item, response) ? { ...item, ...fromServer(response) } : item
      ),
    }));
    toast.success("Done");
  } catch (err) {
    // 5. Rollback the entire snapshot
    set({ items: prev });
    toast.error("Failed");
    throw err;
  }
}
```

Concrete instances:
- `patternLibraryStore.toggleCuration` — flips `is_curated` across all items with matching `source_candidate_id` (fan-out matches the backend's behavior)
- `arrangementStore.toggleCuration` — flips on the matching arrangement AND on `selectedDetail` if it points at the same arrangement (so the open detail panel doesn't show stale state)
- `patternLibraryStore.removePattern` — optimistic remove with rollback if the DELETE fails

**Toasts via the wrapper** (`lib/toast`, sonner under the hood) — never directly from `sonner`. Single-file swap if we ever change libraries.

## Consequences

**Positive:**
- All user actions feel instant — no spinners, no disabled states.
- The pattern is consistent enough that a new store action can be written by analogy without inventing new error-handling.
- Rollback is "snapshot the slice, restore the slice" — works with arbitrarily complex state shapes without manual diff tracking.
- Tests verify the failure path explicitly (`vi.spyOn(api, 'X').mockRejectedValue(...)`) — both `patternLibraryStore` and `arrangementStore` have rollback tests.

**Negative:**
- Optimistic UI shows the user a state that briefly *might not be true*. For curation/delete/feedback, the failure rate is low enough that this is acceptable. Not appropriate for actions with non-trivial server-side validation that often rejects (e.g. duplicate detection — handled with synchronous response inspection).
- Rollback restores the slice but doesn't time-travel: if other state changed during the request window, the snapshot might overwrite those changes. In practice our actions are scoped narrowly enough that this hasn't bitten us; if it does, we'd narrow the snapshot to just the affected items rather than the whole list.
- The pattern requires server responses to include enough information to reconcile (e.g. `affected_pattern_ids` on the curation response). Our endpoints are designed for this; new endpoints should follow the same convention.

## Revisit if

We add high-stakes destructive actions where "showed the deletion succeeded but it didn't" is unacceptable (e.g. real-money operations, irreversible publishes). At that point a confirm-then-loading-spinner is the right tradeoff.

## See also

- `frontend/src/stores/patternLibraryStore.ts` (canonical implementation)
- `frontend/src/stores/arrangementStore.ts` (with the `selectedDetail` cross-slice rollback case)
- `frontend/src/components/StarButton.tsx` (300ms trailing-edge debounce on the user-side complement)
