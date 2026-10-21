import base64
import hashlib
import io
import json
import re
from datetime import date
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from PIL import Image

ROOT = Path(__file__).parent
SRC = ROOT / "assets" / "src"
OUT = ROOT / "assets"

INK = "#ededed"
DIM = "#959595"
GROUND = "#0d0d0d"
EDGE = "#262626"
FONTS = {
    "SB": "Poppins-SemiBold.ttf",
    "L": "Poppins-Light.ttf",
    "M": "JetBrainsMono-Regular.ttf",
}
ROW = 812

TILES = [
    {
        "slug": "ai-journal",
        "url": "https://apps.apple.com/app/id6762126820",
        "name": "AI Journal",
        "meta": "iOS · Android",
        "text": "Speak your entries instead of typing. AI cleans up the text and writes weekly and monthly recaps.",
    },
    {
        "slug": "debtaway",
        "url": "https://debt-away.app",
        "name": "DebtAway",
        "meta": "iOS · Android",
        "text": "A debt payoff tracker designed like a tear-off calendar. Counts down to your debt-free day, in 78 languages.",
    },
    {
        "slug": "rechnungsleser",
        "url": "https://rechnungsleser.com",
        "name": "Rechnungsleser",
        "meta": "Extension · Web",
        "text": "Opens German e-invoices (XRechnung, ZUGFeRD) and checks them against the official rules. Nothing is uploaded.",
    },
    {
        "slug": "aiorreal",
        "url": "https://aiorreal.games",
        "name": "AI or Real?",
        "meta": "Daily browser game",
        "text": "Ten new photos every day. For each one, decide whether it is a real photograph or AI-generated.",
    },
]

WORK = {
    "name": "medavis",
    "meta": "Radiology software · since 2024",
    "text": "I set the frontend architecture and dev stack for six squads and drive AI adoption across the company, "
            "from coding agents to self-healing CI/CD. That code is private.",
    "rows": [
        ("Squads building on my frontend stack", "6"),
        ("Pull requests merged by my coding agent", "370+"),
        ("Preview deployments by the agent", "500+"),
        ("Developer hours saved", "420+"),
        ("Internal tools, used company-wide", "~200 staff"),
    ],
}

STACK = [
    ("Frontend", [("react", "React"), ("typescript", "TypeScript"), ("nextdotjs", "Next.js"),
                  ("tanstack", "TanStack"), ("angular", "Angular"), ("tailwindcss", "Tailwind")]),
    ("Mobile", [("react", "React Native"), ("expo", "Expo"), ("flutter", "Flutter"), ("firebase", "Firebase")]),
    ("Backend, cloud", [("nodedotjs", "Node.js"), ("hono", "Hono"), ("cloudflareworkers", "Cloudflare Workers"),
                        ("amazonwebservices", "AWS"), ("docker", "Docker")]),
    ("Tooling", [("jenkins", "Jenkins"), ("gitlab", "GitLab CI"), ("figma", "Figma"), ("claude", "Claude Code")]),
]

LINKS = [
    {"slug": "site", "url": "https://erginos.io", "icon": None, "label": "erginos.io", "w": 176},
    {"slug": "linkedin", "url": "https://www.linkedin.com/in/derginos", "icon": "linkedin", "label": "LinkedIn", "w": 176},
    {"slug": "app-store", "url": "https://apps.apple.com/app/id6759984213", "icon": "apple",
     "label": "Flyva · App Store", "w": 224},
    {"slug": "google-play", "url": "https://play.google.com/store/apps/details?id=app.flyva", "icon": "googleplay",
     "label": "Flyva · Google Play", "w": 224},
]


