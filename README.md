# ynab-mcp

An AI-first [Model Context Protocol](https://modelcontextprotocol.io/) server for [YNAB](https://ynab.com). Lets AI agents read and manage your budget through a clean, predictable tool interface.

## What it does

Exposes two kinds of tools to AI agents:

- **Raw tools** — direct mirrors of the YNAB API (read + write). Use these for precise reads and all writes.
- **Enriched tools** — AI-friendly helpers that consolidate common multi-step workflows into discoverable interfaces. Use these for orientation, triage, and analysis.

Every tool is labeled `read` or `write`. Enriched tools never perform hidden writes.

## Quick start

**1. Get a YNAB Personal Access Token**

Go to [app.ynab.com/settings/developer](https://app.ynab.com/settings/developer) → Generate a new token.

**2. Install**

```bash
git clone <repo-url>
cd ynab-mcp
uv sync
```

**3. Configure**

```bash
cp .env.example .env
# Edit .env: set YNAB_API_KEY and optionally YNAB_PLAN_ID
```

Most users have one budget. Set `YNAB_PLAN_ID` and all tools will default to it without requiring you to pass it every call.

**4. Add to your MCP client**

For Claude Desktop, add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ynab": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ynab-mcp", "python", "-m", "ynab_mcp.cli.main", "stdio"],
      "env": {
        "YNAB_API_KEY": "your_token_here",
        "YNAB_PLAN_ID": "your_budget_id_here"
      }
    }
  }
}
```

**5. Verify**

```bash
make smoke-stdio
```

## Tool families

Start with `overview_available_tools` — it returns the full tool catalog grouped by family, distinguishing raw from enriched, and highlights recommended entry points.

| Family | Type | Purpose |
|--------|------|---------|
| `overview` | enriched | Budget health snapshots and orientation |
| `triage` | enriched | Transaction cleanup queues |
| `bookkeeping` | enriched | Categorization suggestions, memo help, payee history |
| `analysis` | enriched | Spending analysis, funding gaps, scheduled risks |
| `user` | raw | YNAB user info |
| `plans` | raw | Budget/plan management |
| `accounts` | raw | Account reads and creation |
| `categories` | raw | Category and category group management |
| `months` | raw | Month-level budget data |
| `payees` | raw | Payee management |
| `payee_locations` | raw | Payee geographic data (niche) |
| `transactions` | raw | Transaction CRUD, import trigger |
| `scheduled_transactions` | raw | Scheduled transaction management |
| `money_movements` | raw | Money movement data |

## Development commands

```bash
make lint            # ruff check
make format          # ruff format
make typecheck       # mypy
make test            # all tests
make test-unit       # unit tests only
make test-contract   # contract tests only
make test-integration  # integration tests only
make check           # lint + typecheck + test
make smoke-stdio     # quick smoke test against stdio transport
make run-stdio       # start the MCP server over stdio
```

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `YNAB_API_KEY` | Yes | YNAB Personal Access Token |
| `YNAB_PLAN_ID` | Recommended | Default budget ID — makes `plan_id` optional on all tools |
| `LOG_LEVEL` | No | Logging verbosity (default: `INFO`) |

## Amount convention

All YNAB amounts are in **milliunits**: `1000 = $1.00`. Raw tools accept and return milliunits. Enriched tools include human-readable `display_amount` fields alongside canonical milliunit values.

## Roadmap

- **Phase 1 (current):** PAT auth, stdio transport, full raw API coverage, enriched read tools
- **Phase 2:** HTTP transport, Postman/Newman verification, expanded enriched tools
- **Phase 3:** OAuth authorization-code flow, token refresh, hosted usage patterns

## License

MIT
