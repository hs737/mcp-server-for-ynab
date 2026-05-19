# YNAB Public App Requirements

This document captures the YNAB-specific requirements that must be satisfied before submitting or publicly operating an OAuth application against the YNAB API. It is based on YNAB's official API documentation and terms at [api.ynab.com](https://api.ynab.com/).

This document is authoritative for the hosted OAuth product path. The self-hosted PAT mode is not subject to most of these requirements.

---

## Required footer attribution

Every public page, public website, or interface that references YNAB by name in a product context must display the following disclaimer:

> We are not affiliated, associated, authorized, endorsed by, or in any way officially connected with YNAB or any of its subsidiaries or affiliates. The official YNAB website can be found at [https://www.ynab.com](https://www.ynab.com). The names YNAB and You Need A Budget, as well as related names, tradenames, marks, trademarks, emblems, and images are registered trademarks of YNAB.

This text is already present in `README.md` and `NOTICE.md`. It must also appear on any public website or OAuth-adjacent landing page.

---

## OAuth app constraints

### Privacy policy

- A publicly accessible privacy policy URL must be configured in the YNAB OAuth client registration.
- The privacy policy must be reachable at a stable public URL before the OAuth app is submitted for YNAB review.
- The policy must describe what YNAB data is accessed, how it is used, and how users can request deletion of their data.

See [Privacy Policy](privacy-policy.md) for the repo-owned policy draft.

### Naming and branding

- The OAuth client display name must not imply sponsorship, endorsement, or official affiliation with YNAB.
- The display name must not lead with `YNAB` or `You Need A Budget`.
- Graphics and artwork must be clearly distinguishable from YNAB brand assets.

See [Branding](branding.md) for full naming rules and acceptable/unacceptable examples.

### App status claims

Do not represent the app as any of the following unless YNAB has formally granted that status:

- "Official" integration
- "Verified" app
- "Supported by YNAB"
- "Authorized by YNAB"

Third-party apps in YNAB's restricted OAuth mode are waiting for a review process. Do not describe the app as if it has passed that review until it actually has.

---

## Public OAuth app support positioning

### Third-party app notice

Display on any public landing page or OAuth start screen:

> This is an independent third-party application. It is not affiliated with, endorsed by, or officially connected to YNAB.

### Support notice

Display wherever users might seek help:

> For support with this integration, contact [support link]. YNAB support does not provide help for third-party integrations.

This ensures users who have issues with the connector reach the right support channel and do not contact YNAB expecting help with this app.

---

## Naming and branding constraints summary

| Constraint | Rule |
|------------|------|
| App or domain name leading with "YNAB" | Not permitted |
| App or domain name that implies official status | Not permitted |
| YNAB trademark in domain | Only allowed as a non-leading qualifier (e.g., `for-ynab.example.com`) |
| YNAB logo or brand assets | Must not be used as primary visuals |
| Footer disclaimer | Required on all public-facing pages |
| Privacy policy URL | Required in OAuth client config and easy for users to find |

Full naming and domain guidance: [Branding](branding.md)

---

## YNAB restricted mode and review

New public OAuth apps are initially placed in YNAB's restricted mode, which limits the number of authorized users. To remove this restriction:

- The app must be reviewed and approved by YNAB.
- The review requires a working, publicly accessible application with a visible privacy policy.
- The application must not violate naming, branding, or disclaimer requirements.

The public launch checklist in [public-launch-checklist.md](public-launch-checklist.md) tracks what is required before requesting that review.

---

## Reference

- YNAB API documentation and terms: [https://api.ynab.com](https://api.ynab.com/)
- YNAB OAuth developer settings: [https://app.ynab.com/settings/developer](https://app.ynab.com/settings/developer)
