# OS Twin — Security Advisory Report
**Phase 1 Intelligence Gathering**
**Date:** 2026-03-30
**Auditor:** Advisory Hunter (Phase 1)

---

## Architecture Inventory

### System Overview

OS Twin is a multi-component AI-driven software project management platform ("multi-agent war-room orchestrator"). It consists of four distinct sub-systems:

| Component | Runtime | Entrypoint | Role |
|-----------|---------|-----------|------|
| **FastAPI Backend** | Python 3.x + uvicorn | `dashboard/api.py` | REST API, WebSocket, auth, plan/epic management |
| **Next.js Frontend** | Node.js + React 19 | `dashboard/fe/` | Dashboard UI, proxies `/api/*` to FastAPI |
| **Express Server** | Node.js (ESM) | `server.js` (root) | Legacy/test Node server (semester-planner) |
| **Discord Bot** | Node.js (CJS) | `discord-bot/src/index.js` | Discord slash commands, Gemini AI bridge |

### Component Details

#### FastAPI Backend (`dashboard/`)
- **Framework:** FastAPI >= 0.100.0 (installed: 0.135.1)
- **ASGI Server:** uvicorn[standard] >= 0.23.0 (installed: 0.38.0)
- **Routes:** auth, plans, rooms, epics, roles, skills, memory, mcp, engagement, system
- **Auth model:** Single shared `OSTWIN_API_KEY` from env; accepted via `X-API-Key` header, `Authorization: Bearer`, or `ostwin_auth_key` cookie. DEBUG bypass mode when key equals string "DEBUG".
- **WebSocket:** `ws_router.py` with `global_state.broadcaster`
- **Vector search:** `zvec_store.py` using `zvec` + `sentence-transformers`
- **MCP servers:** channel, warroom, memory (stdio), stitch (http), github (stdio)
- **External AI:** Gemini API via `@google/generative-ai` (Discord bot)
- **Database:** PostgreSQL via `pg` (Node, root package); Python side uses file-based state

#### Next.js Frontend (`dashboard/fe/`)
- **Framework:** Next.js 16.2.1 (pinned exact version)
- **React:** 19.2.4
- **Build mode:** Static export (`output: 'export'`) for production; dev mode proxies `/api/*` to `http://localhost:9000`
- **NEXT_PUBLIC_API_BASE_URL:** Configurable backend URL (defaults to `http://localhost:9000`)
- **Auth:** Cookie-based (`ostwin_auth_key`) + API-key stored client-side
- **State:** Zustand + SWR + TanStack Query
- **UI:** Tailwind CSS v4, Framer Motion, dnd-kit, Recharts

#### Express Server (root `package.json`)
- **Framework:** Express 5.2.1
- **Database:** PostgreSQL via `pg` 8.20.0
- **Test infra:** Cypress 15.12.0, Mocha 11.7.5, Supertest 7.2.2, c8, nyc
- **Override pins:** `serialize-javascript@7.0.4`, `diff@8.0.3`

#### Discord Bot (`discord-bot/`)
- **Framework:** discord.js 14.25.1
- **Voice:** @discordjs/voice 0.19.2 + @discordjs/opus 0.10.0
- **AI bridge:** @google/generative-ai 0.24.1 (Gemini 2.0 Flash)
- **Pattern:** Bot receives slash commands, queries FastAPI backend (`DASHBOARD_URL`), builds context, sends to Gemini, returns response to Discord channel

### Transports and Interfaces

| Transport | Source → Destination | Notes |
|-----------|---------------------|-------|
| HTTP REST | Internet → FastAPI (port 9000) | Auth-gated; all public API |
| HTTP proxy | Next.js dev server → FastAPI | Rewrites `/api/*` in dev mode |
| WebSocket | Browser/bot → FastAPI ws_router | Real-time updates |
| Discord Gateway | Discord → discord.js | Bot events, slash commands |
| MCP stdio | FastAPI ↔ local agent processes | channel, warroom, memory, github |
| MCP HTTP | FastAPI ↔ stitch MCP server | External HTTP MCP |
| Gemini API | Discord Bot → Google API | Outbound HTTPS |
| PostgreSQL | Express/FastAPI → Postgres | Local DB |
| Semantic search | Internal → sentence-transformers | Local model inference |

### Trust Boundaries

