# Client Setup

This document explains how to connect `ynab-mcp` to the major current MCP clients.

## What this document is for

Read this page if you need:
- client-specific setup instructions
- the difference between local `stdio` use and hosted remote use
- a compatibility summary across major MCP clients
- troubleshooting tips for common setup issues

Related docs:
- [README.md](../README.md)
- [Architecture](architecture.md)
- [Security](security.md)
- [Contributing](../CONTRIBUTING.md)

## Client Support Matrix

| Client | Current support path | Transport | Best use case | Notes |
|--------|----------------------|-----------|---------------|-------|
| Claude Desktop | Supported now | `stdio` | Easiest local setup | Best personal/local quick start |
| Claude Code | Supported now | `stdio` | CLI and dev workflow | Uses the same local server command |
| Cursor | Supported now | `stdio` | Coding workflow | Configure as an MCP server in Cursor |
| Windsurf | Supported now | `stdio` | Coding workflow | Configure as an MCP plugin/server |
| ChatGPT custom connectors | Hosted path only | remote MCP | Public or hosted connector workflow | Requires a remote endpoint and public app requirements |

## Local stdio Clients

These clients are the best fit for the current local PAT-based mode.

Shared command:

```bash
uv run --directory /path/to/ynab-mcp python -m ynab_mcp.cli.main stdio
```

Important:
- `--directory` should point to the **repository root**
- do **not** point it at `src/ynab_mcp`
- correct example: `/path/to/ynab-mcp`
- incorrect example: `/path/to/ynab-mcp/src/ynab_mcp`

Shared environment:
- `YNAB_API_KEY`
- optional `YNAB_PLAN_ID`

### Claude Desktop

Claude Desktop is the easiest current path for local personal use.

Config file:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

Example:

```json
{
  "mcpServers": {
    "ynab": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ynab-mcp", "python", "-m", "ynab_mcp.cli.main", "stdio"],
      "env": {
        "YNAB_API_KEY": "your_token_here",
        "YNAB_PLAN_ID": "your_plan_id_here"
      }
    }
  }
}
```

After saving the config, restart Claude Desktop and verify the server is available in the app’s MCP/extension tooling.

The `--directory` value in the example must be the repo root, not the `src/ynab_mcp` package directory.

### Claude Code

Claude Code supports MCP servers and can use the same local `stdio` command shape as Claude Desktop.

Use the current Claude Code MCP setup flow from Anthropic and register this repo as a local MCP server with:
- command: `uv`
- args: `run --directory /path/to/ynab-mcp python -m ynab_mcp.cli.main stdio`
- env:
  - `YNAB_API_KEY`
  - optional `YNAB_PLAN_ID`

If Claude Code offers import-from-Claude-Desktop or shared MCP configuration, the same payload can be reused.

### Cursor

Cursor supports MCP servers and can launch a local `stdio` command.

Configure an MCP server in Cursor using:
- command: `uv`
- args: `run --directory /path/to/ynab-mcp python -m ynab_mcp.cli.main stdio`
- env:
  - `YNAB_API_KEY`
  - optional `YNAB_PLAN_ID`

Exact UI labels in Cursor may evolve, but the command and env payload remain the same.

### Windsurf

Windsurf supports MCP integrations for local tools and data sources.

Configure a local MCP server/plugin using:
- command: `uv`
- args: `run --directory /path/to/ynab-mcp python -m ynab_mcp.cli.main stdio`
- env:
  - `YNAB_API_KEY`
  - optional `YNAB_PLAN_ID`

Exact UI labels may change, but this repo is still just a local `stdio` MCP server from the client’s perspective.

## Hosted / Remote Clients

### ChatGPT Custom Connectors

ChatGPT custom connectors use MCP, but they expect a remotely reachable endpoint rather than launching a local `stdio` process.

Important distinction:
- the current repo’s local PAT-based quick start is **not** the same thing as a ChatGPT connector deployment
- ChatGPT cannot use the local `stdio` flow directly

To use this repo with ChatGPT as a custom connector, you will need a hosted/public path such as:
- a public HTTPS MCP endpoint
- public-facing privacy/legal pages
- branding/domain compliance
- likely OAuth for a real public multi-user connector

That hosted path is a separate deployment track from the current local quick start.

Until the hosted OAuth/public app docs are added, treat ChatGPT support as:
- conceptually compatible with MCP
- not a local plug-and-play README quick start

## Which Client Should I Use?

- **Claude Desktop**: best local quick start for personal use
- **Claude Code**: best if you want MCP access inside a CLI/dev workflow
- **Cursor**: best for editor-based coding workflows
- **Windsurf**: best for editor-based coding workflows in Windsurf
- **ChatGPT**: best for a future hosted public connector path, not the current local PAT setup

## Troubleshooting

### `YNAB_API_KEY` missing

Make sure the client config passes `YNAB_API_KEY` into the MCP server environment.

### `YNAB_PLAN_ID` not set and no explicit `plan_id` provided

Set `YNAB_PLAN_ID` in the client env or pass `plan_id` in tool calls when needed.

### Wrong repo path

If the client cannot launch the server, confirm `/path/to/ynab-mcp` points to the actual local checkout.

Common mistake:
- using `/path/to/ynab-mcp/src/ynab_mcp` instead of the repo root

Use the repository root for `--directory`, because that is where `pyproject.toml`, dependencies, and project tooling are expected.

### `uv` not installed

Install `uv` first. The documented command assumes `uv` is available on your system path.

### Local client cannot launch the command

Test the command yourself first:

```bash
uv run --directory /path/to/ynab-mcp python -m ynab_mcp.cli.main stdio
```

If that fails locally, the client will not be able to launch it either.

### ChatGPT cannot use the local server

That is expected. ChatGPT custom connectors require a remote/public MCP endpoint rather than a local `stdio` command.
