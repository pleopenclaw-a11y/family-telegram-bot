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

The public deployment is the static PWA only. The Python API must run on a trusted server or
authenticated private network; it is not deployed as a public unauthenticated endpoint. Production
backend deployment remains blocked because no authorized host or authenticated proxy is configured;
set `FAMILY_BOARD_API_TOKEN` and `FAMILY_BOARD_ALLOWED_ORIGIN` before exposing the API.

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

Open mock mode at `http://127.0.0.1:8080/`, or live server mode at:
`http://127.0.0.1:8080/?mode=live&api=http://127.0.0.1:8787&group=family`.
