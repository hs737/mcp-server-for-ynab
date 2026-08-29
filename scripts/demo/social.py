"""Render the GitHub social preview card (1280x640).

Deliberately not YNAB-branded: their terms require third-party artwork be
distinguishable from their own, so none of their palette, marks, or the tree
appear here. Amber on near-black, which reads as tooling rather than finance.

The card has to work as a 400px-wide thumbnail in a Slack unfurl, so there is
one headline, one promise, and three short proofs — nothing that depends on
being read at full size.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
ASSETS = REPO / "assets"

BG = "#0d0f13"
PANEL = "#151922"
LINE = "#232936"
TEXT = "#e8eaee"
MUTED = "#8b93a3"
ACCENT = "#f5a524"
GREEN = "#4ec9a5"

SANS = "Helvetica Neue, Helvetica, Arial, sans-serif"
MONO = "Menlo, Monaco, DejaVu Sans Mono, monospace"


def tool_count() -> int:
    """How many tools the server registers with writes enabled.

    Derived, not typed. A card claiming a number the server no longer registers
    is the same drift the generated manifests exist to prevent, except nobody
    reviews an image in a diff.
    """
    script = (
        "from mcp_server_for_ynab.server.app import create_app;"
        "from mcp_server_for_ynab.server.registry import tool_registry;"
        "create_app();"
        "print(len(tool_registry.all()))"
    )
    env = {**os.environ, "YNAB_API_KEY": "render-only", "YNAB_ALLOW_WRITES": "1"}
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True, env=env)
    return int(result.stdout.strip().splitlines()[-1])


def chip(x: float, y: float, label: str, width: float) -> str:
    return f"""
  <rect x="{x}" y="{y}" width="{width}" height="38" rx="19" fill="none" stroke="{LINE}" stroke-width="1.5"/>
  <circle cx="{x + 19}" cy="{y + 19}" r="4" fill="{GREEN}"/>
  <text x="{x + 33}" y="{y + 24}" font-family="{SANS}" font-size="16" fill="{MUTED}">{label}</text>"""


def build(tools: int) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="640" viewBox="0 0 1280 640">
  <defs>
    <linearGradient id="glow" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{ACCENT}" stop-opacity="0.16"/>
      <stop offset="55%" stop-color="{ACCENT}" stop-opacity="0.03"/>
      <stop offset="100%" stop-color="{ACCENT}" stop-opacity="0"/>
    </linearGradient>
  </defs>

  <rect width="1280" height="640" fill="{BG}"/>
  <rect width="1280" height="640" fill="url(#glow)"/>
  <rect x="0" y="0" width="1280" height="5" fill="{ACCENT}"/>

  <!-- left column -->
  <text x="80" y="150" font-family="{MONO}" font-size="17" fill="{ACCENT}" letter-spacing="3">MODEL CONTEXT PROTOCOL</text>

  <text x="78" y="235" font-family="{SANS}" font-size="66" font-weight="700" fill="{TEXT}">MCP Server</text>
  <text x="78" y="308" font-family="{SANS}" font-size="66" font-weight="700" fill="{TEXT}">for <tspan fill="{ACCENT}">YNAB</tspan></text>

  <text x="80" y="368" font-family="{SANS}" font-size="26" fill="{MUTED}">Ask your budget a question.</text>

  {chip(78, 420, "Read-only by default", 232)}
  {chip(322, 420, f"{tools} tools", 132)}
  {chip(466, 420, "Every write reversible", 236)}

  <rect x="78" y="508" width="392" height="52" rx="10" fill="{PANEL}" stroke="{LINE}"/>
  <text x="100" y="541" font-family="{MONO}" font-size="19" fill="{MUTED}">$ <tspan fill="{TEXT}">uvx mcp-server-for-ynab</tspan></text>

  <!-- right column: the exchange that shows the value -->
  <rect x="742" y="112" width="462" height="416" rx="14" fill="{PANEL}" stroke="{LINE}" stroke-width="1.5"/>

  <circle cx="770" cy="142" r="5.5" fill="#3d4351"/>
  <circle cx="789" cy="142" r="5.5" fill="#3d4351"/>
  <circle cx="808" cy="142" r="5.5" fill="#3d4351"/>

  <line x1="742" y1="170" x2="1204" y2="170" stroke="{LINE}"/>

  <text x="770" y="212" font-family="{MONO}" font-size="17" fill="{ACCENT}">&gt;</text>
  <text x="792" y="212" font-family="{MONO}" font-size="17" fill="{TEXT}">What subscriptions am I</text>
  <text x="792" y="236" font-family="{MONO}" font-size="17" fill="{TEXT}">paying for?</text>

  <text x="770" y="288" font-family="{MONO}" font-size="15" fill="{GREEN}">●</text>
  <text x="792" y="288" font-family="{MONO}" font-size="15" fill="{MUTED}">analysis_recurring_charges</text>

  <text x="792" y="330" font-family="{MONO}" font-size="16" fill="{TEXT}">6 found</text>
  <text x="890" y="330" font-family="{MONO}" font-size="16" fill="{MUTED}">·</text>
  <text x="910" y="330" font-family="{MONO}" font-size="16" fill="{ACCENT}">$4,418.88 / year</text>

  <text x="792" y="372" font-family="{MONO}" font-size="15" fill="{MUTED}">Nationwide Insurance</text>
  <text x="1090" y="372" font-family="{MONO}" font-size="15" fill="{TEXT}">$1,704.00</text>

  <text x="792" y="402" font-family="{MONO}" font-size="15" fill="{MUTED}">Fiber Internet</text>
  <text x="1102" y="402" font-family="{MONO}" font-size="15" fill="{TEXT}">$959.88</text>

  <text x="792" y="432" font-family="{MONO}" font-size="15" fill="{MUTED}">Mobile Plan</text>
  <text x="1102" y="432" font-family="{MONO}" font-size="15" fill="{TEXT}">$783.24</text>

  <text x="792" y="462" font-family="{MONO}" font-size="15" fill="{MUTED}">Streaming Plus</text>
  <text x="1102" y="462" font-family="{MONO}" font-size="15" fill="{TEXT}">$275.88</text>

  <line x1="770" y1="486" x2="1176" y2="486" stroke="{LINE}"/>
  <text x="770" y="512" font-family="{SANS}" font-size="13" fill="#5c6373">Sample data</text>

  <text x="1176" y="512" font-family="{SANS}" font-size="13" fill="#5c6373" text-anchor="end">github.com/hs737/mcp-server-for-ynab</text>
</svg>"""


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    svg = HERE / ".social.svg"
    png = ASSETS / "social-preview.png"
    tools = tool_count()
    print(f"tool count: {tools}")
    svg.write_text(build(tools))
    subprocess.run(
        ["rsvg-convert", "-w", "1280", "-h", "640", "-o", str(png), str(svg)],
        check=True,
    )
    print(f"wrote {png} ({png.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
