---
name: architecture-boundaries
description: Preserve clean system layering and prevent logic from smearing across handlers, services, persistence, integrations, and agent runtime.
---

# Architecture Boundaries

Use this skill when adding or changing core logic, MCP tools, HTTP APIs, jobs, integrations, or runtime orchestration in this **Python** repository.

## Use When

- Adding MCP tools, resources, or prompts
- Adding HTTP routes (if any)
- Adding orchestration or business logic
- Adding database access patterns
- Adding jobs, workers, or scheduled tasks
- Adding third-party integrations (for example YNAB API clients)
- Reviewing whether a change belongs in the right layer

## Read First

- `AGENTS.md` (if present)
- `README.md`
- `pyproject.toml` (package layout, entry points)
- Any repo-specific architecture docs (for example `docs/architecture.md`, `docs/current-state.md`)

## Core Rules

1. **Transport / protocol layer** (MCP server setup, FastAPI routers, CLI entrypoints) owns wiring, validation at the boundary, and mapping to/from wire types—not core business rules.
2. **Services or domain modules** own workflows, state transitions, and business rules.
3. **Data access** owns persistence and queries, not business policy.
4. **Integration clients** (YNAB SDK, HTTP clients) own provider-specific IO and normalization, not app-wide orchestration.
5. **MCP tool handlers** should stay thin: parse inputs, call services, map errors to structured tool results. Do not hide durable invariants only in tool docstrings or prompts.
6. Do not invent a parallel architecture when the repo already has one; follow existing package layout (`src/` layout, module naming).
7. Keep boundaries obvious enough that future agents can place code correctly.
8. **Multi-step workflows:** Reusable step logic belongs in domain or service modules, not duplicated in each tool or route.
9. **Persistence:** Prefer normalized storage and explicit fields as source of truth. Use **`data-access-discipline`** for schema and transactions.

## Typical Python layout (adapt to this repo)

| Layer | Examples |
|-------|----------|
| Entry | `__main__.py`, `server.py`, Typer/Click CLI, FastAPI `APIRouter` |
| MCP surface | Tool/resource registration; argument validation via Pydantic |
| Services | `services/`, `domain/`, use-case functions |
| Integrations | `clients/ynab.py`, thin wrappers around external APIs |
| Persistence | `db/`, repositories, SQLAlchemy models (if used) |

## Workflow

1. Identify the type of change: protocol surface, orchestration, persistence, integration.
2. Find the existing repo pattern for that kind of work.
3. Place new logic in the narrowest correct layer.
4. Check whether cross-layer documentation needs to be updated.
5. Verify the change did not create new ambiguity about responsibility.

## Common Failure Modes

- business logic in MCP tool functions or route handlers
- raw DB or file access scattered through tools
- integration clients owning multi-step workflows
- prompts replacing durable validation rules
- multiple competing patterns for the same concern

## Completion Standard

The change fits the existing architecture cleanly, layer responsibilities remain legible, and no new ambiguity was introduced.
