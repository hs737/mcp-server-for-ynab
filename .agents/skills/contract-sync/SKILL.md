---
name: contract-sync
description: Keep source-of-truth contracts, generated artifacts, and tests aligned whenever interfaces change.
---

# Contract Sync

Use this skill when the repo has any source-of-truth contract and derived artifacts such as OpenAPI, JSON Schema, generated clients, MCP tool schemas, or prompt/task contracts.

## Use When

- Changing HTTP routes or MCP tool inputs/outputs
- Changing request or response shapes (Pydantic models, dataclasses, TypedDicts)
- Changing schema-driven generated artifacts
- Updating public interface docs
- Updating codegen outputs
- Reviewing drift between source and generated files

## Read First

- `AGENTS.md` (if present)
- `README.md` and `pyproject.toml` (`[project.scripts]`, `[tool.*]`, optional dependency groups)
- `CONTRIBUTING.md` if present and maintained
- Contract-related docs in this repo (for example `docs/api-strategy.md`, `docs/contract-discipline.md`)
- `postman/` or OpenAPI under `docs/api/`, only if this repo maintains them
- Generation scripts under `scripts/` or `tools/`

## Core Rules

1. Identify the source of truth before editing anything.
   - Common patterns in Python repos: **Pydantic** (or similar) models; FastAPI/Starlette route signatures; hand-authored OpenAPI; JSON Schema; MCP tool parameter schemas derived from types or explicit definitions.
   - Derived artifacts (OpenAPI YAML, JSON Schema exports, generated clients, Postman collections) must be regenerated from that source unless the repo documents otherwise.
2. Do not hand-edit generated artifacts unless the repo explicitly says to.
3. Regenerate derived artifacts when the source changes, using commands in `pyproject.toml`, `Makefile`, `uv run`, `poetry run`, or documented in `README.md` / `AGENTS.md`.
4. Commit source changes and generated changes together.
5. Update docs that describe the public or shared contract surface.
6. Ensure tests validate the actual interface (`pytest`, contract tests, schema snapshots)—not only internal mocks.

## Workflow

1. Determine whether the change affects a contract.
2. Identify the hand-authored source and the generated outputs (`pyproject.toml`, CI config, repo docs).
3. Update the source of truth (models, tool definitions, route handlers).
4. Run the appropriate generation or export step.
5. Update any relevant docs or examples.
6. Run the relevant tests or checks.

## Common Failure Modes

- generated artifacts not regenerated
- public docs still describing old request or response shapes
- manually patched generated files
- tests passing while contract artifacts drift
- MCP tool schema out of sync with implementation
- temporary undocumented contract changes

## Completion Standard

The source-of-truth contract, generated artifacts, tests, and docs all describe the same interface.
