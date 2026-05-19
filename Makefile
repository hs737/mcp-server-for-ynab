.PHONY: lint format typecheck test test-unit test-contract test-integration check \
        smoke-stdio run-stdio run-http \
        postman-generate postman-check \
        test-postman test-postman-operator

# ---------------------------------------------------------------------------
# Code quality
# ---------------------------------------------------------------------------

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy src

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

test:
	uv run pytest

test-unit:
	uv run pytest tests/unit -v

test-contract:
	uv run pytest tests/contract -v

test-integration:
	uv run pytest tests/integration -v

# ---------------------------------------------------------------------------
# Full check (CI)
#
# Runs lint, typecheck, unit/contract/integration tests, and Postman drift
# detection. Does NOT run Newman (live API calls require credentials).
# ---------------------------------------------------------------------------

check: lint typecheck test postman-check

# ---------------------------------------------------------------------------
# Server — start
#
# Two transports, one application:
#   stdio   Production transport for LLM clients (Claude Desktop, etc.)
#   http    Development transport for MCP Inspector, Newman, manual HTTP testing
#
# The MCP HTTP endpoint is JSON-RPC, not a REST API:
#   POST http://127.0.0.1:8000/mcp
# ---------------------------------------------------------------------------

run-stdio:
	uv run python -m ynab_mcp.cli.main stdio

run-http:
	uv run python -m ynab_mcp.cli.main http

run-http-debug:
	FASTMCP_LOG_LEVEL=DEBUG uv run python -m ynab_mcp.cli.main http

smoke-stdio:
	uv run python -m ynab_mcp.cli.smoke

# ---------------------------------------------------------------------------
# Postman — generation and drift detection
#
# Source of truth:
#   Operator → postman/sources/operator/routes.yaml
#   QA       → tests/qa/features/*.feature + tests/qa/cases/*.yaml
#
# Edit the source files, not the generated JSON.
# ---------------------------------------------------------------------------

postman-generate:
	uv run python scripts/generate_operator_collection.py
	uv run python scripts/generate_qa_collection.py

postman-check:
	uv run python scripts/generate_operator_collection.py --check
	uv run python scripts/generate_qa_collection.py --check

# ---------------------------------------------------------------------------
# Postman — Newman tests
#
# Prerequisites:
#   npm install -g newman
#
# Credentials are loaded from .env (YNAB_API_KEY, YNAB_PLAN_ID).
# All QA cases are read-only or use deliberately invalid credentials —
# safe to run against a real YNAB budget.
#
# test-postman:          Run all 31 QA cases (recommended for CI with live creds)
# test-postman-operator: Run read-only operator routes as a smoke check
# ---------------------------------------------------------------------------

.env:
	@echo "ERROR: .env file not found. Copy .env.example and fill in your credentials." && exit 1

_check-newman:
	@command -v newman >/dev/null 2>&1 || { \
		echo "ERROR: newman not found. Install with: npm install -g newman"; \
		exit 1; \
	}

test-postman: _check-newman .env
	@set -a && . ./.env && set +a && \
	newman run postman/collections/ynab-qa.postman_collection.json \
	  --environment postman/environments/ynab-qa.postman_environment.json \
	  --env-var "api_key=$$YNAB_API_KEY" \
	  --env-var "plan_id=$$YNAB_PLAN_ID" \
	  --reporters cli

# Read-only operator folders only. Skips write folders (Categories, Accounts,
# Payees, Scheduled Transactions, Transactions — Write) to avoid side effects.
test-postman-operator: _check-newman .env
	@set -a && . ./.env && set +a && \
	newman run postman/collections/ynab-operator.postman_collection.json \
	  --environment postman/environments/ynab-operator.postman_environment.json \
	  --env-var "api_key=$$YNAB_API_KEY" \
	  --env-var "plan_id=$$YNAB_PLAN_ID" \
	  --folder "User" \
	  --folder "Plans" \
	  --folder "Months" \
	  --folder "Transactions — Read" \
	  --folder "Money Movements" \
	  --reporters cli
