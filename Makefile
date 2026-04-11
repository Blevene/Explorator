.PHONY: dev test lint neo4j-up neo4j-down sync-genres backend frontend e2e e2e-headed

# Infrastructure
neo4j-up:
	docker compose up -d neo4j

neo4j-down:
	docker compose down

# Backend
backend:
	cd backend && uv run uvicorn explorator.api.app:create_app --factory --host 0.0.0.0 --port 8000 --reload

test:
	cd backend && uv run pytest tests/ -v

test-unit:
	cd backend && uv run pytest tests/unit/ -v

test-integration:
	cd backend && uv run pytest tests/integration/ -v

lint:
	cd backend && uv run ruff check src/ tests/
	cd backend && uv run mypy src/

# Genre sync (placeholder — will be a CLI command)
sync-genres:
	@echo "Genre sync will be implemented as a CLI command. For now, genres load on app startup."

# Frontend (placeholder for Task 10)
frontend:
	cd frontend && npm run dev

# E2E Tests (requires Neo4j running)
e2e:
	cd e2e && npx playwright test

e2e-headed:
	cd e2e && npx playwright test --headed
