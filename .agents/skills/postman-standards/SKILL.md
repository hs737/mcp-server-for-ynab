---
name: postman-standards
description: Keep Postman collections complete and aligned with API contracts when this repo documents HTTP testing with Postman or Newman.
---

# Postman standards

**Scope:** Use this skill only if this repo maintains Postman/Newman collections or an HTTP API. Many MCP-only Python repos do not—skip this skill if there is no `postman/` or documented HTTP operator workflow.

Use when editing Postman surfaces or HTTP routes and you need collections to stay a high-quality operator and integration-testing surface.

## Use when

- This repo exposes HTTP endpoints (FastAPI, etc.) with Postman collections
- Changing request or response shapes or route behavior
- Updating Postman examples, naming, variables, or tests
- Adding or updating OpenAPI- or script-generated Postman artifacts

## Read first

- `AGENTS.md` (if present)
- `README.md` and `pyproject.toml` (generation scripts, if any)
- `.agents/skills/contract-sync/SKILL.md`
- OpenAPI or contract docs in this repo

## Core rules

1. **Source of truth**: contracts live in hand-authored Python (Pydantic models, route handlers, tests). OpenAPI and generated Postman collections are derived unless the repo documents otherwise.
   - Do not hand-edit generated OpenAPI or collection JSON; regenerate using commands in `pyproject.toml`, `Makefile`, or repo docs.
2. **Variable contract (inputs equal outputs)**:
   - Path params must use the OpenAPI parameter name as the Postman variable name.
   - Post-scripts that capture ids must write to the same canonical keys the collection documents.
3. **Every request needs a description** with: `Purpose:`, `Auth:`, `Reads:`, `Writes:`, `Assumptions:`, `Side Effects:`, `Downstream:`, `Notes:`.
4. **Variables**: `{{baseUrl}}` in environment; collection variables for workflow ids; never hardcode tokens or production ids.
5. **Body examples**: happy path, minimal payload, and a common edge case where applicable.
6. **Post-script tests**: assert status and stable fields; avoid brittle full-body string matches on dynamic content.

## Postman runtime note

Postman and Newman run **JavaScript** in the sandbox, not Python from this repo. Shared logic belongs in repo templates injected at generation time—not imported Python modules.

Use `postmanDebug=true` on the collection or environment to gate verbose script logs.

## Completion standard

An operator can run the collection end to end for the implemented subset with minimal guessing: clear descriptions, runnable examples, and tests that capture ids for chained requests.
