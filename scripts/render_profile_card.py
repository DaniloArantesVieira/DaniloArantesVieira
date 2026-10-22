"""Render a self-contained terminal card; paths are independent of cwd."""

from html import escape
from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[1] / "assets/profile-card.svg"
FONT = "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, monospace"
ROWS = [
    ("Name", "Danilo Arantes Vieira"),
    ("Role", "Cybersecurity & Computer Science Student"),
    ("Focus", "Blue Team • Security Engineering • Software Development"),
    ("Domains", "Cyber Defense • AppSec • Networks • Cryptography • Automation"),
    ("Systems", "Linux • Windows • Docker • GitHub Actions"),
    ("Languages", "Python • PowerShell • TypeScript • JavaScript • C"),
]


def main() -> None:
    rows = []
    for index, (label, value) in enumerate(ROWS):
        y = 88 + index * 27
        rows.append(
            f'<g class="line" style="animation-delay:{index * 110 + 80}ms">'
            f'<text x="28" y="{y}" fill="#58A6FF">{escape(label)}</text>'
            f'<text x="144" y="{y}" fill="#C9D1D9">{escape(value)}</text></g>'
        )
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="260" viewBox="0 0 900 260" role="img" aria-labelledby="title description">
  <title id="title">Danilo Arantes Vieira — terminal profile</title>
  <desc id="description">{escape('; '.join(f'{key}: {value}' for key, value in ROWS))}</desc>
  <style>
    text {{ font-family: {FONT}; font-size: 13px; }}
    .line {{ animation: reveal 360ms ease-out both; }}
    @keyframes reveal {{ from {{ opacity: 0; transform: translateX(-6px); }} to {{ opacity: 1; transform: translateX(0); }} }}
    @media (prefers-reduced-motion: reduce) {{ .line {{ animation: none; }} }}
  </style>
  <rect x="0.5" y="0.5" width="899" height="259" rx="12" fill="#0D1117" stroke="#30363D"/>
  <path d="M13 1H887Q899 1 899 13V48H1V13Q1 1 13 1" fill="#161B22"/>
  <path d="M1 48H899" stroke="#30363D"/>
  <circle cx="24" cy="24" r="4" fill="#F85149"/>
  <circle cx="40" cy="24" r="4" fill="#8B949E"/>
  <circle cx="56" cy="24" r="4" fill="#3FB950"/>
  <text x="80" y="29" fill="#22D3EE">danilo@github:~$ <tspan fill="#C9D1D9">whoami</tspan></text>
  <rect x="255" y="17" width="7" height="14" rx="1" fill="#8B949E" opacity="0.65"/>
  {''.join(rows)}
</svg>
'''
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(svg, encoding="utf-8")
    print("Rendered assets/profile-card.svg (900 x 260).")


if __name__ == "__main__":
    main()
