# Family Telegram Bot

Pilot Telegram family assistant for one shared group (4–5 members).

## Safety

Do not commit `.env`. Use a newly rotated 9arm API key; the previously pasted key must be revoked.

## Models

- Primary: `deepseek-v4-flash-0731`
- Fallback: `qwen3.8-27b-fp8`
- Embeddings: configured only after the authenticated gateway model list confirms an embedding model. No local embeddings.

## Current status

Local Family Board MVP is implemented and verified:

- `web/` contains the Thai-first PWA dashboard.
- `src/api_server.py` provides the server-side board and capture API.
- `src/board_service.py` is the shared write/read domain boundary.
- Telegram capture uses preview → explicit ใช่/ไม่ confirmation before writing;
  shopping captures are stored with `kind=shopping`.
- SQLite is the local persistence adapter; production Firestore migration is intentionally separate.
- `pytest -q` is the required verification command.

## Render deployment

Render is the selected target because its paid web service supports a persistent disk, which keeps
the existing SQLite database at `/var/data/family_memory.sqlite3` across deploys. `Dockerfile` and
`render.yaml` are ready for a Render Blueprint. The service listens on Render's `PORT` and exposes
`GET /api/healthz` for health checks.

Required Render setup:

1. Create a Blueprint from this repository and select the `family-board-api` service.
2. Set secret `NINEARM_API_KEY` and a long random `FAMILY_BOARD_API_TOKEN` in the Render dashboard.
3. Set `FAMILY_BOARD_ALLOWED_ORIGIN` to the exact HTTPS origin of the hosted `web/` PWA.
4. Verify `https://<render-service>.onrender.com/api/healthz` returns `{"status":"ok"}`.

The Vercel proxy in `api/family-board.js` is the authenticated frontend: it only forwards health,
board, preview, and commit operations and adds `FAMILY_BOARD_API_TOKEN` server-side. Set these
Vercel environment variables: `RENDER_API_URL` and `FAMILY_BOARD_API_TOKEN`. The browser never
receives the token.

Vercel deployment:

1. Import the repository into Vercel.
2. Set `RENDER_API_URL` to the Render service URL and `FAMILY_BOARD_API_TOKEN` to the same token
   configured on Render.
3. Set Render's `FAMILY_BOARD_ALLOWED_ORIGIN` to the Vercel site's exact HTTPS origin.

## Run locally

Terminal 1 — API:

```bash
cd /home/jornjud/projects/family-telegram-bot
PYTHONPATH=src .venv/bin/python -m api_server
```

Terminal 2 — PWA shell:

```bash
cd /home/jornjud/projects/family-telegram-bot/web
python3 -m http.server 8080
```

Open mock mode at `http://127.0.0.1:8080/`, or local live server mode at:
`http://127.0.0.1:8080/?mode=live&api=http://127.0.0.1:8787&group=family`.
The explicit `api=` URL is required for local direct-server development; deployed live mode uses
the same-origin Vercel proxy without an `api=` parameter.
