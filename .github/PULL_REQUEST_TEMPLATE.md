# What this changes

<!-- One or two sentences. What behavior differs after this merges? -->

## Why

<!-- The problem. Link an issue if there is one. -->

## Verification

<!-- Tick what you actually ran. Leave the rest unticked rather than assuming. -->

- [ ] `make check` passes (lint, typecheck, tests, Postman drift)
- [ ] `make verify-live` — read tools still parse against the real API
- [ ] `make verify-write PLAN_ID=<disposable>` — if this touches a write path
- [ ] `make verify-mcp-http` — if this touches transport, startup, or tool registration
- [ ] Not applicable — this change is docs only

## If this touches a response model

The test suite cannot catch a model that disagrees with the real API, because
the fixtures are ours. Confirm the shape came from a live response:

- [ ] I fetched the endpoint and checked the fields across **every** record, not
      just the first, before deciding what is required and what is nullable
- [ ] Fixtures are recorded from a live response with identifiers replaced
- [ ] No real account IDs, transaction IDs, payee names, balances, or tokens

## If this adds or changes a tool

- [ ] The description matches what the tool can actually do — every documented
      parameter exists and is honored by the API
- [ ] Classified `read` or `write` in the registry, with matching annotations
- [ ] `docs/tool-surface.md` updated if a family changed
