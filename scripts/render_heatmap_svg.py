"""Render real contribution days in Sunday-first calendar columns."""

import json
from datetime import date, timedelta
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PALETTE = ("#161B22", "#0B3A53", "#0E7490", "#06B6D4", "#67E8F9")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
FONT = "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, monospace"


def render(data: dict) -> str:
    days = data["days"]
    if not days:
        raise ValueError("Cannot render an empty calendar.")
    parsed = {}
    for record in days:
        day = date.fromisoformat(record["date"])
        level = record["level"]
        if type(level) is not int or level not in range(5):
            raise ValueError(f"Invalid contribution level for {day}.")
        if day in parsed:
            raise ValueError(f"Duplicate contribution date: {day}.")
        if "count" in record and (type(record["count"]) is not int or record["count"] < 0):
            raise ValueError(f"Invalid contribution count for {day}.")
        parsed[day] = record
    first, last = min(parsed), max(parsed)
    start = first - timedelta(days=(first.weekday() + 1) % 7)
    weeks = (last - start).days // 7 + 1
    # Rare leap-year alignments can span 54 columns; never silently drop a day.
    if weeks > 54:
        raise ValueError("Expected at most 54 calendar weeks.")
    step = min(15, 798 / weeks)
    cells, months = [], []
    previous_month = None
    last_month_x = -100
    for day, record in sorted(parsed.items()):
        column, row = divmod((day - start).days, 7)
        x, y = 70 + column * step, 98 + row * 17
        if (day.year, day.month) != previous_month:
            if x - last_month_x >= 34:
                months.append(f'<text x="{x:.1f}" y="84">{MONTHS[day.month - 1]}</text>')
                last_month_x = x
            previous_month = (day.year, day.month)
        activity = f"{record['count']} contributions" if "count" in record else f"activity level {record['level']} of 4"
        label = escape(f"{day.isoformat()}: {activity}", quote=True)
        delay = column * 16 + row * 20
        cells.append(
            f'<rect class="day" x="{x:.1f}" y="{y}" width="{step - 3:.1f}" height="12" rx="2" '
            f'fill="{PALETTE[record["level"]]}" style="animation-delay:{delay}ms"><title>{label}</title></rect>'
        )
    username = escape(str(data["username"]))
    fetched = escape(str(data["fetched_at"]))
    legend = ''.join(f'<rect x="{741 + index * 17}" y="239" width="12" height="12" rx="2" fill="{color}"/>' for index, color in enumerate(PALETTE))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="280" viewBox="0 0 900 280" role="img" aria-labelledby="title description">
  <title id="title">{username} — GitHub contribution activity</title>
  <desc id="description">Public GitHub calendar from {first} to {last}. Only supplied days are drawn. Retrieved {fetched}. No estimated contribution totals.</desc>
  <style>
    text {{ font-family: {FONT}; font-size: 11px; fill: #8B949E; }}
    .day {{ animation: reveal 350ms ease-out both; }}
    @keyframes reveal {{ from {{ opacity: 0; transform: translateY(-4px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    @media (prefers-reduced-motion: reduce) {{ .day {{ animation: none; }} }}
  </style>
  <rect x="0.5" y="0.5" width="899" height="279" rx="12" fill="#0D1117" stroke="#30363D"/>
  <text x="28" y="32" style="font-size:14px;fill:#22D3EE">{username}</text>
  <circle cx="28" cy="53" r="3" fill="#3FB950"/>
  <text x="39" y="57">GitHub activity • updated daily</text>
  {''.join(months)}
  <text x="28" y="124">Mon</text>
  <text x="28" y="158">Wed</text>
  <text x="28" y="192">Fri</text>
  {chr(10).join(cells)}
  <path d="M28 222H872" stroke="#30363D"/>
  <text x="28" y="249">{first} — {last}</text>
  <text x="700" y="249">Less</text>{legend}<text x="832" y="249">More</text>
</svg>
'''


def main() -> None:
    data = json.loads((ROOT / "data/contributions.json").read_text(encoding="utf-8"))
    svg = render(data)
    output = ROOT / "assets/contrib-heatmap.svg"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg, encoding="utf-8")
    print(f"Rendered assets/contrib-heatmap.svg ({len(data['days'])} days).")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError) as error:
        raise SystemExit(f"Heatmap render failed: {error}") from error
