# Contributing

Thanks for contributing to `mcp-server-for-ynab`.

This project is designed to be understandable and maintainable by both humans and AI agents. Good contributions improve the code, tests, and docs together.

## What this document is for

Read this page if you need:
- the preferred contribution workflow
- local setup steps
- pull request expectations
- rules for code, tests, and docs

Related docs:
- [README.md](README.md)
- [Architecture](docs/architecture.md)
- [Repo Structure](docs/repo-structure.md)
- [Tool Surface](docs/tool-surface.md)
- [Testing](docs/testing.md)
- [Agent Guidance](AGENTS.md)

## Before You Start

Make sure you understand:
- what layer you are changing
- whether the change belongs in raw tools, enriched tools, models, or docs
- how the change will be tested
- whether the docs or diagrams need to change too

For most contributions, read these first:
1. [README.md](README.md)
2. [docs/architecture.md](docs/architecture.md)
3. [docs/repo-structure.md](docs/repo-structure.md)
4. [docs/testing.md](docs/testing.md)

## Local Setup

Requirements:
- Python 3.12
- `uv`
- optional: `newman` for Postman-based verification

Setup:

```bash
git clone <repo-url>
cd mcp-server-for-ynab
uv sync
cp .env.example .env
```

If you need live YNAB access for smoke checks or Postman runs, set:
- `YNAB_API_KEY`
- optionally `YNAB_PLAN_ID`

## Development Workflow

Typical workflow:

1. Create a branch for your change.
2. Make the smallest coherent change you can.
3. Add or update tests.
4. Update docs if structure, behavior, commands, or tool surface changed.
5. Run the relevant checks locally.
6. Open a pull request with a clear summary.

## What to Change Where

### Raw YNAB route behavior

Use:
- `src/mcp_server_for_ynab/ynab_client/`
- `src/mcp_server_for_ynab/models/ynab/`
- `src/mcp_server_for_ynab/server/tools/raw/`
- `tests/contract/`

### Enriched AI-facing workflows

Use:
- `src/mcp_server_for_ynab/enriched/`
- `src/mcp_server_for_ynab/server/tools/enriched.py`
- `tests/unit/`
- `tests/integration/` when MCP-boundary behavior matters

### Shared platform behavior

Use:
- `src/mcp_server_for_ynab/http_client/`
- `src/mcp_server_for_ynab/server/`
- `src/mcp_server_for_ynab/config/`
- `src/mcp_server_for_ynab/auth/`

### Docs and diagrams

Use:
- `README.md`
- `docs/`
- `AGENTS.md`
- this file

For more detail, see [docs/repo-structure.md](docs/repo-structure.md).

## Code Standards

Follow the repo’s current conventions:
- keep the stack async
- use typed models
- keep raw tools close to YNAB semantics
- keep enriched tools read-oriented unless there is a deliberate design change
- use milliunits for canonical monetary fields
- preserve the shared error shape

Do not:
- add hidden writes to enriched tools
- move YNAB route logic into the wrong layer
- add sync wrappers around async paths
- let docs drift from implementation

## Test Expectations

Every meaningful code change should come with verification.

Common commands:

```bash
make lint
make typecheck
make test
make test-unit
make test-contract
make test-integration
make check
```

Use the smallest relevant set while developing, then run broader checks before opening a PR.

Expected mapping:
- helper logic → unit tests
- new raw route wrappers → contract tests
- MCP-boundary behavior → integration tests
- generated Postman assets → `make postman-generate` and `make postman-check`

## Documentation Expectations

Documentation is part of the product.

Update docs when you change:
- package layout
- request flow
- test commands
- tool families
- configuration behavior
- legal or operational instructions

Update Mermaid diagrams when you change:
- architecture layers
- request paths
- repo structure
- tool taxonomy

Docs should be:
- truthful to the current implementation
- concise but explicit
- link-rich
- easy to scan

## Pull Request Guidelines

A good PR should include:
- what changed
- why it changed
- how it was tested
- whether docs were updated
- any follow-up work or known gaps

Keep PRs focused. Small, reviewable PRs are preferred over large mixed changes.

## Suggested PR Checklist

- [ ] Code matches the intended layer
- [ ] Tests were added or updated
- [ ] `make lint` passes
- [ ] `make typecheck` passes
- [ ] Relevant tests pass
- [ ] Docs were updated if behavior or structure changed
- [ ] Mermaid diagrams were updated if the documented structure changed
- [ ] Examples and commands still work

## Contributing Tools

If you are adding a raw tool:
- add or update models
- add the async route wrapper
- add MCP registration
- add contract tests
- update docs if the surface area changed

If you are adding an enriched tool:
- define the agent-facing question clearly
- keep the behavior explicit
- reuse raw clients
- add tests
- update [docs/tool-surface.md](docs/tool-surface.md)

## Reporting Gaps

If you notice:
- architecture docs drifting from code
- outdated examples
- missing tests
- misleading tool descriptions

please open an issue or PR. Those are high-value contributions in this repo.
