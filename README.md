# Starlink in the Middle East

Interactive dashboard tracking Starlink's rollout across 14 Middle Eastern markets, plus an infographic on how the network works and how it's secured.

**Live site:** enable GitHub Pages (Settings → Pages → Deploy from branch `main`, folder `/`).

## Files

| File | Purpose |
|---|---|
| `index.html` | Dashboard + infographic. Reads `data.json` (and `snapshots/availability-me.json` if present) at load; falls back to an embedded snapshot offline. |
| `data.json` | All country statuses, dates, prices, notes and timeline events. **This is the file you edit to update the site.** |
| `scripts/check_sources.py` | Weekly checker. Pulls three public sources and writes a digest. No API keys. |
| `.github/workflows/weekly-check.yml` | Runs the checker every Monday and opens a pull request with the digest. |
| `snapshots/` | Last known Starlink map status and IP allocations per country (created by the workflow). |
| `reports/` | One digest per week (created by the workflow). |

## What the weekly check does

Every Monday a GitHub Action fetches, without any account or key:

1. **Starlink's own availability map data** (`api.starlink.com/public-files/`): the status Starlink itself shows for each country: Available now, Pending regulatory approval, Service date unknown, blacklisted.
2. **Starlink's GeoIP feed** (`geoip.starlinkisp.net/feed.csv`): how many IP subnets Starlink has assigned to each country. A country going from 0 to some usually means a launch is imminent.
3. **Google News RSS** for "Starlink + country": the week's headlines, up to five per country.

It compares 1 and 2 with last week's snapshot and opens a **pull request** whose description starts with "What needs a human look": any status flips or new IP allocations, followed by the tables and headlines. Nothing on the site changes automatically. You read the digest, edit `data.json` if warranted, and merge (to record the snapshot) or close.

The dashboard also shows "Starlink's own map says…" inside each expanded country row once the first snapshot exists, so map-vs-dashboard disagreements are visible on the page itself.

## One-time setup

1. Upload all files including the hidden `.github` folder.
2. **Settings → Actions → General → Workflow permissions**: choose *Read and write permissions* and tick *Allow GitHub Actions to create and approve pull requests*. Save.
3. **Actions tab → Weekly source check → Run workflow** to test. A pull request should appear within two minutes.

## If the map fetch fails

Starlink occasionally renames the JSON its map uses. The digest will say so. To fix: open <https://www.starlink.com/map>, press F12 → Network tab, filter for `avail`, copy the JSON URL, and add it to `AVAILABILITY_URLS` at the top of `scripts/check_sources.py`. The GeoIP feed and news checks keep working regardless.

## Editing `data.json`

Statuses: `live`, `launch`, `sector` (aviation/maritime only), `licensed` (licensed, not active), `pending`, `blocked`. Dates are `"YYYY-MM"` or `null`. Add timeline milestones under `events` as `{"d":"YYYY-MM","t":"Label","c":"status"}`. Update `updated` so the page footer stays honest.
