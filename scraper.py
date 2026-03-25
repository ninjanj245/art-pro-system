"""
ART PRO SYSTEM v5 – Multi-Calendar Scraper
Generates 3 focused ICS calendars:
  • ART_PRO_SLOVENIA.ics
  • ART_PRO_EU.ics
  • ART_PRO_GLOBAL.ics
"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import uuid
from urllib.parse import urlparse
import time
import random

# Playwright for JS-heavy sites
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️ Playwright not installed – falling back to requests only")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "sl,en-US;q=0.9,en;q=0.5",
}

# ─── KEYWORD FILTERS ────────────────────────────────────────────────────────
CALL_KEYWORDS = [
    "razpis", "natečaj", "open call", "prijava", "rok oddaje", "oddaj", "poziv",
    "stipendija", "rezidenca", "grant", "sofinanciranje", "javni poziv", "javni razpis",
    "razpisuje", "prijavi", "deadline", "apply", "application", "submission", "call for",
    "fellowship", "award", "prize", "residency", "funding", "opportunity", "entries",
    "proposals", "rok:", "deadline:", "prijave do", "do ", "artist in residence"
]

EXCLUDE_KEYWORDS = [
    "razstava", "vernisaz", "opening", "exhibition opens", "on view",
    "koncert", "concert", "predstava", "premiere", "performance on",
    "ticket", "vstopnica", "program events", "dogodek", "festival program"
]

def is_call(text):
    text_lower = text.lower()
    has_call = any(kw in text_lower for kw in CALL_KEYWORDS)
    has_exclude = any(kw in text_lower for kw in EXCLUDE_KEYWORDS)
    return has_call and not has_exclude

# ─── STATIC EVENTS (split by region) ────────────────────────────────────────
STATIC_SLO = [
    ("MOL: Letni razpis za kulturo", "20260401", "https://www.ljubljana.si/sl/mestna-obcina/mestna-uprava-mu-mol/oddelki/oddelek-za-kulturo/razpisi/", "GRANT", "HIGH", "Letni razpis Mestne občine Ljubljana"),
    ("MK: Javni razpis za mednarodno dejavnost", "20260331", "https://www.gov.si/zbirke/javne-objave/?category=17&type=javni-razpis", "GRANT", "HIGH", "Ministrstvo za kulturo"),
    ("MK: Javni poziv za sofinanciranje projektov", "20260430", "https://www.gov.si/zbirke/javne-objave/?category=17&type=javni-razpis", "GRANT", "HIGH", "Ministrstvo za kulturo"),
    ("CNVOS: Razpisi za kulturo", "20260430", "https://www.cnvos.si/razpisi/?podrocje=kultura", "GRANT", "MEDIUM", "CNVOS agregator"),
    ("Aksioma / Kapelica: Open Call", "20260601", "https://aksioma.org/", "DIGITAL", "HIGH", "Aksioma – digitalna umetnost"),
    ("SKUC: Open Call za razstave", "20260501", "https://skuc.org/", "VISUAL", "HIGH", "SKUC galerija Ljubljana"),
    ("Kibla: Open Call", "20260501", "https://www.kibla.org/", "DIGITAL", "MEDIUM", "Kibla Maribor"),
    ("Nagrada OHO: Prijave", "20260601", "https://www.oho.si/", "VISUAL", "HIGH", "Nagrada OHO"),
]

STATIC_EU = [
    ("Creative Europe: Culture strand", "20260404", "https://culture.ec.europa.eu/calls/calls-for-proposals", "EU", "HIGH", "Creative Europe – Culture strand"),
    ("Creative Europe: Cooperation Projects", "20260610", "https://culture.ec.europa.eu/calls/calls-for-proposals", "EU", "HIGH", "EU kooperacijski projekti"),
    ("European Cultural Foundation: Connect grant", "20260430", "https://www.culturalfoundation.eu/grants", "EU", "HIGH", "ECF grant"),
]

STATIC_GLOBAL = [
    ("Res Artis: Open Calls", "20260430", "https://resartis.org/open-calls/", "RESIDENCY", "HIGH", "Mednarodne umetniške rezidence"),
    ("Artenda: Residencies & Calls", "20260501", "https://artenda.net/art-open-call-opportunity/residency", "RESIDENCY", "HIGH", "Artenda platform"),
    ("Fulbright: Artist stipends", "20261001", "https://fulbrightscholars.org/", "GRANT", "HIGH", "Fulbright for artists"),
    ("DAAD: Stipendije za umetnike", "20261115", "https://www.daad.de/en/study-and-research-in-germany/scholarships/", "GRANT", "HIGH", "DAAD Germany"),
    ("Pollock-Krasner Foundation", "20260901", "https://pkf.org/", "GRANT", "HIGH", "Pollock-Krasner Grant"),
    ("Saatchi Art: Call for Entries", "20260430", "https://www.saatchiart.com/", "VISUAL", "MEDIUM", "Saatchi Art"),
    ("Ars Electronica: Open Call", "20260315", "https://ars.electronica.art/festival/en/calls/", "DIGITAL", "HIGH", "Ars Electronica"),
]

# ─── SCRAPE SOURCES (split by region) ───────────────────────────────────────
SCRAPE_SLO = [
    ("asociacija.si", "https://www.asociacija.si/si/category/razpisne-priloznosti/", "GENERAL", "HIGH"),
    ("kulturnik.si", "https://novice.kulturnik.si/cat/razpisi", "GENERAL", "MEDIUM"),
    ("CNVOS kultura", "https://www.cnvos.si/razpisi/?podrocje=kultura", "GRANT", "MEDIUM"),
    ("MOL razpisi", "https://www.ljubljana.si/sl/mestna-obcina/mestna-uprava-mu-mol/oddelki/oddelek-za-kulturo/razpisi/", "GRANT", "HIGH"),
    ("MK gov.si", "https://www.gov.si/zbirke/javne-objave/?category=17&type=javni-razpis", "GRANT", "HIGH"),
]

SCRAPE_EU = [
    ("Creative Europe", "https://culture.ec.europa.eu/calls/calls-for-proposals", "EU", "HIGH"),
]

SCRAPE_GLOBAL = [
    ("Res Artis", "https://resartis.org/open-calls/", "RESIDENCY", "HIGH"),
    ("Artenda", "https://artenda.net/art-open-call-opportunity/residency", "RESIDENCY", "HIGH"),
]

# ─── EMOJIS & HELPERS ───────────────────────────────────────────────────────
CATEGORY_EMOJI = {"DIGITAL": "💻", "VISUAL": "🎨", "RESIDENCY": "✈️", "EU": "🇪🇺", "GRANT": "💰", "GENERAL": "📋"}
PRIORITY_EMOJI = {"HIGH": "🔥", "MEDIUM": "⚡", "LOW": "💤"}

def resolve_href(href, base_url, fallback):
    if not href: return fallback
    if href.startswith("http"): return href
    if href.startswith("//"): return "https:" + href
    if href.startswith("/"):
        p = urlparse(base_url)
        return f"{p.scheme}://{p.netloc}{href}"
    return fallback

def fold_line(line):
    if len(line.encode("utf-8")) <= 75: return line
    result = []
    while len(line.encode("utf-8")) > 75:
        chunk = line[:70]
        result.append(chunk)
        line = " " + line[70:]
    result.append(line)
    return "\r\n".join(result)

def make_alarms():
    reminders = [
        ("-P60D", "ZAČNI PRIPRAVO – deadline čez 2 meseca"),
        ("-P30D", "1 MESEC DO DEADLINEA"),
        ("-P14D", "2 TEDNA – pripravi gradiva"),
        ("-P7D", "1 TEDEN – finaliziraj prijavo"),
        ("-P2D", "POJUTRIŠNJEM je deadline!"),
        ("-P1D", "JUTRI JE DEADLINE – oddaj!"),
    ]
    return "\r\n".join([
        "BEGIN:VALARM", f"TRIGGER:{trigger}", "ACTION:DISPLAY", f"DESCRIPTION:{desc}", "END:VALARM"
        for trigger, desc in reminders
    ])

def make_vevent(summary, dtstart, category, priority, url="", description=""):
    uid = str(uuid.uuid4()) + "@artprosystem"
    cat_e = CATEGORY_EMOJI.get(category, "📋")
    pri_e = PRIORITY_EMOJI.get(priority, "")
    dt = datetime.strptime(dtstart, "%Y%m%d")
    dtend = (dt + timedelta(days=1)).strftime("%Y%m%d")
    full_summary = f"{cat_e} {summary} {pri_e}"
    desc_clean = (description + (" | " + url if url else "")).replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")
    lines = [
        "BEGIN:VEVENT",
        fold_line(f"UID:{uid}"),
        fold_line(f"SUMMARY:{full_summary}"),
        f"CATEGORIES:{category}",
        f"DTSTART;VALUE=DATE:{dtstart}",
        f"DTEND;VALUE=DATE:{dtend}",
    ]
    if url: lines.append(fold_line(f"URL:{url}"))
    if desc_clean: lines.append(fold_line(f"DESCRIPTION:{desc_clean[:400]}"))
    lines.append(make_alarms())
    lines.append("END:VEVENT")
    return "\r\n".join(lines)

def generate_ics(events, calendar_name):
    header = "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ART PRO SYSTEM//v5//SL",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{calendar_name}",
        "X-WR-CALDESC:Umetniški razpisi in natečaji",
        "X-WR-TIMEZONE:Europe/Ljubljana",
    ])
    seen = set()
    vevents = []
    events = sorted(events, key=lambda e: e["dtstart"])
    for ev in events:
        key = (ev["summary"][:50].lower(), ev["dtstart"])
        if key in seen: continue
        seen.add(key)
        vevents.append(make_vevent(
            summary=ev["summary"],
            dtstart=ev["dtstart"],
            category=ev.get("category", "GENERAL"),
            priority=ev.get("priority", "MEDIUM"),
            url=ev.get("url", ""),
            description=ev.get("description", ""),
        ))
    print(f"   → {calendar_name}: {len(vevents)} events")
    return header + "\r\n" + "\r\n".join(vevents) + "\r\nEND:VCALENDAR"

# ─── SCRAPING ───────────────────────────────────────────────────────────────
def scrape_source(name, url, category, priority):
    events = []
    try:
        print(f" → Scraping {name} ...")
        if PLAYWRIGHT_AVAILABLE and any(x in url for x in ["resartis.org", "artenda.net"]):
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=30000)
                page.wait_for_timeout(6000)
                html = page.content()
                browser.close()
            soup = BeautifulSoup(html, "html.parser")
        else:
            r = requests.get(url, headers=HEADERS, timeout=25)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

        candidates = soup.select("article, .post, .item, .entry, .card, .listing-item, .opportunity, .razpis, .call, .grant, li, tr, div[class*='post'], div[class*='item'], div[class*='card'], section > div, .event")[:80]
        if not candidates:
            candidates = soup.find_all(["p", "h1", "h2", "h3", "h4", "li", "div"])

        date_patterns = [
            (re.compile(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(202[6-9])"), "dmy"),
            (re.compile(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{2})"), "dmy_short"),
            (re.compile(r"(202[6-9])-(\d{2})-(\d{2})"), "ymd"),
            (re.compile(r"(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(202[6-9])", re.I), "dmonthy"),
            (re.compile(r"(?:rok|deadline|do|until|by|prijave do)[:\s-]*(\d{1,2})\.\s*(\d{1,2})\.\s*(202[6-9])", re.I), "dmy"),
        ]
        MONTHS = {"january":1,"february":2,"march":3,"april":4,"may":5,"june":6,"july":7,"august":8,"september":9,"october":10,"november":11,"december":12}

        for el in candidates:
            text = el.get_text(" ", strip=True)
            if len(text) < 20 or not is_call(text):
                continue

            dt = None
            for pattern, fmt in date_patterns:
                m = pattern.search(text)
                if m:
                    try:
                        if fmt == "dmy":
                            dt = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                        elif fmt == "dmy_short":
                            y = int(m.group(3)); y = 2000 + y if y < 100 else y
                            dt = datetime(y, int(m.group(2)), int(m.group(1)))
                        elif fmt == "ymd":
                            dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                        elif fmt == "dmonthy":
                            dt = datetime(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
                        if dt and dt > datetime.now():
                            break
                    except:
                        continue
            if not dt: continue

            title_el = el.select_one("h1, h2, h3, h4, .title, a, strong")
            title = (title_el.get_text(strip=True)[:120] if title_el else text[:100])
            if len(title) < 5: title = text[:80]

            link_el = el.select_one("a[href]")
            href = resolve_href(link_el["href"] if link_el else None, url, url)

            events.append({
                "summary": title.strip(),
                "dtstart": dt.strftime("%Y%m%d"),
                "category": category,
                "priority": priority,
                "url": href,
                "description": f"Vir: {name} | {text[:200]}...",
            })

        print(f"   ✓ {name}: {len(events)} events found")
        time.sleep(random.uniform(1.5, 3.5))

    except Exception as e:
        print(f"   ✗ {name}: {type(e).__name__} – {e}")

    return events

# ─── MAIN ───────────────────────────────────────────────────────────────────
def main():
    print("🎨 ART PRO SYSTEM v5 – Generating 3 calendars...\n")
    now = datetime.now()

    # Slovenia
    events_slo = [dict(summary=t, dtstart=d, category=c, priority=p, url=u, description=desc)
                  for t, d, u, c, p, desc in STATIC_SLO if datetime.strptime(d, "%Y%m%d") > now]
    for name, url, cat, pri in SCRAPE_SLO:
        events_slo += scrape_source(name, url, cat, pri)

    # EU
    events_eu = [dict(summary=t, dtstart=d, category=c, priority=p, url=u, description=desc)
                 for t, d, u, c, p, desc in STATIC_EU if datetime.strptime(d, "%Y%m%d") > now]
    for name, url, cat, pri in SCRAPE_EU:
        events_eu += scrape_source(name, url, cat, pri)

    # Global
    events_global = [dict(summary=t, dtstart=d, category=c, priority=p, url=u, description=desc)
                     for t, d, u, c, p, desc in STATIC_GLOBAL if datetime.strptime(d, "%Y%m%d") > now]
    for name, url, cat, pri in SCRAPE_GLOBAL:
        events_global += scrape_source(name, url, cat, pri)

    # Generate files
    calendars = [
        ("Slovenia", events_slo, "ART_PRO_SLOVENIA.ics", "🎨 ART PRO – Slovenija"),
        ("EU", events_eu, "ART_PRO_EU.ics", "🎨 ART PRO – EU"),
        ("Global", events_global, "ART_PRO_GLOBAL.ics", "🎨 ART PRO – Global"),
    ]

    for region, events, filename, cal_name in calendars:
        print(f"\nGenerating {filename} ...")
        ics = generate_ics(events, cal_name)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(ics)
        print(f"✅ {filename} saved ({len(events)} events)")

    print("\n🎉 All three calendars generated successfully!")

if __name__ == "__main__":
    main()
