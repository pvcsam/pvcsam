#!/usr/bin/env python3
"""Hand-author a neofetch-style info card SVG.

This is the story the numbers can't tell. The contribution graph already covers
the GitHub stats, so keep counts out of here -- role, stack and highlights only.

Each line fades and slides in on a short stagger, so the panel looks like it is
printing next to the portrait. Set STATIC=1 to emit a frozen frame, which is
what you want for a local Quick Look preview.

    python scripts/make_info_card.py   # writes info-card.svg
"""

from __future__ import annotations

import os
from pathlib import Path
from xml.sax.saxutils import escape

# ---------------------------------------------------------------------------
# CONFIG -- everything you need to personalise is in this block.
# Replace every TODO. Keep values short; long ones overflow the card.
# ---------------------------------------------------------------------------

USER = "pvcsam"
HOST = "github"

TITLE = "TODO: Your Name"            # e.g. "Matthieu D."
SUBTITLE = "TODO: one-line tagline"  # e.g. "Full-stack dev, France"

# (key, value) -- an empty key continues the previous row's value block.
ROWS = [
    ("Now",        "TODO: what you're doing now"),
    ("Prev",       "TODO: what you did before"),
    ("Stack",      "JavaScript - TypeScript - React"),
    ("",           "HTML - CSS - Python - C#"),
    ("Editor",     "WebStorm"),
    ("Highlights", "TODO: something you shipped"),
    ("",           "TODO: something you're proud of"),
    ("",           "TODO: something you're learning"),
]

# ---------------------------------------------------------------------------

BG = "#0d1117"
BORDER = "#30363d"
KEY = "#39d353"        # neofetch keys carry the accent colour
VALUE = "#c9d1d9"
DIM = "#8b949e"
ACCENT = "#58a6ff"

FONT = "'SFMono-Regular', 'DejaVu Sans Mono', 'Menlo', 'Consolas', monospace"
FS = 13.0              # font size
LINE_H = 22.0
PAD = 22.0
KEY_W = 100.0          # x offset where values start on two-column rows
WIDTH = 490.0          # must match the <img width> used in the README

STATIC = os.environ.get("STATIC") == "1"

STAGGER = 0.09         # seconds between rows
FADE = 0.45            # how long one row takes to appear
# Every row shares one timeline, so it has to be long enough for the last one.
TOTAL = 0.35 + (len(ROWS) + 3) * STAGGER + FADE


def row(y: float, i: float, key: str, value: str, color: str = VALUE) -> str:
    """A two-column key/value row, staggered by index `i`."""
    return _group(i, [
        _text(PAD, y, key, KEY, bold=True) if key else "",
        _text(PAD + KEY_W, y, value, color),
    ])


def banner(y: float, i: float, value: str, color: str = VALUE) -> str:
    """A full-width row with no key column -- header, tagline, prompt."""
    return _group(i, [_text(PAD, y, value, color)])


def _text(x: float, y: float, s: str, color: str, bold: bool = False) -> str:
    weight = ' font-weight="bold"' if bold else ""
    return f'<text x="{x}" y="{y}" fill="{color}"{weight}>{escape(s)}</text>'


def _group(i: float, parts: list[str]) -> str:
    """One staggered row.

    SMIL rather than CSS keyframes, and the first keyframe is the *finished*
    state: a renderer that holds the clock at t=0 (which is what happens to an
    SVG embedded via <img>) shows a complete card rather than an empty frame,
    while a running clock plays the real slide-in. See reveal() in
    render_heatmap_svg.py for the full reasoning.
    """
    body = "".join(parts)
    if STATIC:
        return f"<g>{body}</g>"

    delay = 0.35 + i * STAGGER
    a = max(0.0002, min(delay / TOTAL, 0.997))
    b = max(a + 0.0005, min((delay + FADE) / TOTAL, 0.999))
    kt = f"0;0.0001;{a:.4f};{b:.4f};1"
    return (
        f'<g opacity="1">'
        f'<animate attributeName="opacity" values="1;0;0;1;1"'
        f' keyTimes="{kt}" dur="{TOTAL:.2f}s" fill="freeze"/>'
        f'<animateTransform attributeName="transform" type="translate"'
        f' values="0 0;-10 0;-10 0;0 0;0 0" keyTimes="{kt}"'
        f' dur="{TOTAL:.2f}s" fill="freeze"/>'
        f"{body}</g>"
    )


def build() -> str:
    body: list[str] = []
    y = PAD + 26.0
    handle = f"{USER}@{HOST}"

    # neofetch header: user@host over a rule the same width as that string.
    body.append(banner(y, 0, handle, ACCENT))
    y += 16.0
    body.append(banner(y, 0.5, "-" * len(handle), DIM))
    y += LINE_H + 4

    body.append(banner(y, 1, TITLE, VALUE))
    y += LINE_H
    body.append(banner(y, 1.5, SUBTITLE, DIM))
    y += LINE_H + 10

    for n, (key, value) in enumerate(ROWS, start=2):
        body.append(row(y, n, key, value))
        y += LINE_H

    y += 6
    body.append(banner(y, len(ROWS) + 2, f"{USER} ~ $ _", KEY))

    height = round(y + PAD + 8, 2)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}"'
        f' viewBox="0 0 {WIDTH} {height}" role="img"'
        f' aria-label="neofetch-style info card for {escape(USER)}">'
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="8"'
        f' fill="{BG}" stroke="{BORDER}"/>'
        f'<g font-family="{FONT}" font-size="{FS}">{"".join(body)}</g>'
        f"</svg>\n"
    )


def main() -> int:
    out = Path("info-card.svg")
    out.write_text(build(), encoding="utf-8")
    print(f"wrote {out}{' (static frame)' if STATIC else ''}")
    if "TODO" in TITLE or any("TODO" in v for _, v in ROWS):
        print("  ! placeholders still present -- edit the CONFIG block in this script")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
