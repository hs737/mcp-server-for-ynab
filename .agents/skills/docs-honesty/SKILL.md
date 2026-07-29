---
name: docs-honesty
description: Keep repo documentation aligned with implementation reality and prevent overclaiming.
---

# Docs Honesty

Use this skill when changing documentation or when code changes affect documented behavior.

## Use When

- Updating README
- Updating architecture docs
- Updating current-state docs
- Adding or modifying workflows
- Changing behavior that docs describe
- Reviewing whether docs still match implementation

## Read First

- `AGENTS.md` (if present)
- `README.md`
- Relevant architecture docs in this repo (for example `docs/architecture.md`, `docs/system-design.md`, `docs/current-state.md`)
- `CONTRIBUTING.md` (if maintained)

## Core Rules

1. Distinguish implemented vs deferred vs conceptual.
2. Do not present future-state thinking as current-state reality.
3. If behavior changed materially, update the matching docs in the same task.
4. If a documented flow or relationship changed materially, update the matching diagram (for example Mermaid) in the same task when the repo uses diagrams for that flow.
5. Prefer blunt accuracy over polished ambiguity.
6. If something is partial, say it is partial.
7. If something is unknown, mark it as unknown.

## Workflow

1. Inspect the code or behavior being changed.
2. Identify which docs claim or imply behavior in that area.
3. Update the docs so they match actual implementation.
4. Check whether a diagram should be added or updated.
5. Re-read for overstatement, stale claims, and future-state leakage.

## Common Failure Modes

- README implies the system is more complete than it is
- architecture docs describe intended design instead of implemented behavior
- current-state doc is stale
- diagrams describe old flows
- partial systems are described as complete

## Completion Standard

The relevant docs accurately describe the current implementation and clearly label deferred or conceptual work.
