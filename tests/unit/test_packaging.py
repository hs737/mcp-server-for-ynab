"""Unit tests: claims the distribution makes about itself.

pyproject declares the `Typing :: Typed` classifier. That classifier is a
promise to downstream type checkers, and they honour it only when a py.typed
marker actually ships inside the package — without the file the annotations are
invisible to anyone who installs this, and nothing else in CI notices.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import mcp_server_for_ynab

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def test_py_typed_marker_ships_with_the_package() -> None:
    package_dir = Path(mcp_server_for_ynab.__file__).parent
    assert (package_dir / "py.typed").is_file()


def test_typed_classifier_and_marker_agree() -> None:
    classifiers = tomllib.loads(PYPROJECT.read_text())["project"]["classifiers"]
    package_dir = Path(mcp_server_for_ynab.__file__).parent

    assert ("Typing :: Typed" in classifiers) == (package_dir / "py.typed").is_file()