| Boundary | Description |
|----------|-------------|
| **Internet-facing** | FastAPI API (port 9000), Next.js dev server (port 3000), Discord gateway |
| **Internal-only** | MCP stdio servers, WebSocket broadcaster, local Postgres |
| **Discord user → Bot** | Untrusted input: Discord message content routed to Gemini + backend APIs |
| **Bot → Backend** | API key authenticated; `DASHBOARD_URL` env-controlled |
| **Frontend → Backend** | Cookie/key auth; Next.js rewrites in dev mode (no rewrite in prod static export) |
| **Debug bypass** | `OSTWIN_API_KEY=DEBUG` disables all auth |

### Execution Environments

- Python 3.x process (FastAPI/uvicorn) — no sandbox
- Node.js ESM process (Express/Cypress) — no sandbox
- Node.js CJS process (Discord bot) — no sandbox
- Next.js static export (production) served by FastAPI's `StaticFiles`
- Next.js dev server with hot-reload and `/api` proxy

### Highest-Risk Flows

1. **Discord user → Gemini prompt injection**: User controls `question` string embedded verbatim into Gemini system prompt context. Prompt injection possible.
2. **Next.js `/api` proxy → FastAPI**: Dev-mode proxy rewrites all `/api/*` to backend; misconfiguration of `NEXT_PUBLIC_API_BASE_URL` could cause SSRF.
3. **FastAPI auth DEBUG mode**: `OSTWIN_API_KEY=DEBUG` completely bypasses all authentication.
4. **MCP HTTP server (stitch)**: Outbound HTTP MCP transport — potential SSRF if attacker controls MCP server URL.
5. **`semanticSearch(query)` → `/api/search?q=`**: User query directly URL-encoded into search endpoint without additional sanitization visible in `agent-bridge.js`.

---

## Dependency Intelligence

### Node.js — Root Package (Express server + Cypress tests)

| Package | Version | Role | Notes |
|---------|---------|------|-------|
| express | 5.2.1 | HTTP server framework | Patched; all historic vulns pre-5.0.0 |
| pg | 8.20.0 | PostgreSQL client | Patched; historic CRITICAL RCE in <2.11.2 |
| cypress | 15.12.0 | E2E testing | No public CVEs for current version |
| mocha | 11.7.5 | Unit test runner | No public CVEs |
| chai | 6.2.2 | Assertion library | No public CVEs |
| supertest | 7.2.2 | HTTP testing | No public CVEs |
| tailwindcss | 4.2.1 | CSS framework | No public CVEs |
| postcss | 8.5.8 | CSS processing | All known CVEs patched (>8.4.31) |
| c8 | 11.0.0 | Code coverage | No public CVEs |
| nyc | 18.0.0 | Code coverage | No public CVEs |
| **serialize-javascript** | **7.0.4** (override) | JS serialization (Cypress dep) | **VULNERABLE: CVE-2026-34043, fixed 7.0.5** |
| diff | 8.0.3 (override) | Diff utility (Cypress dep) | Patched; CVE-2026-24001 fixed at 8.0.3 |

### Node.js — Frontend (`dashboard/fe/`)

| Package | Version | Role | Notes |
|---------|---------|------|-------|
| next | 16.2.1 (pinned) | React framework + SSR | All known 16.x CVEs patched (>16.1.7) |
| react | 19.2.4 | UI library | No public CVEs for this version |
| react-dom | 19.2.4 | DOM rendering | No public CVEs |
| @tanstack/react-query | ~5.95.2 | Data fetching | No public CVEs |
| swr | ~2.4.1 | Data fetching | No public CVEs |
| zustand | ~5.0.12 | State management | No public CVEs |
| framer-motion | ~12.38.0 | Animation | No public CVEs |
| recharts | ~3.8.0 | Charts | No public CVEs |
| @dnd-kit/core | ~6.3.1 | Drag-and-drop | No public CVEs |
| tailwindcss | ^4 | CSS framework | No public CVEs |

### Node.js — Discord Bot (`discord-bot/`)

| Package | Version | Role | Notes |
|---------|---------|------|-------|
| discord.js | 14.25.1 | Discord API client | No public CVEs in OSV for current version |
| @discordjs/voice | 0.19.2 | Voice channel handling | No public CVEs |
| @discordjs/opus | 0.10.0 | Audio codec | No public CVEs |
| @google/generative-ai | 0.24.1 | Gemini AI client | No public CVEs |
| dotenv | 17.3.1 | Env file loader | No public CVEs |
| libsodium-wrappers | 0.8.2 | Crypto/NaCl bindings | No public CVEs |
| opusscript | 0.1.1 | Opus codec fallback | No public CVEs |
| prism-media | 1.3.5 | Media transcoding | No public CVEs |
| sinon | 21.0.3 | Test mocking | No public CVEs |

