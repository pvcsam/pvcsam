#!/usr/bin/env python3
"""Render data/contributions.json as an animated 53x7 contribution calendar.

Rounded boxes on a GitHub-ish green ramp, revealed once by a diagonal
line-after-line slide-down and then frozen -- no looping glow. The stagger is
CSS-class-based rather than per-cell inline style, which keeps the file ~5x
smaller than 365 individual animation-delay declarations.

    python scripts/render_heatmap_svg.py   # writes contrib-heatmap.svg
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

SRC = Path("data/contributions.json")
OUT = Path("contrib-heatmap.svg")

#          none  ->  brightest (level 5 is a neon top end GitHub doesn't have)
PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]

BG = "#0d1117"
BORDER = "#30363d"
TEXT = "#c9d1d9"
DIM = "#8b949e"
ACCENT = "#39d353"

FONT = "'SFMono-Regular', 'DejaVu Sans Mono', 'Menlo', 'Consolas', monospace"

WIDTH = 860.0          # matches 370 (portrait) + 490 (card) so the edges line up
LEFT = 34.0            # room for the Mon/Wed/Fri labels
RIGHT = 14.0
TOP = 30.0             # room for the month labels
WEEKS = 53
DAYS = 7
GAP = 3.0
RADIUS = 2.5

PITCH = (WIDTH - LEFT - RIGHT) / WEEKS
CELL = PITCH - GAP

STEP = 0.014           # seconds between diagonal bands
FADE = 0.45            # how long one band takes to appear
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def keytimes(delay: float, total: float) -> str:
    """Shared timeline positions for a group revealed `delay` seconds in."""
    a = max(0.0002, min(delay / total, 0.997))
    b = max(a + 0.0005, min((delay + FADE) / total, 0.999))
    return f"0;0.0001;{a:.4f};{b:.4f};1"


def reveal(delay: float, total: float) -> str:
    """A staggered fade-in whose t=0 frame is the *finished* image.

    Renderers that embed an SVG via <img> -- which is the only way GitHub will
    show one -- may hold the animation clock at t=0 instead of running it. So
    the first keyframe is opacity 1: a held clock shows a complete calendar,
    while a running clock drops to 0 within a fraction of a millisecond
    (far under one frame) and then plays the real diagonal reveal.

    This is the same property that makes the existing snake.svg survive in an
    <img>: its resting state is already a complete picture.
    """
    return (
        f'<animate attributeName="opacity" values="1;0;0;1;1"'
        f' keyTimes="{keytimes(delay, total)}" dur="{total:.2f}s" fill="freeze"/>'
    )


def to_grid(days: list[dict]) -> list[list[dict | None]]:
    """Lay the flat day list out as [week][weekday], GitHub-style (Sunday first)."""
    grid: list[list[dict | None]] = [[None] * DAYS for _ in range(WEEKS)]
    if not days:
        return grid

    first = date.fromisoformat(days[0]["date"])
    offset = (first.weekday() + 1) % DAYS   # Python: Monday=0; GitHub: Sunday=0

    for n, day in enumerate(days):
        week, weekday = divmod(n + offset, DAYS)
        if week < WEEKS:
            grid[week][weekday] = day
    return grid


def level_of(day: dict, neon_at: int) -> int:
    """GitHub reports levels 0-4; promote the heaviest days to our level 5."""
    level = day["level"]
    if level >= 4 and neon_at and day["count"] >= neon_at:
        return 5
    return level


def neon_threshold(days: list[dict]) -> int:
    """Top quartile of the already-maxed-out days, so level 5 stays rare."""
    top = sorted(d["count"] for d in days if d["level"] >= 4)
    if len(top) < 4:
        return 0
    return top[int(len(top) * 0.75)]


def month_labels(grid: list[list[dict | None]]) -> str:
    out: list[str] = []
    previous = None
    last_week = -99
    for w, week in enumerate(grid):
        cell = next((d for d in week if d), None)
        if not cell:
            continue
        month = int(cell["date"][5:7])
        if month == previous:
            continue
        previous = month
        # A month starting mid-week would collide with the previous label.
        if w - last_week < 3:
            continue
        x = round(LEFT + w * PITCH, 2)
        out.append(f'<text x="{x}" y="{TOP - 10}" fill="{DIM}" font-size="10">'
                   f"{MONTHS[month - 1]}</text>")
        last_week = w
    return "".join(out)


def day_labels() -> str:
    out = []
    for i, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        y = round(TOP + i * PITCH + CELL * 0.75, 2)
        out.append(f'<text x="0" y="{y}" fill="{DIM}" font-size="9">{name}</text>')
    return "".join(out)


def build(payload: dict) -> str:
    days = payload["days"]
    stats = payload["stats"]
    grid = to_grid(days)
    neon_at = neon_threshold(days)

    grid_h = TOP + DAYS * PITCH
    legend_y = grid_h + 18
    footer_y = legend_y + 30
    height = round(footer_y + 18, 2)

    # Cells are grouped by diagonal band so one <animate> drives a whole band
    # instead of 371 individual ones -- same reveal, a fraction of the bytes.
    bands: dict[int, list[str]] = {}
    for w, week in enumerate(grid):
        for d, day in enumerate(week):
            if day is None:
                continue
            x = round(LEFT + w * PITCH, 2)
            y = round(TOP + d * PITCH, 2)
            fill = PALETTE[level_of(day, neon_at)]
            plural = "" if day["count"] == 1 else "s"
            bands.setdefault(w + d, []).append(
                f'<rect x="{x}" y="{y}" width="{round(CELL, 2)}"'
                f' height="{round(CELL, 2)}" rx="{RADIUS}" fill="{fill}">'
                f'<title>{day["count"]} contribution{plural} on {day["date"]}</title>'
                f"</rect>"
            )

    total = max(bands) * STEP + FADE if bands else FADE
    cells = "".join(
        f'<g opacity="1">{reveal(b * STEP, total)}{"".join(rects)}</g>'
        for b, rects in sorted(bands.items())
    )

    # Legend: Less [][][][][] More, right-aligned under the grid.
    legend: list[str] = []
    lx = WIDTH - RIGHT - (len(PALETTE) * PITCH) - 44
    legend.append(f'<text x="{round(lx - 6, 2)}" y="{legend_y + CELL * 0.8:.2f}"'
                  f' fill="{DIM}" font-size="10" text-anchor="end">Less</text>')
    for i, color in enumerate(PALETTE):
        legend.append(
            f'<rect x="{round(lx + i * PITCH, 2)}" y="{legend_y}"'
            f' width="{round(CELL, 2)}" height="{round(CELL, 2)}"'
            f' rx="{RADIUS}" fill="{color}"/>'
        )
    legend.append(f'<text x="{round(lx + len(PALETTE) * PITCH + 2, 2)}"'
                  f' y="{legend_y + CELL * 0.8:.2f}" fill="{DIM}" font-size="10">More</text>')

    footer = (
        f'<text x="{LEFT}" y="{footer_y}" fill="{TEXT}" font-size="12">'
        f'<tspan fill="{ACCENT}" font-weight="bold">{stats["total"]:,}</tspan>'
        f" contributions in the last year</text>"
        f'<text x="{WIDTH - RIGHT}" y="{footer_y}" fill="{DIM}" font-size="11"'
        f' text-anchor="end">current streak '
        f'<tspan fill="{TEXT}">{stats["current_streak"]}d</tspan>'
        f' &#183; longest <tspan fill="{TEXT}">{stats["longest_streak"]}d</tspan>'
        f' &#183; best day <tspan fill="{TEXT}">{stats["best_day"]["count"]}</tspan></text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}"'
        f' viewBox="0 0 {WIDTH} {height}" role="img"'
        f' aria-label="{stats["total"]} contributions in the last year">'
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="8"'
        f' fill="{BG}" stroke="{BORDER}"/>'
        f'<g font-family="{FONT}">'
        f"{month_labels(grid)}{day_labels()}"
        f"{cells}{''.join(legend)}{footer}"
        f"</g></svg>\n"
    )


def main() -> int:
    if not SRC.exists():
        print(f"error: {SRC} not found -- run fetch_contributions.py first", file=sys.stderr)
        return 1

    payload = json.loads(SRC.read_text(encoding="utf-8"))
    OUT.write_text(build(payload), encoding="utf-8")
    print(f"wrote {OUT} -- {len(payload['days'])} days, "
          f"{payload['stats']['total']:,} contributions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
