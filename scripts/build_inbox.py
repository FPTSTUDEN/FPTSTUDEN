#!/usr/bin/env python3
"""Rebuild traveler-mail.svg from GitHub issues.

Stateless on purpose: every run reads all issues titled "[hello] ..." or
"[message] ..." and redraws the whole board, so a dropped, re-ordered or
repeated workflow run can never corrupt it. Standard library only.

Status lifecycle (derived from the issue itself):
  open, no staff reply  -> LANDED
  open, staff replied   -> CLEARED
  closed                -> AT BELT n
Moderation: issues labelled "hidden" never show. Set REQUIRE_APPROVAL=true to
show only issues labelled "approved".
"""
import base64
import datetime as dt
import html
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
import zlib

REPO = os.environ.get("GITHUB_REPOSITORY", "")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("BOARD_PATH", "traveler-mail.svg")
REQUIRE_APPROVAL = os.environ.get("REQUIRE_APPROVAL", "false").lower() == "true"
ROWS = 6
TOP = 94            # y of the first row
ROW_H = 52
PREFIXES = ("[hello]", "[message]")
MAX_MSG_PX = 245    # message column width before truncating with an ellipsis
STAFF = ("OWNER", "MEMBER", "COLLABORATOR")

STYLE_DEFS = r"""<style>
    .sans{font-family:'Helvetica Neue',Helvetica,Arial,sans-serif}
    .mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,'Courier New',monospace}
    .title{font-weight:700;font-size:19px;fill:#0B0B0C}
    .sub{font-weight:600;font-size:9.5px;letter-spacing:1.3px;fill:#0B0B0C;opacity:.75}
    .big{font-weight:700;font-size:22px;fill:#0B0B0C;text-anchor:end}
    .col{font-weight:700;font-size:9px;letter-spacing:1.6px;fill:#FFB000}
    .code{font-weight:700;font-size:13px;fill:#0A0E14;text-anchor:middle;letter-spacing:1px}
    .nm{font-weight:700;font-size:13px;letter-spacing:.4px}
    .meta{font-weight:600;font-size:8.5px;letter-spacing:1.1px;fill:#7C8794}
    .msg{font-size:12px}
    .fl{font-weight:700;font-size:12px;fill:#F2F5F8;text-anchor:middle}
    .chip{font-weight:700;font-size:8.5px;letter-spacing:1.4px}
    .dv{stroke:#1E2631;stroke-width:1;stroke-dasharray:3 3}
  </style>
  <defs>
    <clipPath id="c"><rect width="640" height="418" rx="18"/></clipPath>
    <pattern id="haz" width="12" height="12" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="12" fill="#FFC82C"/><rect x="6" width="6" height="12" fill="#0B0B0C"/></pattern>
    <clipPath id="avc"><circle r="16"/></clipPath>
    <g id="avatar"><circle r="16" fill="currentColor" fill-opacity=".22"/><g clip-path="url(#avc)" fill="currentColor"><circle cy="-4" r="5.5"/><ellipse cy="16" rx="12" ry="10"/></g><circle r="15.5" fill="none" stroke="#2A3340" stroke-width="1"/></g>
    <filter id="rough" x="-5%" y="-20%" width="110%" height="140%"><feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" seed="4" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="1.6"/></filter>
    <g id="stamp" fill="none" stroke="currentColor"><rect x="-60" y="-13" width="120" height="26" rx="3" stroke-width="1.8"/><rect x="-56" y="-9" width="112" height="18" rx="1.5" stroke-width=".8"/><text y="3.4" text-anchor="middle" fill="currentColor" stroke="none" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,'Courier New',monospace" font-weight="700" font-size="9.5" letter-spacing="1.4">ENTRY APPROVED</text></g>
    <g id="plane"><path d="M-14 0Q-14-3-10-3L8-3Q16-3 16 0Q16 3 8 3L-10 3Q-14 3-14 0Z"/><path d="M-2-3L-8-15L-4-15L6-3Z"/><path d="M-2 3L-8 15L-4 15L6 3Z"/><path d="M-12-3L-15-8L-12-8L-8-3Z"/><path d="M-12 3L-15 8L-12 8L-8 3Z"/></g>
  </defs>"""