class Faces:
    def __init__(self):
        self.used = {k: set() for k in FONTS}

    def use(self, key, text):
        self.used[key].update(text)
        return esc(text)

    def css(self):
        rules = []
        for key, chars in self.used.items():
            if not chars:
                continue
            font = TTFont(ROOT / "fonts" / FONTS[key], recalcTimestamp=False)
            options = subset.Options()
            options.flavor = "woff"
            options.layout_features = ["kern", "liga"]
            subsetter = subset.Subsetter(options)
            subsetter.populate(text="".join(chars))
            subsetter.subset(font)
            buf = io.BytesIO()
            font.flavor = "woff"
            font.save(buf)
            data = base64.b64encode(buf.getvalue()).decode()
            rules.append(f"@font-face{{font-family:F{key};src:url(data:font/woff;base64,{data}) format('woff')}}")
        return "".join(rules)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


def text_width(text, key, size):
    font = TTFont(ROOT / "fonts" / FONTS[key])
    cmap, hmtx = font.getBestCmap(), font["hmtx"]
    upm = font["head"].unitsPerEm
    return sum(hmtx[cmap[ord(c)]][0] for c in text) * size / upm


def wrap(text, key, size, limit):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if text_width(trial, key, size) <= limit:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + [line]


def data_uri(path, size=None, fmt=None):
    im = Image.open(path)
    if size:
        im = im.convert("RGBA").resize(size, Image.LANCZOS)
    buf = io.BytesIO()
    if fmt == "JPEG" or path.suffix == ".jpg":
        buf.write(path.read_bytes())
        mime = "image/jpeg"
    else:
        im.save(buf, "PNG", optimize=True)
        mime = "image/png"
    return f"data:{mime};base64,{base64.b64encode(buf.getvalue()).decode()}"


def panel(w, h):
    return f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="12" fill="{GROUND}" stroke="{EDGE}"/>'


def hairline(x1, x2, y):
    return f'<path d="M{x1} {y + .5}H{x2}" stroke="{EDGE}"/>'


def icon(path, x, y, size, uid):
    r = size * 0.225
    return (
        f'<clipPath id="ic{uid}"><rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{r}"/></clipPath>'
        f'<image href="{data_uri(path, (size * 2, size * 2))}" x="{x}" y="{y}" width="{size}" height="{size}" clip-path="url(#ic{uid})"/>'
    )


def logo(slug, x, y, size):
    d = re.search(r' d="([^"]+)"', (SRC / "icons" / f"{slug}.svg").read_text()).group(1)
    return f'<path d="{d}" fill="{INK}" transform="translate({x} {y}) scale({size / 24:g})"/>'


def globe(x, y, size):
    return (
        f'<g transform="translate({x} {y}) scale({size / 24:g})" fill="none" stroke="{INK}" stroke-width="1.8">'
        '<circle cx="12" cy="12" r="10"/><ellipse cx="12" cy="12" rx="4.2" ry="10"/><path d="M2 12h20"/></g>'
    )


def styles(f, *rules):
    return f"<defs><style>{f.css()}{''.join(rules)}</style></defs>"


def downloads_line(stats):
    flyva = stats["apps"]["flyva"]
    return f"{flyva['downloads']:,} downloads in {flyva['countries']} countries"


def as_of(stats):
    day = max(date.fromisoformat(d) for d in stats["through"].values() if d and d != "None")
    return f"as of {day:%b} {day.day}"


