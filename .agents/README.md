# Agent skills (ynab-mcp)

This repository is **Python**. Skills under `skills/` assume:

- **`pyproject.toml`** for dependencies, scripts, and tool config (`ruff`, `pytest`, `mypy`, etc.)
- **MCP** as the primary agent surface (thin tools, logic in services/domain modules)
- **`pytest`** for tests; optional HTTP/Postman only if documented in the repo

| Skill | When to use |
|-------|-------------|
| `architecture-boundaries` | Layering MCP tools, services, clients, persistence |
| `agent-runtime-guardrails` | MCP tools, prompts, observability, bounded behavior |
| `python-api-docs` | Docstrings, type hints, public API and tool descriptions |
| `contract-sync` | Pydantic models, OpenAPI, schemas, generated artifacts |
| `live-api-verification` | Response models, new routes, transport changes, "does it work" claims |
| `data-access-discipline` | DB schema, queries, transactions (if used) |
| `docs-honesty` | README and docs match implementation |
| `local-workflow-reproducibility` | Local dev, env, seeds, repeatable commands |
| `hardening-review` | Pre-merge / signoff review |
| `postman-standards` | Only if repo maintains HTTP Postman collections |
| `karpathy-guidelines` | General coding discipline |
| `find-skills` | Discover installable skills from the ecosystem |
| `requesting-code-review` | Structured review before merge |
| `writing-clearly-and-concisely` | Human-facing prose |

Installed third-party skills are recorded in `.skill-lock.json`.
