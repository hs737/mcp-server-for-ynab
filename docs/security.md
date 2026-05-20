# Security

## PAT handling

`YNAB_API_KEY` is loaded from the environment at startup. It is:
- Never written to disk by this application
- Never logged (the HTTP client redacts `Authorization` headers before logging)
- Never included in error responses
- Never echoed back in tool outputs

Do not commit your `.env` file. The `.gitignore` excludes it.

## Log redaction

The `http_client` redacts sensitive headers before any log output:
- `Authorization: Bearer <token>` → `Authorization: Bearer [REDACTED]`

If you add new auth mechanisms such as OAuth, extend the redaction rules in
`http_client/client.py` to cover OAuth tokens and any callback parameters that
contain secrets.

## Write safety

- Raw write tools (`[WRITE]`) mutate YNAB data when called.
- Enriched tools never write. They are currently `read`-only.
- The MCP itself has no autonomous behavior — it only acts when an AI agent explicitly
  calls a tool with explicit parameters.
- `transactions_bulk_update` has partial-success behavior: it may succeed on some
  transactions and fail on others. Callers should check the response for per-transaction
  status rather than assuming atomic success.

## Transfer mutations

Transfer transactions are paired. Mutating one side of a transfer affects both
linked transactions. Raw write tools document transfer fields explicitly.
AI agents should inspect transfer fields before modifying linked transactions.

## Hosted OAuth boundary

Public OAuth, callback handling, durable grant storage, and session identity do
not belong in this repo. They belong in the separate hosted runtime that imports
`ynab-mcp` as a library.

The only core responsibility for hosted auth is the embed boundary:
- accept any `AuthProvider` implementation
- keep token material out of logs and error payloads
- keep tool logic auth-agnostic

## Threat model

This MCP server is designed for **single-user self-hosted use**. It assumes:
- The machine running the server is trusted
- The AI client connecting over stdio is operating on behalf of the authenticated user
- No multi-tenant isolation is required

Do not expose the stdio process to untrusted AI clients or run it in a shared environment
without additional isolation.