### Python — FastAPI Backend (`dashboard/requirements.txt`)

| Package | Spec | Installed | Role | Notes |
|---------|------|-----------|------|-------|
| fastapi | >=0.100.0 | 0.135.1 | REST + WebSocket framework | All known CVEs patched (>0.65.2) |
| uvicorn[standard] | >=0.23.0 | 0.38.0 | ASGI server | All known CVEs patched (>0.23.0) |
| websockets | >=11.0 | 15.0.1 | WebSocket library | All known CVEs patched (>9.1) |
| sentence-transformers | ==5.2.3 | (pinned) | Semantic vector search | No public CVEs |
| python-dotenv | >=1.0.0 | installed | Env loading | No public CVEs |
| httpx | (unpinned) | 0.28.1 | HTTP client | CRITICAL fixed at 0.23.0; installed version patched |
| mcp[cli] | >=1.1.3 | 1.26.0 | MCP server/client | All known CVEs patched (>1.23.0) |
| zvec | >=0.2.0 | installed | Vector store | No public CVEs |
| deepagents | >=0.4.0 | installed | Agent framework | No public CVEs |

### Security-Relevant Dependency Pattern Cross-References

- **DoS via serialization** (serialize-javascript 7.0.4 VULNERABLE): This is a transitive dependency pulled in by Cypress. It is only exercised in the test/CI pipeline, not in the production server. Risk is limited to CI environments but the override pin is one version behind the fix.
- **SSRF via Next.js proxy**: `BACKEND_URL` in `next.config.ts` controls destination of all `/api/*` rewrites. If this env var is attacker-controlled (e.g., via CI injection), it constitutes an SSRF amplification surface. GHSA-4342-x723-ch2f (Next.js SSRF in middleware rewrites) was patched in 14.2.32/15.4.7 — `next@16.2.1` is not in the affected range.
- **Auth bypass concern**: The `OSTWIN_API_KEY=DEBUG` bypass in `dashboard/auth.py` is a structural risk not covered by any CVE; it bypasses all endpoint authentication entirely.
- **Prompt injection surface**: `@google/generative-ai` processes user-controlled Discord message content directly. No sanitization layer observed in `agent-bridge.js`.

---

## Known Advisories (CVE/GHSA/OSV)

**Historical coverage metadata:**
- Tier reached: 1 (2yr) with supplementary all-time coverage for key packages
- Total advisories collected: 58 unique (Next.js: 41, Python backends: 14, JS deps: 14, overlap removed)
- Severity distribution — CRITICAL: 2, HIGH: 18, MODERATE: 22, LOW: 9

### Active Vulnerabilities (Confirmed Unpatched)

| ID | CVE | Severity | CVSS | Package | Affected | Fixed | Component | Description |
|----|-----|----------|------|---------|----------|-------|-----------|-------------|
| GHSA-qj8w-gfj5-8c6v | CVE-2026-34043 | MODERATE | — | serialize-javascript | <7.0.5 | 7.0.5 | Root/Cypress devDep | CPU exhaustion DoS via crafted array-like objects; **installed: 7.0.4** |

### Next.js Advisories (next@16.2.1 — all patched)