STATUS = {  # colour, plane angle, chip outline
    "LANDED": ("#2FD27A", 28, "#2FD27A"),
    "CLEARED": ("#38BDF8", -28, "#38BDF8"),
    "AT BELT": ("#8A95A3", 0, "#3A4452"),
}
AVATAR_TINTS = ["#F0A35E", "#5EC4A8", "#8AA4F0", "#C79BF0", "#F08A9B", "#9BB0C4"]

# Extend freely. Anything missing falls back to the first three letters of the city.
AIRPORTS = {
    "osaka": "KIX", "sao paulo": "GRU", "bengaluru": "BLR", "bangalore": "BLR", "helsinki": "HEL",
    "madrid": "MAD", "austin": "AUS", "london": "LHR", "paris": "CDG", "berlin": "BER",
    "new york": "JFK", "san francisco": "SFO", "los angeles": "LAX", "tokyo": "HND",
    "singapore": "SIN", "sydney": "SYD", "toronto": "YYZ", "mumbai": "BOM", "delhi": "DEL",
    "new delhi": "DEL", "hanoi": "HAN", "ho chi minh city": "SGN", "saigon": "SGN",
    "bangkok": "BKK", "seoul": "ICN", "dubai": "DXB", "amsterdam": "AMS", "dublin": "DUB",
    "lisbon": "LIS", "rome": "FCO", "istanbul": "IST", "cairo": "CAI", "lagos": "LOS",
    "nairobi": "NBO", "mexico city": "MEX", "buenos aires": "EZE", "bogota": "BOG",
    "chicago": "ORD", "seattle": "SEA", "boston": "BOS", "stockholm": "ARN",
    "copenhagen": "CPH", "oslo": "OSL", "zurich": "ZRH", "vienna": "VIE", "warsaw": "WAW",
    "prague": "PRG", "kyiv": "KBP", "jakarta": "CGK", "manila": "MNL", "kuala lumpur": "KUL",
    "taipei": "TPE", "hong kong": "HKG", "shanghai": "PVG", "beijing": "PEK",
    "melbourne": "MEL", "auckland": "AKL", "cape town": "CPT", "tel aviv": "TLV",
    "vancouver": "YVR", "montreal": "YUL", "munich": "MUC", "barcelona": "BCN",
    "milan": "MXP", "brussels": "BRU", "athens": "ATH", "tallinn": "TLL",
}


# ----------------------------------------------------------------- GitHub I/O
def http(url, accept="application/vnd.github+json", limit=None):
    headers = {"Accept": accept, "User-Agent": "traveler-mail-board"}
    if TOKEN and urllib.parse.urlparse(url).hostname == "api.github.com":
        headers["Authorization"] = f"Bearer {TOKEN}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read(limit + 1) if limit else r.read(), r.headers


def gh(path):
    data, _ = http("https://api.github.com" + path)
    return json.loads(data)


def fetch_issues():
    out = []
    for page in range(1, 11):  # newest first, up to 1000 issues
        batch = gh(f"/repos/{REPO}/issues?state=all&sort=created&direction=desc&per_page=100&page={page}")
        out += batch
        if len(batch) < 100:
            break
    return out


def fetch_comments(number):
    return gh(f"/repos/{REPO}/issues/{number}/comments?per_page=100")


def fetch_avatar(url):
    """Return a data: URI (SVGs shown in a README cannot load remote images)."""
    try:
        host = urllib.parse.urlparse(url).hostname or ""
        if not host.endswith("githubusercontent.com"):
            return None
        url += ("&" if "?" in url else "?") + "s=64"
        data, hdr = http(url, accept="image/*", limit=60000)
        ctype = hdr.get_content_type()
        if len(data) > 60000 or ctype not in ("image/png", "image/jpeg", "image/gif", "image/webp"):
            return None
        return f"data:{ctype};base64,{base64.b64encode(data).decode()}"
    except Exception as exc:  # fall back to the silhouette
        print(f"avatar skipped: {exc}", file=sys.stderr)
        return None


