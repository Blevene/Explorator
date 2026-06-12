# Archived Product Documents

These are the original product documents written before any code was implemented (2026-03-25). They are preserved as a time capsule — a record of how the project was scoped at inception.

**They have not been kept in sync with the implementation.** Material divergence from current reality is expected. For the current state of the system, see:

- Repo root [`README.md`](../../README.md) — what the system is today, milestone status, quick start
- [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) — current system architecture
- [`docs/DESIGN.md`](../../docs/DESIGN.md) — frontend design language
- [`docs/design/specs/`](../../docs/design/specs/) — design specs for each milestone (point-in-time, preserved)
- [`docs/design/plans/`](../../docs/design/plans/) — implementation plans for each milestone

## Files in this archive

| File | What it was |
|---|---|
| `MusicExplorator_PRD.md` | Initial product requirements document |
| `MusicExplorator_FunctionalSpec.md` | Functional specification — features, flows, acceptance criteria |
| `MusicExplorator_Architecture.md` | First-pass architecture sketch |
| `MusicExplorator_CanonicalObjectModel.md` | Original domain object model proposal |
| `MusicExplorator_HybridGraphModel.md` | Original graph schema design |

The PRD's vision and the Functional Spec's user-flow descriptions remain the closest match to current behavior. The Architecture and HybridGraphModel docs predate the LangGraph adoption and the Pydantic/Neo4j-as-source-of-truth choices, and have diverged the most.
