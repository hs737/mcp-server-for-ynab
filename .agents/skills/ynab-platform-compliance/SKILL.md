---
name: ynab-platform-compliance
description: Keep this project compliant with YNAB's API terms, OAuth requirements, naming rules, and branding restrictions.
---

# YNAB Platform Compliance

YNAB publishes binding requirements for applications built on their API. Some
constrain things that are expensive to change later — the project name, the DNS
name, what a privacy policy must say. Check this skill before naming anything,
before publishing, and before any hosted or OAuth work.

Source: <https://api.ynab.com/#oauth-requirements>. Re-read it when the answer
matters; the requirements below were captured from that page and may have moved.

## Use When

- Naming or renaming the project, package, binary, repository, or a domain
- Writing README, site, or docs copy that mentions YNAB
- Adding branding, logos, or a "Works with YNAB" badge
- Any work toward OAuth, hosting, or multi-user
- Drafting or revising a privacy policy
- Before publishing to a package registry or announcing the project

## Naming — the rule most likely to bite

> "The application and the web address (DNS name) must not include 'YNAB' or
> 'You Need A Budget' unless preceded by the word 'for'."

Acceptable: "Budget Tools", "Transaction Syncer", "Currency Tools for YNAB".
Unacceptable: "YNAB Tools", "YNAB Transaction Syncer", "Advanced YNAB".

This project therefore uses:

| Thing | Value |
|-------|-------|
| Repository and package | `mcp-server-for-ynab` |
| Server name reported to clients | `mcp-for-ynab` |
| English title | MCP for YNAB |

A future domain must follow the same rule: `mcp-for-ynab.com` is fine,
`ynab-mcp.com` is not. `scripts/mcp_http_check.sh` asserts the reported server
name complies, and a unit test covers it. Do not weaken either check.

## Required disclaimer

This exact text must appear in the site footer, and is currently in `README.md`
and `NOTICE.md`:

> "We are not affiliated, associated, or in any way officially connected with
> YNAB or any of its subsidiaries or affiliates. The official YNAB website can
> be found at https://www.ynab.com. The names YNAB and You Need A Budget, as
> well as related names, tradenames, marks, trademarks, emblems, and images are
> registered trademarks of YNAB."

## Branding

- artwork "may not be modifications to our official branding and must be
  distinguishable from YNAB itself"
- the official "Works with YNAB" linked image may be used to show compatibility
- never imply YNAB sponsors, endorses, or supports this project

## Conduct

- do not deceive, misrepresent, or enable unauthorized use of the API
- do not access, aggregate, or analyze YNAB user data if it will be sold to a
  third party
- never request, handle, or store financial account credentials other than an
  access token obtained from the institution via OAuth
- maintain a secure operating environment
- request the minimum necessary permissions, and use incremental authorization
  where possible

## Rate limits

200 requests per hour per access token, rolling. This server budgets below that
in `http_client/rate_budget.py` so the limit hit first is local and legible.
Keep it that way; a client that hammers the API reflects on the project when
YNAB reviews it.

## If OAuth is ever built

Everything above still applies, plus:

1. **Restricted Mode.** A new OAuth application may obtain at most 25 access
   tokens for users other than the owner. Lifting it needs a review request,
   and YNAB says the review takes 2-4 weeks.
2. **A published privacy policy is mandatory**, displayed to users, with its URL
   in the OAuth client configuration. It must state:
   - the purpose for which user data is used, including every purpose
   - how API data is handled, stored, secured, and how long it is kept
   - that data will not unknowingly be passed to any third party
   - a method for users to delete their data on request — which must be honored
   - a maintained "Last Updated" date
3. **Consent on change.** Accessing new data types or changing how data is used
   requires updating the policy and prompting users to consent.
4. YNAB explicitly does not review your privacy policy for legal compliance.
   That responsibility is yours, and financial data raises the stakes.

## The design consequence people miss

Requirements 2 and 4 above are architecture, not paperwork. "How long is data
kept" and "a method for users to delete their data" cannot be answered honestly
by a system that was not designed to scope, retain, and delete per user.

The strongest position is to store as little as possible. Data you never hold
needs no retention policy, no deletion endpoint, and cannot leak. Prefer
discarding over storing, and holding tokens in memory over persisting them,
before reaching for policy language that promises careful handling of data you
did not need to keep.

Today this server is single-tenant: one process, one token from the
environment, history on the operator's own disk. That design is why it has no
custodial obligations. Any move to multi-user changes that, and the compliance
work becomes real work rather than a document.

## Related Skills

- `live-api-verification` — verifying behavior against the real API
- `docs-honesty` — keeping claims matched to what is implemented
