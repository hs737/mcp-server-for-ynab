# Privacy Policy

**Last updated: 2026-05-19**

This privacy policy describes how the ynab-mcp hosted MCP service ("the Service") collects, uses, and handles your information. It applies to the planned hosted OAuth deployment of this service. The current self-hosted PAT mode is a local tool that processes data entirely on your own machine and is not covered by this policy.

---

## Overview

The Service is a third-party MCP connector that lets AI agents access your YNAB budget data on your behalf. It is not affiliated with, endorsed by, or officially connected to YNAB or its parent company.

---

## What data may be accessed

When you connect the Service using YNAB OAuth, it may access the following YNAB budget data on your behalf:

- Plan (budget) metadata: name, currency, date format
- Account list and balances
- Category groups and categories
- Month-level budget amounts and activity
- Transactions, payees, and scheduled transactions
- Money movements

The Service only accesses data that the YNAB OAuth scope you approve permits. The initial hosted deployment is expected to use a read/write scope. A read-only mode may be offered in the future.

---

## How data is used

Data accessed from YNAB is used solely to respond to requests made by the AI agent you have authorized. Specifically:

- Budget data retrieved during a request is used to construct the tool response for that request.
- Short-lived cache entries may be held in memory or fast storage to reduce redundant YNAB API calls within a session.
- No budget data is retained as a durable dataset or used for any purpose other than serving your requests.

---

## Storage and caching

The Service may briefly cache the following for performance:

- Plan metadata (name, currency, date settings)
- Category and category group lists
- Month snapshots

Cached entries are short-lived and are not retained beyond the session or cache TTL. No long-term database of plan contents is maintained.

---

## OAuth token and session storage

To operate the Service on your behalf across requests, the following data is stored:

- YNAB OAuth access token
- YNAB OAuth refresh token
- Token expiry metadata
- OAuth session and grant state (e.g., your internal user identifier within the Service, which YNAB plan was authorized)

This data is stored using Cloudflare-managed storage primitives appropriate for the hosted deployment target. It is stored only as long as needed to maintain an active connection.

---

## Retention and deletion

You may request deletion of your stored OAuth credentials and related session data at any time by:

- Revoking the OAuth connection from within YNAB's developer settings
- Contacting the Service at the address below

On receipt of a verified deletion request, stored tokens and session records for your account will be deleted. Cached budget data, which is short-lived and not tied to a persistent record, will expire on its own schedule.

If the Service shuts down or the connection expires and is not renewed, stored credentials will be deleted within a reasonable time.

---

## Data sharing

The Service does not sell, rent, or share your YNAB data with third parties. Data accessed from YNAB is not used for advertising, profiling, training, or any purpose outside of serving your explicit requests.

The Service uses Cloudflare infrastructure for hosting and storage. Cloudflare's own privacy policy governs infrastructure-level data handling.

---

## Security

The Service is designed to minimize credential exposure:

- YNAB OAuth tokens are never logged
- OAuth callback codes are never logged
- Budget content is never logged
- Token exchange is performed server-side only
- Credentials are stored using Cloudflare-managed storage

If the Service suspects a credential compromise, affected tokens will be revoked and you will be notified through the available contact channel.

---

## Your choices

- You may revoke the Service's access to your YNAB account at any time through YNAB's developer settings.
- You may request deletion of your stored session data by contacting us.
- You may stop using the Service at any time.

---

## Changes to this policy

If this policy changes to cover additional data types or materially new uses, users will be notified and, where required, re-consented before the new uses take effect.

The "Last updated" date at the top of this document will be updated on each revision.

---

## Contact

For privacy questions, data deletion requests, or other inquiries:

**Email:** `support@example.com` *(placeholder — replace before publication)*

---

## YNAB attribution

We are not affiliated, associated, authorized, endorsed by, or in any way officially connected with YNAB or any of its subsidiaries or affiliates. The official YNAB website can be found at [https://www.ynab.com](https://www.ynab.com).

The names YNAB and You Need A Budget, as well as related names, tradenames, marks, trademarks, emblems, and images are registered trademarks of YNAB.
