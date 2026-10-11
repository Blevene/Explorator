.PHONY: dev test lint neo4j-up neo4j-down neo4j-test-up neo4j-test-down backend frontend e2e e2e-parallel e2e-neo4j e2e-headed screenshots

# Infrastructure
# Blocks until healthy so a backend started right after doesn't fall back to
# limited (in-memory) mode during the Neo4j start-up.
neo4j-up:
	docker compose up -d --wait neo4j

neo4j-down:
	docker compose down

# Isolated test DB — required by the pytest suite, which wipes all nodes
# between tests. Never share state with the dev container. Blocks until the
# container reports `healthy`; otherwise pytest races the Neo4j start-up
# and the first test hits "connection refused" / auth failures.
neo4j-test-up:
	docker compose up -d --wait neo4j-test

neo4j-test-down:
	docker compose rm -sf neo4j-test

# Backend
backend:
	cd backend && uv run uvicorn explorator.api.app:create_app --factory --host 0.0.0.0 --port 8000 --reload

test: neo4j-test-up
	cd backend && uv run pytest tests/ -v

test-unit: neo4j-test-up
	cd backend && uv run pytest tests/unit/ -v

test-integration: neo4j-test-up
	cd backend && uv run pytest tests/integration/ -v

lint:
	cd backend && uv run ruff check src/ tests/
	cd backend && uv run mypy src/

# Frontend dev server on :5173. Vite's proxy defaults to the e2e backend
# (:8100), so point it at `make backend` (:8000) unless overridden.
frontend:
	cd frontend && VITE_API_TARGET=$${VITE_API_TARGET:-http://localhost:8000} npm run dev

# E2E Tests.
#   e2e-parallel: generation/realization/UI specs, fully parallel, each worker
#                 on its own in-memory backend (no Neo4j needed).
#   e2e-neo4j:    learning-feature specs (pattern library, genre research, etc.),
#                 serial against the shared Neo4j backend (requires Neo4j running;
#                 set NEO4J_CONTAINER for cypher cleanup).
#   e2e:          both lanes.
e2e: e2e-parallel e2e-neo4j

e2e-parallel:
	cd e2e && npx playwright test

e2e-neo4j:
	cd e2e && npx playwright test --config playwright.neo4j.config.ts

e2e-headed:
	cd e2e && npx playwright test --headed

# Regenerate the README screenshots in docs/images/ by driving the live
# dev stack through a real session. Requires `make neo4j-up`, `make backend`
# and `make frontend`. Calls the configured LLM — takes ~3 minutes for four
# screenshots with Gemini.
screenshots:
	cd e2e && npx playwright test capture-screenshots.spec.ts --config capture.config.ts
