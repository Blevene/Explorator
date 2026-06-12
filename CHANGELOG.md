# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once tagged releases begin. There are no tagged releases yet; everything below
tracks the state of the `main` branch.

## [Unreleased]

### Added
- Token-usage instrumentation: per-round, per-phase, and per-session Gemini token
  counts with an estimated cost, streamed live during a round and shown in a
  `TokenUsagePanel`. See [ADR 011](docs/decisions/011-token-usage-instrumentation.md).
- Open-source readiness: `LICENSE` (MIT), `SECURITY.md`, `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md`, `ROADMAP.md`, issue/PR templates, `CODEOWNERS`,
  Dependabot, and a CodeQL workflow.

### Changed
- Documentation refresh for public release: renamed the design-history directory
  to `docs/design/`, corrected the genre count (39) and e2e count, and declared
  the license in both package manifests.

## History

Pre-release development proceeded through milestones **M0–M5d** (foundations →
harmonic MVP → realization → mutation/feedback → export/comparison → groove /
melody / genre-research agent / pattern library). See [ROADMAP.md](ROADMAP.md)
for the milestone glossary and [`docs/design/plans/`](docs/design/plans/) for the
point-in-time implementation plans.
