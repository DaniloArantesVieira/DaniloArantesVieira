"""Fetch the public GitHub calendar without authentication or invented counts."""

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
USERNAME = "DaniloArantesVieira"
OUTPUT = ROOT / "data/contributions.json"


def parse_contributions(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    tooltips = {
        tip.get("for"): tip.get_text(" ", strip=True)
        for tip in soup.select("tool-tip[for]")
    }
    days = {}
    for cell in soup.select("[data-date][data-level]"):
        try:
            day = date.fromisoformat(cell["data-date"]).isoformat()
            level = int(cell["data-level"])
        except (ValueError, TypeError):
            continue
        if level not in range(5):
            continue
        record = {"date": day, "level": level}
        # Only accept explicit counts; a level is never an exact count.
        raw_count = cell.get("data-count", "")
        if re.fullmatch(r"[0-9]+", raw_count):
            record["count"] = int(raw_count)
        else:
            label = tooltips.get(cell.get("id"), "") or cell.get("aria-label", "")
            match = re.match(r"^([0-9]+(?:,[0-9]{3})*) contributions?\b", label, re.I)
            if match:
                record["count"] = int(match[1].replace(",", ""))
            elif re.match(r"^No contributions\b", label, re.I):
                record["count"] = 0
        previous = days.get(day)
        if previous and previous["level"] != level:
            raise ValueError(f"Conflicting contribution levels for {day}.")
        if previous and "count" in previous:
            if "count" in record and record["count"] != previous["count"]:
                raise ValueError(f"Conflicting contribution counts for {day}.")
            record = previous
        days[day] = record
    if not days:
        raise ValueError("No contribution days found: GitHub calendar markup may have changed.")
    return [days[key] for key in sorted(days)]


def main() -> None:
    response = requests.get(
        f"https://github.com/users/{USERNAME}/contributions",
        headers={
            "User-Agent": f"{USERNAME}-profile-art/1.0 (public contribution calendar)",
            "Accept-Language": "en-US,en;q=0.9",
        },
        timeout=(10, 30),
    )
    response.raise_for_status()
    days = parse_contributions(response.text)
    if OUTPUT.exists():
        try:
            existing = json.loads(OUTPUT.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeError):
            existing = None
        if (
            isinstance(existing, dict)
            and existing.get("username") == USERNAME
            and existing.get("days") == days
        ):
            print("Contribution data unchanged.")
            return
    payload = {
        "username": USERNAME,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "days": days,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    # Replace only after a complete, successful fetch and parse.
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT)
    print(f"Saved {len(days)} days ({days[0]['date']} to {days[-1]['date']}).")


if __name__ == "__main__":
    try:
        main()
    except (requests.RequestException, ValueError) as error:
        raise SystemExit(f"Contribution fetch failed: {error}") from error
