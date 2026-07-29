---
name: agent-runtime-guardrails
description: Keep autonomous runtime behavior observable, bounded, and separate from durable business logic.
---

# Agent Runtime Guardrails

Use this skill when working on MCP servers, tool execution, planning loops, memory, checkpoints, approvals, or other agent-facing runtime behavior in this **Python** repository.

## Use When

- Adding or editing MCP tools, resources, or prompts
- Changing tool-calling or error-mapping behavior
- Adding memory or checkpoint systems
- Adding human-in-the-loop approval boundaries
- Reviewing runtime safety and observability

## Read First

- `AGENTS.md` (if present)
- `README.md`
- MCP SDK usage in this repo (server setup, lifespan, tool registration)
- Any runtime or workflow docs (for example `docs/agent-design.md`, `docs/current-state.md`)

## Core Rules

1. Prompts and tool descriptions do not replace durable business rules or validation in code.
2. Ephemeral conversation or session state does not replace persistent storage when durability is required.
3. Runtime orchestration should be observable (structured logging, clear error types, traceable tool results).
4. Human approvals or intervention boundaries should be explicit where relevant.
5. Tools must not silently bypass application invariants (budget scope, auth, rate limits).
6. Long-running or multi-step behavior should use explicit checkpoints or idempotent steps—not implicit “continue from chat” assumptions.
7. Tool and server capabilities advertised to clients must match what is implemented.
8. **MCP boundary:** Each tool should have a narrow, documented contract (Pydantic models or typed parameters). Prefer structured errors (`isError`, clear messages) over opaque stack traces in tool results.

## Workflow

1. Identify what belongs in MCP wiring versus service/domain logic.
2. Make durable state transitions explicit in code, not only in prompts.
3. Ensure important steps are observable through logs or persisted records.
4. Check auth, env vars, and secrets handling (`YNAB_*`, tokens via env—not hardcoded).
5. Update docs if tool behavior or required env changed.
6. Verify unhappy paths: API failures, partial data, timeouts, invalid user input.

## Common Failure Modes

- critical logic only in tool docstrings or system prompts
- session memory used as system-of-record
- unhandled exceptions surfaced as generic tool failures
- no clear boundary between “call YNAB API” and “orchestrate workflow”
- tools that do too much in one invocation
- overstated autonomy in README vs actual tool set

## Completion Standard

Runtime behavior is bounded, observable, documented honestly, and does not hide durable business logic behind MCP or prompt layers.