def header(stats):
    W, H = 880, 380
    f = Faces()
    sw, sh = 198, 430
    bezel = 8
    px, py = 606, 48
    sx, sy = px + bezel, py + bezel
    screens = sorted(SRC.glob("flyva-*.jpg"))
    frames = screens + screens[:1]
    hold = 100 / len(screens)
    stops = []
    for i in range(len(screens)):
        start = i * hold
        stops.append(f"{start:.2f}%{{transform:translateX(-{i * sw}px)}}")
        stops.append(f"{start + hold * 0.86:.2f}%{{transform:translateX(-{i * sw}px)}}")
    stops.append(f"100%{{transform:translateX(-{len(screens) * sw}px)}}")

    facts = [
        ("featured in Die Rheinpfalz", DIM),
        ("iOS & Android · built solo", DIM),
    ]
    body = [
        panel(W, H),
        f'<text x="40" y="88" class="name"><tspan class="b">{f.use("SB", "Deniz")}</tspan>{f.use("L", " Erginos")}</text>',
        f'<text x="40" y="118" class="role">{f.use("L", "Lead Software Engineer & Technical Product Owner")}</text>',
        icon(SRC / "icon-flyva.png", 40, 166, 64, "f"),
        f'<text x="122" y="194" class="title">{f.use("SB", "Flyva")}</text>',
        f'<text x="122" y="220" class="line">{f.use("L", "Meal plans from this week’s grocery deals")}</text>',
        f'<text x="40" y="282" class="mono"><tspan fill="{INK}">{f.use("M", downloads_line(stats))}</tspan>'
        f'<tspan fill="{DIM}">{f.use("M", " " + as_of(stats))}</tspan></text>',
        *[
            f'<text x="40" y="{303 + i * 21}" class="mono" fill="{c}">{f.use("M", t)}</text>'
            for i, (t, c) in enumerate(facts)
        ],
        '<g clip-path="url(#panel)">',
        f'<rect x="{px - 2.5}" y="{py + 96}" width="3" height="30" rx="1.5" fill="#2a2a2a"/>',
        f'<rect x="{px - 2.5}" y="{py + 140}" width="3" height="52" rx="1.5" fill="#2a2a2a"/>',
        f'<rect x="{px - 2.5}" y="{py + 202}" width="3" height="52" rx="1.5" fill="#2a2a2a"/>',
        f'<rect x="{px + sw + 2 * bezel - .5}" y="{py + 160}" width="3" height="74" rx="1.5" fill="#2a2a2a"/>',
        f'<rect x="{px}" y="{py}" width="{sw + 2 * bezel}" height="{sh + 2 * bezel}" rx="40" fill="#171717" stroke="#3d3d3d"/>',
        f'<g clip-path="url(#screen)"><g class="reel">',
        *[
            f'<image href="{data_uri(p)}" x="{sx + i * sw}" y="{sy}" width="{sw}" height="{sh}"/>'
            for i, p in enumerate(frames)
        ],
        "</g></g>",
        f'<rect x="{sx + sw / 2 - 31}" y="{sy + 10}" width="62" height="18" rx="9" fill="#000"/>',
        "</g>",
    ]
    css = f.css() + "".join([
        f".name{{font-size:42px;font-family:FL;fill:{INK}}}.name .b{{font-family:FSB}}",
        f".role{{font-size:17px;font-family:FL;fill:{DIM}}}",
        f".title{{font-size:26px;font-family:FSB;fill:{INK}}}",
        f".line{{font-size:15px;font-family:FL;fill:{DIM}}}",
        ".mono{font-size:12.5px;font-family:FM}",
        "@keyframes reel{" + "".join(stops) + "}",
        ".reel{animation:reel 15s cubic-bezier(.65,0,.35,1) infinite}",
        "@media (prefers-reduced-motion:reduce){.reel{animation:none}}",
    ])
    defs = (
        f"<defs><style>{css}</style>"
        f'<clipPath id="panel"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="11.5"/></clipPath>'
        f'<clipPath id="screen"><rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="32"/></clipPath></defs>'
    )
    return svg(W, H, header_label(stats), defs + "".join(body))


def header_label(stats):
    return ("Deniz Erginos, Lead Software Engineer and Technical Product Owner. "
            f"Flyva: meal plans from this week's grocery deals, {downloads_line(stats)}.")


