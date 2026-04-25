# ADR 004 — Provenance is first-class on every candidate

**Status:** Accepted

## Context

Several features need to know "where did this come from":

- **Mutation lineage** (M3a) — when the user mutates a candidate, the child needs to remember its parent and what mutation produced it. The frontend renders a lineage tree; the explanation feature describes the transformation.
- **Comparison view** (M4b/M4c) — side-by-side comparison only makes sense when the system can describe what's different. That requires both the parent linkage and the per-step diffs.
- **Export with provenance trace** (M4b) — the JSON sidecar of an exported MIDI includes the candidate's full lineage so the producer has a record.
- **Pattern harvesting** (M5d-1) — the harvested pattern's `source_candidate_id` is the link back to the arrangement that produced it.
- **Round structure** — every candidate belongs to a session and a round; the ranker pulls finalists per-round.

Without a consistent way to express this, each feature would either reach into different fields or invent new joins, and we'd accumulate special cases.

## Decision

**Every candidate carries its provenance as first-class fields on its node.**

The base `CandidateBase` Pydantic model (in `backend/src/explorator/models/base.py`) defines:

```python
session_id: str
family_id: str | None        # groups candidates produced from the same prompt+round
parent_candidate_id          # set on a Candidate via its rationale/lineage where applicable
intent_tags: list[str]       # ["wistful", "ethereal"] etc.
mutation_lineage_ids: list[str]  # full ancestry chain (oldest first)
rationale: str               # human-readable description of why this candidate was generated
warnings: list[str]
```

Concrete subclasses (`ProgressionCandidate`, `ArrangementCandidate`) add domain-specific fields but inherit this base. Neo4j stores all of these as node properties — no separate "lineage" table or relationship type required. Lineage queries walk the `mutation_lineage_ids` array or `parent_candidate_id` field directly.

`PatternLibraryEntry` has its own equivalent: `source_candidate_id` ties every pattern back to the arrangement that produced it.

## Consequences

**Positive:**
- Adding a new feature that needs lineage is free — the data is already there.
- The explanation, comparison, and export features all consume the same provenance fields. No duplication.
- Queries are simple property reads rather than relationship traversals.
- ADR-001's "Neo4j as single source of truth" stays simple — there's no separate lineage subsystem.

**Negative:**
- `mutation_lineage_ids` is a denormalized array that can theoretically grow unboundedly. In practice a session has a bounded number of rounds and mutations; not a concern.
- Provenance fields on every candidate slightly increase node size. Not a meaningful storage cost at our scale.
- Tempting to use the same fields for unrelated lookups; convention is that lineage is read, not joined-on. Lineage relationships traversed via Cypher MATCH on `parent_candidate_id` properties, not relationship types.

## Revisit if

We need to traverse lineage in graph-native ways (e.g. PageRank-style influence, multi-hop ancestor queries). At that point converting `parent_candidate_id` properties to actual relationships pays off. Today it doesn't.

## See also

- `backend/src/explorator/models/base.py` for the inheritance shape
- `backend/src/explorator/api/routes/realization_rounds.py:get_arrangement` for an example consumer
