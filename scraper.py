"""
ART PRO SYSTEM v7
Three calendars by geography:
  - ART_PRO_SLOVENIA.ics
  - ART_PRO_EU.ics
  - ART_PRO_GLOBAL.ics
"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import uuid
from urllib.parse import urljoin
import time
import random

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "sl,en-US;q=0.9,en;q=0.5",
}

# ── GEOGRAPHY ROUTING ─────────────────────────────────────────────────────────
# Each source is tagged: "SI", "EU", or "GLOBAL"

# ── KEYWORDS ──────────────────────────────────────────────────────────────────

CALL_KEYWORDS = [
    "razpis", "natečaj", "open call", "prijava", "rok oddaje", "poziv",
    "stipendija", "rezidenca", "grant", "sofinanciranje", "javni poziv",
    "javni razpis", "deadline", "apply", "application", "submission",
    "call for", "fellowship", "award", "prize", "residency", "funding",
    "opportunity", "proposals", "artist in residence", "entries",
]

EXCLUDE_KEYWORDS = [
    "razstava odprtje", "vernisaz", "exhibition opens", "on view until",
    "koncert", "concert", "predstava", "premiere", "vstopnica", "ticket",
]

def is_call(text):
    t = text.lower()
    return (
        any(kw in t for kw in CALL_KEYWORDS)
        and not any(kw in t for kw in EXCLUDE_KEYWORDS)
    )

# ── DATE PARSING ──────────────────────────────────────────────────────────────

MONTHS_ALL = {
    "januar": 1, "februar": 2, "marec": 3, "april": 4, "maj": 5, "junij": 6,
    "julij": 7, "avgust": 8, "september": 9, "oktober": 10, "november": 11,
    "december": 12,
    "january": 1, "february": 2, "march": 3, "may": 5, "june": 6,
    "july": 7, "august": 8, "october": 10,
}

DATE_PATTERNS = [
    (re.compile(r"\b(\d{1,2})[.\s]+(\d{1,2})[.\s]+(202[5-9])\b"), "dmy"),
    (re.compile(r"\b(202[5-9])-(\d{2})-(\d{2})\b"), "ymd"),
    (re.compile(
        r"\b(\d{1,2})\.?\s+(" + "|".join(MONTHS_ALL.keys()) + r")\s+(202[5-9])\b",
        re.I
    ), "dmonthy"),
    (re.compile(r"\b(\d{1,2})[.\s]+(\d{1,2})[.\s]+(\d{2})\b"), "dmy_short"),
]

def parse_date(text):
    now = datetime.now()
    for pattern, fmt in DATE_PATTERNS:
        for m in pattern.finditer(text):
            try:
                if fmt == "dmy":
                    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                elif fmt == "ymd":
                    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                elif fmt == "dmonthy":
                    d = int(m.group(1))
                    mo = MONTHS_ALL[m.group(2).lower()]
                    y = int(m.group(3))
                elif fmt == "dmy_short":
                    d, mo = int(m.group(1)), int(m.group(2))
                    y = 2000 + int(m.group(3))
                else:
                    continue
                dt = datetime(y, mo, d)
                if dt > now:
                    return dt
            except (ValueError, KeyError):
                continue
    return None

def parse_date_from_element(el):
    time_el = el.find("time")
    if time_el:
        dt = parse_date(time_el.get("datetime", "")) or parse_date(time_el.get_text())
        if dt:
            return dt
    for attr in ["data-date", "data-deadline", "data-end", "data-expiry"]:
        val = el.get(attr, "")
        if val:
            dt = parse_date(val)
            if dt:
                return dt
    dt = parse_date(el.get_text(" ", strip=True))
    if dt:
        return dt
    parent = el.parent
    if parent:
        dt = parse_date(parent.get_text(" ", strip=True))
        if dt:
            return dt
    return None

def fetch_date_from_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        deadline_re = re.compile(
            r"(rok|deadline|prijave do|oddaj do|do:|until|by:)", re.I
        )
        for el in soup.find_all(string=deadline_re):
            parent = el.parent
            if parent:
                dt = parse_date(parent.get_text(" ", strip=True))
                if dt:
                    return dt
        return parse_date(soup.get_text(" ", strip=True))
    except Exception:
        return None

def abs_url(href, base):
    if not href:
        return base
    return urljoin(base, href)

# ── ICS GENERATION ────────────────────────────────────────────────────────────

CALENDAR_CONFIGS = {
    "SI": {
        "filename": "ART_PRO_SLOVENIA.ics",
        "name": "🇸🇮 ART PRO – Slovenija",
        "desc": "Slovenski umetniški razpisi\\, natečaji\\, rezidence",
        "emoji": "🇸🇮",
    },
    "EU": {
        "filename": "ART_PRO_EU.ics",
        "name": "🇪🇺 ART PRO – EU & Evropa",
        "desc": "Evropski razpisi\\, Creative Europe\\, EU rezidence",
        "emoji": "🇪🇺",
    },
    "GLOBAL": {
        "filename": "ART_PRO_GLOBAL.ics",
        "name": "🌍 ART PRO – Global",
        "desc": "Mednarodni razpisi\\, rezidence\\, fellowships",
        "emoji": "🌍",
    },
}

CATEGORY_EMOJI = {
    "GRANT": "💰", "RESIDENCY": "✈️", "AWARD": "🏆",
    "FELLOWSHIP": "🎓", "GENERAL": "📋",
}
PRIORITY_EMOJI = {"HIGH": "🔥", "MEDIUM": "⚡", "LOW": "💤"}

def fold(line):
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    result, pos = [], 0
    while pos < len(encoded):
        limit = 75 if pos == 0 else 74
        chunk = encoded[pos:pos + limit]
        while len(chunk) > 1 and (chunk[-1] & 0xC0) == 0x80:
            chunk = chunk[:-1]
        result.append(chunk.decode("utf-8"))
        pos += len(chunk)
    return "\r\n ".join(result)

def escape_ics(s):
    return (s.replace("\\", "\\\\")
             .replace("\n", "\\n")
             .replace(",", "\\,")
             .replace(";", "\\;"))

def make_alarms():
    reminders = [
        ("-P60D", "ZAČNI PRIPRAVO – deadline čez 2 meseca"),
        ("-P30D", "1 MESEC DO DEADLINEA"),
        ("-P14D", "2 TEDNA – produkcija gradiv"),
        ("-P7D",  "1 TEDEN – finaliziraj prijavo"),
        ("-P2D",  "POJUTRIŠNJEM je deadline!"),
        ("-P1D",  "JUTRI JE DEADLINE – oddaj!"),
    ]
    blocks = []
    for trigger, desc in reminders:
        lines = [
            "BEGIN:VALARM",
            "TRIGGER:" + trigger,
            "ACTION:DISPLAY",
            "DESCRIPTION:" + desc,
            "END:VALARM",
        ]
        blocks.append("\r\n".join(lines))
    return "\r\n".join(blocks)

def make_vevent(ev):
    uid = str(uuid.uuid4()) + "@artprosystem"
    cat_e = CATEGORY_EMOJI.get(ev.get("category", "GENERAL"), "📋")
    pri_e = PRIORITY_EMOJI.get(ev.get("priority", "MEDIUM"), "")
    geo_e = CALENDAR_CONFIGS[ev["geo"]]["emoji"]
    dtstart = ev["dtstart"]
    dtend = (datetime.strptime(dtstart, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")
    summary = escape_ics(f"{geo_e} {cat_e} {ev['summary'][:90]} {pri_e}".strip())
    desc = escape_ics(ev.get("description", "")[:400])
    url = ev.get("url", "")
    if url and desc:
        desc = f"{desc} | {url}"
    elif url:
        desc = url

    lines = [
        "BEGIN:VEVENT",
        fold(f"UID:{uid}"),
        fold(f"SUMMARY:{summary}"),
        f"CATEGORIES:{ev.get('category', 'GENERAL')}",
        f"DTSTART;VALUE=DATE:{dtstart}",
        f"DTEND;VALUE=DATE:{dtend}",
    ]
    if url:
        lines.append(fold(f"URL:{url}"))
    if desc:
        lines.append(fold(f"DESCRIPTION:{desc}"))
    lines.append(make_alarms())
    lines.append("END:VEVENT")
    return "\r\n".join(lines)

def generate_ics(events, geo):
    cfg = CALENDAR_CONFIGS[geo]
    geo_events = [e for e in events if e["geo"] == geo]

    header = "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//ART PRO SYSTEM//v6//{geo}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{cfg['name']}",
        f"X-WR-CALDESC:{cfg['desc']}",
        "X-WR-TIMEZONE:Europe/Ljubljana",
    ])

    seen, vevents = set(), []
    for ev in sorted(geo_events, key=lambda e: e["dtstart"]):
        key = (ev["summary"][:50].lower(), ev["dtstart"])
        if key in seen:
            continue
        seen.add(key)
        vevents.append(make_vevent(ev))

    print(f"  {cfg['filename']}: {len(vevents)} razpisov")
    return header + "\r\n" + "\r\n".join(vevents) + "\r\nEND:VCALENDAR\r\n"

# ── STATIC BASE ───────────────────────────────────────────────────────────────
# geo: "SI" = Slovenia, "EU" = Europe/EU, "GLOBAL" = worldwide

STATIC_EVENTS = [
    # ── SLOVENIA ──────────────────────────────────────────────────────────────
    {
        "summary": "MOL: Letni razpis za kulturo",
        "dtstart": "20260401",
        "geo": "SI", "category": "GRANT", "priority": "HIGH",
        "url": "https://www.ljubljana.si/sl/mestna-obcina/mestna-uprava-mu-mol/oddelki/oddelek-za-kulturo/razpisi/",
        "description": "Letni razpis Mestne občine Ljubljana",
    },
    {
        "summary": "MK: Javni razpis za mednarodno dejavnost",
        "dtstart": "20260331",
        "geo": "SI", "category": "GRANT", "priority": "HIGH",
        "url": "https://www.gov.si/zbirke/javne-objave/?category=17&type=javni-razpis",
        "description": "Ministrstvo za kulturo RS",
    },
    {
        "summary": "MK: Javni poziv za sofinanciranje projektov",
        "dtstart": "20260430",
        "geo": "SI", "category": "GRANT", "priority": "HIGH",
        "url": "https://www.gov.si/zbirke/javne-objave/?category=17&type=javni-razpis",
        "description": "Ministrstvo za kulturo RS",
    },
    {
        "summary": "JSKD: Razpis za kulturne projekte",
        "dtstart": "20260315",
        "geo": "SI", "category": "GRANT", "priority": "HIGH",
        "url": "https://www.jskd.si/razpisi/",
        "description": "Javni sklad RS za kulturne dejavnosti",
    },
    {
        "summary": "MO Maribor: Razpis za kulturo",
        "dtstart": "20260331",
        "geo": "SI", "category": "GRANT", "priority": "MEDIUM",
        "url": "https://www.maribor.si/podrocje.aspx?id=451",
        "description": "Mestna občina Maribor – razpis za kulturne projekte",
    },
    # ── EU ────────────────────────────────────────────────────────────────────
    {
        "summary": "Creative Europe: Culture strand",
        "dtstart": "20260404",
        "geo": "EU", "category": "GRANT", "priority": "HIGH",
        "url": "https://culture.ec.europa.eu/calls/calls-for-proposals",
        "description": "Creative Europe – Culture strand open calls",
    },
    {
        "summary": "Creative Europe: MEDIA strand",
        "dtstart": "20260530",
        "geo": "EU", "category": "GRANT", "priority": "HIGH",
        "url": "https://culture.ec.europa.eu/calls/calls-for-proposals",
        "description": "Creative Europe – MEDIA strand",
    },
    {
        "summary": "European Cultural Foundation: Grants",
        "dtstart": "20260430",
        "geo": "EU", "category": "GRANT", "priority": "HIGH",
        "url": "https://www.culturalfoundation.eu/grants",
        "description": "ECF grants for arts and culture",
    },
    {
        "summary": "Culture Moves Europe: Mobility grants",
        "dtstart": "20260430",
        "geo": "EU", "category": "GRANT", "priority": "HIGH",
        "url": "https://culturemoveseurope.eu/mobility-grants/",
        "description": "Individual mobility grants for artists in Europe",
    },
    {
        "summary": "European Media Art Festival: Open Call",
        "dtstart": "20260115",
        "geo": "EU", "category": "AWARD", "priority": "MEDIUM",
        "url": "https://www.emaf.de/open-call/",
        "description": "EMAF – European Media Art Festival open call",
    },
    # ── GLOBAL ────────────────────────────────────────────────────────────────
    {
        "summary": "Res Artis: Open Calls (global)",
        "dtstart": "20260430",
        "geo": "GLOBAL", "category": "RESIDENCY", "priority": "HIGH",
        "url": "https://resartis.org/open-calls/",
        "description": "Global artist residency network",
    },
    {
        "summary": "Artenda: Residency Open Calls",
        "dtstart": "20260430",
        "geo": "GLOBAL", "category": "RESIDENCY", "priority": "HIGH",
        "url": "https://artenda.net/art-open-call-opportunity/residency",
        "description": "Artenda – international residencies",
    },
    {
        "summary": "Call for Entry: International open calls",
        "dtstart": "20260430",
        "geo": "GLOBAL", "category": "GENERAL", "priority": "MEDIUM",
        "url": "https://www.callforentry.org/",
        "description": "CAFE – Call for Entry aggregator",
    },
    {
        "summary": "Submittable: Arts & Culture grants",
        "dtstart": "20260430",
        "geo": "GLOBAL", "category": "GRANT", "priority": "MEDIUM",
        "url": "https://www.submittable.com/discover/",
        "description": "Submittable – global arts grants and open calls",
    },
    {
        "summary": "Rockefeller Foundation: Arts & Culture",
        "dtstart": "20260531",
        "geo": "GLOBAL", "category": "GRANT", "priority": "HIGH",
        "url": "https://www.rockefellerfoundation.org/grants/",
        "description": "Rockefeller Foundation arts grants",
    },
]

# ── SCRAPERS ──────────────────────────────────────────────────────────────────

def scrape_generic(name, url, geo, category, priority, article_sel, title_sel=None):
    events = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        articles = soup.select(article_sel)
        print(f"  {name}: {len(articles)} kandidatov")

        for el in articles:
            text = el.get_text(" ", strip=True)
            if not is_call(text):
                continue
            t_el = el.select_one(title_sel) if title_sel else el.select_one("h1,h2,h3,h4,.title,a")
            title = t_el.get_text(strip=True) if t_el else text[:80]
            if len(title) < 4:
                title = text[:80]
            a_el = el.select_one("a[href]")
            link = abs_url(a_el["href"], url) if a_el else url
            dt = parse_date_from_element(el)
            if not dt and link != url:
                dt = fetch_date_from_page(link)
            if not dt:
                continue
            events.append({
                "summary": title.strip(),
                "dtstart": dt.strftime("%Y%m%d"),
                "geo": geo,
                "category": category,
                "priority": priority,
                "url": link,
                "description": f"Vir: {name}",
            })
    except Exception as e:
        print(f"  ✗ {name}: {type(e).__name__} – {e}")
    print(f"  ✓ {name}: {len(events)} razpisov")
    return events


# ── SLOVENIA scrapers ─────────────────────────────────────────────────────────

def scrape_asociacija():
    return scrape_generic(
        "asociacija.si",
        "https://www.asociacija.si/si/category/razpisne-priloznosti/",
        "SI", "GENERAL", "HIGH",
        "article, .post, .type-post",
        "h2 a, h3 a, .entry-title a",
    )

def scrape_kulturnik():
    events = []
    url = "https://novice.kulturnik.si/cat/razpisi"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for el in soup.select(".post, article, .news-item, li.item"):
            text = el.get_text(" ", strip=True)
            if not is_call(text):
                continue
            a = el.select_one("a[href]")
            title = a.get_text(strip=True) if a else text[:80]
            link = abs_url(a["href"], url) if a else url
            dt = parse_date_from_element(el) or fetch_date_from_page(link)
            if not dt:
                continue
            events.append({
                "summary": title,
                "dtstart": dt.strftime("%Y%m%d"),
                "geo": "SI",
                "category": "GENERAL",
                "priority": "MEDIUM",
                "url": link,
                "description": "Vir: kulturnik.si",
            })
    except Exception as e:
        print(f"  ✗ kulturnik.si: {e}")
    print(f"  ✓ kulturnik.si: {len(events)} razpisov")
    return events

def scrape_cnvos():
    return scrape_generic(
        "CNVOS",
        "https://www.cnvos.si/razpisi/?podrocje=kultura",
        "SI", "GRANT", "MEDIUM",
        ".razpis, .item, article, .listing-item, tr",
        "h2, h3, .title, td a",
    )

def scrape_mol():
    events = []
    url = "https://www.ljubljana.si/sl/mestna-obcina/mestna-uprava-mu-mol/oddelki/oddelek-za-kulturo/razpisi/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for row in soup.select("table tr, .razpis-item, article, .item"):
            text = row.get_text(" ", strip=True)
            if not is_call(text):
                continue
            a = row.select_one("a[href]")
            title = a.get_text(strip=True) if a else text[:80]
            link = abs_url(a["href"], url) if a else url
            dt = parse_date_from_element(row) or fetch_date_from_page(link)
            if not dt:
                continue
            events.append({
                "summary": title,
                "dtstart": dt.strftime("%Y%m%d"),
                "geo": "SI",
                "category": "GRANT",
                "priority": "HIGH",
                "url": link,
                "description": "Vir: MOL",
            })
    except Exception as e:
        print(f"  ✗ MOL: {e}")
    print(f"  ✓ MOL: {len(events)} razpisov")
    return events

def scrape_mk():
    return scrape_generic(
        "MK gov.si",
        "https://www.gov.si/zbirke/javne-objave/?category=17&type=javni-razpis",
        "SI", "GRANT", "HIGH",
        ".item, article, .govsi-item, li, tr",
        "h2, h3, .title, a",
    )

def scrape_jskd():
    return scrape_generic(
        "JSKD",
        "https://www.jskd.si/razpisi/",
        "SI", "GRANT", "HIGH",
        "article, .post, .razpis, .item, li",
        "h2, h3, a, .title",
    )

# ── EU scrapers ───────────────────────────────────────────────────────────────

def scrape_creative_europe():
    events = []
    url = "https://culture.ec.europa.eu/calls/calls-for-proposals"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for el in soup.select(".call-item, .ecl-card, article, .item, li"):
            text = el.get_text(" ", strip=True)
            if len(text) < 20:
                continue
            a = el.select_one("a[href]")
            title = a.get_text(strip=True) if a else text[:100]
            link = abs_url(a["href"], url) if a else url
            dt = parse_date_from_element(el)
            if not dt:
                continue
            events.append({
                "summary": title,
                "dtstart": dt.strftime("%Y%m%d"),
                "geo": "EU",
                "category": "GRANT",
                "priority": "HIGH",
                "url": link,
                "description": "Vir: Creative Europe",
            })
    except Exception as e:
        print(f"  ✗ Creative Europe: {e}")
    print(f"  ✓ Creative Europe: {len(events)} razpisov")
    return events

def scrape_ecf():
    return scrape_generic(
        "European Cultural Foundation",
        "https://www.culturalfoundation.eu/grants",
        "EU", "GRANT", "HIGH",
        "article, .grant, .item, .card, .post",
        "h2, h3, .title, a",
    )

def scrape_culture_moves():
    return scrape_generic(
        "Culture Moves Europe",
        "https://culturemoveseurope.eu/mobility-grants/",
        "EU", "GRANT", "HIGH",
        "article, .post, .item, .card, section",
        "h2, h3, .title",
    )

# ── GLOBAL scrapers ───────────────────────────────────────────────────────────

def scrape_resartis():
    return scrape_generic(
        "Res Artis",
        "https://resartis.org/open-calls/",
        "GLOBAL", "RESIDENCY", "HIGH",
        "article, .post, .call-item, .opportunity",
        "h2 a, h3 a, .entry-title",
    )

def scrape_artenda():
    return scrape_generic(
        "Artenda",
        "https://artenda.net/art-open-call-opportunity/residency",
        "GLOBAL", "RESIDENCY", "HIGH",
        ".opportunity, article, .post, .item, .card",
        "h2, h3, .title",
    )

def scrape_callforentry():
    return scrape_generic(
        "Call for Entry",
        "https://www.callforentry.org/festivals_unique_byloc.php?country=",
        "GLOBAL", "GENERAL", "MEDIUM",
        ".opportunity, article, .listing, li, .item",
        "h2, h3, .title, a",
    )

# ── SCRAPER REGISTRY ──────────────────────────────────────────────────────────

SCRAPERS = [
    # Slovenia
    scrape_asociacija,
    scrape_kulturnik,
    scrape_cnvos,
    scrape_mol,
    scrape_mk,
    scrape_jskd,
    # EU
    scrape_creative_europe,
    scrape_ecf,
    scrape_culture_moves,
    # Global
    scrape_resartis,
    scrape_artenda,
    scrape_callforentry,
]

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("ART PRO SYSTEM v6 – 3 calendars\n")
    all_events = []

    # 1. Static base
    print("1. Statična baza...")
    now = datetime.now()
    for ev in STATIC_EVENTS:
        try:
            if datetime.strptime(ev["dtstart"], "%Y%m%d") > now:
                all_events.append(ev)
        except ValueError:
            pass
    si = sum(1 for e in all_events if e["geo"] == "SI")
    eu = sum(1 for e in all_events if e["geo"] == "EU")
    gl = sum(1 for e in all_events if e["geo"] == "GLOBAL")
    print(f"  SI:{si}  EU:{eu}  GLOBAL:{gl}\n")

    # 2. Live scraping
    print("2. Scrapam strani...")
    for scraper in SCRAPERS:
        try:
            all_events += scraper()
        except Exception as e:
            print(f"  ✗ {scraper.__name__}: {e}")
        time.sleep(random.uniform(1.5, 3.0))

    # 3. Write 3 ICS files
    print(f"\n3. Generiram .ics datoteke ({len(all_events)} skupaj)...")
    for geo in ("SI", "EU", "GLOBAL"):
        cfg = CALENDAR_CONFIGS[geo]
        ics = generate_ics(all_events, geo)
        with open(cfg["filename"], "w", encoding="utf-8") as f:
            f.write(ics)
        print(f"  ✅ {cfg['filename']}")

    print("\n✅ Končano!")

if __name__ == "__main__":
    main()
