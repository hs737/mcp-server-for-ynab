# Public Launch Checklist

This checklist tracks what must be in place before the hosted OAuth deployment of ynab-mcp can be submitted for YNAB review and opened to the public.

Items are grouped by category. All items in a category must be complete before that category is considered done.

---

## Legal and public docs

- [ ] Privacy policy published at a stable public URL
- [ ] Privacy policy covers: data accessed, how used, storage, caching, token storage, retention, deletion, sharing, security, contact
- [ ] Privacy policy URL added to YNAB OAuth client configuration
- [ ] Footer disclaimer present on all public-facing pages (website, landing, OAuth start screen)
- [ ] Contact/deletion method live and reachable (not a placeholder)
- [ ] Support notice present — makes clear that support goes to this app, not YNAB

---

## Branding and domain compliance

- [ ] Product name reviewed against [branding guidelines](branding.md) (no leading YNAB, no implied official status)
- [ ] Domain reviewed against [branding guidelines](branding.md)
- [ ] OAuth client display name reviewed against naming rules
- [ ] App artwork and logo are clearly distinguishable from YNAB brand assets
- [ ] No claims of "official", "verified", "authorized by YNAB" status

---

## OAuth app configuration

- [ ] YNAB OAuth app created in [developer settings](https://app.ynab.com/settings/developer)
- [ ] Privacy policy URL configured in OAuth client registration
- [ ] Redirect URI set to the Cloudflare Worker callback endpoint
- [ ] Client secret stored in Cloudflare secrets (not in code or env files)
- [ ] OAuth client display name compliant with branding rules

---

## Hosted security posture

- [ ] Token exchange performed server-side only (client never sees authorization code or client secret)
- [ ] `state` parameter validated on callback (CSRF protection)
- [ ] PKCE implemented in authorization flow
- [ ] OAuth tokens never logged (access token, refresh token, callback code)
- [ ] Budget content never logged
- [ ] Cloudflare storage primitive chosen and implemented for token/grant storage
- [ ] Token refresh flow implemented
- [ ] Expired/revoked refresh token error surfaced to user clearly
- [ ] Log redaction rules in `http_client/client.py` extended to cover OAuth tokens and callback parameters

---

## Token deletion path

- [ ] User can revoke connection from within YNAB developer settings (inherent to YNAB's own revocation flow)
- [ ] Worker-side deletion deletes stored grant record and tokens from Cloudflare storage on revoke/disconnect
- [ ] Deletion request via contact email deletes stored grant record within a reasonable time
- [ ] Deletion behavior documented in privacy policy

---

## Support and contact readiness

- [ ] Support email or contact method is live (not a placeholder)
- [ ] Support contact is reachable before the app is public
- [ ] Support notice does not imply YNAB provides support for this app

---

## YNAB review readiness

- [ ] App is functional end-to-end in hosted mode (OAuth flow, tool calls, token refresh)
- [ ] Privacy policy is live at a public URL
- [ ] App name and domain comply with YNAB naming rules (see [branding](branding.md) and [ynab-app-requirements](ynab-app-requirements.md))
- [ ] Footer disclaimer is visible on the public landing page
- [ ] Restricted-mode removal review request prepared for YNAB

---

## References

- [Privacy Policy](privacy-policy.md)
- [Branding](branding.md)
- [YNAB App Requirements](ynab-app-requirements.md)
- [OAuth Architecture](oauth-architecture.md)
- [Security](security.md)
