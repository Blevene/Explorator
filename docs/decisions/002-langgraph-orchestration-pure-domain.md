# ADR 002 — LangGraph for orchestration; pure Python for domain

**Status:** Accepted

## Context

The system has several multi-step pipelines: progression generation (intent → genre → generate → evaluate → rank → persist), realization (load context → voicing → bass → groove → melody → assemble → evaluate → rank → persist → harvest), and genre research (research → draft → critique → refine → validate). Each step calls some combination of: Gemini, music21, Pydantic models, Neo4j repos.

Three obvious shapes for this:

1. **Imperative orchestrator** — one big `async def` per pipeline that calls each step in order. Pro: simple. Con: hard to introspect, no SSE-progress hook surface, hard to compose sub-graphs.
2. **Custom DAG framework** — invent our own. Pro: total control. Con: not the project's value-add.
3. **LangGraph** — typed state graph, explicit nodes, conditional edges, sub-graph composition. Pro: maps cleanly to our pipelines, gives us per-node progress callbacks for free. Con: external dependency, learning curve for contributors.

## Decision

**LangGraph orchestrates; pure-Python domain code does the work.**

- LangGraph nodes know the pipeline shape — what calls what, in what order, with what state.
- Domain services (in `backend/src/explorator/domain/`) know music theory and algorithms — they take in dataclasses / Pydantic models and return dataclasses / Pydantic models. They don't know about LangGraph state, HTTP, or Cypher.
- Repositories (in `graph/`) translate between domain models and Cypher. They don't know about LangGraph.
- Adapters (in `adapters/`) wrap external services (Gemini, music21). They don't know about domain models or graph state.

LangGraph nodes are the thin glue layer at the top. Each node:
1. Pulls what it needs from `state: TypedDict`.
2. Calls one or more domain services or repos.
3. Optionally calls the `on_progress` callback for SSE.
4. Returns a dict that LangGraph merges back into state.

Three graphs compile at module load: `build_exploration_graph`, `build_realization_subgraph`, and the genre-research sub-graph. They are reused across all requests.

## Consequences

**Positive:**
- Domain logic is unit-testable without mocking out a graph framework. Most tests in `backend/tests/unit/domain/` import a generator/evaluator directly and feed it inputs.
- New pipelines or pipeline edits are local — touch a node and the surrounding `add_edge` calls, not a thousand-line orchestrator class.
- SSE progress events come for free via the per-node `on_progress` callback hook in state.
- Sub-graph composition handles the M5d "harvest only at end of round" case naturally — `realize_subgraph` is callable standalone or as a sub-step of the full exploration graph.

**Negative:**
- LangGraph state is a `TypedDict`, not a Pydantic model — we lose validation between nodes. Mitigation: nodes return a small dict that gets shallow-merged; type errors show up at the next node that reads the field.
- Debugging traversal across many nodes is harder than stepping through imperative code. Mitigation: every node logs its name + a short status; SSE progress events also surface per-node activity.
- We're tied to LangGraph as a dependency. If it breaks something across versions, we have to either pin or migrate.

## Revisit if

- LangGraph as a project drifts in a direction that materially complicates our usage (e.g. requires LCEL we don't want, mandates async event loops we can't use).
- We start needing fine-grained per-node retry / circuit-breaker semantics that LangGraph doesn't give us — at that point a workflow engine like Temporal becomes worth considering.

## See also

- [`docs/ARCHITECTURE.md#pipelines`](../ARCHITECTURE.md#pipelines) for current pipeline shapes
- `backend/src/explorator/engine/` for the actual node implementations
