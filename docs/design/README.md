# Superpowers — historical milestone records

The files under `specs/` and `plans/` are point-in-time records captured during implementation of each milestone (M0 through M5d). They are **preserved, not maintained** — design choices, file paths, test counts, and commands inside them describe the state of the project on the date in the filename.

Treat them as a project diary, not a reference. They're useful for:

- Understanding *why* a milestone was scoped the way it was
- Tracing how a feature came together (the plan often shows the day-by-day order of work)
- Seeing earlier critique passes and how they shaped the final design

For **current** documentation, use:

- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — system architecture, data model, pipelines as they exist today
- [`../DESIGN.md`](../DESIGN.md) — frontend design language, current components, CSS tokens
- [`../decisions/`](../decisions/) — ADRs for the load-bearing decisions

When something in `specs/` or `plans/` contradicts current code, current code wins.