| ID | CVE | Severity | Fixed Version | CWE | Description |
|----|-----|----------|--------------|-----|-------------|
| GHSA-f82v-jwr5-mffw | CVE-2025-29927 | CRITICAL | 13.5.9 / 14.2.25 | CWE-284 | Authorization bypass in Next.js Middleware via `x-middleware-subrequest` header |
| GHSA-9qr9-h5gf-34mp | — | CRITICAL | 15.0.5 / 15.1.9 | CWE-94 | RCE in React flight protocol (Server Components) |
| GHSA-77r5-gw3j-2mpf | CVE-2024-34350 | HIGH | 13.5.1 | CWE-444 | HTTP Request Smuggling |
| GHSA-7gfc-8cq8-jh5f | CVE-2024-51479 | HIGH | 14.2.15 | CWE-287 | Authorization bypass vulnerability |
| GHSA-5j59-xgg2-r9c4 | — | HIGH | 14.2.35 / 15.0.7 | CWE-400 | DoS with Server Components (incomplete fix) |
| GHSA-fr5h-rqp8-mj6g | CVE-2024-34351 | HIGH | 14.1.1 | CWE-918 | SSRF in Server Actions |
| GHSA-gp8f-8m3g-qvj9 | CVE-2024-46982 | HIGH | 13.5.7 / 14.2.10 | CWE-444 | Cache poisoning |
| GHSA-fq54-2j52-jc42 | CVE-2024-39693 | HIGH | 13.5.0 | CWE-400 | DoS condition |
| GHSA-mwv6-3258-q52c | — | HIGH | 14.2.34 / 15.0.6 | CWE-400 | DoS with Server Components |
| GHSA-h25m-26qc-wcjf | — | HIGH | 15.0.8 / 15.1.12 | CWE-502 | DoS via insecure React deserialization |
| GHSA-67rr-84xm-4c7r | CVE-2025-49826 | HIGH | 15.1.8 | CWE-400 | DoS via cache poisoning |
| GHSA-25mp-g6fv-mqxx | CVE-2021-43803 | HIGH | 11.1.3 / 12.0.5 | CWE-400 | Unexpected server crash |
| GHSA-9gr3-7897-pp7m | CVE-2021-39178 | HIGH | 11.1.1 | CWE-79 | XSS in Image Optimization API |
| GHSA-3f5c-4qxj-vmpf | CVE-2017-16877 | HIGH | 2.4.1 | CWE-22 | Directory Traversal |
| GHSA-m34x-wgrh-g897 | CVE-2018-6184 | HIGH | 4.2.3 | CWE-22 | Directory Traversal |
| GHSA-5vj8-3v2h-h38v | — | HIGH | 5.1.0 | CWE-94 | Remote Code Execution |
| GHSA-4342-x723-ch2f | CVE-2025-57822 | MODERATE | 14.2.32 / 15.4.7 | CWE-918 | SSRF via improper middleware redirect |
| GHSA-3x4c-7xq6-9pq8 | CVE-2026-27980 | MODERATE | 15.5.14 / 16.1.7 | CWE-400 | Unbounded disk cache growth (image) |
| GHSA-5f7q-jpqc-wp7h | CVE-2025-59472 | MODERATE | 16.1.5 | CWE-400 | Unbounded memory via PPR Resume endpoint |
| GHSA-9g9p-9gw9-jx7f | CVE-2025-59471 | MODERATE | 15.5.10 / 16.1.5 | CWE-400 | DoS via Image Optimizer remotePath |
| GHSA-ggv3-7p47-pfv8 | CVE-2026-29057 | MODERATE | 15.5.13 / 16.1.7 | CWE-444 | HTTP request smuggling in rewrites |
| GHSA-h27x-g6w4-24gq | CVE-2026-27979 | MODERATE | 16.1.7 | CWE-400 | Unbounded postponed resume buffering DoS |
| GHSA-mq59-m269-xvcx | CVE-2026-27978 | MODERATE | 16.1.7 | CWE-352 | null origin bypasses Server Actions CSRF |
| GHSA-jcc7-9wpm-mj36 | CVE-2026-27977 | LOW | 16.1.7 | CWE-352 | null origin bypasses dev HMR WebSocket CSRF |
| GHSA-g5qg-72qw-gw5v | CVE-2025-57752 | MODERATE | 14.2.31 / 15.4.5 | CWE-444 | Cache key confusion for Image Optimization |
| GHSA-xv57-4mr9-wg8v | CVE-2025-55173 | MODERATE | 14.2.31 / 15.4.5 | CWE-74 | Content injection via Image Optimization |
| GHSA-7m27-7ghc-44w9 | CVE-2024-56332 | MODERATE | 13.5.8 / 14.2.21 | CWE-400 | DoS via Server Actions |
| GHSA-g77x-44xx-532m | CVE-2024-47831 | MODERATE | 14.2.7 | CWE-400 | DoS in image optimization |
| GHSA-3h52-269p-cp9r | CVE-2025-48068 | LOW | 14.2.30 / 15.2.2 | CWE-200 | Info exposure in dev server (origin verification) |
| GHSA-223j-4rm8-mrmf | CVE-2025-30218 | LOW | 12.3.6 / 13.5.10 | CWE-200 | x-middleware-subrequest-id leaks to external hosts |
| GHSA-qpjv-v59x-3qc4 | CVE-2025-32421 | LOW | 14.2.24 / 15.1.6 | CWE-362 | Race condition → cache poisoning |
| GHSA-r2fc-ccr8-96c4 | CVE-2025-49005 | LOW | 15.3.3 | CWE-346 | Cache poisoning via missing Vary header |
| GHSA-w37m-7fhw-fmv9 | — | MODERATE | 15.0.6 / 15.1.10 | CWE-200 | Server Actions source code exposure |
| GHSA-c59h-r6p8-q9wc | CVE-2023-46298 | LOW | 13.4.20-canary.13 | CWE-400 | Missing cache-control may cause CDN empty-reply DoS |
| GHSA-fmvm-x8mv-47mj | CVE-2022-23646 | MODERATE | 12.1.0 | CWE-358 | Improper CSP in Image Optimization |
| GHSA-wff4-fpwg-qqv3 | CVE-2022-36046 | MODERATE | 12.2.4 | CWE-400 | Server crash |
| GHSA-wr66-vrwm-5g5x | CVE-2022-21721 | MODERATE | 12.0.9 | CWE-400 | DoS vulnerability |
| GHSA-vxf5-wxwp-m7g9 | CVE-2021-37699 | MODERATE | 11.1.0 | CWE-601 | Open Redirect |
| GHSA-fq77-7p7r-83rj | CVE-2020-5284 | MODERATE | 9.3.2 | CWE-22 | Directory Traversal |
| GHSA-x56p-c8cg-q435 | CVE-2020-15242 | MODERATE | 9.5.4 | CWE-601 | Open Redirect |
| GHSA-qw96-mm2g-c8m7 | CVE-2018-18282 | MODERATE | 7.0.2 | CWE-79 | XSS via 404/500 error page |

