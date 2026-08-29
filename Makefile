.PHONY: lint format typecheck test test-unit test-contract test-integration check \
        smoke-stdio run-stdio run-http \
        verify-live verify-write verify-mcp-http \
        postman-generate postman-check \
        packaging-sync packaging-check mcpb docker-build docker-smoke \
        assets assets-check \
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

check: lint typecheck test postman-check packaging-check assets-check

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
	uv run python -m mcp_server_for_ynab.cli.main stdio

run-http:
	uv run python -m mcp_server_for_ynab.cli.main http

run-http-debug:
	FASTMCP_LOG_LEVEL=DEBUG uv run python -m mcp_server_for_ynab.cli.main http

smoke-stdio:
	uv run python -m mcp_server_for_ynab.cli.smoke

# ---------------------------------------------------------------------------
# Live verification
#
# The test suite validates against payloads we wrote ourselves, so a response
# model that disagrees with the real YNAB API passes it and still fails in
# production. These two targets are the checks that close that gap. Both need
# real credentials in .env and are therefore not part of `make check`.
#
# verify-live:      invoke every read-only tool against the live API
# verify-write:     invoke every write tool against a disposable plan
# verify-mcp-http:  walk the MCP HTTP handshake with curl on a throwaway port
#
# verify-write creates and deletes data. It requires an explicit plan id and
# never falls back to YNAB_PLAN_ID:
#
#   make verify-write PLAN_ID=<disposable-plan-uuid>
# ---------------------------------------------------------------------------

verify-live: .env
	@set -a && . ./.env && set +a && uv run python scripts/live_read_sweep.py

verify-write: .env
	@test -n "$(PLAN_ID)" || { \
		echo "ERROR: set PLAN_ID to a disposable plan, e.g. make verify-write PLAN_ID=<uuid>"; \
		exit 1; \
	}
	@set -a && . ./.env && set +a && uv run python scripts/live_write_sweep.py --plan-id $(PLAN_ID)

verify-mcp-http: .env
	@set -a && . ./.env && set +a && ./scripts/mcp_http_check.sh

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

# ---------------------------------------------------------------------------
# Packaging — install surfaces
#
# The Claude Code plugin, its marketplace, the MCP client config, and the MCPB
# bundle manifest all repeat the version and launch command. They are generated
# from pyproject.toml so they cannot drift; `packaging-check` is the CI guard.
#
# The .mcpb bundle is what makes desktop install one click: the host renders a
# form for the token and stores it in the OS keychain instead of asking someone
# to hand-edit JSON. Building it needs Node, for npx.
# ---------------------------------------------------------------------------

packaging-sync:
	uv run python scripts/sync_packaging.py

packaging-check:
	uv run python scripts/sync_packaging.py --check

mcpb: packaging-sync
	uv run python scripts/build_mcpb.py

# ---------------------------------------------------------------------------
# Docker
#
# stdio only — there is no port to publish. Mount a volume onto
# /home/app/.mcp-server-for-ynab when writes are enabled, or every --rm discards
# the history that makes a revert possible.
# ---------------------------------------------------------------------------

docker-build:
	docker build -t mcp-server-for-ynab .

docker-smoke: docker-build
	docker run -i --rm -e YNAB_API_KEY=fake-token-for-startup mcp-server-for-ynab smoke

# ---------------------------------------------------------------------------
# Marketing assets
#
# The README GIF and the social preview card are generated, not drawn. Every
# figure in them comes from the real tools run against a synthetic budget in
# scripts/demo/, so the demo cannot claim something the server does not do, and
# nobody's real finances are published.
#
# Re-render after any change that alters what they show: tool names, the shape
# or wording of enriched output, money formatting, or the tool count.
#
# Needs rsvg-convert and ImageMagick:  brew install librsvg imagemagick
# ---------------------------------------------------------------------------

assets:
	uv run python scripts/demo/capture.py
	uv run python scripts/demo/social.py
	uv run python scripts/demo/gif.py
	uv run python scripts/check_assets.py --write

# Fails when the assets assert something the code no longer does. Compares the
# claims (tool count, tools shown, money format), not the pixels: the renderers
# are deterministic but ImageMagick and font rendering are not stable across
# machines, and a check that fails for the wrong reason gets muted.
assets-check:
	uv run python scripts/check_assets.py
