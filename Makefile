# NexGauge — Project Commands
PY ?= python
.PHONY: check check-ui lint test-unit migrate up up-detached down down-clean restart test test-local health logs clean

up:
	docker-compose up --build

up-detached:
	docker-compose up --build -d

down:
	docker-compose down

down-clean:
	docker-compose down -v

restart:
	docker-compose restart api

test:
	# throwaway DB on the compose db server (pis_user can CREATE DATABASE); never the app DB
	docker-compose exec api sh -c 'TEST_ADMIN_DATABASE_URL="$${DATABASE_URL%/*}/postgres" pytest tests/ -v --tb=short'

lint:
	$(PY) -m ruff check . && $(PY) -m ruff format --check . && $(PY) -m mypy

test-unit:
	PIS_TESTS_NO_DB=1 pytest tests/test_core.py tests/test_github_api.py tests/test_leetcode_api.py tests/test_config.py tests/test_migrate.py -v --tb=short

migrate:
	docker-compose exec api python -m ingest.migrate

# needs only DATABASE_URL + TEST_ADMIN_DATABASE_URL (role with CREATEDB); tests build a throwaway DB
test-local:
	@test -n "$$TEST_ADMIN_DATABASE_URL" || { echo 'set TEST_ADMIN_DATABASE_URL (role with CREATEDB, e.g. postgresql://<superuser>:<pw>@localhost:5432/postgres)'; exit 2; }
	$(PY) -m pytest tests/ -v --tb=short

health:
	curl -s http://localhost:8000/health/detailed | python -m json.tool

logs:
	docker-compose logs -f api

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

# lint + typecheck + tests with the coverage floor (.coveragerc); same as CI. DB tests need TEST_ADMIN_DATABASE_URL
check: lint
	$(PY) -m pytest --cov=app --cov=services --cov=ml --cov=ingest --cov-report=term-missing

check-ui:
	cd apps/desktop && npm run typecheck && npm run lint && npm run format && npm test
