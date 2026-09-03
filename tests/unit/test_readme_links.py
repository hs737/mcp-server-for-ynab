"""Unit tests: the README's links have to work off GitHub as well as on it.

`readme = "README.md"` in pyproject means this file is also the PyPI project
description, and PyPI renders it standalone. A relative link that GitHub
resolves against the repository resolves on PyPI against
`https://pypi.org/project/mcp-server-for-ynab/` instead, so
`docs/client-setup.md#vs-code` becomes a 404 — which is what happened to every
setup link in the install table, the one part of the page a new user is most
likely to click.

Absolute links work in both places, so the rule is simply that the README has
none of the relative kind. In-page anchors are fine: PyPI's renderer gives
headings ids the same way GitHub does.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "README.md"

LINK = re.compile(r"\]\(([^)]+)\)")
ABSOLUTE = re.compile(r"^(https?:|mailto:|#)")


def _targets() -> list[str]:
    return LINK.findall(README.read_text())


def test_no_relative_links_survive_in_the_readme() -> None:
    relative = sorted({t for t in _targets() if not ABSOLUTE.match(t)})

    assert not relative, (
        "These README links are relative, so they 404 on PyPI, which renders the file "
        f"standalone: {relative}. Point them at "
        "https://github.com/hs737/mcp-server-for-ynab/blob/master/<path> instead."
    )


def test_repository_links_point_at_a_branch_not_a_bare_path() -> None:
    """`github.com/<owner>/<repo>/docs/x.md` is a 404 — it needs blob/<ref>."""
    bad = sorted(
        t
        for t in _targets()
        if t.startswith("https://github.com/hs737/mcp-server-for-ynab/")
        and not re.match(
            r"https://github\.com/hs737/mcp-server-for-ynab/(blob|tree|raw|releases|actions|issues|pull)/",
            t,
        )
    )

    assert not bad, f"These repository links are missing a blob/tree ref and will 404: {bad}"
