# Architecture

## Product intent

`ynab-mcp` is an MCP server, not a consumer app. It exists to let AI agents interact with YNAB budgets safely and effectively. The product optimizes for:

- **Tool clarity** over UI
- **Explicit schemas** over loosely described behavior
- **Predictable mutations** over smart magic
- **Discoverability** for language models

## Toolchain baseline

| Concern | Choice | Why |
|---------|--------|-----|
| Python version | 3.12 | Stable, strong typing, compatible with mcp SDK |
| MCP server framework | `mcp` (official SDK) | Canonical implementation, closest to protocol source |
| Concurrency | `asyncio` end-to-end | mcp SDK is async-first; avoids sync/async impedance |
| Outbound HTTP | `httpx` | Native async, aligns with mcp SDK ecosystem |
| Data validation | `pydantic` v2 | Strict typed models, good MCP schema generation |
| Lint/format | `ruff` | Fast, single tool for both concerns |
| Type checking | `mypy` (strict) | Catches bugs before runtime |
| Testing | `pytest` + `pytest-asyncio` + `pytest-httpx` | Async-native, httpx mocking |

## Package layout

```
src/ynab_mcp/
├── config/
│   └── settings.py       env loading, YNAB_API_KEY, YNAB_PLAN_ID, LOG_LEVEL
├── auth/
│   ├── base.py           AuthProvider protocol
│   └── pat.py            PatAuthProvider — Phase 1 implementation
├── http_client/
│   └── client.py         async httpx wrapper, retries, 429 handling, redaction
├── models/
│   ├── errors.py         YnabMcpError, ErrorType enum
│   ├── amounts.py        milliunit helpers
│   ├── ynab/             typed YNAB request/response shapes (per resource)
│   └── mcp_types.py      MCP input/output schema helpers
├── ynab_client/
│   ├── base.py           shared request execution
│   ├── user.py           GET /user
│   ├── plans.py          GET /budgets, GET /budgets/{id}, GET /budgets/{id}/settings
│   ├── accounts.py       accounts resource
│   ├── categories.py     categories + category groups resource
│   ├── months.py         months resource
│   ├── payees.py         payees resource
│   ├── payee_locations.py  payee locations resource
│   ├── transactions.py   transactions resource (includes delta sync)
│   ├── scheduled_transactions.py
│   └── money_movements.py
├── enriched/
│   ├── overview.py       budget_snapshot, month_health, cash_position, available_tools
│   ├── triage.py         uncategorized, unapproved transactions
│   ├── bookkeeping.py    categorization suggestions, memo annotation, transaction history
│   └── analysis.py       overspent categories, funding gaps, upcoming risks
├── server/
│   ├── registry.py       ToolRegistry: registration, metadata storage
│   ├── tools/
│   │   ├── raw/          one file per resource family
│   │   └── enriched.py   enriched tool registrations
│   └── stdio.py          stdio server entry via mcp SDK
└── cli/
    ├── main.py           `ynab-mcp stdio` entrypoint
    └── smoke.py          smoke test helper
```

## Request flow

```
MCP client (stdio)
  → server/stdio.py          (mcp SDK handles protocol framing)
  → server/registry.py       (routes tool name to handler)
  → server/tools/raw/*.py    (raw tool handler)
    OR enriched/<family>.py  (enriched tool handler)
  → ynab_client/<resource>   (async method per YNAB endpoint)
  → http_client/client.py    (httpx, auth header, retries)
  → YNAB API
```

## Auth abstraction

`AuthProvider` is a protocol with one method: `async def get_access_token() -> str`.

Phase 1: `PatAuthProvider` reads `YNAB_API_KEY` from config and returns it directly.
Phase 3: `OAuthAuthProvider` will implement token refresh and persistence behind the same interface. No tool layer code changes are needed when OAuth is added.

## Raw vs enriched tools

**Raw tools** are thin wrappers over YNAB API endpoints. They:
- accept the same parameters the YNAB API does (normalized to snake_case)
- return the same response shapes YNAB returns (typed Pydantic models)
- expose `last_knowledge_of_server` and return `server_knowledge` on delta-capable endpoints
- are labeled `[READ]` or `[WRITE]` in their description

**Enriched tools** consolidate multi-step read workflows. They:
- accept intent-level parameters (e.g., a budget month, a transaction to classify)
- call multiple `ynab_client` methods internally
- return structured findings with rationale
- are always `read` in Phase 1
- never write to YNAB

## Default plan behavior

`YNAB_PLAN_ID` in config sets a default budget ID for all tools that accept `plan_id`.
When a default is configured, `plan_id` is an optional parameter in tool schemas.
When no default is configured and `plan_id` is not provided, tools return `validation_error`.

The YNAB API also accepts `last-used` as a budget ID sentinel. The MCP may pass this
through on supported endpoints but `YNAB_PLAN_ID` is the primary ergonomics path.

## Transfer semantics

YNAB transfer transactions are **paired** — a transfer from account A to account B
creates two linked transactions. Key implications:
- `transfer_account_id` identifies the linked account
- `transfer_transaction_id` identifies the paired transaction
- Deleting one side of a transfer affects both
- Enriched tools must not misclassify transfer pairs as duplicates or ordinary spending
- Category/memo suggestion tools skip transfers

## Subtransaction semantics

Split transactions use the `subtransactions` array on a parent transaction.
- All transaction models include `subtransactions: list[SubTransaction]`
- List/get tools surface them in the response
- Create/update tools accept them where YNAB supports it
- Enriched tools that compute amounts must sum subtransaction amounts for splits

## Delta sync

Several YNAB endpoints support incremental updates via `last_knowledge_of_server` / `server_knowledge`.
Raw tools for these endpoints:
- Accept `last_knowledge_of_server: int | None` as an optional parameter
- Return `server_knowledge: int` in their output
- Phase 1 has no local cache, but the contract does not block callers from implementing one

Delta-capable endpoints: budgets, accounts, categories, months, payees, transactions,
scheduled transactions.

## Amount convention (milliunits)

**All YNAB amounts are in milliunits. `1000 = $1.00`.**

- Raw tool inputs and outputs use milliunits for all canonical amount fields
- Enriched tool outputs include `display_amount: str` (e.g., `"$12.50"`) alongside milliunit values
- Conversion utilities live in `models/amounts.py`
- Any future dollar-input convenience mode must be opt-in and route through `models/amounts.py`

## Shared error shape

All tool failures normalize to `YnabMcpError` (see `models/errors.py`):

```
error_type    required  stable string from ErrorType enum
message       required  human-readable description
status_code   optional  HTTP status code from YNAB if applicable
retry_after   optional  seconds to wait (set for rate_limited errors)
details       optional  additional structured context
ynab_error_name  optional  YNAB's own error name field
ynab_error_id    optional  YNAB's own error ID field
```

## Testing strategy

See `docs/testing.md` for commands. The test architecture:

- **Unit tests** (`tests/unit/`) — isolated logic: config parsing, auth, models, amounts, error mapping, enriched heuristics
- **Contract tests** (`tests/contract/`) — one test file per `ynab_client` resource; verify route, payload, and response shape using `pytest-httpx` mocks
- **Integration tests** (`tests/integration/`) — full stdio startup + representative tool invocations through mocked YNAB responses
