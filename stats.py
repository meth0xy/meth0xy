"""Counts first-time downloads per app from App Store Connect sales reports and the Play reporting bucket."""
import base64
import gzip
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
CACHE = ROOT / "cache"
START = date(2026, 3, 1)
APPS = {
    "flyva": ("6759984213", "app.flyva"),
    "ai-journal": ("6762126820", "com.aijournal.pro"),
    "debtaway": ("6807138792", "app.debtaway"),
}
UNKNOWN_COUNTRIES = {"", "ZZ"}


def load_env():
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = load_env()


def b64url(data):
    if isinstance(data, str):
        data = data.encode()
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def sign(msg, key_file):
    return subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", key_file], input=msg.encode(), capture_output=True, check=True
    ).stdout


def asc_token():
    def der_to_raw(der):
        idx = 2 + (der[1] & 0x7F if der[1] & 0x80 else 0)
        r_len = der[idx + 1]
        r = der[idx + 2:idx + 2 + r_len]
        idx += 2 + r_len
        s = der[idx + 2:idx + 2 + der[idx + 1]]
        return r.lstrip(b"\x00").rjust(32, b"\x00") + s.lstrip(b"\x00").rjust(32, b"\x00")

    now = int(time.time())
    h = b64url(json.dumps({"alg": "ES256", "kid": ENV["ASC_KEY_ID"], "typ": "JWT"}, separators=(",", ":")))
    p = b64url(json.dumps({"iss": ENV["ASC_ISSUER"], "iat": now, "exp": now + 1200, "aud": "appstoreconnect-v1"},
                          separators=(",", ":")))
    msg = f"{h}.{p}"
    return f"{msg}.{b64url(der_to_raw(sign(msg, ENV['ASC_KEY_FILE'])))}"


def asc_sales(frequency, report_date, final):
    """Returns the SUMMARY sales report as TSV, or "" when Apple has none. Final answers are cached."""
    path = CACHE / "asc" / f"{frequency}-{report_date}.tsv"
    if path.exists():
        return path.read_text()
    q = urllib.parse.urlencode({
        "filter[frequency]": frequency,
        "filter[reportType]": "SALES",
        "filter[reportSubType]": "SUMMARY",
        "filter[vendorNumber]": ENV["ASC_VENDOR_NUMBER"],
        "filter[reportDate]": report_date,
    })
    req = urllib.request.Request(f"https://api.appstoreconnect.apple.com/v1/salesReports?{q}",
                                 headers={"Authorization": f"Bearer {asc_token()}", "Accept": "application/a-gzip"})
    try:
        tsv = gzip.decompress(urllib.request.urlopen(req, timeout=60).read()).decode()
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        tsv = None
    if tsv is not None or final:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(tsv or "")
    return tsv or ""


def add_ios(tsv, totals, countries):
    lines = [l for l in tsv.split("\n") if l.strip()]
    if not lines:
        return
    head = [h.strip() for h in lines[0].split("\t")]
    i_type, i_units, i_country, i_app = (
        head.index(n) for n in ("Product Type Identifier", "Units", "Country Code", "Apple Identifier"))
    ids = {apple_id: slug for slug, (apple_id, _) in APPS.items()}
    for line in lines[1:]:
        cells = [c.strip() for c in line.split("\t")]
        slug = ids.get(cells[i_app])
        if not slug or not cells[i_type].startswith("1"):
            continue
        units = int(cells[i_units] or 0)
        totals[slug] += units
        countries[slug][cells[i_country]] += units


def month_starts(today):
    d = START
    while d <= today:
        yield d
        d = date(d.year + d.month // 12, d.month % 12 + 1, 1)


def ios(today):
    totals, countries = Counter(), {slug: Counter() for slug in APPS}
    last_day = None
    for start in month_starts(today):
        end = date(start.year + start.month // 12, start.month % 12 + 1, 1)
        if end <= today:
            tsv = asc_sales("MONTHLY", start.strftime("%Y-%m"), final=(today - end).days > 20)
            if tsv:
                add_ios(tsv, totals, countries)
                last_day = end - timedelta(days=1)
                continue
        d = start
        while d < min(end, today):
            tsv = asc_sales("DAILY", d.isoformat(), final=(today - d).days > 7)
            if tsv:
                add_ios(tsv, totals, countries)
                last_day = d
            d += timedelta(days=1)
    return totals, countries, last_day


def google_token():
    key = json.loads(Path(ENV["GOOGLE_SA"]).read_text())
    now = int(time.time())
    h = b64url(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")))
    p = b64url(json.dumps({"iss": key["client_email"], "scope": "https://www.googleapis.com/auth/devstorage.read_only",
                           "aud": "https://oauth2.googleapis.com/token", "iat": now, "exp": now + 3600},
                          separators=(",", ":")))
    msg = f"{h}.{p}"
    with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as f:
        f.write(key["private_key"])
        pem = f.name
    try:
        sig = sign(msg, pem)
    finally:
        os.unlink(pem)
    data = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                   "assertion": f"{msg}.{b64url(sig)}"}).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    return json.loads(urllib.request.urlopen(req, timeout=60).read())["access_token"]


def play_csv(token, name):
    obj = urllib.parse.quote(name, safe="")
    req = urllib.request.Request(
        f"https://storage.googleapis.com/storage/v1/b/{ENV['PLAY_REPORT_BUCKET']}/o/{obj}?alt=media",
        headers={"Authorization": f"Bearer {token}"})
    try:
        raw = urllib.request.urlopen(req, timeout=60).read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")
    rows = [l.split(",") for l in text.splitlines() if l.strip()]
    return rows[0], rows[1:]


def play(today):
    token = google_token()
    totals, countries = Counter(), {slug: Counter() for slug in APPS}
    last_day = None
    for slug, (_, package) in APPS.items():
        for start in month_starts(today):
            res = play_csv(token, f"stats/installs/installs_{package}_{start.strftime('%Y%m')}_country.csv")
            if not res:
                continue
            head, rows = res
            i_country, i_inst = head.index("Country"), head.index("Daily User Installs")
            for r in rows:
                n = int(r[i_inst] or 0)
                totals[slug] += n
                countries[slug][r[i_country]] += n
                last_day = max(last_day or r[0], r[0])
    return totals, countries, last_day


def main():
    today = date.today()
    ios_totals, ios_countries, ios_last = ios(today)
    play_totals, play_countries, play_last = play(today)
    apps = {}
    for slug in APPS:
        reached = {c for c, n in (ios_countries[slug] + play_countries[slug]).items() if n and c not in UNKNOWN_COUNTRIES}
        apps[slug] = {
            "downloads": ios_totals[slug] + play_totals[slug],
            "ios": ios_totals[slug],
            "android": play_totals[slug],
            "countries": len(reached),
        }
    stats = {"through": {"ios": str(ios_last), "android": play_last}, "apps": apps}
    (ROOT / "stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
