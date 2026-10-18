# PIS — Project Commands
.PHONY: lint test-unit migrate up up-detached down down-clean restart test test-local seed pipeline-all health logs clean

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
	docker-compose exec api pytest tests/ -v --tb=short

lint:
	ruff check . && ruff format --check . && mypy

test-unit:
	pytest tests/test_core.py tests/test_insights.py tests/test_github_api.py tests/test_leetcode_api.py tests/test_config.py tests/test_migrate.py -v --tb=short

migrate:
	docker-compose exec api python -m ingest.migrate

# needs only DATABASE_URL + TEST_ADMIN_DATABASE_URL (role with CREATEDB); tests build a throwaway DB
test-local:
	pytest tests/ -v --tb=short

seed:
	docker-compose exec api python -m ingest.coding
	docker-compose exec api python -m ingest.github

pipeline-all:
	curl -s -X POST http://localhost:8000/pipeline/batch \
		-H "Authorization: Bearer $(PIS_API_TOKEN)" -H "Content-Type: application/json" \
		-d '{"student_ids":[1,2,3,4,5,6,7,8]}' | python -m json.tool

health:
	curl -s http://localhost:8000/health/detailed | python -m json.tool

logs:
	docker-compose logs -f api

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
