"""
Weekly, key-free source check for the Starlink Middle East dashboard.

Pulls three public sources, compares against last week's snapshot, and writes:
  snapshots/availability-me.json   Starlink's own map status per country (read by index.html)
  snapshots/geoip-me.json          Starlink IP subnets allocated per country
  reports/YYYY-MM-DD.md            Weekly digest used as the pull-request body

No API keys. Standard library only. Never edits data.json itself: humans do that.
"""
import csv, datetime as dt, io, json, os, re, sys, urllib.request, urllib.parse
import xml.etree.ElementTree as ET

TODAY = dt.date.today()
UA = {"User-Agent": "Mozilla/5.0 (starlink-me-dashboard weekly check)"}

# ISO alpha-2 -> name as used in data.json
COUNTRIES = {
    "AE": "United Arab Emirates", "BH": "Bahrain", "EG": "Egypt", "IL": "Israel", "IQ": "Iraq",
    "IR": "Iran", "JO": "Jordan", "KW": "Kuwait", "LB": "Lebanon", "OM": "Oman", "QA": "Qatar",
    "SA": "Saudi Arabia", "SY": "Syria", "YE": "Yemen",
}
ALIASES = {"united arab emirates": "AE", "uae": "AE", "bahrain": "BH", "egypt": "EG", "israel": "IL",
           "iraq": "IQ", "iran": "IR", "iran, islamic republic of": "IR", "jordan": "JO", "kuwait": "KW",
           "lebanon": "LB", "oman": "OM", "qatar": "QA", "saudi arabia": "SA", "syria": "SY",
           "syrian arab republic": "SY", "yemen": "YE"}
NEWS_QUERY = {"AE": "Starlink UAE", "IR": "Starlink Iran", "SA": "Starlink Saudi Arabia"}

# Candidate URLs for the JSON that paints starlink.com/map. If Starlink renames it,
# open starlink.com/map with browser devtools > Network, filter "avail", and add the URL here.
AVAILABILITY_URLS = [
    "https://api.starlink.com/public-files/availability.json",
    "https://api.starlink.com/public-files/availability-map.json",
    "https://www.starlink.com/public-files/availability.json",
]
GEOIP_URL = "https://geoip.starlinkisp.net/feed.csv"


def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def load_json(path, default):
    try: return json.load(open(path))
    except Exception: return default

def code_for(entry):
    """Find a Middle East ISO code anywhere in a dict entry."""
    for k, v in entry.items():
        if not isinstance(v, str): continue
        s = v.strip()
        if len(s) == 2 and s.upper() in COUNTRIES and k.lower() in ("code", "iso", "iso2", "country", "countrycode", "country_code", "id", "alpha2", "a2"):
            return s.upper()
        if len(s) == 3 and s.upper()[:2] in COUNTRIES and k.lower() in ("iso3", "alpha3", "a3", "iso_a3", "adm0_a3"):
            pass
        if s.lower() in ALIASES: return ALIASES[s.lower()]
    return None

def status_for(entry):
    """Best-effort human status string from an entry."""
    for k in ("status", "availability", "availabilityStatus", "state", "label", "category", "type", "display"):
        if k in entry and isinstance(entry[k], str): 
            extra = entry.get("expectedDate") or entry.get("expected") or entry.get("date") or ""
            return (entry[k] + (f" ({extra})" if extra else "")).strip()
    return json.dumps({k: v for k, v in entry.items() if isinstance(v, (str, int, bool))})[:120]

