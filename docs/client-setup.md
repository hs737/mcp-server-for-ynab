# Client Setup

This document explains how to connect `mcp-server-for-ynab` to the major current MCP clients.

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
uvx mcp-server-for-ynab stdio
```

Shared environment:
- `YNAB_API_KEY` (required)
- `YNAB_PLAN_ID` (recommended)
- `YNAB_ALLOW_WRITES=1` (optional; without it the server is read-only)

Running from a clone instead? Use `uv run --directory /path/to/mcp-server-for-ynab
python -m mcp_server_for_ynab.cli.main stdio`, where `--directory` points at the
repository root and not at `src/mcp_server_for_ynab`.

### Claude Desktop

Claude Desktop is the easiest current path for local personal use.

Config file:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

Example:

```json
{
  "mcpServers": {
    "ynab": {
      "command": "uvx",
      "args": ["mcp-server-for-ynab", "stdio"],
      "env": {
        "YNAB_API_KEY": "your_token_here",
        "YNAB_PLAN_ID": "your_plan_id_here"
      }
    }
  }
}
```

No clone and no checkout to keep up to date — `uvx` fetches the published
package. To allow writes, add `"YNAB_ALLOW_WRITES": "1"` to `env`; without it the
server is read-only and the write tools are not offered to the model.

<details>
<summary>From a local clone instead</summary>

```json
{
  "mcpServers": {
    "ynab": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp-server-for-ynab", "python", "-m", "mcp_server_for_ynab.cli.main", "stdio"],
      "env": {
        "YNAB_API_KEY": "your_token_here",
        "YNAB_PLAN_ID": "your_plan_id_here"
      }
    }
  }
}
```

`--directory` must point at the repository root, not `src/mcp_server_for_ynab`.

</details>

After saving the config, restart Claude Desktop and verify the server is available in the app’s MCP/extension tooling.

### Claude Code

Claude Code supports MCP servers and can use the same local `stdio` command shape as Claude Desktop.

Use the current Claude Code MCP setup flow from Anthropic and register this repo as a local MCP server with:
- command: `uvx`
- args: `mcp-server-for-ynab stdio`
- env:
  - `YNAB_API_KEY`
  - optional `YNAB_PLAN_ID`
  - optional `YNAB_ALLOW_WRITES=1` to enable write tools

If Claude Code offers import-from-Claude-Desktop or shared MCP configuration, the same payload can be reused.

### Cursor

Cursor supports MCP servers and can launch a local `stdio` command.

Configure an MCP server in Cursor using:
- command: `uvx`
- args: `mcp-server-for-ynab stdio`
- env:
  - `YNAB_API_KEY`
  - optional `YNAB_PLAN_ID`
  - optional `YNAB_ALLOW_WRITES=1` to enable write tools

Exact UI labels in Cursor may evolve, but the command and env payload remain the same.

### Windsurf

Windsurf supports MCP integrations for local tools and data sources.

Configure a local MCP server/plugin using:
- command: `uvx`
- args: `mcp-server-for-ynab stdio`
- env:
  - `YNAB_API_KEY`
  - optional `YNAB_PLAN_ID`
  - optional `YNAB_ALLOW_WRITES=1` to enable write tools

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

That hosted path is a separate deployment track from the current local quick
start, and it has not been built. Only the local personal-access-token setup
described above works today.

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

If the client cannot launch the server, confirm `/path/to/mcp-server-for-ynab` points to the actual local checkout.

Common mistake:
- using `/path/to/mcp-server-for-ynab/src/mcp_server_for_ynab` instead of the repo root

Use the repository root for `--directory`, because that is where `pyproject.toml`, dependencies, and project tooling are expected.

### `uv` not installed

Install `uv` first. The documented command assumes `uv` is available on your system path.

### Local client cannot launch the command

Test the command yourself first:

```bash
uv run --directory /path/to/mcp-server-for-ynab python -m mcp_server_for_ynab.cli.main stdio
```

If that fails locally, the client will not be able to launch it either.

### ChatGPT cannot use the local server

That is expected. ChatGPT custom connectors require a remote/public MCP endpoint rather than a local `stdio` command.