# -------------------------------------------------------------------- parsing
def clean(text):
    """Strip HTML comments and every control / zero-width / bidi character."""
    text = re.sub(r"<!--.*?-->", "", text or "", flags=re.S)
    return "".join(c for c in text if c == "\n" or unicodedata.category(c)[0] != "C")


def fold(s):
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def field(body, name):
    m = re.search(rf"^[ \t]*{name}:[ \t]*(.*)$", body, flags=re.I | re.M)
    return m.group(1).strip() if m else ""


def message_of(body):
    m = re.search(r"^[ \t]*Message:[ \t]*(.*)$", body, flags=re.I | re.M)
    if not m:
        return ""
    for line in body[m.start(1):].splitlines():
        if line.strip():
            return line.strip()
    return ""


def split_city(raw):
    raw = re.sub(r"\s+", " ", raw).strip()
    if "," in raw:
        city, last = raw.rsplit(",", 1)
        if re.fullmatch(r"[A-Za-z]{2}", last.strip()):
            return city.strip(), last.strip().upper()
    return raw, ""


def airport(city):
    key = fold(city)
    if key in AIRPORTS:
        return AIRPORTS[key]
    letters = "".join(c for c in key if c.isalpha() and c.isascii()).upper()
    return (letters[:3].ljust(3, "X")) if letters else "---"


def char_px(c):
    if unicodedata.east_asian_width(c) in "WF":
        return 12
    if c in "il.,'!:;|1()[] ":
        return 3.6
    return 7.6 if c.isupper() or c in "mwMW@%" else 6.1


def fit(text, max_px):
    total = 0
    for i, c in enumerate(text):
        total += char_px(c)
        if total > max_px - 8:
            return text[:i].rstrip() + "…"
    return text


def parse_issue(it):
    title = (it.get("title") or "").strip()
    if "pull_request" in it or not it.get("user") or not title.lower().startswith(PREFIXES):
        return None
    labels = {(l.get("name") or "").lower() for l in it.get("labels", [])}
    if "hidden" in labels or (REQUIRE_APPROVAL and "approved" not in labels):
        return None
    body = clean(it.get("body"))
    city, cc = split_city(field(body, "City"))
    msg = message_of(body)
    hello = title.lower().startswith("[hello]")
    if not msg:
        msg = "Stopped by to say hello." if hello else "Left a message."
    return {
        "number": it["number"], "login": it["user"]["login"], "avatar_url": it["user"].get("avatar_url", ""),
        "city": city, "cc": cc, "message": fit(re.sub(r"\s+", " ", msg), MAX_MSG_PX),
        "created": dt.datetime.strptime(it["created_at"], "%Y-%m-%dT%H:%M:%SZ"),
        "state": it["state"], "comments": it.get("comments", 0),
    }


def status_of(e):
    if e["state"] == "closed":
        return f"AT BELT {e['number'] % 4 + 1}"
    if e["comments"] and any(c.get("author_association") in STAFF for c in fetch_comments(e["number"])):
        return "CLEARED"
    return "LANDED"


def meta_of(e):
    if not e["city"]:
        return "UNKNOWN ORIGIN"
    s = f"{airport(e['city'])} · {e['city'].upper()}" + (f", {e['cc']}" if e["cc"] else "")
    return s if len(s) <= 20 else s[:19] + "…"


# ------------------------------------------------------------------ rendering
def esc(s):
    return html.escape(s, quote=True)


