# Distribution

Where this server is published, how each channel updates, and what a release
has to do to keep them in step.

## Automated by a release

Pushing a version tag runs `.github/workflows/release.yml`, which publishes to
all of these. Nothing here needs a manual step.

| Channel | Artifact | Notes |
|---------|----------|-------|
| [PyPI](https://pypi.org/project/mcp-server-for-ynab/) | wheel + sdist | Trusted Publishing (OIDC). No token is stored in this repository. |
| [GitHub Releases](https://github.com/hs737/mcp-server-for-ynab/releases) | `.mcpb` bundle | Attached after the PyPI upload, because the bundle launches `uvx mcp-server-for-ynab==<version>` and would otherwise be a one-click install that cannot resolve. |
| [MCP Registry](https://registry.modelcontextprotocol.io) | `server.json` | Also after PyPI: ownership is verified by reading the `mcp-name` marker out of the package description on PyPI, so that description has to exist first. |
| GHCR | container image | `ghcr.io/hs737/mcp-server-for-ynab`, amd64 and arm64. Also rebuilt on `master` as `:edge`. |

`scripts/sync_packaging.py` generates every manifest that repeats the version —
the plugin, its marketplace, `.mcp.json`, the MCPB manifest, and `server.json`.
`make packaging-check` fails CI when a committed copy has drifted. Never edit
those files by hand.

## Needs configuration once

**Docker Hub.** The container workflow pushes there only when it is configured,
and skips it otherwise rather than failing, so a fork without credentials still
gets a GHCR image. To enable it:

- repository **variable** `DOCKERHUB_USERNAME` — a variable, not a secret,
  because it forms part of the image name and a secret would be masked in the
  tag list and break the push
- repository **secret** `DOCKERHUB_TOKEN` — an access token, not the password

## Directories that index on their own

These crawl public repositories and the MCP Registry. Being in the registry is
the highest-leverage entry, because several of them read from it.

- **[Glama](https://glama.ai/mcp/servers)** — `glama.json` in the repo root
  records the maintainer so the listing attributes correctly.
- **[PulseMCP](https://www.pulsemcp.com/servers)** — indexes public servers;
  has a submit form to speed it up.

## Listed

- **[mcpservers.org](https://mcpservers.org/servers/hs737/mcp-server-for-ynab)**
  — submitted and live. The README carries their badge.

## Directories that need a human

No API and no pull-request path — a web form, with a paid upsell that is not
required.

- **[pulsemcp.com](https://www.pulsemcp.com)** — Submit in the nav bar.

Text to paste, so the listings stay consistent with everything else:

- **Name:** MCP Server for YNAB
- **Link:** https://github.com/hs737/mcp-server-for-ynab
- **Category:** Finance
- **Short description:** Connect your AI assistant to YNAB. Read-only by
  default, with reversible opt-in writes.
- **Long description:** An MCP server for YNAB. Ask in plain language how a
  month is going, what is overspent, which transactions still need a category,
  or what your subscriptions cost per year. Read-only by default — the write
  tools are not registered at all until you opt in — and every write records the
  state that preceded it, so it can be undone. Nothing is sent anywhere except
  api.ynab.com.

## Curated lists

- **[awesome-ynab](https://github.com/scottrobertson/awesome-ynab)** — added by
  pull request; entries are alphabetical.

## Adding a channel

Two rules, both learned the hard way:

1. If it carries a version number, generate it in `scripts/sync_packaging.py`
   and add it to `targets()`. A hand-maintained copy drifts silently, and the
   symptom is an install surface that quietly fetches the previous release.
2. Validate against the real service, not a local copy of its schema. The
   registry rejected the first `server.json` for a description over its
   100-character limit — a rule no local linting would have known about, and one
   that would otherwise have surfaced only after a tag was already pushed.