### Express Advisories (express@5.2.1 — all patched)

| ID | CVE | Severity | Fixed | Description |
|----|-----|----------|-------|-------------|
| GHSA-qw6h-vgh9-j6wx | CVE-2024-43796 | LOW | 4.20.0 / 5.0.0 | XSS via response.redirect() |
| GHSA-rv95-896h-c2vc | CVE-2024-29041 | MODERATE | 4.19.2 / 5.0.0-beta.3 | Open Redirect in malformed URLs |
| GHSA-cm5g-3pgc-8rg4 | CVE-2024-10491 | MODERATE | 4.0.0-rc1 (3.x only) | Resource injection in Express 3.x |
| GHSA-jj78-5fmv-mv28 | CVE-2024-9266 | LOW | 4.0.0-rc1 (3.x only) | Open Redirect in Express 3.x |
| GHSA-gpvr-g6gh-9mc2 | CVE-2014-6393 | MODERATE | 3.11.0 / 4.5.0 | No charset in Content-Type |

### serialize-javascript Advisories (installed: 7.0.4)

| ID | CVE | Severity | Fixed | Status | Description |
|----|-----|----------|-------|--------|-------------|
| **GHSA-qj8w-gfj5-8c6v** | **CVE-2026-34043** | **MODERATE** | **7.0.5** | **UNPATCHED** | CPU exhaustion DoS via crafted array-like objects |
| GHSA-76p7-773f-r4q5 | CVE-2024-11831 | MODERATE | 6.0.2 | Patched (7.0.4>6.0.2) | XSS in serialized output |
| GHSA-5c6j-r48x-rmvq | — | HIGH | 7.0.3 | Patched (7.0.4>7.0.3) | RCE via RegExp.flags and Date.prototype |
| GHSA-hxcc-f52p-wc94 | CVE-2020-7660 | HIGH | 3.1.0 | Patched | Insecure serialization → RCE |
| GHSA-h9rv-jmmf-4pgx | CVE-2019-16769 | MODERATE | 2.1.1 | Patched | XSS |

### diff Advisories (installed: 8.0.3 — patched)

| ID | CVE | Severity | Fixed | Status | Description |
|----|-----|----------|-------|--------|-------------|
| GHSA-73rr-hh4g-fpgx | CVE-2026-24001 | LOW | 8.0.3 | Patched (boundary) | DoS via parsePatch/applyPatch |
| GHSA-h6ch-v84p-w6p9 | — | HIGH | 3.5.0 | Patched | ReDoS |

### pg Advisories (pg@8.20.0 — patched)

| ID | CVE | Severity | Fixed | Status | Description |
|----|-----|----------|-------|--------|-------------|
| GHSA-wc9v-mj63-m9g5 | CVE-2017-16082 | CRITICAL | 2.11.2 / 3.6.4 | Patched (8.20.0 >> fix) | Remote Code Execution |

### postcss Advisories (postcss@8.5.8 — patched)

