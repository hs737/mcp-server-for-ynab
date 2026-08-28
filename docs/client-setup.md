# Client Setup

Connect `mcp-server-for-ynab` to your MCP client. Each section below is a
copy-paste command or config block.

Jump to your client:

| Client | Setup |
|--------|-------|
| [Claude Code](https://claude.com/product/claude-code) | [one command](#claude-code) |
| [Claude Desktop](https://claude.ai/download) | [config file](#claude-desktop) |
| [Cursor](https://cursor.com) | [one-click link](#cursor) |
| [VS Code](https://code.visualstudio.com) (GitHub Copilot) | [one command](#vs-code) |
| [Codex CLI](https://developers.openai.com/codex) | [one command](#codex-cli) |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | [one command](#gemini-cli) |
| [Windsurf](https://windsurf.com), [Zed](https://zed.dev), others | [generic stdio config](#other-stdio-clients) |
| [MCP Inspector](https://github.com/modelcontextprotocol/inspector) | [debugging](#mcp-inspector) |

Related docs:
- [README](../README.md)
- [Security](security.md)
- [Tool Surface](tool-surface.md)
- [Architecture](architecture.md)

## Before You Start

You need two things.

**1. `uv`**, which provides the `uvx` command that runs the server:

```bash
# macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# macOS with Homebrew
brew install uv

# Windows
winget install --id=astral-sh.uv -e
```

**2. A YNAB personal access token.** Generate one at
[app.ynab.com/settings/developer](https://app.ynab.com/settings/developer). The
token can read and modify every budget in your account, so treat it like a
password — see [Security](security.md).

Optionally, grab your plan ID — YNAB calls it a budget ID. Open your budget in a
browser and copy the UUID from the address bar. Setting `YNAB_PLAN_ID` makes
`plan_id` optional on most tools, which is worth doing if you have one budget.

Check that both work before touching any client config:

```bash
YNAB_API_KEY=your_token uvx mcp-server-for-ynab smoke
```

Expected output:

```
smoke: checking environment and startup...
smoke: YNAB_API_KEY present (length=64)
smoke: YNAB_PLAN_ID not set (plan_id required per-call)
smoke: app created, 44 tools registered
smoke: tool registry has 44 entries across families: ['accounts', 'analysis', ...]
smoke: OK
```

`smoke` validates configuration and tool registration, then exits. It makes no
YNAB API calls and changes nothing.

## What Every Client Needs

All clients run the same local process. Only the file format differs.

| Field | Value |
|-------|-------|
| Command | `uvx` |
| Arguments | `mcp-server-for-ynab stdio` |
| Transport | `stdio` |
| Required env | `YNAB_API_KEY` |
| Recommended env | `YNAB_PLAN_ID` |
| Optional env | `YNAB_ALLOW_WRITES=1` to register write tools |

Most clients accept this JSON:

```json
{
  "mcpServers": {
    "ynab": {
      "command": "uvx",
      "args": ["mcp-server-for-ynab", "stdio"],
      "env": {
        "YNAB_API_KEY": "your_ynab_token",
        "YNAB_PLAN_ID": "your_plan_id"
      }
    }
  }
}
```

Without `YNAB_ALLOW_WRITES`, the server is read-only and the 19 write tools are
never registered. See [Enabling Writes](#enabling-writes).

## Claude Code

Add the server with one command:

```bash
claude mcp add --env YNAB_API_KEY=your_ynab_token --env YNAB_PLAN_ID=your_plan_id \
  --transport stdio --scope user ynab -- uvx mcp-server-for-ynab stdio
```

`--scope user` makes the server available in every project. Use `--scope
project` instead to write it to a `.mcp.json` your team shares, or omit the flag
to limit it to the current project. Everything after `--` is the command Claude
Code runs.

Verify:

```bash
claude mcp list
```

Look for `ynab: ... - ✔ Connected`. Inside a session, `/mcp` shows the same
thing.

To share the server with a repository, commit a `.mcp.json` at its root — but
read the token from your environment rather than committing it:

```json
{
  "mcpServers": {
    "ynab": {
      "command": "uvx",
      "args": ["mcp-server-for-ynab", "stdio"],
      "env": {
        "YNAB_API_KEY": "${YNAB_API_KEY}"
      }
    }
  }
}
```

Remove the server with `claude mcp remove ynab`.

## Claude Desktop

Open **Settings → Developer → Edit Config**, or edit the file directly:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "ynab": {
      "command": "uvx",
      "args": ["mcp-server-for-ynab", "stdio"],
      "env": {
        "YNAB_API_KEY": "your_ynab_token",
        "YNAB_PLAN_ID": "your_plan_id"
      }
    }
  }
}
```

Restart Claude Desktop, then check the tools icon in the message box for the
`ynab` server.

If the server fails to start here but works in your terminal, Claude Desktop
probably cannot find `uvx` — see
[the client cannot find `uvx`](#the-client-cannot-find-uvx).

## Cursor

Click to install, then fill in your token when Cursor opens the config:

[**Add to Cursor**](https://cursor.com/install-mcp?name=ynab&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyJtY3Atc2VydmVyLWZvci15bmFiIiwic3RkaW8iXSwiZW52Ijp7IllOQUJfQVBJX0tFWSI6IllPVVJfWU5BQl9UT0tFTiJ9fQ%3D%3D)

Or edit the config yourself — `~/.cursor/mcp.json` for every project, or
`.cursor/mcp.json` for one:

```json
{
  "mcpServers": {
    "ynab": {
      "type": "stdio",
      "command": "uvx",
      "args": ["mcp-server-for-ynab", "stdio"],
      "env": {
        "YNAB_API_KEY": "your_ynab_token",
        "YNAB_PLAN_ID": "your_plan_id"
      }
    }
  }
}
```

Cursor also reads `envFile`, so you can point at a `.env` instead of pasting the
token:

```json
{
  "mcpServers": {
    "ynab": {
      "type": "stdio",
      "command": "uvx",
      "args": ["mcp-server-for-ynab", "stdio"],
      "envFile": "/absolute/path/to/.env"
    }
  }
}
```

Confirm the server under **Settings → MCP**.

## VS Code

With GitHub Copilot installed, add the server from the command line:

```bash
code --add-mcp '{"name":"ynab","command":"uvx","args":["mcp-server-for-ynab","stdio"],"env":{"YNAB_API_KEY":"your_ynab_token"}}'
```

To keep the token out of the config, use a `.vscode/mcp.json` that prompts for
it instead. VS Code asks once and stores it in secret storage:

```json
{
  "inputs": [
    {
      "type": "promptString",
      "id": "ynab-token",
      "description": "YNAB personal access token",
      "password": true
    }
  ],
  "servers": {
    "ynab": {
      "type": "stdio",
      "command": "uvx",
      "args": ["mcp-server-for-ynab", "stdio"],
      "env": {
        "YNAB_API_KEY": "${input:ynab-token}"
      }
    }
  }
}
```

Note the top-level key is `servers`, not `mcpServers`. Open Copilot Chat in
agent mode and use the tools picker to confirm the `ynab` tools are listed.

## Codex CLI

```bash
codex mcp add ynab --env YNAB_API_KEY=your_ynab_token --env YNAB_PLAN_ID=your_plan_id \
  -- uvx mcp-server-for-ynab stdio
```

Or edit `~/.codex/config.toml`:

```toml
[mcp_servers.ynab]
command = "uvx"
args = ["mcp-server-for-ynab", "stdio"]

[mcp_servers.ynab.env]
YNAB_API_KEY = "your_ynab_token"
YNAB_PLAN_ID = "your_plan_id"
```

To keep the token out of the file, forward it from your shell environment
instead:

```toml
[mcp_servers.ynab]
command = "uvx"
args = ["mcp-server-for-ynab", "stdio"]
env_vars = ["YNAB_API_KEY", "YNAB_PLAN_ID"]
```

Verify with `codex mcp list`.

## Gemini CLI

```bash
gemini mcp add -s user -e YNAB_API_KEY=your_ynab_token -e YNAB_PLAN_ID=your_plan_id \
  ynab uvx mcp-server-for-ynab stdio
```

Or edit `~/.gemini/settings.json` for every project, or `.gemini/settings.json`
for one:

```json
{
  "mcpServers": {
    "ynab": {
      "command": "uvx",
      "args": ["mcp-server-for-ynab", "stdio"],
      "env": {
        "YNAB_API_KEY": "$YNAB_API_KEY",
        "YNAB_PLAN_ID": "$YNAB_PLAN_ID"
      }
    }
  }
}
```

Gemini CLI expands `$VAR` and `${VAR}` in `env`, so the values above come from
your shell rather than the file. Verify with `/mcp` in a session.

Leave `trust` unset. Setting it to `true` skips the confirmation dialog on every
tool call, which is the wrong default for a server holding a financial
credential.

## Other stdio Clients

Windsurf, Zed, and most other MCP clients launch a local command the same way.
Give them:

- command: `uvx`
- args: `mcp-server-for-ynab stdio`
- env: `YNAB_API_KEY`, optionally `YNAB_PLAN_ID` and `YNAB_ALLOW_WRITES=1`

Client UIs and config paths change often, so follow the client's own MCP
documentation for where the file lives. From the client's perspective this is an
ordinary local stdio server with no special requirements.

Zed is the one common exception to the JSON shape above: it nests the command
under a `context_servers` key rather than `mcpServers`. Check Zed's current MCP
docs for the exact schema.

## MCP Inspector

To see the tools, call them by hand, and read raw responses:

```bash
YNAB_API_KEY=your_ynab_token npx @modelcontextprotocol/inspector uvx mcp-server-for-ynab stdio
```

The Inspector opens in a browser. The **Tools** tab lists all 44 read-only tools
and lets you run one with arguments you choose. `overview_available_tools` is a
good first call — it returns the tool catalog grouped by family and costs no
YNAB API requests.

If the server reports a missing `YNAB_API_KEY`, add it in the Inspector's
**Environment Variables** panel and reconnect. The Inspector does not always
forward the whole parent environment to the process it spawns.

This is the fastest way to tell a server problem apart from a client problem. If
the Inspector works and your client does not, the fault is in the client config.

## Verify It Works

Ask your client:

> Using the ynab tools, call overview_available_tools and tell me how many tools are registered.

A working read-only setup reports 44 tools. With `YNAB_ALLOW_WRITES=1`, it
reports 63.

Then try a real read:

> What's my current cash position across all accounts?

## Enabling Writes

The server starts read-only. Write tools are not registered unless you opt in:

```json
"env": {
  "YNAB_API_KEY": "your_ynab_token",
  "YNAB_ALLOW_WRITES": "1"
}
```

Note the string `"1"`, not the number `1`. Environment variables are strings,
and some clients reject a config that uses a number here.

Without it, the write tools are absent from `tools/list` entirely, so an agent
cannot call them. Every write is recorded before it happens and most can be
undone with `history_revert`. Read [Write Tools](../README.md#write-tools)
before turning this on.

## Running from a Clone

For development, point the client at your checkout instead of the published
package:

```json
{
  "mcpServers": {
    "ynab": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/mcp-server-for-ynab",
        "python",
        "-m",
        "mcp_server_for_ynab.cli.main",
        "stdio"
      ],
      "env": {
        "YNAB_API_KEY": "your_ynab_token"
      }
    }
  }
}
```

`--directory` must point at the repository root — the directory holding
`pyproject.toml` — not at `src/mcp_server_for_ynab`.

## ChatGPT Custom Connectors

Not supported. ChatGPT connectors call a remote HTTPS endpoint; they cannot
launch a local stdio process, and no hosted deployment of this server exists.

Building one would need a public HTTPS MCP endpoint, OAuth in place of personal
access tokens, and public-app compliance work. That belongs in a separate
repository, which is why this package exposes an embed surface rather than
carrying OAuth and session code. See [Architecture](architecture.md).

## Troubleshooting

### The client cannot find `uvx`

The most common failure, and it affects desktop apps in particular. Apps
launched from Finder or the Start menu do not inherit your shell `PATH`, so
`uvx` resolves in your terminal but not in the client.

Find the absolute path:

```bash
which uvx     # macOS and Linux, e.g. /Users/you/.local/bin/uvx
where uvx     # Windows
```

Then use that path as `command`:

```json
"command": "/Users/you/.local/bin/uvx"
```

Write the path out in full. `~` is not expanded in these config files.

### `Required environment variable 'YNAB_API_KEY' is not set`

The client did not pass the variable through. Env vars exported in your shell do
not reach a client-launched process — put the token in the client's own `env`
block, or use a mechanism the client supports for reading it, such as Cursor's
`envFile` or Codex's `env_vars`.

The server exits immediately with this one line on stderr, so a client that
shows you any server output at all will show you this.

### `plan_id is required`

Either set `YNAB_PLAN_ID` in the client's `env`, or pass `plan_id` explicitly on
each tool call. The ID is the UUID in your YNAB browser URL. `plans_list`
returns every plan ID on the account, so you can also just ask the agent for it.

### The write tools are missing

That is the default. Set `YNAB_ALLOW_WRITES=1` — see
[Enabling Writes](#enabling-writes).

### `Local request budget exhausted`

YNAB allows 200 requests per hour per token, and this server stops at 190 so the
limit you hit is a clear local error rather than a 429 mid-workflow. Call
`overview_request_budget` for how many requests remain, and, once the budget is
spent, how many seconds until the next one frees up. It costs no requests.
Raise the ceiling with `YNAB_RATE_LIMIT_PER_HOUR` if you understand the
tradeoff.

### The server fails to start, and the client only says "failed"

Run the same command yourself. Client error panels rarely show the real reason:

```bash
YNAB_API_KEY=your_ynab_token uvx mcp-server-for-ynab smoke
```

If that fails, the client cannot work either, and the output tells you why. If
it succeeds, the problem is the client config — usually the `uvx` path or a
missing env var.

Include the version when reporting a problem — it needs no token:

```bash
uvx mcp-server-for-ynab --version
```

For more detail, raise the log level with `LOG_LEVEL=DEBUG` in the client's
`env`. Logs go to stderr, which most clients surface in an MCP log panel.
Credentials are redacted.
