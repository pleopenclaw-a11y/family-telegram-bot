# Family Board — web/ PWA surface

A dependency-free, Thai-first, mobile/tablet-first **progressive web app** that shows a shared
Family Board dashboard. This is **Track B** of the family-telegram-bot refactor plan (see
`task_plan.md`).

## What it does

A single dashboard with six sections:

- ☀️ **วันนี้ (Today)** – today's label + events/tasks due today
- 📅 **อีเวนต์ที่จะถึง (Upcoming events)**
- ✅ **งานที่ต้องทำ (Tasks)**
- 🗒️ **บันทึก (Notes)**
- 🛒 **รายการซื้อของ (Shopping)**
- 📥 **ฝากสิ่งสำคัญให้ AI (AI capture box)** – type a message, pick a type, confirm, and it lands
  on the board as a local draft

Everything is **Thai-first**: labels, headings, dates, and inputs are in Thai.

## Requirements

- Any modern browser (Chrome / Edge / Safari / Firefox).
- No build step, no Node, no dependencies — plain HTML + CSS + JS modules.

## Run locally for preview

Because the app uses ES modules + a service worker, serve it over HTTP rather than opening the
file directly:

```bash
cd /home/jornjud/projects/family-telegram-bot/web
python3 -m http.server 8080
```

Then open <http://localhost:8080> (or on a phone on the same LAN, `http://<your-ip>:8080`).

> To preview from a phone/tablet: `python3 -m http.server 8080 --bind 0.0.0.0`
> and open `http://<your-computer-ip>:8080`. (Job of a separate host firewall if needed.)

## Data modes

`js/api.js` is the **only** data boundary. It supports two modes:

- Default mode uses `MockApiAdapter` and localStorage for a safe offline preview.
- `?mode=live&api=http://127.0.0.1:8787&group=family` uses `RealApiAdapter` and the server API.

- **Display sections** are seeded with fake sample data (already "live-looking" relative to today).
- In mock mode, capture is simulated locally — no AI, no network. Confirmed items are stored only
  in this browser's `localStorage` (`family-board.drafts.v1`) and shown as drafts.
- In live mode, capture uses server-side preview → browser confirmation → server-side commit.

**No API key ever appears in `web/` or is sent from the browser.** The AI/9arm key stays
server-side (Tracks C/D).

## Live server mode

The board now includes a `RealApiAdapter` for the local server boundary. Start both processes:

```bash
# terminal 1 — API (server-side AI key only)
cd /home/jornjud/projects/family-telegram-bot
PYTHONPATH=src ./.venv/bin/python -m api_server

# terminal 2 — web shell
cd /home/jornjud/projects/family-telegram-bot/web
python3 -m http.server 8080
```

Open:

```text
http://127.0.0.1:8080/?mode=live&api=http://127.0.0.1:8787&group=family
```

The browser never receives `NINEARM_API_KEY`. The live UI follows preview → confirmation → commit;
protect the API with `FAMILY_BOARD_API_TOKEN` and an authenticated private network before deployment.


## PWA notes

- `manifest.webmanifest` + generated icons enable "Add to Home Screen".
- `sw.js` caches the static shell for offline viewing. It only handles same-origin static GETs it
  explicitly lists — it never proxies AI/API requests, so it can't leak credentials.

## Files

```
web/
  index.html            dashboard markup (Thai-first)
  css/styles.css        mobile/tablet-first styling (no framework)
  js/app.js             UI rendering + capture flow
  js/api.js             data boundary (MockApiAdapter → swap for real adapter)
  manifest.webmanifest  PWA manifest
  sw.js                 offline service worker (static shell only)
  icons/                app icons (192/512)
  README.md             this file
```

## Project constraints honored

- No Python files touched (`src/`, `tests/`, `family_memory.sqlite3` untouched).
- No `.env` or credentials read or written.
- Nothing committed — this is an uncommitted working change.
