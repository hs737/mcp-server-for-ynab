"""Render the README demo GIF.

Frames are drawn as SVG and assembled with ImageMagick. The numbers come from
captured.json — real output from the real tools, run against a synthetic budget,
so nothing here is typed by hand and nobody's finances are published.

Kept deliberately short. The job of this GIF is to answer "what do I get?" in
the seconds before someone scrolls past, not to tour the tool surface.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
ASSETS = REPO / "assets"
FRAMES = HERE / ".frames"

W, H = 920, 540
BG = "#0d0f13"
CHROME = "#151922"
LINE = "#232936"
TEXT = "#e8eaee"
MUTED = "#8b93a3"
DIM = "#5c6373"
ACCENT = "#f5a524"
GREEN = "#4ec9a5"
RED = "#e5766b"

MONO = "Menlo, Monaco, DejaVu Sans Mono, monospace"
SANS = "Helvetica Neue, Helvetica, Arial, sans-serif"

FS = 16.5  # font size
LH = 27.5  # line height
X0 = 42.0  # left margin
Y0 = 108.0  # first baseline
CW = 9.92  # character width at this size, for cursor placement

# The session is longer than the window, so old lines scroll off the top the
# way a terminal does. Padding the canvas to a fixed height instead would
# leave the second answer half below the fold, which is the one that sells it.
MAX_LINES = 14


def money(payload: dict[str, object], key: str) -> str:
    """Read the tool's own formatted string for a field.

    Deliberately not a second formatter. The GIF should show exactly what a
    client receives, so if the display format ever changes the demo changes with
    it instead of quietly disagreeing with the product.
    """
    value = payload[f"{key}_display"]
    assert isinstance(value, str)
    return value


@dataclass
class Line:
    """One rendered terminal line."""

    segments: list[tuple[str, str]] = field(default_factory=list)  # (text, colour)
    indent: float = 0.0

    def svg(self, y: float) -> str:
        out = []
        x = X0 + self.indent
        for text, colour in self.segments:
            safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            out.append(
                f'<text x="{x:.1f}" y="{y:.1f}" font-family="{MONO}" '
                f'font-size="{FS}" fill="{colour}" xml:space="preserve">{safe}</text>'
            )
            x += len(text) * CW
        return "".join(out)

    @property
    def width(self) -> float:
        return sum(len(text) for text, _ in self.segments) * CW


def frame_svg(lines: list[Line], cursor_on: bool, cursor_line: int | None) -> str:
    body = []
    for index, line in enumerate(lines):
        y = Y0 + index * LH
        body.append(line.svg(y))
        if cursor_on and cursor_line == index:
            cx = X0 + line.indent + line.width + 2
            body.append(f'<rect x="{cx:.1f}" y="{y - FS + 3:.1f}" width="9" height="{FS + 4:.1f}" fill="{ACCENT}"/>')

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <rect width="{W}" height="{H}" rx="10" fill="{BG}"/>
  <rect width="{W}" height="46" rx="10" fill="{CHROME}"/>
  <rect y="36" width="{W}" height="10" fill="{CHROME}"/>
  <line x1="0" y1="46" x2="{W}" y2="46" stroke="{LINE}"/>
  <circle cx="26" cy="23" r="5.5" fill="#3d4351"/>
  <circle cx="45" cy="23" r="5.5" fill="#3d4351"/>
  <circle cx="64" cy="23" r="5.5" fill="#3d4351"/>
  <text x="{W / 2}" y="28" font-family="{SANS}" font-size="13" fill="{DIM}" text-anchor="middle">MCP Server for YNAB</text>
  {"".join(body)}
  <text x="{W - 20}" y="{H - 16}" font-family="{SANS}" font-size="12" fill="#454b58" text-anchor="end">sample data</text>
</svg>"""


def prompt_line(typed: str) -> Line:
    return Line([("> ", ACCENT), (typed, TEXT)])


def tool_line(name: str) -> Line:
    return Line([("● ", GREEN), (name, MUTED)])


def kv(label: str, value: str, value_colour: str = TEXT, pad: int = 24) -> Line:
    return Line([(label.ljust(pad), MUTED), (value, value_colour)], indent=22)


