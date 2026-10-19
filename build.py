import base64
import io
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

TILES = [
    {
        "slug": "ai-journal",
        "name": "AI Journal",
        "meta": "iOS · Android",
        "text": "Speak your entries instead of typing. AI cleans up the text and writes weekly and monthly recaps.",
    },
    {
        "slug": "debtaway",
        "name": "DebtAway",
        "meta": "iOS · Android",
        "text": "A debt payoff tracker designed like a tear-off calendar. Counts down to your debt-free day, in 78 languages.",
    },
    {
        "slug": "rechnungsleser",
        "name": "Rechnungsleser",
        "meta": "Extension · Web",
        "text": "Opens German e-invoices (XRechnung, ZUGFeRD) and checks them against the official rules. Nothing is uploaded.",
    },
    {
        "slug": "aiorreal",
        "name": "AI or Real?",
        "meta": "Daily browser game",
        "text": "Ten new photos every day. For each one, decide whether it is a real photograph or AI-generated.",
    },
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
            font = TTFont(ROOT / "fonts" / FONTS[key])
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
    return s.replace("&", "&amp;").replace("<", "&lt;")


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


def icon(path, x, y, size, uid):
    r = size * 0.225
    return (
        f'<clipPath id="ic{uid}"><rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{r}"/></clipPath>'
        f'<image href="{data_uri(path, (size * 2, size * 2))}" x="{x}" y="{y}" width="{size}" height="{size}" clip-path="url(#ic{uid})"/>'
    )


def header():
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
        ("2,700+ downloads in 40+ countries", INK),
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
        *[
            f'<text x="40" y="{282 + i * 21}" class="mono" fill="{c}">{f.use("M", t)}</text>'
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
    label = "Deniz Erginos, Lead Software Engineer and Technical Product Owner. Flyva: meal plans from this week's grocery deals, 2,700+ downloads in 40+ countries."
    return svg(W, H, label, defs + "".join(body))


def tile(t):
    W, H = 400, 184
    vx, vy, vw = 264, 22, 116
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
    return svg(W, H, f"{t['name']}: {t['text']}", defs + "".join(body))


def svg(w, h, label, inner):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{esc(label)}">{inner}</svg>\n'
    )


def main():
    out = {"header.svg": header(), **{f"{t['slug']}.svg": tile(t) for t in TILES}}
    for name, content in out.items():
        (OUT / name).write_text(content)
        print(f"assets/{name}: {len(content) // 1024} KB")


if __name__ == "__main__":
    main()