def tiles(label, n, x):
    s = "    "
    for k, ch in enumerate(f"{min(n, 99):02d}"):  # shows 99 for 99+
        tx = x + k * 15
        s += (f'<rect x="{tx}" y="17" width="13" height="23" rx="2" fill="#0B0B0C"/>'
              f'<text class="mono" x="{tx + 6.5}" y="33.5" fill="#FFC82C" font-size="14" font-weight="700" text-anchor="middle">{ch}</text>'
              f'<line x1="{tx}" y1="28.5" x2="{tx + 13}" y2="28.5" stroke="#FFC82C" stroke-width="1"/>')
    return s + f'<text class="sub sans" x="{x}" y="55" font-size="7.5" letter-spacing=".8">{label}</text>'


def barcode(y, number, new):
    seed, cur, out = (number * 7919) & 0x7FFFFFFF or 1, y + 8, []
    col = "#6B7684" if new else "#3F4957"
    while cur < y + 44:
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        h, gap = [1, 1, 2, 3][(seed >> 8) & 3], [1, 2, 2][(seed >> 10) % 3]
        if cur + h > y + 44:
            break
        out.append(f'<rect x="626" y="{cur}" width="8" height="{h}" fill="{col}"/>')
        cur += h + gap
    return "".join(out)


def row(i, e):
    y, st = TOP + ROW_H * i, e["status"]
    new = st == "LANDED"
    col, rot, stroke = STATUS["AT BELT" if st.startswith("AT BELT") else st]
    o = []
    if i:
        o.append(f'<line class="dv" x1="0" y1="{y}" x2="640" y2="{y}"/>')
    if new:
        o.append(f'<rect x="0" y="{y}" width="640" height="52" fill="#111925"/><rect x="0" y="{y}" width="4" height="52" fill="#2FD27A"/>')
    if e.get("avatar"):
        o.append(f'<g transform="translate(36 {y + 26})"><image href="{e["avatar"]}" x="-16" y="-16" width="32" height="32" '
                 f'preserveAspectRatio="xMidYMid slice" clip-path="url(#avc)"/><circle r="15.5" fill="none" stroke="#2A3340"/></g>')
    else:
        tint = AVATAR_TINTS[zlib.crc32(e["login"].encode()) % len(AVATAR_TINTS)]
        o.append(f'<use href="#avatar" color="{tint}" transform="translate(36 {y + 26})"/>')
    handle = e["login"] if len(e["login"]) <= 14 else e["login"][:13] + "…"
    o.append(f'<text class="nm sans" x="62" y="{y + 25}" fill="{"#F2F5F8" if new else "#B4BDC8"}">@{esc(handle)}</text>'
             f'<text class="meta sans" x="62" y="{y + 39}">{esc(meta_of(e))}</text>')
    if not new:
        o.append(f'<use href="#stamp" color="{"#38BDF8" if st == "CLEARED" else "#8A95A3"}" opacity=".42" filter="url(#rough)" '
                 f'transform="translate(392 {y + 40}) rotate(-4) scale(.78)"/>')
    o.append(f'<text class="msg sans" x="186" y="{y + 27}" fill="{"#F2F5F8" if new else "#7C8794"}" '
             f'font-weight="{600 if new else 400}">{esc(e["message"])}</text>')
    hhmm = e["created"].strftime("%H:%M")
    for ch, x in zip((hhmm[0], hhmm[1], hhmm[3], hhmm[4]), (448, 461, 481, 494)):
        o.append(f'<rect x="{x}" y="{y + 16}" width="11" height="20" rx="2" fill="#161D27"/>'
                 f'<text class="fl mono" x="{x + 5.5}" y="{y + 31}">{ch}</text>'
                 f'<line x1="{x}" y1="{y + 26}" x2="{x + 11}" y2="{y + 26}" stroke="#0A0E14" stroke-width="1"/>')
    o.append(f'<text class="mono" x="475.5" y="{y + 30.5}" fill="#5B6572" font-size="12" font-weight="700" text-anchor="middle">:</text>')
    o.append(f'<rect x="520.5" y="{y + 17.5}" width="99" height="17" rx="3" fill="{col}" fill-opacity=".12" stroke="{stroke}"/>'
             f'<use href="#plane" fill="{col}" transform="translate(534 {y + 26}) rotate({rot}) scale(.5)"/>'
             f'<text class="chip sans" x="546" y="{y + 29.2}" fill="{col}">{st}</text>')
    o.append(barcode(y, e["number"], new))
    return "\n    ".join(o)


