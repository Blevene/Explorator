# Roadmap

Explorator is built and documented in milestones (the `M…` codes you'll see in
the README, ADRs, and `docs/design/plans/`). This file decodes those codes and
sketches what's next. It's a personal project, so the roadmap is best-effort, not
a commitment.

## Shipped

| Milestone | What it delivered |
|---|---|
| **M0** | Foundations — repo, FastAPI + LangGraph skeleton, Neo4j wiring, core models. |
| **M1** | Harmonic MVP — genre-aware chord-progression generation, theory + LLM evaluation, ranking. |
| **M2** | Realization — turn a progression into a voiced arrangement: voicings, bass, groove, melody, assembly, evaluation; piano-roll playback. |
| **M3** | Mutation loop — substitute/extend/transform candidates, plain-text feedback that reweights the scorer, and Pareto ranking of finalists. |
| **M4** | Export & explain — MIDI + JSON export, LLM-generated explanations, DAW-style comparison, and first-class provenance. |
| **M5** | Long-term memory — groove (M5a) and melody (M5b) layers, the genre-research agent (M5c), and the pattern library with curation (M5d). |
| **Limited mode** | Neo4j is optional and auto-detected: without it the backend runs generation on an in-memory store and hides the long-term-memory features (`GET /v1/capabilities`). |
| **Token usage** | Cross-cutting instrumentation: per-round / per-phase / per-session LLM token counts with an estimated cost, shown live ([ADR 011](docs/decisions/011-token-usage-instrumentation.md)). |
| **LLM providers** | Native Gemini or any OpenAI-compatible endpoint (OpenAI, vLLM, Ollama, LM Studio, OpenRouter) via `LLM_*` settings; the token panel shows "not priced" and LLM fallback counts ([ADR 012](docs/decisions/012-configurable-llm-provider.md)). |

For the point-in-time design specs and implementation plans behind each, see
[`docs/design/`](docs/design/); for the current architecture, see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## In progress / planned

- **M6 — multi-layer mutation** (specced, pending): mutate voicing / bass / groove
  / melody layers independently rather than only the harmonic layer.
- **Curated-aware retrieval**: warm-start retrieval currently uses score-ordered
  top-K; bias it toward curated patterns once there's enough curated data to tune
  against.
- **Tension-curve evaluation** ([#3](https://github.com/Blevene/Explorator/issues/3)):
  add the deferred `tension_curve` arrangement dimension.
- **Cadence / loopability granularity** ([#2](https://github.com/Blevene/Explorator/issues/2)).

## Ideas / not scheduled

- Durable, cross-session token-spend trends (persist per-round usage; the current
  panel is per-session only).
- Multi-user / sharing (the tool is single-operator and unauthenticated by
  design — see [ADR 010](docs/decisions/010-no-authentication.md)).

Have a suggestion? Open an [issue](https://github.com/Blevene/Explorator/issues).
