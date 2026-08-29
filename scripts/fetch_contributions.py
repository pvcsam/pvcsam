#!/usr/bin/env python3
"""Scrape the public contribution calendar into data/contributions.json.

No GraphQL, no personal access token: GitHub serves the calendar as public HTML
at https://github.com/users/<user>/contributions -- the same fragment the
profile page itself renders. That means the daily workflow needs no secret and
cannot break when a token expires.

The flip side is that this is an undocumented endpoint, so the parse is
defensive and fails loudly rather than writing a half-empty calendar over a good
one.

    python scripts/fetch_contributions.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

USER = "pvcsam"
URL = f"https://github.com/users/{USER}/contributions"
OUT = Path("data/contributions.json")

HEADERS = {
    "User-Agent": f"{USER}-profile-art/1.0 (+https://github.com/{USER}/{USER})",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "text/html",
}

# "5 contributions on January 3rd." / "No contributions on June 1st."
COUNT_RE = re.compile(r"^(No|[\d,]+)\s+contribution", re.I)


def fetch_html() -> str:
    resp = requests.get(URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_days(html: str) -> list[dict]:
    """Pull (date, count, level) out of the calendar's day cells."""
    soup = BeautifulSoup(html, "html.parser")
    cells = soup.select("td.ContributionCalendar-day[data-date]")
    if not cells:
        raise RuntimeError(
            "no day cells found -- GitHub changed the contributions markup, "
            "the selector in parse_days() needs updating"
        )

    # The count lives in a tooltip keyed by the cell id, not on the cell itself.
    tooltips: dict[str, str] = {}
    for tip in soup.select("tool-tip[for]"):
        tooltips[tip["for"]] = tip.get_text(" ", strip=True)

    days: list[dict] = []
    for cell in cells:
        iso = cell["data-date"]
        level = int(cell.get("data-level", 0))

        count = 0
        text = tooltips.get(cell.get("id", ""), "")
        m = COUNT_RE.match(text)
        if m:
            count = 0 if m.group(1).lower() == "no" else int(m.group(1).replace(",", ""))
        elif level > 0:
            # Tooltip missing but the cell is shaded -- don't silently claim zero.
            count = level

        days.append({"date": iso, "count": count, "level": level})

    days.sort(key=lambda d: d["date"])
    return days


def streaks(days: list[dict]) -> tuple[int, int]:
    """Current and longest run of consecutive days with at least one contribution.

    Today is excluded from breaking the current streak: a day that has not
    happened yet legitimately has zero contributions.
    """
    longest = run = 0
    for day in days:
        run = run + 1 if day["count"] > 0 else 0
        longest = max(longest, run)

    today = date.today().isoformat()
    trailing = [d for d in days if d["date"] <= today]
    if trailing and trailing[-1]["date"] == today and trailing[-1]["count"] == 0:
        trailing = trailing[:-1]

    current = 0
    for day in reversed(trailing):
        if day["count"] == 0:
            break
        current += 1

    return current, longest


def build_payload(days: list[dict]) -> dict:
    total = sum(d["count"] for d in days)
    current, longest = streaks(days)
    best = max(days, key=lambda d: d["count"]) if days else {"date": None, "count": 0}

    monthly: dict[str, int] = defaultdict(int)
    for day in days:
        monthly[day["date"][:7]] += day["count"]

    return {
        "user": USER,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "range": {"start": days[0]["date"], "end": days[-1]["date"]} if days else {},
        "stats": {
            "total": total,
            "current_streak": current,
            "longest_streak": longest,
            "best_day": {"date": best["date"], "count": best["count"]},
            "monthly": dict(sorted(monthly.items())),
        },
        "days": days,
    }


def main() -> int:
    print(f"fetching {URL}")
    try:
        days = parse_days(fetch_html())
    except Exception as exc:  # noqa: BLE001 -- surface any failure to the workflow log
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # A real year is 365-371 cells. Anything far short means a bad parse, and
    # overwriting a good calendar with it would be worse than failing.
    if len(days) < 300:
        print(f"error: only {len(days)} days parsed, refusing to write", file=sys.stderr)
        return 1

    payload = build_payload(days)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    s = payload["stats"]
    print(f"wrote {OUT} -- {len(days)} days, {s['total']:,} contributions, "
          f"streak {s['current_streak']} (longest {s['longest_streak']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
