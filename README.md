# MCP for YNAB

An AI-first [Model Context Protocol](https://modelcontextprotocol.io/) server for [YNAB](https://ynab.com). It exposes the YNAB API as MCP tools for AI agents, then adds enriched read-only tools for orientation, triage, and bookkeeping workflows.

**Read-only by default.** Write tools are not registered unless you opt in with
`YNAB_ALLOW_WRITES=1`. See [Write Tools](#write-tools).

This repo is structured so a contributor or AI agent can answer three questions quickly:
- where the MCP server lives
- where YNAB API wrappers and models live
- where to add new tools, tests, and docs

## What this document is for

Read this page if you need:
- a quick understanding of the product
- local setup and run commands
- a map of the repository docs
- a high-level view of the architecture

Next reads:
- [Client Setup](docs/client-setup.md)
- [Architecture](docs/architecture.md)
- [Repo Structure](docs/repo-structure.md)
- [Tool Surface](docs/tool-surface.md)
- [Testing](docs/testing.md)
- [Security](docs/security.md)
- [Contributing](CONTRIBUTING.md)
- [Agent Guidance](AGENTS.md)
- [Docs Index](docs/README.md)
- [Legal Notice](NOTICE.md)
- [Postman Notes](postman/README.md)

## High-Level Architecture

```mermaid
flowchart LR
    A["MCP Client"] --> B["FastMCP Server"]
    B --> C["Tool Handlers"]
    C --> D["ynab_client"]
    D --> E["http_client (httpx)"]
    E --> F["YNAB API"]
    C --> G["enriched/"]
    G --> D
```

## What it does

The server exposes two kinds of tools:

- **Raw tools**: close mirrors of YNAB endpoints. Use these for exact reads and all writes.
- **Enriched tools**: AI-friendly helpers that combine multiple reads into clearer workflows. Use these for orientation, investigation, and analysis.

Every tool is labeled `read` or `write`. Enriched tools do not perform hidden writes.

## How the Repo Is Organized

The code is centered around a small set of layers:

- `src/mcp_server_for_ynab/server/`: FastMCP app, tool metadata, tool registration, error boundary
- `src/mcp_server_for_ynab/ynab_client/`: one async wrapper module per YNAB resource family
- `src/mcp_server_for_ynab/http_client/`: outbound `httpx` wrapper with retries, redaction, and error normalization
- `src/mcp_server_for_ynab/models/`: typed YNAB shapes, shared error model, milliunit helpers
- `src/mcp_server_for_ynab/enriched/`: higher-level read-only workflows built on top of raw clients
- `tests/`: unit, contract, integration, and QA/Postman source assets

For the full tree and “where do I put X?” guidance, read [Repo Structure](docs/repo-structure.md).

## Quick Start

### 1. Get a YNAB Personal Access Token

Go to [app.ynab.com/settings/developer](https://app.ynab.com/settings/developer) and generate a token.

### 2. Install

Nothing to clone. With [uv](https://docs.astral.sh/uv/):

```bash
uvx mcp-server-for-ynab smoke
```

`uvx` fetches the package and runs it in a throwaway environment. The `smoke`
subcommand checks configuration and tool registration, then exits — a safe first
command.

<details>
<summary>From a clone, for development</summary>

```bash
git clone https://github.com/hs737/mcp-server-for-ynab
cd mcp-server-for-ynab
uv sync
make smoke-stdio
```

</details>

### 3. Configure

Set `YNAB_API_KEY` in the environment, or in your MCP client's config (see
[Client Setup](docs/client-setup.md)). For local development, copy the example
file:

```bash
cp .env.example .env
# Edit .env: set YNAB_API_KEY and optionally YNAB_PLAN_ID
```

Most users have one budget. If you set `YNAB_PLAN_ID`, tools that accept `plan_id` can default to it.

The server starts **read-only**. Set `YNAB_ALLOW_WRITES=1` when you want an agent
to be able to change budget data — see [Write Tools](#write-tools).

### 4. Run Over stdio

```bash
YNAB_API_KEY=... uvx mcp-server-for-ynab stdio
```

From a clone, `make run-stdio` does the same thing.

## Use with MCP Clients

This repo works best today as a local `stdio` MCP server.

- easiest local path: **Claude Desktop**
- also suitable for: **Claude Code**, **Cursor**, and **Windsurf**
- hosted connector path: **ChatGPT custom connectors** require a remote/public MCP deployment rather than the local PAT quick start

For client-specific setup instructions, see [docs/client-setup.md](docs/client-setup.md).
A hosted/public connector is **not implemented**. The intent is for it to live
in its own repository so OAuth and public-app concerns stay out of this package;
the core exposes an embed surface for that purpose. Today this is a local,
personal-access-token server only.

## Tool Families

Start with `overview_available_tools`. It returns the current tool catalog grouped by family, including raw vs enriched classification and low-priority families.

| Family | Type | Purpose |
|--------|------|---------|
| `overview` | enriched | Budget health snapshots and orientation |
| `triage` | enriched | Transaction cleanup queues |
| `bookkeeping` | enriched | Categorization suggestions, memo help, history |
| `analysis` | enriched | Spending analysis, funding gaps, scheduled risks |
| `user` | raw | YNAB user info |
| `plans` | raw | Plan and settings reads |
| `accounts` | raw | Account reads and creation |
| `categories` | raw | Categories and category groups |
| `months` | raw | Month-level budget data |
| `payees` | raw | Payee management |
| `payee_locations` | raw | Geographic payee metadata, niche/low-priority |
| `transactions` | raw | Transaction CRUD and import trigger |
| `scheduled_transactions` | raw | Scheduled transaction management |
| `money_movements` | raw | Money movement data |
| `history` | enriched | Review and roll back writes this server made |

More detail: [Tool Surface](docs/tool-surface.md)

## Write Tools

Write tools are **not registered unless you opt in**:

```bash
YNAB_ALLOW_WRITES=1
```

Without it the server is read-only, and the write tools are absent from
`tools/list` — an agent cannot call what it cannot see. This is deliberate: the
server holds a credential that can modify real financial records, and refusing a
call at execution time would still advertise the capability.

### Every write is recorded, and most can be undone

When writes are enabled, each one records the state that existed *before* it.
YNAB has no history endpoint, so this is the only way to get an overwritten
value back.

| Tool | Purpose |
|------|---------|
| `history_list` | Recent writes, newest first, each marked revertible or not |
| `history_show` | One entry in full, including the before state |
| `history_revert` | Undo one write |
| `history_revert_to` | Roll the plan back to its state at a chosen entry |

`history_revert_to` undoes everything after the entry you name, newest first,
because overlapping edits to the same record only compose correctly in reverse.
Reverting is itself recorded, so a revert can be reverted.

**What cannot be undone.** YNAB has no delete route for accounts, categories,
category groups, or payees, so creating one is permanent. Those operations are
recorded as non-revertible with the reason, and a rollback reports them under
`blocked` rather than skipping them silently — an incomplete rollback that
claims success is worse than one that tells you what it left behind. A
recreated transaction also gets a new id and loses any bank-import link.

### Writes are checked, not assumed

Tools that change a value re-read it afterwards and report a `verification`
block. A 200 response is not proof: YNAB accepts `budgeted` on the category
update route, returns 200, and ignores it. Verification is what catches that.

## Where to Read Next

If you are:

- **trying to connect a client**: read [Client Setup](docs/client-setup.md)
- **new to the repo**: read [Architecture](docs/architecture.md)
- **adding code**: read [Contributing](CONTRIBUTING.md), [Repo Structure](docs/repo-structure.md), and [Agent Guidance](AGENTS.md)
- **adding or changing tools**: read [Tool Surface](docs/tool-surface.md)
- **verifying behavior**: read [Testing](docs/testing.md)
- **working on auth, error handling, or logging**: read [Security](docs/security.md)

## Common Contributor Paths

### Add a raw tool

Read:
- [Contributing](CONTRIBUTING.md)
- [Repo Structure](docs/repo-structure.md)
- [Architecture](docs/architecture.md)
- [Agent Guidance](AGENTS.md)

### Add an enriched tool

Read:
- [Contributing](CONTRIBUTING.md)
- [Tool Surface](docs/tool-surface.md)
- [Architecture](docs/architecture.md)
- [Agent Guidance](AGENTS.md)

### Run the server

```bash
make run-stdio
make run-http
```

### Run tests

```bash
make test
make test-unit
make test-contract
make test-integration
make test-postman-operator
```

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `YNAB_API_KEY` | Yes | YNAB personal access token |
| `YNAB_PLAN_ID` | Recommended | Default plan ID to make `plan_id` optional on most tools |
| `YNAB_ALLOW_WRITES` | No | Register write tools. Off means read-only |
| `YNAB_HISTORY_PATH` | No | Write history file, default `~/.mcp-for-ynab/history.jsonl` |
| `YNAB_RATE_LIMIT_PER_HOUR` | No | Client-side request budget, default `190` of YNAB's 200 |
| `YNAB_RATE_WARN_THRESHOLD` | No | Warn when this many requests remain, default `50` |
| `LOG_LEVEL` | No | Logging verbosity, default `INFO` |

### Rate limits

YNAB allows 200 requests per hour per token, and a single enriched tool can
spend several. The server tracks its own usage in a rolling hour and stops
just below YNAB's ceiling, so the limit you hit is local and clearly reported
rather than a 429 in the middle of a workflow. Call `overview_request_budget`
to see what is left; it costs no API requests.

## Amount Convention

All YNAB monetary amounts are in **milliunits**: `1000 = $1.00`.

- Raw tools accept and return milliunits for canonical amount fields.
- Enriched tools may include display helpers alongside canonical values.

## Current State

The current implementation uses:
- Python 3.12
- `FastMCP` from the official `mcp` package
- `asyncio` end to end
- `httpx` for outbound YNAB calls
- built-in stdio and streamable HTTP transports from the current FastMCP stack

Hosted runtimes should import the core package through its embed surface instead
of adding OAuth, session, or database code to this repo. No hosted runtime
exists yet.

If architecture and implementation ever diverge, the source of truth should be [Architecture](docs/architecture.md), updated to reflect the actual code.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).

## Disclaimer

We are not affiliated, associated, or in any way officially connected with YNAB or any of its subsidiaries or affiliates. The official YNAB website can be found at [https://www.ynab.com](https://www.ynab.com).

The names YNAB and You Need A Budget, as well as related names, tradenames, marks, trademarks, emblems, and images are registered trademarks of YNAB.

## Your Data

This server stores exactly one thing on your machine: a record of the writes it
made, used by `history_revert`. Nothing is sent anywhere except `api.ynab.com`,
and there is no telemetry.

```bash
uvx mcp-server-for-ynab history --show          # where it is, how much is there
uvx mcp-server-for-ynab history --export out.json
uvx mcp-server-for-ynab history --delete        # also removes the ability to revert
```

These need no credentials and no agent: getting your data back, or gone, should
not require running an LLM.
