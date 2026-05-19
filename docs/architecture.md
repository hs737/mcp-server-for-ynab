# Architecture

This document describes the current implementation of `ynab-mcp`.

## What this document is for

Read this page if you need:
- the actual package and layer structure
- request flow through the server
- error flow and tool boundary behavior
- current implementation notes where code differs from older plans

Adjacent docs:
- [Repo Structure](repo-structure.md)
- [Tool Surface](tool-surface.md)
- [Testing](testing.md)
- [Security](security.md)
- [OAuth Architecture](oauth-architecture.md)
- [Agent Guidance](../AGENTS.md)

## Deployment Modes

This repo is evolving from a local-first tool into a dual-mode product. Both modes expose the same logical tool surface. The auth and transport layers differ.

### Current mode: local self-hosted (PAT)

```mermaid
flowchart LR
    A["Local MCP client\n(Claude Desktop, etc.)"] -->|stdio| B["FastMCP server\n(local process)"]
    B --> C["PAT auth\n(YNAB_API_KEY env var)"]
    C --> D["YNAB API"]
```

- Auth: Personal Access Token from environment variable
- Transport: stdio
- Users: single user per process
- Deployment: local machine

### Planned mode: hosted OAuth (Cloudflare Worker)

```mermaid
flowchart LR
    A["Public MCP client\n(any user)"] -->|HTTP| B["Cloudflare Worker"]
    B --> C["OAuth token store\nper-user grant record"]
    C --> D["YNAB API"]
```

- Auth: per-user OAuth access token + refresh token
- Transport: streamable HTTP
- Users: multi-user
- Deployment: Cloudflare Worker
- Status: planned — not yet implemented

The OAuth design is documented in [OAuth Architecture](oauth-architecture.md). Implementation begins after the public/legal layer is in place.

## Product Model

`ynab-mcp` is an MCP server for AI agents. It exposes:
- raw tools that mirror the YNAB API closely
- enriched tools that consolidate common read workflows into more discoverable agent-facing operations

The system is optimized for:
- explicit tool contracts
- predictable writes
- agent discoverability
- async I/O across the stack

## Current Technical Baseline

| Concern | Current implementation |
|---------|------------------------|
| Python | 3.12 |
| Concurrency | `asyncio` |
| MCP framework | `FastMCP` from the `mcp` package |
| Outbound HTTP | `httpx` |
| Validation/models | `pydantic` v2 |
| Test stack | `pytest`, `pytest-asyncio`, `pytest-httpx` |

## Current State Notes

- The current server uses `FastMCP`, not a hand-built lower-level protocol layer.
- The CLI supports both `stdio` and HTTP transports today.
- HTTP transport currently runs through FastMCP’s built-in streamable HTTP mode rather than a dedicated `http_transport` package.
- Structured tool errors are handled through `server/tools/boundary.py`.

These are implementation truths and should be preferred over older planning assumptions.

## Package and Layer Overview

```mermaid
flowchart TD
    A["cli/"] --> B["server/app.py"]
    B --> C["server/tools/"]
    C --> D["server/tools/boundary.py"]
    C --> E["enriched/"]
    C --> F["ynab_client/"]
    F --> G["http_client/client.py"]
    G --> H["YNAB API"]
    F --> I["models/ynab/"]
    E --> F
    B --> J["server/context.py"]
    J --> F
    J --> K["auth/"]
    B --> L["server/registry.py"]
```

## Package Layout

```text
src/ynab_mcp/
├── auth/           auth abstraction and PAT provider
├── cli/            stdio/http entrypoints and smoke helper
├── config/         settings and environment loading
├── enriched/       consolidated read-only workflows
├── http_client/    outbound httpx client for YNAB API calls
├── models/         shared errors, amount helpers, typed YNAB models
├── server/         FastMCP app, context, metadata, tool boundary, tool registration
└── ynab_client/    async resource wrappers over the YNAB API
```

## Responsibilities by Layer

### `config/`

Loads runtime configuration:
- `YNAB_API_KEY`
- optional `YNAB_PLAN_ID`
- `LOG_LEVEL`

Also owns default plan resolution via `Settings.resolve_plan_id()`.

### `auth/`

Owns access token retrieval.

Current implementation:
- PAT-only via `PatAuthProvider`

Planned future change:
- OAuth provider can be added behind the same interface later

### `http_client/`

Owns outbound YNAB API concerns:
- auth header injection
- retries and backoff
- rate-limit handling
- header redaction
- normalization into the shared error contract

### `models/`

Owns:
- milliunit helpers
- shared `YnabMcpError`
- typed YNAB request/response models

### `ynab_client/`

Owns async wrappers around YNAB resource families:
- plans
- accounts
- categories
- months
- payees
- transactions
- scheduled transactions
- money movements

This is where YNAB route semantics belong, not in the server layer.

### `enriched/`

Owns higher-level read workflows, including:
- overview
- triage
- bookkeeping guidance
- analysis

These modules combine multiple raw reads into structured agent-friendly outputs.

### `server/`

