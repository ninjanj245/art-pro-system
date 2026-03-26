# 🎨 ART PRO SYSTEM

Automated scraper that generates three `.ics` calendar files for artists,
updated daily via GitHub Actions.

| Calendar | File | What's in it |
|---|---|---|
| 🇸🇮 Slovenia | `ART_PRO_SLOVENIA.ics` | MOL, MK, JSKD, asociacija.si, kulturnik.si, CNVOS |
| 🇪🇺 EU & Europe | `ART_PRO_EU.ics` | Creative Europe, ECF, Culture Moves Europe |
| 🌍 Global | `ART_PRO_GLOBAL.ics` | Res Artis, Artenda, Call for Entry |

---

## 1. Repo setup

### File structure

Your repo must look like this:

```
your-repo/
├── scraper.py
├── requirements.txt
└── .github/
    └── workflows/
        └── scrape.yml
```

The three `.ics` files are created automatically on first run —
you do not commit them manually.

---

## 2. GitHub Actions permissions

The workflow needs write access to push the `.ics` files back to the repo.

1. Go to your repo on GitHub
2. **Settings → Actions → General**
3. Scroll to **Workflow permissions**
4. Select **Read and write permissions**
5. Click **Save**

Without this the push step will fail with a 403 error.

---

## 3. First run

Trigger the workflow manually to generate the `.ics` files before
subscribing your calendar:

1. Go to **Actions** tab in your repo
2. Click **ART PRO SYSTEM – Dnevni scraper** in the left sidebar
3. Click **Run workflow → Run workflow**
4. Wait ~1 minute for it to complete
5. Check that three `.ics` files now appear in your repo root

---

## 4. Get the calendar URLs

Each `.ics` file has a raw URL you use to subscribe.
The format is:

```
https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/FILENAME.ics
```

Replace `YOUR_USERNAME` and `YOUR_REPO` with your actual values. Example:

```
https://raw.githubusercontent.com/ninjanj245/art-pro-system/main/ART_PRO_SLOVENIA.ics
https://raw.githubusercontent.com/ninjanj245/art-pro-system/main/ART_PRO_EU.ics
https://raw.githubusercontent.com/ninjanj245/art-pro-system/main/ART_PRO_GLOBAL.ics
```

---

## 5. Subscribe in Google Calendar

Do this once for each of the three URLs:

1. Open [Google Calendar](https://calendar.google.com)
2. On the left sidebar, click **+** next to "Other calendars"
3. Choose **From URL**
4. Paste the raw URL
5. Click **Add calendar**

Google will refresh the calendar approximately every 24 hours.
There is no way to force a faster refresh in Google Calendar.

---

## 6. Subscribe in Apple Calendar

Do this once for each of the three URLs:

1. Open **Calendar** on Mac or go to [iCloud Calendar](https://www.icloud.com/calendar)
2. **File → New Calendar Subscription** (Mac) or **Add calendar → Other CalDAV Account** (iOS)
3. Paste the raw URL
4. Click **Subscribe**
5. Set **Auto-refresh** to **Every hour**
6. Choose which local calendar to add it to (or keep as separate)
7. Click **OK**

On iPhone/iPad: Settings → Calendar → Accounts → Add Account →
Other → Add Subscribed Calendar → paste URL.

---

## 7. Schedule

The workflow runs every day at **07:00 UTC (08:00 Ljubljana time)**.
You can change the time by editing the cron line in `scrape.yml`:

```yaml
- cron: '0 7 * * *'
```

Format is: `minute hour day month weekday`
Examples:
- `0 6 * * *` — 06:00 UTC every day
- `0 7 * * 1` — every Monday at 07:00 UTC only

You can also trigger it manually any time from the **Actions** tab.

---

## 8. Adding new sources

Open `scraper.py` and find the two places to edit:

**Static events** (known recurring calls with fixed dates):
Add a dict to the `STATIC_EVENTS` list:
```python
{
    "summary": "Name of the call",
    "dtstart": "20261231",       # YYYYMMDD format
    "geo": "SI",                 # "SI", "EU", or "GLOBAL"
    "category": "GRANT",        # GRANT, RESIDENCY, AWARD, FELLOWSHIP, GENERAL
    "priority": "HIGH",         # HIGH, MEDIUM, LOW
    "url": "https://...",
    "description": "Short note",
},
```

**Live scraped sources** (scraped fresh every day):
Add a function to the scrapers section and register it in `SCRAPERS`:
```python
def scrape_mysite():
    return scrape_generic(
        "My Site",
        "https://mysite.com/calls/",
        "EU",           # geo
        "GRANT",        # category
        "MEDIUM",       # priority
        "article, .item",   # CSS selector for listing items
        "h2, h3, .title",   # CSS selector for title within item
    )

# Then add scrape_mysite to the SCRAPERS list at the bottom
```

---

## 9. Troubleshooting

**Push rejected (fetch first)**
The `--force-with-lease` flag in the workflow handles this.
If it still fails, go to Actions, find the failed run, click Re-run jobs.

**Scraper runs but 0 events found from a site**
The CSS selectors in `scrape_generic()` may not match that site's HTML.
Add a temporary debug line to see the actual structure:
```python
print(soup.prettify()[:3000])
```
Then update the selector to match what you see.

**ICS file is empty / only static events**
Most scraped sites require a date to be present in the article or on
the detail page. If they don't publish deadlines clearly, the event
is skipped. Add them manually to `STATIC_EVENTS` instead.

**Node.js deprecation warning in Actions**
This is a GitHub warning about their own action runners, not your code.
It does not affect the scraper. It will go away when GitHub updates their runners.
