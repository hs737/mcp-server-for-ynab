---
name: data-access-discipline
description: Keep persistence logic explicit, consistent, and separate from transport concerns and business rules.
---

# Data Access Discipline

Use this skill when adding tables, queries, migrations, persistence helpers, cross-entity writes, or scope or tenant enforcement.

## Use When

- Adding or changing schema
- Writing new queries
- Adding persistence helpers or repository modules
- Adding cross-table workflows
- Reviewing DB access placement
- Tightening scope or tenant rules

## Read First

- `AGENTS.md` (if present)
- `README.md`
- Architecture and data docs in this repo (for example `docs/architecture.md`, `docs/data-access-patterns.md`, `docs/data-model.md`, `docs/environment.md`)
- Migration tooling config (for example `alembic.ini`, SQLAlchemy models under `src/`, Django migrations—whatever this repo uses)

## Core Rules

1. Persistence code should be consistent and discoverable.
2. Business rules should not be buried in route or MCP tool handlers.
3. Persistence helpers should not quietly own domain policy.
4. Cross-entity workflows should have a clear orchestration layer (service/module), not ad hoc scripts.
5. Scope or tenant boundaries should be enforced explicitly.
6. Schema changes, migrations, and related docs should move together.
7. Domain-facing shapes should be intentional, not accidental spillover from ORM rows or raw dicts.
8. **Single source of truth:** Prefer normalized tables and explicit columns for durable state. In-memory aggregates assembled for reads must not be duplicated as parallel persisted blobs unless documented and intentional.
9. **Multi-write consistency:** When several SQL statements must succeed or fail together, use one outer transaction (`session.begin()`, `async with session.begin()`, or equivalent). Pass the same session/connection into helpers; avoid nested transaction calls that commit independently. Keep slow network or external API calls outside the transaction; persist only after durable inputs are ready.

## Workflow

1. Identify whether the task is schema, query, migration, or workflow related.
2. Place query or persistence logic in the repo’s established pattern.
3. Keep cross-entity business logic out of thin repository functions.
4. Review whether scope and ownership enforcement are explicit.
5. Update migrations, docs, and tests as needed.

## Common Failure Modes

- raw SQL or ORM calls scattered unpredictably
- MCP handlers or FastAPI routes directly owning DB logic
- hidden cross-tenant reads or writes
- business rules implemented implicitly in query code
- schema changes without migration or documentation updates
- leaking ORM instances or untyped dicts into higher layers without intent
- multiple commits for one logical unit of work

## Completion Standard

The data-access change follows the repo’s pattern, respects scope boundaries, keeps business logic in the right place, and remains easy to reason about.
