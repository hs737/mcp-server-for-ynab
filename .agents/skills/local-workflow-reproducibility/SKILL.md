---
name: local-workflow-reproducibility
description: Turn repeated local setup, seed, and manual-test workflows into safe, documented, repeatable scripts.
---

# Local Workflow Reproducibility

Use this skill when local development or manual testing depends on repeated setup, seed, reset, fixture, or scenario-loading steps.

## Use When

- local setup is repetitive or error-prone
- realistic test state requires many manual steps
- developers are copying IDs, tokens, or env values between tools
- manual testing depends on exact ordering
- seed or reset flows need guardrails

## Read First

- `AGENTS.md` (if present)
- `README.md` and `pyproject.toml` (scripts, optional groups, entry points)
- `Makefile` or `scripts/` if present
- Environment docs (for example `docs/environment.md`, `.env.example`)
- Existing fixtures under `tests/`, `scripts/`, or `tools/`

## Core Rules

1. Repeated workflows should become scripts or documented commands, not tribal knowledge.
2. Destructive reset flows should be explicit and guarded (confirm DB name, env file, or `--dry-run` where appropriate).
3. Scenario data should be intentional and named.
4. Local workflows should prefer exercising real app code paths where practical (run the MCP server, call tools via inspector/CLI).
5. Docs should explain how to reset, seed, and test locally—including required env vars (for example YNAB API tokens) without committing secrets.
6. Use a virtual environment (`uv`, `venv`, `poetry`) consistently; document the canonical install and run commands.

## Workflow

1. Identify repeated manual setup pain.
2. Decide whether it needs reset, load, list, or verify commands.
3. Script the workflow with safety checks (Python CLI, `make` targets, or shell wrappers that call `python -m ...`).
4. Document the command surface and expected state.
5. Add or update `pytest` fixtures or seed data as the model evolves.

## Common Failure Modes

- manual setup requires many fragile steps
- resets can accidentally target the wrong environment
- scenarios drift from current schema or tool contracts
- docs list workflows that no longer work
- secrets committed or assumed in docs
- “works on my machine” without pinned deps in `pyproject.toml` / lockfile

## Completion Standard

The repeated local workflow is safe, repeatable, discoverable, and documented well enough that future humans and agents can use it without tribal knowledge.
