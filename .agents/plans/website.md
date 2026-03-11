# Plan: Agent OS Command Center — Web Demo

## Config
working_dir: /Users/paulaan/PycharmProjects/agent-os

## Task: TASK-001 — FastAPI backend with SSE war-room API

Build `demo/api.py` — a FastAPI server that:
- `GET /` — serves `demo/index.html`
- `GET /api/rooms` — scans `.agents/war-rooms/room-*/` and returns JSON list with status, task_ref, message_count, retries, last_activity
- `GET /api/rooms/{room_id}/channel` — reads `channel.jsonl` and returns parsed messages
- `GET /api/events` — SSE stream that polls all war-room channel files every 1s and emits changes
- `GET /api/release` — returns content of `.agents/RELEASE.md` if it exists
- `GET /api/config` — returns `.agents/config.json`
- `POST /api/run` — accepts `{"plan": "...plan content..."}`, writes to temp file, spawns `.agents/run.sh` in background subprocess
- Mount `demo/assets/` as static files at `/assets/`

Acceptance criteria:
- Server starts with `python demo/api.py` on port 8000
- `/api/rooms` returns correct data when war-rooms exist
- SSE endpoint streams updates when channel files change
- CORS enabled for local development

## Task: TASK-002 — HTML + dark cyber CSS theme

Build `demo/index.html` (full SPA, not just shell — all content inline) and `demo/assets/main.css`:

Layout (3-column):
- **Top bar**: ASCII logo "⬡ AGENT OS", global status badge (rooms active/total), version
- **Left panel** (25%): Plan Launcher — monospace textarea with example plan, `[▶ LAUNCH]` button
- **Center panel** (50%): War-Room Grid — cards in CSS grid, each showing room ID, task ref, status chip, retry count, message count
- **Right panel** (25%): Channel Feed — scrolling log of latest messages color-coded by type
- **Bottom bar**: Release Notes — shows RELEASE.md content when ready, glows green

Colors:
- Background: `#0a0a0f` (near black)
- Surface: `#111118` (cards)
- Border: `#1a1a2e` (subtle)
- Cyan: `#00d4ff` (engineering, messages)
- Green: `#00ff88` (passed, success)
- Amber: `#ffd93d` (qa-review)
- Orange: `#ff9f43` (fixing)
- Red: `#ff6b6b` (failed)
- Text: `#e0e0ff` (primary), `#888` (muted)
- Font: `'JetBrains Mono', 'Fira Code', monospace`

Acceptance criteria:
- Opens in browser without a server (links to localhost API)
- War-room grid looks great with 0 and 10+ rooms
- Status chips are visually distinct per status
- Channel feed is readable and scrolls automatically

## Task: TASK-003 — Real-time JavaScript SSE client

Build `demo/assets/app.js`:
- On load: fetch `/api/rooms`, render initial war-room cards
- `EventSource('/api/events')` — on message, update the matching room card OR add new one
- Room card update: change status chip color, increment message count, animate transition
- Channel feed: append new messages at bottom, auto-scroll, max 200 messages shown
- Fetch `/api/release` every 3s, show bottom bar when available
- Plan Launcher: on [LAUNCH] click, POST textarea content to `/api/run`, show spinner, then start polling for new rooms
- Reconnect SSE on disconnect with exponential backoff

Message type colors in feed:
- `task` → cyan
- `done` → green
- `review` → blue
- `pass` → bright green + ✓
- `fail` → red + ✗
- `fix` → orange
- `signoff` → purple
- `error` → red + ⚠

Acceptance criteria:
- War-room cards update without page refresh
- Channel feed scrolls and shows messages in real-time
- Plan launcher works end-to-end (POST → war-rooms appear)
- No console errors on load

## Task: TASK-004 — Animations, polish, and integration

Polish `demo/index.html`, `demo/assets/main.css`, `demo/assets/app.js`:

Animations:
- War-room cards: `@keyframes slideUp` when appearing (0.3s ease-out from translateY(20px))
- Status chip: `@keyframes pulse` for `engineering` and `qa-review` statuses (infinite)
- Status chip: `@keyframes glow` for `passed` (green glow)
- Channel message: `@keyframes fadeIn` (0.2s)
- Release bar: `@keyframes celebrate` — green glow pulsing when release detected

Pipeline visualization:
- Between left panel and grid: animated SVG arrows showing ENG → QA → MGR flow
- Arrows animate with moving dashes while rooms are active

Summary stats row (above grid):
- "Active: N | Engineering: N | QA Review: N | Passed: N/Total | Failed: N"

Mobile responsive:
- Stack 3 columns to single column below 768px
- Channel feed becomes bottom sheet on mobile

`demo/requirements.txt`:
```
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
```

Acceptance criteria:
- All animations are smooth (60fps)
- No jank on card updates
- Mobile layout is usable
- Server + browser demo is completely self-contained
