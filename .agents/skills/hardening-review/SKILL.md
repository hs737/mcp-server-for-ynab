---
name: hardening-review
description: Review completed work for edge cases, drift, missing tests, overstated claims, and signoff readiness.
---

# Hardening Review

Use this skill when reviewing a completed feature, workflow, or integration for quality and signoff readiness in this **Python** repository.

## Use When

- Reviewing another agent’s work
- Preparing for merge
- Auditing a feature or phase
- Checking whether implementation is truly complete
- Looking for edge cases and drift

## Read First

- `AGENTS.md` (if present)
- `README.md` and `pyproject.toml`
- Relevant architecture docs and tests under `tests/`
- Contract or MCP tool schema docs, if present

## Core Rules

1. “Works on the happy path” is not enough.
2. Docs honesty is part of completion.
3. Missing or weak tests (`pytest`) are a real issue, not a footnote.
4. Scope, auth, or boundary mistakes are high severity (wrong budget, leaked tokens in logs).
5. Generated artifact drift (OpenAPI, schemas) matters when the repo uses codegen.
6. Overclaiming implementation is a bug.
7. Review should prioritize bugs, regressions, and risks before summaries.
8. Run or verify `pytest`, `ruff`, `mypy`/`pyright`—whatever this repo’s CI uses—when judging signoff.

## Workflow

1. Identify the implemented scope.
2. Check the actual code path, not just the claimed behavior.
3. Review unhappy paths and partial-data behavior (API errors, empty lists, invalid ids).
4. Check docs and contract alignment (README, tool descriptions, Pydantic models).
5. Check tests for real proof, not only heavy mocking of the code under test.
6. Report findings ordered by severity.
7. State clearly whether the work is signoff-ready.

## Common Failure Modes

- unit tests exist but MCP tools or integrations are untested
- docs still describe old or aspirational behavior
- env vars or secrets handling is unclear or unsafe
- generated artifacts drift from Pydantic/OpenAPI source
- incomplete feature presented as complete
- type hints lie about optional vs required fields

## Completion Standard

The work has been checked for implementation reality, unhappy paths, docs honesty, contract alignment, and verification depth, and is clearly judged ready or not ready for signoff.