def tile(t):
    W, H = 404, 184
    vw = 116
    vx, vy = W - 20 - vw, 22
    f = Faces()
    lines = wrap(t["text"], "L", 13.5, vx - 22 - 18)
    assert len(lines) <= 4, (t["slug"], lines)
    body = [
        panel(W, H),
        icon(SRC / f"icon-{t['slug']}.png", 22, 22, 44, t["slug"]),
        f'<text x="78" y="41" class="title">{f.use("SB", t["name"])}</text>',
        f'<text x="78" y="61" class="mono">{f.use("M", t["meta"])}</text>',
        *[f'<text x="22" y="{98 + i * 20}" class="line">{f.use("L", ln)}</text>' for i, ln in enumerate(lines)],
        '<g clip-path="url(#panel)">',
        f'<clipPath id="shot"><rect x="{vx}" y="{vy}" width="{vw}" height="{H}" rx="12"/></clipPath>',
        f'<image href="{data_uri(SRC / f"screen-{t["slug"]}.jpg")}" x="{vx}" y="{vy}" width="{vw}" height="{vw * 340 / 232:.1f}" clip-path="url(#shot)"/>',
        f'<rect x="{vx}" y="{vy}" width="{vw}" height="{H}" rx="12" fill="none" stroke="#ffffff" stroke-opacity=".08"/>',
        "</g>",
    ]
    css = f.css() + "".join([
        f".title{{font-size:18px;font-family:FSB;fill:{INK}}}",
        f".mono{{font-size:11px;font-family:FM;fill:{DIM}}}",
        f".line{{font-size:13.5px;font-family:FL;fill:{DIM}}}",
    ])
    defs = (
        f"<defs><style>{css}</style>"
        f'<clipPath id="panel"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="11.5"/></clipPath></defs>'
    )
    return svg(W, H, tile_label(t), defs + "".join(body))


def tile_label(t):
    return f"{t['name']}: {t['text']}"


def work():
    W, pad = ROW, 28
    tx, row_h, top = 412, 36, 28
    H = top + row_h * len(WORK["rows"]) + 20
    f = Faces()
    lines = wrap(WORK["text"], "L", 14, tx - pad - 48)
    body = [
        panel(W, H),
        f'<text x="{pad}" y="51" class="title">{f.use("SB", WORK["name"])}</text>',
        f'<text x="{pad}" y="75" class="meta">{f.use("M", WORK["meta"])}</text>',
        *[f'<text x="{pad}" y="{114 + i * 22}" class="line">{f.use("L", ln)}</text>' for i, ln in enumerate(lines)],
    ]
    assert 114 + (len(lines) - 1) * 22 < H - pad, lines
    for i, (label, value) in enumerate(WORK["rows"]):
        y = top + i * row_h
        assert text_width(label, "L", 14) + text_width(value, "M", 13) + 24 < W - pad - tx, label
        if i:
            body.append(hairline(tx, W - pad, y))
        body.append(f'<text x="{tx}" y="{y + 23}" class="label">{f.use("L", label)}</text>')
        body.append(f'<text x="{W - pad}" y="{y + 23}" class="value" text-anchor="end">{f.use("M", value)}</text>')
    css = [
        f".title{{font-size:22px;font-family:FSB;fill:{INK}}}",
        f".meta{{font-size:11.5px;font-family:FM;fill:{DIM}}}",
        f".line{{font-size:14px;font-family:FL;fill:{DIM}}}",
        f".label{{font-size:14px;font-family:FL;fill:{INK}}}",
        f".value{{font-size:13px;font-family:FM;fill:{INK}}}",
    ]
    return svg(W, H, work_label(), styles(f, *css) + "".join(body))


def work_label():
    rows = "; ".join(f"{label}: {value}" for label, value in WORK["rows"])
    return f"Day job at {WORK['name']}, {WORK['meta']}. {WORK['text']} {rows}."


