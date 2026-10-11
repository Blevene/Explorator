# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once tagged releases begin. There are no tagged releases yet; everything below
tracks the state of the `main` branch.

## [Unreleased]

### Added
- Configurable LLM provider: native Gemini (default) or any OpenAI-compatible
  endpoint (OpenAI, vLLM, Ollama, LM Studio, OpenRouter, …) through one set of
  `LLM_*` settings (`LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`,
  `LLM_PRO_MODEL`, `LLM_FLASH_MODEL`, plus `LLM_MAX_CONCURRENCY`,
  `LLM_CONTEXT_TOKENS` and `LLM_EXTRA_BODY` for server-specific options such as
  disabling reasoning). See
  [ADR 012](docs/decisions/012-configurable-llm-provider.md). (#66)
- The token panel shows "not priced" when no rates apply to the provider, and a
  badge counting LLM fallbacks (nodes that fell back to defaults after an LLM
  failure). (#66)
- Limited mode: Neo4j is optional. The backend auto-detects it and, when it is
  absent, runs generation on an in-memory store while long-term-memory features
  degrade gracefully; `GET /v1/capabilities` reports the mode, and the UI shows a
  limited-mode banner. Also adds the genre / key / mode pickers and the parallel
  in-memory e2e lane (`make e2e-parallel`). (#21, #22)
- Token-usage instrumentation: per-round, per-phase, and per-session LLM token
  counts with an estimated cost, streamed live during a round and shown in a
  `TokenUsagePanel`. See [ADR 011](docs/decisions/011-token-usage-instrumentation.md).
- Open-source readiness: `LICENSE` (MIT), `SECURITY.md`, `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md`, `ROADMAP.md`, issue/PR templates, `CODEOWNERS`,
  Dependabot, and a CodeQL workflow.

### Changed
- Per-candidate fan-out calls (voicing planning, melody generation, theory
  evaluation) cap output at 4096 tokens. Gemini now retries once on malformed
  output, matching the OpenAI-compatible client. (#67)
- Internal rename gemini → llm: `FakeLLMClient`, `LLMScores`,
  `LLMExplanationOutput`, `llm=` parameters, and the `LLM_MOCK` switch for the
  fake client. (#68)
- Generation uses a single profile (8 candidates, top 3 realized,
  `max_rounds=2`); the balanced / exploratory mode selector is gone. (#21)
- Dependency updates: langgraph 1.2.4, fastapi 0.136.3, pydantic 2.13.4,
  google-genai 2.8.0, neo4j driver 6.2.0, uvicorn, python-ulid, the frontend
  minor/patch group, Playwright, and GitHub Actions. The new `openai` package is
  required by the OpenAI-compatible client. (#28, #33–#35, #39–#41, #48, #66)
- Documentation refresh for public release: renamed the design-history directory
  to `docs/design/`, corrected the genre count (39) and e2e count, and declared
  the license in both package manifests.
- Unknown keys in `backend/.env` (and unrecognized `LLM_*` / `GEMINI_*`
  environment variables) are ignored with a startup warning instead of
  aborting startup; `LLM_MOCK` / `OPENAI_API_KEY` placed in `backend/.env` get a
  hint that they belong in the process environment.

### Removed
- Unused settings `DEFAULT_MAX_ROUNDS`, `DEFAULT_TARGET_SCORE`,
  `DEFAULT_GENERATION_MODE` and `NEO4J_QUERY_TIMEOUT_SECONDS` (never read;
  their values contradicted the ones actually used).
- The placeholder `make sync-genres` target (genres sync at startup and on
  approval) and the unused `readSSEStream` helper in `frontend/src/services/sse.ts`.

### Deprecated
- `GEMINI_*` settings (`GEMINI_API_KEY`, `GEMINI_PRO_MODEL`, …) are aliases for
  their `LLM_*` equivalents, honoured only with `LLM_PROVIDER=gemini` and logged
  as deprecated at startup. (#66)
- `GEMINI_MOCK=true` still enables the fake LLM client but logs a warning; use
  `LLM_MOCK=true`. (#68)

### Fixed
- `LLM_TIMEOUT_SECONDS` (formerly `GEMINI_TIMEOUT_SECONDS`, default 120 s) is
  now enforced for Gemini; it was previously ignored. (#66)
- Structured output cut off at the token limit is repaired before validation
  instead of failing, so runaway fan-out calls no longer fall back to default
  strategies. Repair runs only when the provider reports truncation. (#67)
- Rounds no longer crash on catalog genres whose voicing terms fall outside the
  voicing model. (#21)

## History

Pre-release development proceeded through milestones **M0–M5d** (foundations →
harmonic MVP → realization → mutation/feedback → export/comparison → groove /
melody / genre-research agent / pattern library). See [ROADMAP.md](ROADMAP.md)
for the milestone glossary and [`docs/design/plans/`](docs/design/plans/) for the
point-in-time implementation plans.
