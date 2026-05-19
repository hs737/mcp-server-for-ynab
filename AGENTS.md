# AGENTS.md

This file tells AI agents how this repository works and how to extend it correctly.

## Mission

`ynab-mcp` is an MCP server for AI agents to interact with YNAB budgets. It exposes the full YNAB API through raw tools and adds enriched AI-friendly helpers on top. The goal is safe, explicit budget management — not autonomous financial decision-making.

## Architecture map

```
src/ynab_mcp/
├── config/       env loading, runtime validation, default plan resolution
├── auth/         AuthProvider abstraction + PAT implementation
├── http_client/  async httpx wrapper: retries, error normalization, redaction
├── models/       Pydantic types: YNAB shapes, shared error model, milliunit helpers
├── ynab_client/  one module per YNAB resource family (thin async wrappers)
├── enriched/     cross-resource AI-friendly read tools
├── server/       MCP tool registry, metadata, stdio wiring
└── cli/          run-stdio entrypoint and smoke helpers
```

Request flow for a raw tool call:
```
MCP client → server/registry → ynab_client/<resource> → http_client → YNAB API
```

Request flow for an enriched tool call:
```
MCP client → server/registry → enriched/<tool> → ynab_client/* → http_client → YNAB API
```

## Tool conventions

### Classification

Every tool is tagged as one of:
- `read` — inspects YNAB data, makes no changes
- `write` — mutates YNAB data (create, update, delete)

Enriched tools in Phase 1 are all `read`. No enriched tool performs a hidden write.

### Naming

Raw tools: `<resource>_<action>` — e.g. `transactions_list`, `categories_update`
Enriched tools: `<family>_<intent>` — e.g. `triage_uncategorized_transactions`, `overview_budget_snapshot`

### Metadata

Every registered tool carries:
- `family` — tool family string
- `classification` — `"read"` or `"write"`
- `tool_type` — `"raw"` or `"enriched"`
- `summary` — one-sentence description
- `priority` — `"standard"` or `"low"` (low = niche tools like payee_locations)

## Milliunit rule

**YNAB amounts are always milliunits. `1000 = $1.00`.**

- Raw tools accept and return milliunit values for all canonical amount fields.
- Enriched tools include a `display_amount` helper string alongside milliunit values.
- If you add a tool that involves amounts, document the milliunit requirement explicitly in the tool description.
- Any future convenience dollar-input mode must be opt-in, clearly named, and routed through `models.amounts.dollars_to_milliunits()`.

## Shared error shape

All tool failures return a consistent structure. Never invent a different top-level error contract.

```python
class YnabMcpError(BaseModel):
    error_type: str   # see ErrorType enum in models/errors.py
    message: str
    status_code: int | None = None
    retry_after: int | None = None   # seconds, for rate_limited errors
    details: dict | None = None
    ynab_error_name: str | None = None
    ynab_error_id: str | None = None
```

`error_type` values: `auth_failure`, `rate_limited`, `not_found`, `validation_error`,
`conflict`, `transport_error`, `ynab_api_error`, `internal_error`

For 429 responses, always set `retry_after` when the YNAB API provides it.

## Default plan behavior

If `YNAB_PLAN_ID` is set in config, all tools that accept `plan_id` default to it.
The `plan_id` parameter is marked optional in all tool schemas when a default exists.
If called without `plan_id` and no default is configured, the tool returns a `validation_error`.

## Transfer semantics

Transfer transactions in YNAB are **paired** — each transfer creates two linked transactions across accounts. Raw mutation tools must document transfer-related fields. Enriched tools must not misclassify transfer pairs as ordinary spending or as duplicates.

## Subtransaction semantics

Split transactions use `subtransactions`. Raw transaction models always include the `subtransactions` field. List/get tools surface them. Create/update paths handle split payloads correctly where YNAB supports it.

## Delta sync

Delta-capable YNAB endpoints accept `last_knowledge_of_server` and return `server_knowledge`.
Raw tools for these endpoints expose both parameters. The tool contract must not prevent callers from doing incremental sync even when Phase 1 has no local cache.

## Mutation safety

- Raw write tools mutate only when explicitly called.
- Enriched tools never write.
- Tool descriptions for write tools must include `[WRITE]` in the summary.
- Examples in docs should demonstrate review-before-write patterns.

## How to add a raw tool

1. Add or update the Pydantic model in `models/` if the resource shape is new.
2. Add or update the async wrapper method in `ynab_client/<resource>.py`.
3. Write a contract test in `tests/contract/test_<resource>.py`.
4. Register the tool in `server/tools/<resource>.py` with correct metadata.
5. Add an integration test in `tests/integration/`.
6. Update `docs/architecture.md` if the resource family is new.

## How to add an enriched tool

1. Define the agent intent clearly — what question does this tool answer?
2. Classify it: `read` (almost always) or `write` (rare, requires justification).
3. Implement in `enriched/<family>.py`, reusing `ynab_client` methods.
4. Return structured output per the enriched output rules (scope, boundaries, findings, rationale).
5. Use the shared error shape on failure.
6. Add fixture-driven tests in `tests/unit/`.
7. Register in `server/tools/enriched.py` with metadata.
8. Keep it async throughout.

## Async rule

The entire stack is `asyncio`-based. Do not introduce sync I/O wrappers into the call path. All `ynab_client` methods are `async def`. All enriched tool methods are `async def`. Tests use `pytest-asyncio` with `asyncio_mode = "auto"`.

## Cross-phase quality gate

A change is not done unless:
- Docs are updated
- Tool descriptions match actual behavior
- Tests pass
- Milliunit rules are consistent
- Errors use the shared shape
- No hidden writes were introduced
- Quick-start flows still work