def stack():
    W, pad = ROW, 28
    lx, top, row_h, size = 168, 72, 42, 17
    H = top + row_h * len(STACK) + 14
    f = Faces()
    body = [panel(W, H), f'<text x="{pad}" y="51" class="title">{f.use("SB", "Stack")}</text>']
    for i, (group, items) in enumerate(STACK):
        y = top + i * row_h
        body.append(hairline(pad, W - pad, y))
        body.append(f'<text x="{pad}" y="{y + 26}" class="group">{f.use("L", group)}</text>')
        x = lx
        for slug, name in items:
            body.append(logo(slug, x, y + 12.5, size))
            body.append(f'<text x="{x + size + 8}" y="{y + 26}" class="item">{f.use("L", name)}</text>')
            x += size + 8 + text_width(name, "L", 14) + 26
        assert x - 26 < W - pad, (group, x)
    css = [
        f".title{{font-size:22px;font-family:FSB;fill:{INK}}}",
        f".group{{font-size:13.5px;font-family:FL;fill:{DIM}}}",
        f".item{{font-size:14px;font-family:FL;fill:{INK}}}",
    ]
    return svg(W, H, stack_label(), styles(f, *css) + "".join(body))


def stack_label():
    return "Stack. " + " ".join(f"{group}: {', '.join(n for _, n in items)}." for group, items in STACK)


def link(l):
    W, H, size = l["w"], 44, 18
    f = Faces()
    mark = globe(16, 13, size) if l["icon"] is None else logo(l["icon"], 16, 13, size)
    assert 44 + text_width(l["label"], "L", 14) < W - 34, l["label"]
    body = [
        panel(W, H),
        mark,
        f'<text x="44" y="27" class="label">{f.use("L", l["label"])}</text>',
        f'<path d="M{W - 25} 26.5l8-8m-6 0h6v6" fill="none" stroke="{DIM}" stroke-width="1.5" '
        'stroke-linecap="round" stroke-linejoin="round"/>',
    ]
    css = [f".label{{font-size:14px;font-family:FL;fill:{INK}}}"]
    return svg(W, H, l["label"], styles(f, *css) + "".join(body))


def readme(stats, assets):
    def img(src, width, alt):
        version = hashlib.sha1(assets[src].encode()).hexdigest()[:8]
        return f'<img src="assets/{src}?v={version}" width="{width}" alt="{esc(alt)}" />'

    tiles = "\n".join(
        f'  <a href="{t["url"]}">{img(t["slug"] + ".svg", 404, tile_label(t))}</a>' for t in TILES)
    links = "\n".join(f'  <a href="{l["url"]}">{img("link-" + l["slug"] + ".svg", l["w"], l["label"])}</a>' for l in LINKS)
    return (
        f'<a href="https://flyva.app">{img("header.svg", ROW, header_label(stats))}</a>\n\n'
        f"<p>\n{tiles}\n</p>\n\n"
        f'<a href="https://www.linkedin.com/in/derginos">{img("work.svg", ROW, work_label())}</a>\n\n'
        f'<a href="https://erginos.io">{img("stack.svg", ROW, stack_label())}</a>\n\n'
        f"<p>\n{links}\n</p>\n"
    )


def svg(w, h, label, inner):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{esc(label)}">{inner}</svg>\n'
    )


def flyva_json(stats):
    """Read by erginos.io. Only Flyva, the other apps' numbers stay out of the public repo."""
    flyva = stats["apps"]["flyva"]
    return json.dumps({"downloads": flyva["downloads"], "countries": flyva["countries"]}) + "\n"


def main():
    stats = json.loads((ROOT / "stats.json").read_text())
    out = {
        "header.svg": header(stats),
        "flyva.json": flyva_json(stats),
        **{f"{t['slug']}.svg": tile(t) for t in TILES},
        "work.svg": work(),
        "stack.svg": stack(),
        **{f"link-{l['slug']}.svg": link(l) for l in LINKS},
    }
    for name, content in out.items():
        (OUT / name).write_text(content)
        print(f"assets/{name}: {len(content) // 1024} KB")
    (ROOT / "README.md").write_text(readme(stats, out))


if __name__ == "__main__":
    main()
