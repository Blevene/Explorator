.PHONY: test test-unit test-integration lint neo4j-up neo4j-down neo4j-test-up neo4j-test-down up down logs backend frontend e2e e2e-parallel e2e-neo4j e2e-headed screenshots

# Host interface for published ports and dev servers. Loopback by default;
# `BIND_ADDR=0.0.0.0 make ...` opens them to the LAN (the API has no auth).
BIND_ADDR ?= 127.0.0.1
export BIND_ADDR

# The dev Neo4j password lives in backend/.env; scripts/neo4j-password.sh
# generates it on first use and `rotate` moves an old volume off the former
# public default.
NEO4J_PW = NEO4J_PASSWORD="$$(scripts/neo4j-password.sh)"

# Infrastructure
# Blocks until healthy so a backend started right after doesn't fall back to
# limited (in-memory) mode during the Neo4j start-up.
neo4j-up:
	@scripts/neo4j-password.sh >/dev/null
	$(NEO4J_PW) docker compose up -d --wait neo4j
	@scripts/neo4j-password.sh rotate

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

# Optional all-in-Docker stack: Neo4j + backend + frontend (UI on :8080).
# Rebuilds images from the working tree. Configure the LLM in backend/.env.
# The backend runs as the host user and bind-mounts backend/.env, exports and
# the genre catalog, so the host paths must exist before compose starts.
up:
	mkdir -p backend/exports && touch backend/.env
	@scripts/neo4j-password.sh >/dev/null
	$(NEO4J_PW) docker compose up -d --wait neo4j
	@scripts/neo4j-password.sh rotate
	$(NEO4J_PW) APP_UID=$$(id -u) APP_GID=$$(id -g) docker compose --profile app up -d --build --wait backend frontend

# Leaves neo4j-test alone (unlike neo4j-down); data stays in the volume.
down:
	docker compose --profile app down backend frontend neo4j

logs:
	docker compose --profile app logs -f backend frontend

# Backend
backend:
	cd backend && uv run uvicorn explorator.api.app:create_app --factory --host $(BIND_ADDR) --port 8000 --reload

test: neo4j-test-up
	cd backend && uv run pytest tests/ -v

test-unit:
	cd backend && uv run pytest tests/unit/ -v

test-integration: neo4j-test-up
	cd backend && uv run pytest tests/integration/ -v

lint:
	cd backend && uv run ruff check src/ tests/
	cd backend && uv run mypy src/

# Frontend dev server on :5173. Vite's proxy defaults to the e2e backend
# (:8100), so point it at `make backend` (:8000) unless overridden.
frontend:
	cd frontend && ALLOWED_HOSTS=$${ALLOWED_HOSTS:-$$(sed -n 's/^ALLOWED_HOSTS=//p' ../backend/.env 2>/dev/null | tail -n 1)} VITE_API_TARGET=$${VITE_API_TARGET:-http://localhost:8000} npm run dev

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

e2e-neo4j: neo4j-test-up
	cd e2e && npx playwright test --config playwright.neo4j.config.ts

e2e-headed:
	cd e2e && npx playwright test --headed

# Regenerate the README screenshots in docs/images/ by driving the live
# dev stack through a real session. Requires `make neo4j-up`, `make backend`
# and `make frontend`. Calls the configured LLM — takes ~3 minutes for four
# screenshots with Gemini.
screenshots:
	cd e2e && npx playwright test capture-screenshots.spec.ts --config capture.config.ts
