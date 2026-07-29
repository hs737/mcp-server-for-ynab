# Security Policy

This server holds a credential that can read and modify your household finances.
Treat security reports here as higher-stakes than a typical developer tool.

## Reporting a Vulnerability

Report privately. Do not open a public issue for a security problem.

Use GitHub's [private vulnerability reporting](https://github.com/hs737/ynab-mcp/security/advisories/new)
on this repository. Expect an acknowledgement within 7 days.

Please include:
- what an attacker can do, and what access they need to start
- the steps to reproduce
- the version or commit you tested

Please do not include a real YNAB personal access token in a report. If you
believe a token has been exposed, revoke it first at
[app.ynab.com/settings/developer](https://app.ynab.com/settings/developer),
then report.

## What Is In Scope

- leaking the YNAB token: logs, error messages, tool output, crash traces
- a write tool acting outside what the caller asked for
- a read tool returning another plan's data
- dependency vulnerabilities reachable through normal use

## What Is Not In Scope

- YNAB's own API or web application — report those to
  [YNAB](https://support.ynab.com), not here
- an LLM choosing to call a write tool. The server executes what the client
  asks. Deciding whether a write is appropriate belongs to the client and the
  human approving it
- rate limiting by YNAB (200 requests/hour per token) — that is the API's
  documented behavior

## Handling Your Token

- the token is read from the `YNAB_API_KEY` environment variable and held in
  memory for the process lifetime; it is never written to disk by this server
- `Authorization` headers are redacted before logging
- no telemetry, analytics, or outbound calls to anything other than
  `api.ynab.com`

If you ran this server and want to revoke access, delete the token at
[app.ynab.com/settings/developer](https://app.ynab.com/settings/developer).

## Write Tools

This server exposes tools that create, update, and delete real budget data.
There is no undo. Before granting an agent access to a plan you care about,
consider pointing it at a throwaway plan first — `make verify-write` deliberately
refuses to run against a plan whose name does not look disposable.