def walk(obj):
    """Yield every dict in a nested JSON structure."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values(): yield from walk(v)
    elif isinstance(obj, list):
        for v in obj: yield from walk(v)


def fetch_availability():
    for url in AVAILABILITY_URLS:
        try:
            data = json.loads(get(url))
        except Exception as e:
            print(f"availability: {url} -> {e}")
            continue
        found = {}
        for entry in walk(data):
            c = code_for(entry)
            if c and c not in found:
                found[c] = status_for(entry)
        if len(found) >= 5:
            print(f"availability: parsed {len(found)} Middle East entries from {url}")
            return {"source": url, "checked": TODAY.isoformat(), "status": found}
        print(f"availability: {url} parsed but only {len(found)} ME entries; schema may have changed")
    return None


def fetch_geoip():
    try:
        text = get(GEOIP_URL).decode("utf-8", "replace")
    except Exception as e:
        print(f"geoip: {e}"); return None
    counts = {c: 0 for c in COUNTRIES}
    cities = {c: set() for c in COUNTRIES}
    for row in csv.reader(io.StringIO(text)):
        if len(row) >= 2 and row[1].upper() in counts:
            counts[row[1].upper()] += 1
            if len(row) >= 4 and row[3]: cities[row[1].upper()].add(row[3])
    return {"source": GEOIP_URL, "checked": TODAY.isoformat(),
            "subnets": counts, "cities": {k: sorted(v) for k, v in cities.items()}}


def fetch_news(days=8, per_country=5):
    out = {}
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    for code, name in COUNTRIES.items():
        q = NEWS_QUERY.get(code, f"Starlink {name}")
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "en", "gl": "US", "ceid": "US:en"})
        try:
            root = ET.fromstring(get(url))
        except Exception as e:
            print(f"news {name}: {e}"); continue
        items = []
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            pub = it.findtext("pubDate") or ""
            try:
                when = dt.datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=dt.timezone.utc)
            except Exception:
                when = None
            if when and when < since: continue
            items.append({"title": title, "link": link, "date": when.date().isoformat() if when else ""})
        out[code] = items[:per_country]
    return out


def main():
    os.makedirs("snapshots", exist_ok=True); os.makedirs("reports", exist_ok=True)
    prev_av = load_json("snapshots/availability-me.json", {})
    prev_geo = load_json("snapshots/geoip-me.json", {})
    data = load_json("data.json", {"countries": []})
    dash = {c["name"]: c["status"] for c in data.get("countries", [])}

    av = fetch_availability()
    geo = fetch_geoip()
    news = fetch_news()

    lines = [f"# Weekly source check, {TODAY.isoformat()}", ""]
    flags = []

    # --- Starlink map
    lines.append("## Starlink's official availability map")
    if av:
        json.dump(av, open("snapshots/availability-me.json", "w"), indent=2)
        lines.append(f"Source: {av['source']}\n")
        lines.append("| Country | Starlink map says | Last week | Dashboard status |")
        lines.append("|---|---|---|---|")
        for code, name in COUNTRIES.items():
            now = av["status"].get(code, "not listed")
            before = prev_av.get("status", {}).get(code, "not listed") if prev_av else "n/a"
            changed = bool(prev_av) and before != now
            if changed: flags.append(f"**{name}**: Starlink map changed from '{before}' to '{now}'")
            lines.append(f"| {name}{' ⚠️' if changed else ''} | {now} | {before} | {dash.get(name, '-')} |")
    else:
        lines.append("Could not fetch or parse the map data this week. See AVAILABILITY_URLS in scripts/check_sources.py; "
                     "the file name may have changed (find it via devtools on starlink.com/map).")
        flags.append("Availability map fetch failed")
    lines.append("")

    # --- GeoIP
    lines.append("## Starlink IP address allocations (geoip.starlinkisp.net)")
    lines.append("A country gaining subnets for the first time usually precedes a launch.\n")
    if geo:
        json.dump(geo, open("snapshots/geoip-me.json", "w"), indent=2)
        lines.append("| Country | Subnets now | Last week | Cities listed |")
        lines.append("|---|---|---|---|")
        for code, name in COUNTRIES.items():
            now = geo["subnets"][code]; before = prev_geo.get("subnets", {}).get(code)
            mark = ""
            if before is not None and now != before:
                mark = " ⚠️"
                if before == 0 and now > 0: flags.append(f"**{name}**: first Starlink IP subnets allocated ({now})")
                elif now == 0 and before > 0: flags.append(f"**{name}**: IP subnets removed")
            lines.append(f"| {name}{mark} | {now} | {'n/a' if before is None else before} | {', '.join(geo['cities'][code]) or '-'} |")
    else:
        lines.append("GeoIP feed unavailable this week.")
    lines.append("")

    # --- News
    lines.append("## Headlines this week (Google News)")
    any_news = False
    for code, name in COUNTRIES.items():
        items = news.get(code, [])
        if not items: continue
        any_news = True
        lines.append(f"**{name}**")
        for it in items: lines.append(f"- {it['date']} [{it['title']}]({it['link']})")
        lines.append("")
    if not any_news: lines.append("No fresh headlines found.\n")

    # --- Summary at top
    summary = ["## What needs a human look", ""]
    summary += [f"- {f}" for f in flags] if flags else ["- Nothing changed in Starlink's own data this week. Skim the headlines below, then close this PR or merge it to record the snapshot."]
    summary += ["", "To update the dashboard, edit `data.json` (statuses: live, launch, sector, licensed, pending, blocked) and `updated`.", ""]
    report = "\n".join(lines[:2] + summary + lines[2:])
    open(f"reports/{TODAY.isoformat()}.md", "w").write(report)
    open("REPORT.md", "w").write(report)
    print(report)
    # Expose a one-line title for the PR
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f:
        f.write(f"title=Weekly check {TODAY.isoformat()}: {len(flags)} change(s) flagged\n")


if __name__ == "__main__":
    main()
