# Documentation Index

This page is the map for the repository documentation.

## What this document is for

Read this page if you need:
- a quick way to find the right doc
- a recommended reading order
- a breakdown by audience
- Mermaid guidance for structural docs

## Documentation Map

```mermaid
mindmap
  root((ynab-mcp docs))
    README.md
      setup
      overview
      navigation
    CONTRIBUTING.md
      workflow
      PRs
      checks
    architecture.md
      layers
      request flow
      errors
    repo-structure.md
      top-level tree
      code locations
      test locations
    tool-surface.md
      raw tools
      enriched tools
      niche tools
    testing.md
      test layers
      commands
      gaps
    security.md
      auth
      logging
      write safety
    AGENTS.md
      implementation rules
      extension paths
      diagram rules
```

## Recommended Reading Order

1. [README.md](../README.md)
2. [architecture.md](architecture.md)
3. [CONTRIBUTING.md](../CONTRIBUTING.md)
4. [AGENTS.md](../AGENTS.md)
5. [testing.md](testing.md)
6. [security.md](security.md)

## By Audience

### New users

Start with:
- [README.md](../README.md)
- [security.md](security.md)

Use these to understand what the MCP is, how to run it, and what credentials it expects.

### Contributors

Start with:
- [architecture.md](architecture.md)
- [repo-structure.md](repo-structure.md)
- [CONTRIBUTING.md](../CONTRIBUTING.md)
- [testing.md](testing.md)

Use these to understand how the code is laid out and how to verify changes.

### AI agents

Start with:
- [AGENTS.md](../AGENTS.md)
- [architecture.md](architecture.md)
- [tool-surface.md](tool-surface.md)

Use these to understand where to add tools, how requests flow, and how the tool families are organized.

## Document Guide

### [README.md](../README.md)

Front door for the repo:
- product summary
- setup
- architecture snapshot
- doc navigation

### [architecture.md](architecture.md)

System view of the current implementation:
- package layout
- request flow
- error flow
- server and transport choices

### [repo-structure.md](repo-structure.md)

Practical map of where things live:
- top-level directories
- `src/ynab_mcp` subtree
- where to add code by concern

### [tool-surface.md](tool-surface.md)

Guide to the MCP tool surface:
- raw vs enriched tools
- recommended entry points
- low-priority families

### [testing.md](testing.md)

How verification currently works:
- commands
- test layers
- actual current coverage
- known gaps

### [security.md](security.md)

Operational safety guidance:
- PAT handling
- log redaction
- write safety
- trust model

### [CONTRIBUTING.md](../CONTRIBUTING.md)

Contribution workflow guide:
- local setup
- coding and testing expectations
- pull request checklist
- docs and diagram update expectations

### [AGENTS.md](../AGENTS.md)

Implementation companion for AI agents and contributors:
- extension rules
- architecture invariants
- diagram update rules

## Mermaid Guidance

Use Mermaid for:
- architecture diagrams
- request and error flows
- repo structure overviews
- tool family maps

Prefer:
- `flowchart`
- `sequenceDiagram`
- `mindmap`

Keep diagrams:
- structural, not decorative
- short-labeled
- synchronized with code changes

## Adjacent References

- [Postman README](../postman/README.md)
- [Makefile](../Makefile)
