.PHONY: lint format typecheck test test-unit test-contract test-integration check smoke-stdio run-stdio

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy src

test:
	uv run pytest

test-unit:
	uv run pytest tests/unit -v

test-contract:
	uv run pytest tests/contract -v

test-integration:
	uv run pytest tests/integration -v

check: lint typecheck test

smoke-stdio:
	uv run python -m ynab_mcp.cli.smoke

run-stdio:
	uv run python -m ynab_mcp.cli.main stdio
