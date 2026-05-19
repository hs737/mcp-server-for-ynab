# Testing

## Commands

```bash
make lint            # ruff check .
make format          # ruff format .
make typecheck       # mypy src
make test            # all tests
make test-unit       # tests/unit only
make test-contract   # tests/contract only
make test-integration  # tests/integration only
make check           # lint + typecheck + all tests
make smoke-stdio     # quick smoke: start server, call overview_budget_snapshot, exit
```

Or call pytest directly for more control:

```bash
uv run pytest tests/unit/test_models/ -v
uv run pytest tests/contract/test_transactions.py -v -k "delta"
uv run pytest -x --tb=short    # stop on first failure
```

## Required environment for tests

Unit and contract tests run entirely against mocked HTTP — no real YNAB credentials needed.

Integration tests also run against mocked HTTP by default.

The smoke test (`make smoke-stdio`) requires a real `YNAB_API_KEY` and optionally `YNAB_PLAN_ID`.
Set them in `.env` or export them before running.

## Test categories

### Unit tests (`tests/unit/`)

Test isolated logic with no external I/O.

Covers:
- `config/` — env loading, default plan resolution, validation errors
- `auth/` — PAT provider: token loading, error on missing key
- `http_client/` — retry logic, backoff, error mapping, header redaction
- `models/` — milliunit conversions, error shape construction, amount display formatting
- `enriched/` — heuristic logic: categorization scoring, memo pattern detection

### Contract tests (`tests/contract/`)

One test file per `ynab_client` resource. Each verifies:
- Correct HTTP method and URL path
- Query parameter serialization
- Request body shape for mutations
- Response parsing into typed models
- Delta sync parameters (`last_knowledge_of_server`, `server_knowledge`)
- Error mapping (401 → `auth_failure`, 404 → `not_found`, 429 → `rate_limited`)
- Special cases: subtransactions, transfer fields, partial success on bulk update

Uses `pytest-httpx` (`respx`) to mock at the transport layer.

Special contract tests required:
- `test_payees.py` — verify `payees_create` route (added in YNAB v1.81.0)
- `test_plans.py` — verify `plans_get_settings` returns settings object
- `test_transactions.py` — verify `transactions_trigger_import` hits the correct endpoint,
  not an upload endpoint; verify `transactions_bulk_update` partial-success shape

### Integration tests (`tests/integration/`)

Verify the full MCP server stack with mocked YNAB responses.

Covers:
- stdio server startup and graceful shutdown
- representative raw read tool: `accounts_list`
- representative raw write tool: `transactions_create` (via mock)
- representative enriched tool: `overview_budget_snapshot`
- default `YNAB_PLAN_ID` resolution behavior
- `overview_available_tools` returns expected structure
- shared error shape at the tool boundary (401 → structured error)

## Fixture strategy

Fixtures live in `tests/fixtures/`. Start small and expand when a test requires it.

Core fixtures (always present):
- `healthy_budget.json` — single plan, normal accounts and categories
- `overspent_budget.json` — budget with several overspent categories
- `uncategorized_transactions.json` — budget with uncategorized transactions
- `auth_failure.json` — YNAB 401 response body
- `rate_limit.json` — YNAB 429 response body

Expand as needed:
- `transfer_transactions.json` — transaction list with transfer pairs
- `split_transactions.json` — transactions with subtransactions
- `scheduled_pressure.json` — scheduled transactions causing upcoming funding gaps
- `bulk_update_partial.json` — bulk update response with mixed success/failure

## Async testing

All tests that touch async code use `pytest-asyncio`. The `pyproject.toml` sets
`asyncio_mode = "auto"` so `async def test_*` functions run automatically without
requiring `@pytest.mark.asyncio`.

```python
async def test_accounts_list_parses_response(httpx_mock):
    httpx_mock.add_response(json=load_fixture("healthy_budget.json"))
    client = AccountsClient(...)
    result = await client.list(plan_id="abc")
    assert len(result.accounts) > 0
```

## Phase 2 additions

When HTTP transport is added:
- `test-postman` target via Newman
- HTTP integration tests
- Transport parity checks (same tool, same response via stdio and HTTP)

## Phase 3 additions

When OAuth is added:
- OAuth flow unit tests
- Token refresh tests
- Auth-mode matrix: PAT path still works after OAuth is added