def render(rows, stats):
    who = ", ".join(f"@{r['login']}" + (f" from {r['city']}" if r["city"] else "") for r in rows) or "no arrivals yet"
    aria = esc("Traveler mail inbox styled like a digital airport arrivals board. Latest arrivals: " + who + ".")
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 418" width="640" height="418" role="img" aria-label="{aria}">',
         "  " + STYLE_DEFS,
         '  <g clip-path="url(#c)">',
         '    <rect width="640" height="418" fill="#0A0E14"/>',
         '    <!-- header (brand frame) -->',
         '    <rect width="640" height="72" fill="#FFC82C"/>',
         '    <circle cx="38" cy="36" r="17" fill="#0B0B0C"/>',
         '    <rect x="26" y="28" width="24" height="16" rx="2.5" fill="none" stroke="#FFC82C" stroke-width="1.8"/>',
         '    <path d="M27 30 L38 38 L49 30" fill="none" stroke="#FFC82C" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/>',
         '    <text class="title sans" x="66" y="34">Traveler mail</text>',
         '    <text class="sub sans" x="66" y="52">ARRIVALS HALL · LEAVE A MESSAGE BEFORE YOU GO</text>',
         '    <!-- terminal stats -->',
         tiles("TRAVELERS", stats["travelers"], 416),
         tiles("COUNTRIES", stats["countries"], 490),
         tiles("TODAY", stats["today"], 564),
         '    <!-- column strip -->',
         '    <rect y="72" width="640" height="22" fill="#0F141B"/>',
         '    <text class="col sans" x="20" y="87">TRAVELER</text><text class="col sans" x="186" y="87">MESSAGE</text>'
         '<text class="col sans" x="448" y="87">TIME</text><text class="col sans" x="520" y="87">STATUS</text>']
    for i in range(ROWS):
        if i < len(rows):
            o.append("    " + row(i, rows[i]))
        elif i:
            o.append(f'    <line class="dv" x1="0" y1="{TOP + ROW_H * i}" x2="640" y2="{TOP + ROW_H * i}"/>')
    if not rows:
        o.append('    <text class="mono" x="320" y="222" fill="#FFB000" font-size="13" font-weight="700" letter-spacing="2" text-anchor="middle">NO ARRIVALS YET</text>'
                 '<text class="sans" x="320" y="240" fill="#7C8794" font-size="10" letter-spacing="1.4" text-anchor="middle">BE THE FIRST · TAP A BUTTON BELOW</text>')
    o += ['    <line class="dv" x1="0" y1="406" x2="640" y2="406"/>',
          '    <!-- closing hazard strip -->',
          '    <rect x="0" y="412" width="640" height="6" fill="url(#haz)"/>',
          '  </g>',
          '  <rect x=".75" y=".75" width="638.5" height="416.5" rx="17.5" fill="none" stroke="#1E2631" stroke-width="1.5"/>',
          '</svg>', '']
    return "\n".join(o)


def main():
    if not REPO:
        sys.exit("GITHUB_REPOSITORY is not set")
    entries = [e for e in map(parse_issue, fetch_issues()) if e]  # newest first
    today = dt.datetime.now(dt.timezone.utc).date()
    stats = {
        "travelers": len({e["login"].lower() for e in entries}),
        "countries": len({e["cc"] for e in entries if e["cc"]}),
        "today": sum(e["created"].date() == today for e in entries),
    }
    rows = entries[:ROWS]
    for e in rows:
        e["status"] = status_of(e)
        e["avatar"] = fetch_avatar(e["avatar_url"]) if e["avatar_url"] else None
    svg = render(rows, stats)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"board: {len(rows)} rows, stats {stats}")


if __name__ == "__main__":
    main()