Owns MCP-facing concerns:
- FastMCP application factory
- shared app context
- tool metadata registry
- raw and enriched tool registration
- structured tool error boundary
- deterministic MCP-native pagination envelopes for oversized list responses

### `cli/`

Owns entrypoints only:
- `stdio`
- HTTP/streamable HTTP
- smoke validation

Business logic should not accumulate here.

## Raw Request Lifecycle

```mermaid
sequenceDiagram
    participant Client as MCP client
    participant App as FastMCP app
    participant Tool as raw tool handler
    participant Boundary as tool_handler boundary
    participant Ctx as AppContext
    participant YClient as ynab_client
    participant Http as http_client
    participant YNAB as YNAB API

    Client->>App: invoke raw tool
    App->>Boundary: wrapped handler call
    Boundary->>Tool: execute handler
    Tool->>Ctx: get_app_context()
    Tool->>Ctx: resolve plan_id
    Tool->>YClient: call resource method
    YClient->>Http: request(...)
    Http->>YNAB: HTTP request
    YNAB-->>Http: JSON response
    Http-->>YClient: parsed dict or YnabMcpException
    YClient-->>Tool: typed model
    Tool->>Tool: optional MCP-side pagination slice
    Tool-->>Boundary: result dict
    Boundary-->>App: dict payload
    App-->>Client: MCP tool result
```

Current implementation note:
- the `transactions_list*` raw tools use stateless MCP-side `limit` and `offset` parameters to keep payloads under client size limits
- YNAB route wrappers remain unchanged; the tool layer slices the already-filtered typed response and returns `items`, `count`, `total_available`, `has_more`, and optional `next_offset`

## Enriched Request Lifecycle

```mermaid
sequenceDiagram
    participant Client as MCP client
    participant App as FastMCP app
    participant Tool as enriched tool handler
    participant Boundary as tool_handler boundary
    participant Enriched as enriched module
    participant YClient as ynab_client
    participant Http as http_client
    participant YNAB as YNAB API

    Client->>App: invoke enriched tool
    App->>Boundary: wrapped handler call
    Boundary->>Tool: execute handler
    Tool->>Enriched: call workflow function
    Enriched->>YClient: multiple resource reads
    YClient->>Http: one or more requests
    Http->>YNAB: HTTP calls
    YNAB-->>Http: JSON responses
    Http-->>YClient: parsed dict or YnabMcpException
    YClient-->>Enriched: typed models
    Enriched-->>Tool: structured findings
    Tool-->>Boundary: result dict
    Boundary-->>App: result or structured error
    App-->>Client: MCP tool result
```

## Error Flow

```mermaid
flowchart TD
    A["YNAB/API or config failure"] --> B["http_client or settings"]
    B --> C["YnabMcpException or ConfigError"]
    C --> D["server/tools/boundary.py"]
    D --> E["YnabMcpError dict"]
    E --> F["MCP client receives structured error payload"]
```

The intended boundary behavior is:
- `YnabMcpException` becomes `{"error": ...}`
- `ConfigError` becomes `validation_error`
- unexpected exceptions become `internal_error`

The same boundary also handles pagination validation failures, such as invalid `limit` or `offset` values.

## Tool Registration Flow

```mermaid
flowchart LR
    A["server/app.py:create_app"] --> B["initialize AppContext"]
    B --> C["import server.tools.enriched"]
    B --> D["import server.tools.raw"]
    C --> E["FastMCP tool registration"]
    D --> E
    C --> F["ToolRegistry metadata"]
    D --> F
    F --> G["overview_available_tools"]
```

## AppContext and Shared Clients

`server/context.py` creates a shared `AppContext` at startup. It contains:
- settings
- one shared `YnabHttpClient`
- initialized `ynab_client` instances for each resource family

This keeps tool handlers thin and avoids recreating clients per call.

## Tool Metadata Model

`server/registry.py` stores metadata for discoverability:
- tool name
- family
- classification
- tool type (`raw` vs `enriched`)
- summary
- optional priority

This metadata is separate from FastMCP’s protocol registration and is used by `overview_available_tools`.

## Amount Convention

YNAB canonical amounts are milliunits:
- `1000 = $1.00`
- raw tools use milliunits for canonical amount fields
- enriched outputs may include display helpers

All amount conversion logic belongs in `models/amounts.py`.

## Default Plan Resolution

Most tools accept `plan_id: str | None`.

Resolution behavior:
- use the explicit tool argument if present
- otherwise use `YNAB_PLAN_ID`
- otherwise return a validation-style failure through the tool boundary

## Delta Sync

The repo supports YNAB’s delta-sync semantics where available:
- raw tools accept `last_knowledge_of_server`
- responses expose `server_knowledge`
- enriched tools may pass through relevant sync state when useful

There is no local sync cache layer in the current implementation.

## Truthfulness Rules for Future Updates

When the implementation changes, update this document if any of these move:
- package layout
- transport model
- request flow
- error boundary
- tool registration strategy

If a planned architecture differs from the current one, label it clearly as a future change rather than describing it as present reality.
