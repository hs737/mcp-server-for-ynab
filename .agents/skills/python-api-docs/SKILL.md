---
name: python-api-docs
description: Keep public Python APIs documented with accurate docstrings, type hints, and optional generated reference docs.
---

# Python API Docs

Use this skill when adding or changing public Python modules, classes, functions, or MCP tool handlers whose contracts should be clear to humans and agents.

## Use When

- Adding or changing exported functions, classes, or protocols in the package
- Changing behavior, preconditions, side effects, or error semantics
- Refactoring module boundaries that affect the public surface
- Updating Sphinx, MkDocs, or other API-reference build config

## Read First

- `AGENTS.md` (if present)
- `README.md` and `pyproject.toml` (optional doc/build dependency groups)
- `.agents/skills/contract-sync/SKILL.md` (when schemas or OpenAPI are involved)
- `.agents/skills/docs-honesty/SKILL.md`

## Core Rules

1. Public callables should have docstrings. Follow the style this repo already uses (Google, NumPy, or Sphinx reST)—do not mix styles in one module.
2. Use type hints on public functions and methods; update hints when behavior changes.
3. Update docstrings when behavior changes materially; do not leave stale parameter or return descriptions.
4. For MCP tools, docstrings and parameter descriptions are part of the agent-facing contract—keep them accurate and specific (what the tool does, inputs, failure modes).
5. Treat HTTP or JSON Schema contracts (Pydantic models, OpenAPI) as the source of truth for wire formats; module docstrings complement those for Python callers.
6. After substantive public API changes, run this repo’s doc build or type checker if configured (`pytest`, `mypy`, `pyright`, `ruff check`, doc generator in CI or `pyproject.toml` scripts).
7. CI green does not prove prose correctness; verify docstrings against actual code paths.

## Workflow

1. Identify public symbols touched by the change (`__all__`, documented package exports, MCP tool registrations).
2. Update docstrings and type hints for changed semantics (`Args`, `Returns`, `Raises`, or equivalent).
3. Run the repo’s lint/type/doc commands defined in `pyproject.toml`, `Makefile`, or CI.
4. Commit regenerated reference output only if this repo checks it in.
5. Update README or operator docs if user-visible behavior changed.

## Common Failure Modes

- docstrings describe old behavior after refactors
- comments duplicate code but omit invariants or edge cases
- MCP tool descriptions that overpromise or omit auth/env requirements
- Pydantic/OpenAPI and docstrings treated as interchangeable without checking both
- optional doc build never run after API changes

## Completion Standard

Public Python APIs affected by the change have accurate docstrings and type hints, configured checks pass, and any generated reference or README sections stay aligned.
