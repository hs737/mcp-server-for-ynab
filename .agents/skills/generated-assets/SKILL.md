---
name: generated-assets
description: Keep the README GIF and social preview card truthful by re-rendering them whenever a code change alters what they show.
---

# Generated Assets

The README GIF and the social preview card are rendered from the real server,
not drawn by hand. That is what makes them trustworthy, and also what makes them
a maintenance hazard: they assert things about the product inside pixels, where
no reviewer proofreads them. A stale demo is worse than none, because it is a
confident claim that is quietly wrong.

## Use When

- Changing the name, output shape, or wording of any tool the demo shows
- Changing money formatting, or anything else in `models/amounts.py`
- Adding or removing tools, which moves the count on the card
- Changing the project's name, tagline, or headline value proposition
- Editing anything under `scripts/demo/`
- Preparing a release, as a final check

## What exists

| Path | What it is |
|------|-----------|
| `assets/demo.gif` | README demo, ~13s, referenced by absolute URL so it also renders on PyPI |
| `assets/social-preview.png` | 1280×640 card for GitHub's social preview and link unfurls |
| `assets/manifest.json` | The claims the assets make, recorded so drift is detectable |
| `scripts/demo/backend.py` | A synthetic YNAB API the demo runs against |
| `scripts/demo/capture.py` | Invokes the real tools, saves what they return |
| `scripts/demo/social.py` | Renders the card |
| `scripts/demo/gif.py` | Renders the GIF frames and assembles them |
| `scripts/check_assets.py` | Compares the recorded claims against live code |

## Re-rendering

```bash
brew install librsvg imagemagick   # once
make assets                        # capture, render both, record the claims
make assets-check                  # fail if the claims have gone stale
```

`make assets-check` runs in `make check`, so drift fails the build rather than
shipping. It compares the *claims* — tool count, which tools appear, the money
format — not the pixels. Byte comparison would be stricter and useless: the
renderers are deterministic, but ImageMagick and font rendering are not stable
across machines, and a check that fails for the wrong reason gets muted.

## The rules that matter

**Never type a number into an asset.** The tool count on the card is read from
the registry at render time. If you find yourself editing a figure in an SVG,
derive it instead — this is the same drift the generated packaging manifests
exist to prevent, except an image is harder to review.

**Never use real budget data.** Everything comes from `scripts/demo/backend.py`,
a synthetic plan. Publishing a demo built from someone's actual finances is not
recoverable once it is in a README, a cached unfurl, and a dozen forks. Both
assets carry a visible "sample data" marker; keep it.

**Never fake output.** The point of running the real server against a fake
budget is that the demo cannot claim behaviour the code does not have. If a
result looks unimpressive, fix the tool or change the question — do not edit the
numbers. The GIF reads the tools' own `*_display` strings for the same reason:
a second formatter in the renderer could disagree with the product.

**Keep YNAB's branding out.** YNAB requires third-party artwork be
distinguishable from theirs, so the palette is amber on near-black and none of
their marks, colours, or the tree appear. See `ynab-platform-compliance`.

## Design constraints worth preserving

- The card must survive being shown at 400px in a Slack unfurl: one headline,
  one promise, three short proofs, nothing that needs full size to read.
- The GIF answers "what do I get?" in the seconds before someone scrolls past.
  It is not a tour of the tool surface. Two questions is the budget.
- Keep the GIF small enough not to slow the README. It is currently ~140 KB;
  treat 500 KB as the ceiling and drop frames or colours before exceeding it.
- The terminal scrolls rather than growing, because the second answer is the one
  that sells it and it must not sit below the fold.

## Related Skills

- `ynab-platform-compliance` — naming and branding rules these assets must obey
- `docs-honesty` — the same principle applied to prose