def build_script() -> list[tuple[list[Line], int, int | None]]:
    """Return (lines, delay_centiseconds, cursor_line) per frame."""
    data = json.loads((HERE / ".captured.json").read_text())
    health = data["overview_month_health"]
    over = data["analysis_overspent_categories"]
    rec = data["analysis_recurring_charges"]

    frames: list[tuple[list[Line], int, int | None]] = []
    canvas: list[Line] = []

    def emit(delay: int, cursor: int | None = None) -> None:
        visible = canvas[-MAX_LINES:]
        offset = len(canvas) - len(visible)
        shifted = None if cursor is None else cursor - offset
        if shifted is not None and not 0 <= shifted < len(visible):
            shifted = None
        frames.append(([Line(list(x.segments), x.indent) for x in visible], delay, shifted))

    def type_out(text: str, *, step: int = 2) -> None:
        canvas.append(prompt_line(""))
        index = len(canvas) - 1
        for i in range(0, len(text) + 1, step):
            canvas[index] = prompt_line(text[:i])
            emit(5, index)
        canvas[index] = prompt_line(text)
        emit(70, index)

    # ---- question 1
    type_out("How is my budget doing this month?")
    canvas.append(Line())
    canvas.append(tool_line("overview_month_health"))
    emit(60)

    canvas.append(Line())
    canvas.append(kv("income", money(health, "income")))
    emit(18)
    canvas.append(kv("budgeted", money(health, "budgeted")))
    emit(18)
    canvas.append(kv("left to assign", money(health, "to_be_budgeted"), ACCENT))
    emit(18)
    canvas.append(Line())

    total = money(over, "total_overspent")
    names = " and ".join(c["name"] for c in over["categories"][:2])
    canvas.append(Line([(f"On track, but {over['overspent_count']} categories are overspent:", TEXT)], indent=22))
    emit(20)
    canvas.append(Line([(f"{names}, {total} in total.", RED)], indent=22))
    emit(190)

    # ---- question 2
    canvas.append(Line())
    type_out("What subscriptions am I paying for?")
    canvas.append(Line())
    canvas.append(tool_line("analysis_recurring_charges"))
    emit(60)
    canvas.append(Line())

    header = Line(
        [
            (f"{rec['recurring_count']} found", TEXT),
            ("   ·   ", DIM),
            (f"{money(rec, 'estimated_annual_total')} a year", ACCENT),
        ],
        indent=22,
    )
    canvas.append(header)
    emit(45)
    canvas.append(Line())

    for charge in rec["charges"][:5]:
        name = charge["payee_name"][:24]
        annual = money(charge, "estimated_annual_cost")
        canvas.append(
            Line(
                [
                    (name.ljust(26), MUTED),
                    (money(charge, "typical_amount").rjust(9), DIM),
                    ("  " + charge["cadence"].ljust(10), DIM),
                    (annual.rjust(11), TEXT),
                ],
                indent=22,
            )
        )
        emit(16)

    emit(400)
    return frames


def main() -> None:
    if shutil.which("rsvg-convert") is None or shutil.which("magick") is None:
        raise SystemExit("needs rsvg-convert and ImageMagick")

    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True)

    script = build_script()
    print(f"rendering {len(script)} frames")

    args: list[str] = ["magick", "-loop", "0"]
    for index, (lines, delay, cursor) in enumerate(script):
        svg_path = FRAMES / f"f{index:04d}.svg"
        png_path = FRAMES / f"f{index:04d}.png"
        blink = (index // 6) % 2 == 0
        svg_path.write_text(frame_svg(lines, cursor is not None and blink, cursor))
        subprocess.run(["rsvg-convert", "-w", str(W), "-o", str(png_path), str(svg_path)], check=True)
        args += ["-delay", str(delay), str(png_path)]

    ASSETS.mkdir(exist_ok=True)
    out = ASSETS / "demo.gif"
    args += ["-layers", "OptimizePlus", "-colors", "96", str(out)]
    subprocess.run(args, check=True)
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
