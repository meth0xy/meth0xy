import base64
import datetime as dt
import io
import json
import subprocess
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

LOGIN = "meth0xy"
ROOT = Path(__file__).parent
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/header.svg")

W, H = 880, 340
CELL, STEP = 13, 15
INK = "#ededed"
DIM = "#959595"
HAIR = "#3b3b3b"
GROUND = "#0d0d0d"
LEVELS = {
    "NONE": "#1c1c1c",
    "FIRST_QUARTILE": "#474747",
    "SECOND_QUARTILE": "#7a7a7a",
    "THIRD_QUARTILE": "#b3b3b3",
    "FOURTH_QUARTILE": "#f0f0f0",
}

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date weekday contributionLevel } }
      }
    }
  }
}
"""


def calendar():
    raw = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={QUERY}", "-F", f"login={LOGIN}"],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(raw)["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def font_face(family, file, text):
    font = TTFont(ROOT / "fonts" / file)
    options = subset.Options()
    options.flavor = "woff"
    options.layout_features = ["kern", "liga"]
    subsetter = subset.Subsetter(options)
    subsetter.populate(text=text + "0123456789,.–· ")
    subsetter.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff"
    font.save(buf)
    data = base64.b64encode(buf.getvalue()).decode()
    return f"@font-face{{font-family:'{family}';src:url(data:font/woff;base64,{data}) format('woff')}}"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


def main():
    cal = calendar()
    weeks = cal["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    first = dt.date.fromisoformat(days[0]["date"])
    last = dt.date.fromisoformat(days[-1]["date"])
    today = dt.date.today().isoformat()

    name_bold, name_light = "Deniz", " Erginos"
    role = "Lead Software Engineer & Technical Product Owner"
    corner = [
        (f"{cal['totalContributions']:,} contributions", INK),
        (f"{first:%b %Y} – {last:%b %Y}", DIM),
        ("mostly in private repos", DIM),
    ]
    footer_left = "erginos.io"
    footer_right = f"redrawn nightly · {today}"

    grid_w = len(weeks) * STEP - (STEP - CELL)
    grid_h = 7 * STEP - (STEP - CELL)
    x0 = round(40 + (W - 80 - grid_w) / 2)
    y0 = 148
    ruler_y = y0 + grid_h + 10

    cells, ticks, labels = [], [], []
    prev_month = None
    for col, week in enumerate(weeks):
        x = x0 + col * STEP
        for d in week["contributionDays"]:
            y = y0 + d["weekday"] * STEP
            cells.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" fill="{LEVELS[d["contributionLevel"]]}"/>')
        month = dt.date.fromisoformat(week["contributionDays"][0]["date"]).month
        tx = x + CELL / 2
        if month != prev_month and col > 0:
            ticks.append(f'<line x1="{tx}" y1="{ruler_y}" x2="{tx}" y2="{ruler_y + 8}"/>')
            label = dt.date(2000, month, 1).strftime("%b")
            labels.append(f'<text x="{tx}" y="{ruler_y + 24}" text-anchor="middle">{label}</text>')
        else:
            ticks.append(f'<line x1="{tx}" y1="{ruler_y}" x2="{tx}" y2="{ruler_y + 3}"/>')
        prev_month = month

    mono_text = "".join(t for t, _ in corner) + footer_left + footer_right + "JanFebMarAprMayJunJulAugSepOctNovDec"
    css = "".join([
        font_face("PoppinsSB", "Poppins-SemiBold.ttf", name_bold),
        font_face("PoppinsL", "Poppins-Light.ttf", name_light + role),
        font_face("Mono", "JetBrainsMono-Regular.ttf", mono_text),
        f".name{{font:42px PoppinsL;fill:{INK}}}.name tspan.b{{font-family:PoppinsSB}}",
        f".role{{font:17px PoppinsL;fill:{DIM}}}",
        ".mono{font:11.5px Mono}",
        f".ruler line{{stroke:{HAIR};stroke-width:1}}.ruler text{{font:10.5px Mono;fill:{DIM}}}",
        "@keyframes sweep{from{transform:translateX(0)}to{transform:translateX(" + str(grid_w + 120) + "px)}}",
        ".scan{animation:sweep 2.6s cubic-bezier(.22,1,.36,1) .4s both}",
        "@media (prefers-reduced-motion:reduce){.scan{display:none}}",
    ])

    corner_svg = "".join(
        f'<text class="mono" x="{W - 40}" y="{60 + i * 18}" text-anchor="end" fill="{c}">{esc(t)}</text>'
        for i, (t, c) in enumerate(corner)
    )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Deniz Erginos, {esc(role)}. {cal['totalContributions']:,} contributions in the last year.">
<defs><style>{css}</style>
<linearGradient id="beam" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".22"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
<clipPath id="grid"><rect x="{x0}" y="{y0}" width="{grid_w}" height="{grid_h}"/></clipPath></defs>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="{GROUND}" stroke="#262626"/>
<text class="name" x="40" y="76"><tspan class="b">{name_bold}</tspan>{esc(name_light)}</text>
<text class="role" x="40" y="106">{esc(role)}</text>
{corner_svg}
<g>{"".join(cells)}</g>
<g clip-path="url(#grid)"><rect class="scan" x="{x0 - 90}" y="{y0}" width="60" height="{grid_h}" fill="url(#beam)"/></g>
<g class="ruler"><line x1="{x0}" y1="{ruler_y}" x2="{x0 + grid_w}" y2="{ruler_y}"/>{"".join(ticks)}{"".join(labels)}</g>
<text class="mono" x="40" y="{H - 24}" fill="{DIM}">{esc(footer_left)}</text>
<text class="mono" x="{W - 40}" y="{H - 24}" text-anchor="end" fill="{DIM}">{esc(footer_right)}</text>
</svg>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg)
    print(f"{OUT}: {len(svg):,} bytes, {len(weeks)} weeks, {cal['totalContributions']} contributions")


if __name__ == "__main__":
    main()
