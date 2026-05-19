# Branding and Naming Guidance

This document defines acceptable and unacceptable naming, domain, and visual choices for any public deployment of this product. It must be reviewed before a product name, domain, or OAuth client display name is locked.

No public name or domain has been chosen yet. That is intentional — this document exists to prevent invalid choices before launch.

---

## Why this matters

YNAB's API terms and public-app guidelines require that third-party integrations:

- Do not imply sponsorship, endorsement, or official affiliation with YNAB
- Do not include "YNAB" or "You Need A Budget" as a standalone or leading element in the app or domain name
- Use graphics and artwork that are clearly distinguishable from YNAB's own branding
- Display a privacy policy URL in the OAuth client configuration

Violations can result in an OAuth application being rejected or revoked during YNAB's review process.

---

## Product name rules

### Acceptable patterns

A valid product name must:

- Clearly describe the product's function without implying official YNAB status
- Use "for YNAB" as a suffix qualifier, not as the product name itself

Examples:
- `Budget Tools`
- `MCP Connector for YNAB`
- `Cloud Budget Assistant for YNAB`
- `Budget Bridge`
- `AI Budget Connector for YNAB`

### Unacceptable patterns

A product name must not:

- Begin with or consist solely of `YNAB` or `You Need A Budget`
- Include words like `Official`, `Verified`, `Certified`, `Authorized`, or `Supported` unless that status has been formally granted by YNAB
- Imply that the app is built or maintained by YNAB

Examples of invalid names:
- `YNAB MCP` *(leading YNAB)*
- `Advanced YNAB` *(leading YNAB)*
- `YNAB Connector` *(leading YNAB)*
- `Official Budget MCP` *(falsely implies official status)*
- `YNAB Verified Connector` *(falsely implies YNAB endorsement)*

---

## Domain name rules

### Acceptable patterns

- `budgetconnector.app`
- `mcpforynab.com`
- `budgetbridge.io`
- Any domain that describes the function without leading with `ynab`

### Unacceptable patterns

- `ynab-mcp.com` *(leading ynab)*
- `ynabconnector.io` *(leading ynab)*
- `officialynabmcp.com` *(implies official status)*
- Any domain that a reasonable user might mistake for an official YNAB property

---

## OAuth client display name rules

The OAuth client display name (shown on YNAB's consent screen) must follow the same naming rules above. It must also include or link to a live privacy policy URL before the OAuth application is submitted for review.

---

## Logo and artwork rules

- Artwork must be clearly distinguishable from YNAB's own brand assets
- Do not use the YNAB logo, color palette, or typeface as primary visual elements
- Do not create composite logos that combine this product's mark with YNAB's mark in a way that implies a partnership

---

## Copy and style rules for YNAB references

When referring to YNAB in documentation, marketing copy, or UI:

- Use: `for YNAB`, `with YNAB`, `connects to YNAB`
- Do not use: `by YNAB`, `from YNAB`, `a YNAB product`, `YNAB-supported`
- Always include the standard attribution/disclaimer footer on any page that references YNAB by name in a product context

### Standard attribution footer

> We are not affiliated, associated, authorized, endorsed by, or in any way officially connected with YNAB or any of its subsidiaries or affiliates. The official YNAB website can be found at [https://www.ynab.com](https://www.ynab.com). The names YNAB and You Need A Budget, as well as related names, tradenames, marks, trademarks, emblems, and images are registered trademarks of YNAB.

---

## Standardized copy blocks

### Third-party app notice

> This is an independent third-party application. It is not affiliated with, endorsed by, or officially connected to YNAB.

Use this on any public landing page, OAuth start screen, or app store listing.

### Support notice

> For support with this app, contact [support link]. Do not contact YNAB support for issues with this integration.

Use this wherever users might expect YNAB to provide support.

### OAuth consent-adjacent privacy policy pointer

> By connecting your YNAB account, you agree to this app's [Privacy Policy](privacy-policy.md). This app is not affiliated with YNAB.

Display this adjacent to the "Connect with YNAB" button or OAuth initiation screen.

---

## Pre-launch naming checklist

Before locking any product name, domain, or OAuth client configuration, verify:

- [ ] Product name reviewed against acceptable/unacceptable patterns above
- [ ] Domain reviewed against acceptable/unacceptable patterns above
- [ ] OAuth client display name reviewed
- [ ] Website footer disclaimer present on all public pages
- [ ] Privacy policy URL live and linked in OAuth client configuration
- [ ] Support contact path present and does not imply YNAB support