| ID | CVE | Severity | Fixed | Status | Description |
|----|-----|----------|-------|--------|-------------|
| GHSA-7fh5-64p2-3v2j | CVE-2023-44270 | MODERATE | 8.4.31 | Patched | Line return parsing error |
| GHSA-566m-qj78-rww5 | CVE-2021-23382 | MODERATE | 8.2.13 | Patched | ReDoS |
| GHSA-hwj9-h5mp-3pm3 | CVE-2021-23368 | MODERATE | 8.2.10 | Patched | ReDoS |

### Python Backend Advisories (all patched at installed versions)

| ID | CVE | Severity | Fixed | Package | Status | Description |
|----|-----|----------|-------|---------|--------|-------------|
| GHSA-h8pj-cxx2-jfg2 | CVE-2021-41945 | CRITICAL | 0.23.0 | httpx | Patched (0.28.1) | Improper input validation |
| GHSA-8h2j-cgx8-6xv7 | CVE-2021-32677 | HIGH | 0.65.2 | fastapi | Patched (0.135.1) | CSRF vulnerability |
| GHSA-9h52-p55h-vw2f | CVE-2025-66416 | HIGH | 1.23.0 | mcp | Patched (1.26.0) | DNS rebinding protection missing |
| GHSA-3qhf-m339-9g5v | CVE-2025-53366 | HIGH | 1.9.4 | mcp | Patched (1.26.0) | FastMCP Server validation error → DoS |
| GHSA-j975-95f5-7wqh | CVE-2025-53365 | HIGH | 1.10.0 | mcp | Patched (1.26.0) | Streamable HTTP unhandled exception → DoS |
| GHSA-33c7-2mpw-hg34 | CVE-2020-7694 | HIGH | 0.11.7 | uvicorn | Patched (0.38.0) | Log injection |
| GHSA-f97h-2pfx-f59f | CVE-2020-7695 | HIGH | 0.11.7 | uvicorn | Patched (0.38.0) | HTTP response splitting |
| GHSA-6g87-ff9q-v847 | CVE-2018-1000518 | HIGH | 5.0 | websockets | Patched (15.0.1) | DoS memory exhaustion |
| GHSA-8ch4-58qp-g3mp | CVE-2021-33880 | HIGH | 9.1 | websockets | Patched (15.0.1) | Observable timing discrepancy |

---

## Vulnerability Pattern Analysis

### 2a. Component Vulnerability Heatmap

| Component | Advisory Count | Severities | Dominant Bug Types |
|-----------|---------------|-----------|-------------------|
| **Next.js** | 41 | CRITICAL:2, HIGH:13, MOD:20, LOW:6 | DoS, Cache Poisoning, Auth Bypass, SSRF, XSS, Path Traversal |
| serialize-javascript | 5 | HIGH:2, MOD:3 | RCE, XSS, DoS |
| Python MCP (mcp lib) | 3 | HIGH:3 | DNS rebinding, DoS, validation bypass |
| Express | 5 | MOD:3, LOW:2 | Open Redirect, XSS, Resource Injection |
| FastAPI | 1 | HIGH:1 | CSRF |
| uvicorn | 2 | HIGH:2 | Log injection, HTTP response splitting |
| websockets | 2 | HIGH:2 | DoS, Timing oracle |
| httpx | 1 | CRITICAL:1 | Input validation |
| pg | 1 | CRITICAL:1 | RCE (ancient, patched) |
| postcss | 3 | MOD:3 | ReDoS, Parse error |
| diff | 2 | HIGH:1, LOW:1 | ReDoS, DoS |

**High-heat components (3+ advisories or CRITICAL):**
- Next.js (41 advisories, 2 CRITICAL) — highest priority for Phase 3 DFD
- serialize-javascript (5 advisories, 1 currently unpatched) — Phase 5 probe target
- mcp library (3 HIGH) — DNS rebinding + DoS patterns, MCP server attack surface

### 2b. Bug Type Recurrence

