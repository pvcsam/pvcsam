#!/usr/bin/env python3
"""Turn the prepped photo into a self-typing monochrome ASCII SVG.

The image is downsampled to a character grid and each cell's brightness picks a
glyph from a density ramp. Two choices keep it readable instead of noisy:
monochrome (one fill colour -- per-character rainbows are what make most ASCII
portraits look like static) and hard contrast (a washed-out background collapses
to the space glyph, so only the subject prints).

The animation is SMIL: every row sits behind a clip rect that wipes
left-to-right on a stagger, with a small block cursor riding the wipe edge. It
prints once and freezes -- no looping. GitHub strips <script> from READMEs but
does play SMIL inside an <img>-embedded SVG, which is the whole trick.

    python scripts/make_ascii_svg.py   # writes pvcsam-ascii.svg
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
from PIL import Image

# bright (sparse) -> dark (dense)
#  ^ the leading space clears the background to nothing
RAMP = " .`:-=+*cs#%@"

BG = "#0d1117"      # GitHub dark canvas
INK = "#c9d1d9"     # one light grey, monochrome on purpose
CURSOR = "#39d353"

FONT = "'SFMono-Regular', 'DejaVu Sans Mono', 'Menlo', 'Consolas', monospace"

# A monospace glyph is about 0.6 as wide as it is tall; the grid has to account
# for that or the portrait comes out vertically stretched.
CHAR_ASPECT = 0.6

LEAD_IN = 0.15   # delay before the first row starts wiping, seconds


def to_rows(img: Image.Image, cols: int, gamma: float) -> list[str]:
    """Downsample to a character grid and map brightness onto the ramp."""
    rows = max(1, round(cols * (img.height / img.width) * CHAR_ASPECT))
    small = img.convert("L").resize((cols, rows), Image.LANCZOS)

    arr = np.array(small, dtype=np.float32) / 255.0
    if gamma != 1.0:
        arr = np.power(arr, gamma)

    # Brightness 1.0 (white) must land on index 0, the space.
    idx = np.clip(((1.0 - arr) * (len(RAMP) - 1)).round().astype(int), 0, len(RAMP) - 1)
    return ["".join(RAMP[i] for i in row) for row in idx]


def build_svg(rows: list[str], font_size: float, stagger: float, wipe: float) -> str:
    cell_w = font_size * CHAR_ASPECT
    line_h = font_size * 1.0
    cols = max(len(r) for r in rows)
    width = round(cols * cell_w, 2)
    height = round(len(rows) * line_h, 2)

    defs: list[str] = []
    texts: list[str] = []
    cursors: list[str] = []

    for i, row in enumerate(rows):
        # No row may begin at exactly t=0: a renderer holding the clock there
        # would clip that row to nothing. Every row is still un-started at t=0,
        # so the base width (the full row) is what a held clock shows.
        begin = round(LEAD_IN + i * stagger, 3)
        y_top = round(i * line_h, 2)
        baseline = round(y_top + font_size * 0.8, 2)

        # Trailing spaces carry no ink; clipping to the last glyph keeps the
        # cursor from running off past the end of a short row.
        row_len = len(row.rstrip()) or 1
        row_w = round(row_len * cell_w, 2)

        # The rect's own width is the FINISHED state, and SMIL animates up to it
        # from 0. A renderer that ignores SMIL (GitHub's image proxy, Quick Look,
        # any static rasteriser) then shows the completed portrait rather than a
        # blank box -- the animation is an enhancement, never a prerequisite.
        defs.append(
            f'<clipPath id="c{i}">'
            f'<rect x="0" y="{y_top}" width="{row_w}" height="{round(line_h, 2)}">'
            f'<animate attributeName="width" from="0" to="{row_w}"'
            f' begin="{begin}s" dur="{wipe}s" fill="freeze"/>'
            f"</rect></clipPath>"
        )

        texts.append(
            f'<text x="0" y="{baseline}" clip-path="url(#c{i})" xml:space="preserve"'
            f' textLength="{round(cols * cell_w, 2)}" lengthAdjust="spacingAndGlyphs"'
            f">{escape(row)}</text>"
        )

        # The block cursor rides the wipe edge, then blinks out.
        cursors.append(
            f'<rect x="0" y="{y_top}" width="{round(cell_w, 2)}"'
            f' height="{round(line_h, 2)}" fill="{CURSOR}" opacity="0">'
            f'<animate attributeName="x" from="0" to="{row_w}"'
            f' begin="{begin}s" dur="{wipe}s" fill="freeze"/>'
            f'<animate attributeName="opacity" values="0;1;1;0"'
            f' keyTimes="0;0.01;0.9;1" begin="{begin}s" dur="{wipe}s" fill="freeze"/>'
            f"</rect>"
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"'
        f' viewBox="0 0 {width} {height}" role="img"'
        f' aria-label="ASCII portrait that types itself in">'
        f'<rect width="100%" height="100%" fill="{BG}"/>'
        f"<defs>{''.join(defs)}</defs>"
        f'<g font-family="{FONT}" font-size="{font_size}" fill="{INK}">'
        f"{''.join(texts)}</g>"
        f"{''.join(cursors)}"
        f"</svg>\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--input", default="assets/source-prepped.png")
    ap.add_argument("-o", "--out", default="pvcsam-ascii.svg")
    ap.add_argument("--cols", type=int, default=100, help="character grid width")
    ap.add_argument("--font-size", type=float, default=10.0)
    ap.add_argument("--gamma", type=float, default=1.0,
                    help=">1 lightens midtones (thins the art), <1 darkens it")
    ap.add_argument("--stagger", type=float, default=0.05, help="delay between rows, seconds")
    ap.add_argument("--wipe", type=float, default=0.45, help="per-row wipe duration, seconds")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"error: {src} not found -- run prep_photo.py first", file=sys.stderr)
        return 1

    rows = to_rows(Image.open(src), args.cols, args.gamma)
    svg = build_svg(rows, args.font_size, args.stagger, args.wipe)

    out = Path(args.out)
    out.write_text(svg, encoding="utf-8")
    total = round((len(rows) - 1) * args.stagger + args.wipe, 2)
    print(f"wrote {out} -- {args.cols}x{len(rows)} chars, {total}s to print")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
