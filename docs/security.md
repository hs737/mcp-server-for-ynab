# Security

This document covers security considerations for both deployment modes:

- **Local PAT mode** — current implementation, self-hosted, single user
- **Hosted OAuth mode** — planned Cloudflare Worker deployment, multi-user

---

## PAT mode security

### PAT handling

`YNAB_API_KEY` is loaded from the environment at startup. It is:
- Never written to disk by this application
- Never logged (the HTTP client redacts `Authorization` headers before logging)
- Never included in error responses
- Never echoed back in tool outputs

Do not commit your `.env` file. The `.gitignore` excludes it.

### Log redaction

The `http_client` redacts sensitive headers before any log output:
- `Authorization: Bearer <token>` → `Authorization: Bearer [REDACTED]`

When OAuth is implemented, extend the redaction rules in `http_client/client.py` to cover OAuth access tokens, refresh tokens, and any callback parameters that contain secrets.

### Write safety

- Raw write tools (`[WRITE]`) mutate YNAB data when called.
- Enriched tools never write. They are currently `read`-only.
- The MCP itself has no autonomous behavior — it only acts when an AI agent explicitly calls a tool with explicit parameters.
- `transactions_bulk_update` has partial-success behavior: it may succeed on some transactions and fail on others. Callers should check the response for per-transaction status rather than assuming atomic success.

### Transfer mutations

Transfer transactions are paired. Mutating one side of a transfer affects both linked transactions. Raw write tools document transfer fields explicitly. AI agents should inspect transfer fields before modifying linked transactions.

### Threat model (PAT mode)

PAT mode is designed for **single-user self-hosted use**. It assumes:
- The machine running the server is trusted
- The AI client connecting over stdio is operating on behalf of the authenticated user
- No multi-tenant isolation is required

Do not expose the stdio process to untrusted AI clients or run it in a shared environment without additional isolation.

---

## Hosted OAuth mode security

### Token handling

In hosted mode, per-user OAuth tokens replace the process-global PAT. Requirements:

- Access tokens, refresh tokens, and authorization codes are never logged
- Budget content is never logged
- Token exchange is performed server-side only — the Cloudflare Worker holds the client secret and exchanges the code; no token ever reaches the user's browser or MCP client
- Tokens are stored using Cloudflare-managed storage primitives
- The Worker must extend the existing log redaction rules to cover OAuth tokens and callback parameters

### Session and callback security

- `state` parameter must be generated and validated on OAuth callback to prevent CSRF
- PKCE must be used in the authorization flow even when a confidential client secret is also present
- The redirect URI must be a specific, registered endpoint on the Worker — not a wildcard
- Callback parameters (code, state) must never appear in logs

### Secret storage for Cloudflare deployment

- OAuth client secret must be stored in Cloudflare Worker secrets, not in code or environment files committed to the repo
- Refresh tokens and access tokens must be stored in Cloudflare-managed storage with appropriate TTL and access controls
- No secrets should appear in Worker logs, error responses, or MCP tool outputs

### Token deletion and revocation

- When a user disconnects or requests deletion, stored tokens and grant records must be deleted from Cloudflare storage
- If YNAB provides a programmatic token revocation endpoint, the Worker should call it on disconnect
- The deletion path must be documented in the privacy policy and reachable via the contact channel

### Threat model (hosted OAuth mode)

Hosted mode is a **multi-user public service**. It assumes:
- The Worker is the only trusted server-side component
- Each user's tokens are isolated from other users' tokens
- The MCP client (AI agent) is operating on behalf of the authenticated user for that session
- The Worker must verify the correct user/grant record on every YNAB API call

---

## Adjacent references

- [OAuth Architecture](oauth-architecture.md) — full implementation design for hosted mode
- [Privacy Policy](privacy-policy.md) — public data handling commitments
- [YNAB App Requirements](ynab-app-requirements.md) — YNAB-specific public app constraints