| Bug Class | CWEs | Count | Examples |
|-----------|------|-------|---------|
| DoS / resource exhaustion | CWE-400, CWE-770 | 17 | Next.js server crash, image DoS, PPR buffer, Server Components, MCP unhandled exception, websockets memory, diff ReDoS |
| Cache poisoning / HTTP smuggling | CWE-444, CWE-346 | 7 | Next.js cache poisoning, HTTP smuggling in rewrites, image optimization cache key confusion |
| Auth bypass / broken auth | CWE-284, CWE-287, CWE-352 | 5 | Next.js middleware auth bypass (CRITICAL), authorization bypass, CSRF null origin, Server Actions CSRF |
| Open Redirect | CWE-601 | 4 | Express redirect, Next.js redirects (multiple versions) |
| XSS | CWE-79, CWE-74 | 4 | serialize-javascript XSS, Next.js image optimization XSS, error page XSS, content injection |
| Path traversal | CWE-22 | 3 | Next.js directory traversal (3 separate instances across major versions) |
| SSRF | CWE-918 | 2 | Next.js SSRF in Server Actions, SSRF in middleware redirect |
| RCE | CWE-94 | 2 | Next.js React flight RCE, serialize-javascript RCE |
| Info disclosure | CWE-200 | 2 | Next.js dev server, middleware subrequest-id leak |
| Injection / log injection | CWE-117, CWE-89 | 2 | uvicorn log injection, HTTP response splitting |
| Deserialization | CWE-502 | 1 | Next.js React deserialization DoS |
| ReDoS | CWE-1333 | 3 | postcss, diff, serialize-javascript |
| Cryptographic weakness | CWE-326, CWE-330 | 1 | websockets timing oracle |

**Recurring bug types (2+ advisories):**
- DoS/resource exhaustion (17 occurrences) — highest frequency, covers multiple components
- Cache poisoning (7) — structural pattern in Next.js image and routing layers
- Auth/CSRF bypass (5) — recurring across middleware, Server Actions, HMR WebSocket
- Open Redirect (4) — express and Next.js

### 2c. Attack Surface Trends

| Input Vector | Frequency | Key Examples |
|-------------|-----------|-------------|
| **HTTP request routing/middleware** | Very High | Next.js middleware auth bypass (CRITICAL), CSRF via null origin, HTTP smuggling |
| **Image optimization endpoint** | High | Cache poisoning, XSS, Content injection, DoS — repeated across 6 Next.js versions |
| **Server Actions / Server Components** | High | RCE, DoS, SSRF, source code exposure — React flight protocol |
| **Serialized/deserialized data** | Medium | serialize-javascript RCE/XSS, React deserialization DoS |
| **URL/redirect handling** | Medium | Open Redirect in Express + Next.js, SSRF in redirects |
| **Discord message content** | Medium | Prompt injection into Gemini context (no CVE, architectural risk) |
| **Dev server / HMR endpoint** | Low | Origin bypass for CSRF on WebSocket, dev server info disclosure |
| **Log inputs** | Low | uvicorn log injection |
| **Cache/CDN layer** | Low-Medium | Empty reply DoS via missing Cache-Control |

**Repeatedly exploited vectors:**
1. Next.js image optimization pipeline — 6 distinct CVEs across versions; structural weakness
2. Next.js middleware/routing layer — 3 CVEs including 1 CRITICAL auth bypass
3. HTTP protocol edge cases (smuggling, splitting, redirect) — cross-component

### 2d. Patch Quality Signals (Structural Recurrence)

| Component | Recurrence Pattern | Versions Patched | Assessment |
|-----------|-------------------|-----------------|------------|
| **Next.js image optimization** | DoS, XSS, cache poisoning, content injection patched in v10→11, v12, v13, v14, v15, v16 | 14.2.7, 14.2.31, 15.4.5, 16.1.7 | STRUCTURAL: the image optimizer's input handling has been patched 6+ times; root cause not eliminated |
| **Next.js middleware auth** | Auth bypass patched in 13.5.9/14.2.25, then incomplete DoS fix in 14.2.35/15.0.7, then separate bypass in 14.2.15 | Multiple | STRUCTURAL: middleware security model has recurring bypass issues |
| **Next.js cache layer** | Cache poisoning patched in 13.5.7/14.2.10, then race-condition poisoning in 14.2.24/15.1.6, then Vary header poisoning in 15.3.3 | Multiple | STRUCTURAL: caching layer lacks consistent key validation |
| **serialize-javascript** | RCE patched in 2020 (3.1.0), RCE again in 7.0.3, DoS now in 7.0.5 | 3.1.0, 7.0.3, 7.0.5 | STRUCTURAL: serialization of complex types remains unsafe |
| **Open Redirect (Express+Next)** | Express 3.x redirect vuln, Next.js open redirects in v9, v11, v14 | Multiple | Pattern: URL parsing edge cases repeatedly missed |

### Audit Targeting Recommendations

Based on pattern analysis:

**Phase 3 DFD slices** should prioritize:
1. Next.js image optimization pipeline — highest advisory concentration (6+ CVEs), structural
2. Next.js middleware/routing layer — CRITICAL auth bypass precedent; current 16.x behavior needs verification
3. FastAPI auth module — DEBUG bypass mode is a structural flaw not covered by any CVE
4. MCP server interface (stitch HTTP + stdio servers) — DNS rebinding, validation bypass patterns

