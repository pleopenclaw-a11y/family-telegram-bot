# Family Board Refactor Implementation Plan

> **For Hermes:** Execute task-by-task with independent workers, then integrate and verify.

**Goal:** Evolve the existing Telegram-only family memory bot into a small Family Operating System: a shared PWA board backed by a structured API/data layer, with Telegram and AI as input/automation channels.

**Current baseline:** Python Telegram bot; SQLite `memories` table; 9arm-compatible AI client; no web board.

**Target MVP:** Board dashboard, notes, events, tasks, shopping list, daily summary, Telegram capture, confirmation-safe structured actions, server-side API key handling.

**Constraints:** Preserve existing bot behavior while migrating incrementally; do not delete the SQLite database; do not expose credentials; Firestore is the intended production backend, but local development must run without cloud credentials.

## Work split

### Track A — Domain and storage
- Define typed domain entities and migration boundary from `memories` to notes/events/tasks/shopping.
- Add a repository/service layer with SQLite local adapter first.
- Preserve legacy search/delete compatibility.

### Track B — Family Board UI
- Create a separate `web/` PWA surface with dashboard cards for today, events, tasks, notes, and shopping.
- Use mock/local API adapter initially; no secret keys in browser.
- Thai-first labels, mobile/tablet-first layout, simple family-friendly controls.

### Track C — API and AI actions
- Add a server-side API boundary for board reads/writes and AI capture.
- Define confirmation-safe action protocol: preview → confirm → commit.
- Keep 9arm key server-side and add request validation/error handling.

### Track D — Telegram integration
- Adapt Telegram commands to call the domain/API service rather than writing raw memories.
- Add structured capture commands and board link/daily summary hooks.
- Keep existing `/today`, `/week`, `/expenses`, `/search`, `/delete` behavior during migration.

### Track E — Verification and deployment
- Add tests for domain behavior, API contract, confirmation flow, and UI smoke checks.
- Document local run and production deployment path (Vercel + Firebase/Firestore transition).

## Acceptance criteria for MVP

- A family member can view a single dashboard containing today’s events, open tasks, notes, and shopping items.
- A Telegram message can create a structured draft without committing ambiguous data automatically.
- Confirmed actions are persisted through one domain service, not duplicated in Telegram/UI code.
- No AI/API credential appears in `web/` or browser-delivered bundles.
- Existing family-memory tests remain green.
- Local development works with SQLite and no production credentials.

## Execution order

1. Tracks A and C establish contracts and local service boundary.
2. Track B builds against the contract using a local adapter.
3. Track D migrates Telegram handlers.
4. Track E runs full verification and prepares deployment notes.

## Safety

- No destructive delete/reset/force-push.
- No production deployment until explicit authorization.
- Existing `.env` and SQLite data remain untouched.