**Phase 5 deep probe** should target:
1. HTTP request routing edge cases (null Origin, middleware subrequest headers) in Next.js 16.2.1
2. Server Actions and React flight protocol endpoints — RCE precedent
3. Discord bot → Gemini bridge prompt injection via `question` parameter
4. FastAPI `/api/search?q=` parameter and `DASHBOARD_URL` env for SSRF
5. Auth cookie (`ostwin_auth_key`) handling — timing attacks, fixation, bypass

**Phase 8 chambers** must include:
1. DoS / resource exhaustion — mandatory (17 historical instances)
2. Cache poisoning — mandatory (7 instances, structural in Next.js)
3. Auth bypass / CSRF — mandatory (5 instances, 1 CRITICAL precedent)
4. SSRF — mandatory (2 CVEs + architectural risk in discord bot and Next.js proxy)
5. Prompt injection — additional chamber (no CVE but active attack surface)

**Patch-bypass-checker** should flag as structural-recurrence candidates:
1. Next.js image optimization (6 patch cycles, same component)
2. Next.js middleware authentication (3 bypass fixes)
3. serialize-javascript serialization of complex types (3 RCE/DoS patch cycles)
4. Next.js cache layer (3 poisoning patches)

---

## Patch List (Commits/Versions with Security Fixes)

### Active Security Patches Required

| ID | Package | Vulnerable | Fixed | Action |
|----|---------|-----------|-------|--------|
| CVE-2026-34043 / GHSA-qj8w-gfj5-8c6v | serialize-javascript | 7.0.4 | 7.0.5 | Bump override in root `package.json` to `"serialize-javascript": "7.0.5"` |

### Historical Security Patches (for reference — all applied via version upgrades)

| Version Bump | Fixes | Severity |
|-------------|-------|----------|
| next 16.1.7 | GHSA-3x4c-7xq6-9pq8, GHSA-ggv3-7p47-pfv8, GHSA-h27x-g6w4-24gq, GHSA-mq59-m269-xvcx, GHSA-jcc7-9wpm-mj36 | MOD/LOW |
| next 16.1.5 | GHSA-5f7q-jpqc-wp7h, GHSA-9g9p-9gw9-jx7f | MODERATE |
| next 14.2.25 | GHSA-f82v-jwr5-mffw (CRITICAL auth bypass) | CRITICAL |
| next 15.1.9 | GHSA-9qr9-h5gf-34mp (CRITICAL RCE) | CRITICAL |
| serialize-javascript 7.0.3 | GHSA-5c6j-r48x-rmvq (RCE) | HIGH |
| express 5.0.0 | GHSA-qw6h-vgh9-j6wx, GHSA-rv95-896h-c2vc | LOW/MOD |
| mcp 1.23.0 | GHSA-9h52-p55h-vw2f (DNS rebinding) | HIGH |
| mcp 1.10.0 | GHSA-j975-95f5-7wqh (DoS) | HIGH |
| mcp 1.9.4 | GHSA-3qhf-m339-9g5v (validation DoS) | HIGH |
| httpx 0.23.0 | GHSA-h8pj-cxx2-jfg2 (CRITICAL input validation) | CRITICAL |
| fastapi 0.65.2 | GHSA-8h2j-cgx8-6xv7 (CSRF) | HIGH |

### No-CVE Security Findings (Architecture-Level)

| Finding | Component | Risk | Recommendation |
|---------|-----------|------|----------------|
| `OSTWIN_API_KEY=DEBUG` auth bypass | `dashboard/auth.py:79` | CRITICAL (auth disabled) | Remove DEBUG bypass or restrict to non-production builds only |
| User input injected verbatim into Gemini prompt | `discord-bot/src/agent-bridge.js:121` | HIGH (prompt injection) | Add input sanitization / length limit before constructing LLM prompt |
| `DASHBOARD_URL` env used unsanitized in `fetchJSON` | `discord-bot/src/agent-bridge.js:10,21` | MODERATE (SSRF if env compromised) | Validate and allowlist `DASHBOARD_URL` scheme and host |
| Next.js dev proxy rewrites all `/api/*` with no origin check | `dashboard/fe/next.config.ts` | LOW (dev only) | Ensure `NEXT_PUBLIC_API_BASE_URL` is not attacker-controllable in CI |
