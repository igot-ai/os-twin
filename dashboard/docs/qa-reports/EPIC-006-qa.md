# QA REPORT: EPIC-006 — FastMCP Server + Carry-forwards (CARRY-001/002/003)

> Author: @qa
> Date: 2026-04-19
> Inputs: `docs/done-reports/EPIC-006-engineer.md`, `docs/knowledge-mcp.plan.md` (EPIC-006 + ADR-14/15/16/17),
>         `dashboard/knowledge/mcp_server.py`, `dashboard/knowledge/config.py`,
>         `dashboard/knowledge/graph/parsers/markitdown_reader.py`, `dashboard/knowledge/service.py`,
>         `dashboard/routes/settings.py`, `dashboard/api.py`,
>         all `dashboard/tests/test_knowledge_*.py`.

---

## Verdict: **CHANGES-REQUESTED**

Carry-forwards (image support / settings backend / settings-aware service) all pass independently. The 7 MCP tools register, validate inputs, return structured errors, and behave correctly when called as Python functions. **However the headline deliverable — making the MCP server reachable from an external client like opencode over the streamable-HTTP transport — is broken in two distinct ways**, and the engineer's own integration test does not catch the failure because it bypasses the HTTP transport entirely.

The two transport defects are blocking for any real opencode integration:

1. **D1 (Critical)** — The `/mcp` mount is shadowed by the FE catch-all route. `POST /mcp` returns `405 Method Not Allowed` from the FE handler; `GET /mcp` returns the dashboard SPA HTML (20 KB of Next.js index) instead of the MCP server. The engineer's `test_mcp_endpoint_mounted` only asserts `status_code != 404` so it returns a false positive (it gets the SPA HTML, status 200).
2. **D2 (Critical)** — Even when reaching the actual MCP path (`/mcp/mcp`, because FastMCP's `streamable_http_app()` exposes its inner route as `/mcp`), POST requests crash with `RuntimeError: Task group is not initialized. Make sure to use run().` The `streamable_http_app()` lifespan was not propagated when the sub-app was mounted into FastAPI, so the session manager's task group never starts.

Phase 5.4 confirms the bearer-auth wrapper itself works correctly (rejects missing/wrong tokens with 401), so the auth implementation is sound — it's the underlying transport that's broken.

Everything else (Phase 1, 2, 3, 4, 6, 7, 8) passed cleanly. A focused fix to the mount setup (likely <50 LOC) should clear both D1 and D2 without touching any of the tool code.

---

## Phase 1 — DoD re-verification

| Check | Outcome | Notes |
|---|---|---|
| 1A — module importable | ✅ | `from dashboard.knowledge.mcp_server import mcp, get_mcp_app` returns `OK` |
| 1B — 7 tools introspectable | ✅ | `_tool_manager` present; `asyncio.run(mcp.list_tools())` returns 7 expected names |
| 1C — `IMAGE_EXTENSIONS ⊆ SUPPORTED_DOCUMENT_EXTENSIONS` | ✅ | 24 total ext; `.bmp .gif .jpeg .jpg .png .tiff .webp` all present |
| 1D — `MarkitdownReader._get_markitdown()` wires LLM client when key set | ✅ | `md._llm_client is not None`, `md._llm_model = 'claude-sonnet-4-5-20251022'` |
| 1E — `/api/settings/knowledge` GET + PUT routes registered | ✅ | both methods present in `dashboard.routes.settings.router` |
| 1F — `MasterSettings.knowledge` field | ✅ | type `KnowledgeSettings`, default `llm_model='' embedding_model='' embedding_dimension=384` |
| 1G — `/mcp` mount in `app.routes` | ✅ (with caveat) | 1 Mount registered at index 198; FE catch-all at 201 — registration order is correct, but Starlette's `Mount` does not handle the bare `/mcp` path correctly because the inner FastMCP route is at `/mcp` (full = `/mcp/mcp`) — see D1 |
| 1H — lazy-import audit | ✅ | `kuzu / chromadb / sentence_transformers / markitdown / anthropic` all absent after `import dashboard.knowledge.mcp_server` (`-X importtime` filter empty, `sys.modules` check returns `[]`) |
| 1I — knowledge tests | ✅ | `test_knowledge_mcp.py` 18/18 pass; smoke + namespace + ingestion + query 162/162 pass; settings knowledge filter 5/5 pass |
| 1J — boot time avg | ✅ | runs: 1.743 / 1.596 / 1.714 → **1.684 s** average (under <2 s budget) |

---

## CARRY-001/002/003 verification table

| Task | Status | Evidence |
|---|---|---|
| **CARRY-001** — Image support in ingestion (ADR-14, ADR-17) | ✅ PASS | Phase 2 probe ran two ingestions on `{test.png + test.md}` fixtures: <br>• Without `ANTHROPIC_API_KEY`: job state = `COMPLETED`, 1 indexed (md), 1 skipped (png), warning `"produced no text (...vision OCR disabled). Skipping."` <br>• With fake `ANTHROPIC_API_KEY`: vision attempted, Anthropic returned 401, gracefully logged `"vision failed or returned empty. Skipping."`, job still `COMPLETED` |
| **CARRY-002** — Knowledge settings backend (ADR-15) | ✅ PASS | Phase 3 probe via `TestClient`: `GET /api/settings/knowledge` returns defaults `{llm_model:'',embedding_model:'',embedding_dimension:384}`. PUT with `{llm_model:'claude-haiku-4-5', embedding_model:'BAAI/bge-base-en-v1.5', embedding_dimension:768}` returns 200 with the new values; subsequent GET reflects the change. Auth: 401 without key, 200 with `X-API-Key` header, 200 with `Authorization: Bearer`, 401 with bad bearer |
| **CARRY-003** — `KnowledgeService` reads from settings | ✅ PASS | Phase 4 probe: after PUT in Phase 3, fresh `KnowledgeService()` returns `_get_llm().model = 'claude-haiku-4-5'` and `_get_embedder().model_name = 'BAAI/bge-base-en-v1.5'` — settings precedence (MasterSettings > env > hardcoded) confirmed |
| **CARRY-004** — Architect cross-check from EPIC-005 | n/a | Not in scope of this EPIC's QA; CARRY-005 is QA's verification of CARRY-001..003 above which this report covers |

---

## TASK-E-001..009 verification table

| Task | Status | Evidence |
|---|---|---|
| **TASK-E-001** — `dashboard/knowledge/mcp_server.py` with 7 `@mcp.tool()`-decorated functions | ✅ | Module exists, 7 tools registered; names match brief verbatim |
| **TASK-E-002** — Tool docstrings explicit about args / return shape / when-to-use | ✅ | Sampled `knowledge_list_namespaces` (Use-when guidance + Example) and `knowledge_import_folder` (states "supports docx, pdf, xlsx, pptx, html, txt, md, csv, json, png, jpg" and `absolute` keyword) — both meet the bar |
| **TASK-E-003** — Tools never raise; all errors → `{error, code}` | ✅ | Phase 5.2 fuzzed 8 bad-input cases — every one returned a structured envelope. `INVALID_FOLDER_PATH`, `FOLDER_NOT_FOUND`, `INVALID_NAMESPACE_ID`, `NAMESPACE_NOT_FOUND`, `BAD_REQUEST`, `JOB_NOT_FOUND`, `NAMESPACE_EXISTS`, `INTERNAL_ERROR` (None folder_path) |
| **TASK-E-004** — Mount at `/mcp` via `app.mount("/mcp", ...)` | ⚠️ PARTIAL | The mount call exists in `api.py:203/206` but the resulting endpoint is **not externally callable** — see D1 + D2 below |
| **TASK-E-005** — Bearer auth when `OSTWIN_API_KEY` set + dev_mode != 1 | ✅ (auth logic) / ⚠️ (transport unreachable) | Phase 5.4 confirmed the wrapper rejects missing/bad bearer with `401 {"error":"unauthorized","code":"UNAUTHORIZED"}`. Correct token gets past the wrapper but then hits the transport bug (D2) |
| **TASK-E-006** — `dashboard/docs/knowledge-mcp-opencode.md` with copy-pasteable snippet | ✅ | File exists; verbatim snippet uses `http://localhost:3366/mcp` and `Bearer ${env:OSTWIN_API_KEY}` headers — but the URL is wrong for end-users because of D1 (the actual reachable endpoint differs once D1 is fixed) |
| **TASK-E-007** — Dev-mode startup banner | ✅ | `INFO  dashboard.api  Knowledge MCP server live at http://localhost:3366/mcp (dev mode, no auth)` confirmed in subprocess startup logs |
| **TASK-E-008** — Engineer's integration test covering full lifecycle | ❌ FALSE POSITIVE | `test_full_import_query_lifecycle` calls Python tool functions directly — never opens an MCP client session, never POSTs to `/mcp/...`. As a result, D1 + D2 are completely uncovered by the test suite |
| **TASK-E-009** — Done report | ✅ | Engineer's report at `docs/done-reports/EPIC-006-engineer.md` is comprehensive (306 lines) and honest about the 5 divergences |

---

## Engineer's 5 divergences review

| # | Divergence | Verdict | Rationale |
|---|---|---|---|
| 1 | `_get_markitdown()` lives on `MarkitdownReader`, `Ingestor` delegates via `_get_markitdown_converter()` | ✅ **Sound** | `dashboard/knowledge/ingestion.py:457` → `self._markitdown = MarkitdownReader()._get_markitdown()`. Vision wiring in exactly one place (`markitdown_reader.py:76-103`). No duplication |
| 2 | Auth via Starlette `BaseHTTPMiddleware` wrapper | ✅ **Sound (with note)** | Implementation is 24 LOC (`api.py:182-203`), composable, and the auth logic itself works (Phase 5.4 confirmed 401 for missing/bad token). Note: the wrapper sits *outside* the actual MCP transport, so when the transport breaks (D2), the wrapper still passes — useful diagnostic |
| 3 | `_get_service()` reads `OSTWIN_KNOWLEDGE_DIR` at construction | ✅ **Sound** | Phase 6.3 probe: env=`/tmp/X` → `nm.namespace_dir('test-x')` rooted at `/tmp/X`. Reset `_service=None`, env=`/tmp/Y` → next call rooted at `/tmp/Y`. Two distinct service instances, no leak |
| 4 | `"knowledge"` in `_VALID_NAMESPACES` | ✅ **Sound** | `dashboard/routes/settings.py:131-142` — typed `GET/PUT /knowledge` defined at lines 155+ are registered first (FastAPI matches typed routes before generic paths), and `"knowledge"` is also in the generic-namespace allow-list, so both paths work. Documented in code comments at lines 145-152 |
| 5 | Tool docstrings include trigger / anti-trigger guidance | ✅ **Sound** | Every tool has "Use when:" + "Example:" sections. `knowledge_import_folder` explicitly enumerates supported extensions — useful for an LLM doing intent routing. ~10 extra lines per tool, no behaviour change |

All 5 divergences are documented honestly in the engineer's done report and judged sound on independent re-read.

---

## Phase 5 — MCP transport probe (the gate)

### 5.1 + 5.2 Direct (Python-level) tool invocation: ✅ PASS

- All 7 tool names exact-match the expected set
- Bad input fuzz returns structured `{error, code}` for all 8 cases:
  - `relative path` → `INVALID_FOLDER_PATH`
  - `nonexistent folder` → `FOLDER_NOT_FOUND`
  - `name="UPPERCASE"` → `INVALID_NAMESPACE_ID` (regex `^[a-z0-9][a-z0-9_-]{0,63}$`)
  - `name=""` → `INVALID_NAMESPACE_ID`
  - `query` of nonexistent namespace → `NAMESPACE_NOT_FOUND`
  - `mode="bogus"` → `BAD_REQUEST`
  - `job_id="not-a-uuid"` → `JOB_NOT_FOUND`
  - `folder_path=None` → `INTERNAL_ERROR` (graceful but could be more specific — minor)
- Idempotency: 2nd `knowledge_create_namespace` with same name → `NAMESPACE_EXISTS`

### 5.3 Real MCP transport (streamable-HTTP) probe: ❌ **FAIL**

**This is the gate, and it fails.** Probed all four plausible URLs against a real uvicorn-spawned dashboard on a random port (subprocess, not TestClient):

| URL probed | Result |
|---|---|
| `POST /mcp` (init payload) | **`405 Method Not Allowed`** — body `{"detail":"Method Not Allowed"}`, header `allow: GET, HEAD`. The FE catch-all (`api.py:237-244`, declared `methods=["GET","HEAD"]`) is intercepting POSTs to `/mcp` |
| `GET /mcp` | **`200`** — but the body is a 20 403-byte `<!DOCTYPE html>` page (the dashboard SPA). The MCP mount is silently shadowed because Starlette's mount-then-catch-all dispatching delivers the GET to the FE handler. The engineer's `test_mcp_endpoint_mounted` only asserts `!= 404` so it returns a false positive |
| `POST /mcp/` | `404 Not Found` — neither the mount nor the catch-all matches |
| `POST /mcp/mcp` (the actual FastMCP path, since `streamable_http_path` defaults to `/mcp` and we're mounted at `/mcp`) | **`500 Internal Server Error`** — server logs reveal: `RuntimeError: Task group is not initialized. Make sure to use run().` thrown from `mcp/server/streamable_http_manager.py:144`. This is the FastMCP session manager's task group, which requires the parent app to propagate the FastMCP `streamable_http_app()`'s own lifespan — which the engineer's `app.mount("/mcp", _mcp_app)` does not do |

Asyncio MCP client (`streamablehttp_client + ClientSession`) reproduces the same failures (405 on `/mcp`, "Session terminated" on `/mcp/`, hard timeout on `/mcp/mcp`).

### 5.4 Bearer-auth probe: ✅ PASS (auth) / ❌ FAIL (downstream)

With `OSTWIN_API_KEY=phase54-secret`, `OSTWIN_DEV_MODE` unset:
- POST `/mcp/mcp` no `Authorization` → `401 {"error":"unauthorized","code":"UNAUTHORIZED"}` ✅
- POST `/mcp/mcp` `Authorization: Bearer wrong-token` → `401` ✅
- POST `/mcp/mcp` `Authorization: Bearer phase54-secret` → `500 Internal Server Error` ❌ (auth wrapper passes — D2 transport bug surfaces underneath)

The auth implementation is correct in isolation. It just sits in front of a broken transport.

---

## Phase 7 — Standard regressions

### Test counts

| Suite | Result |
|---|---|
| `test_knowledge_mcp.py` (18 new) | **18/18 pass** in 20.6 s |
| `test_knowledge_smoke.py + namespace + ingestion + query` (162 total) | **162/162 pass** in 33.7 s |
| `test_settings_api.py -k knowledge` (5 new) | **5/5 pass** in 1.5 s |
| `pytest tests/ -k "not knowledge"` (full regression w/ engineer's filter) | `88 failed, 568 passed, 1 skipped, 18 errors` — **identical to engineer's claimed baseline**; these failures pre-exist the EPIC and are unrelated (tunnel routes, settings_resolver, etc.). Confirmed via spot-check on tunnel test failures |
| `pytest tests/ -k "not knowledge and not settings"` (stricter — excludes 5 new settings tests too) | `76 failed, 494 passed, 1 skipped` — math checks out: 568−74(deselected settings)≈494, 88−12(known settings deltas)≈76 |

### Cold-boot time

| Run | Time |
|---|---|
| 1 | 1.743 s |
| 2 | 1.596 s |
| 3 | 1.714 s |
| **Avg** | **1.684 s** |

Comfortably under the <2 s budget, even with the MCP server module mounted.

---

## Phase 8 — Independent black-box probes

| Probe | Result |
|---|---|
| **8.1 Concurrent tool calls** — 10 threads simultaneously invoke `knowledge_list_namespaces()` | ✅ 10/10 returned a `dict` with `namespaces` key in 0.02 s. No deadlock, no data race observable at this granularity |
| **8.2 Bad input fuzzing** | ✅ All 8 cases handled — see Phase 5.2 above |
| **8.3 Settings-broadcaster** — verify PUT broadcasts a `settings_updated` event | ✅ Source inspection of `dashboard/routes/settings.py` confirms `await broadcaster.broadcast(...)` is called from the mutation endpoints. (Did not subscribe a real WebSocket consumer — code path verified by reading) |
| **8.4 Idempotency** — `knowledge_create_namespace` twice | ✅ 2nd returns `{error: "Namespace 'X' already exists", code: "NAMESPACE_EXISTS"}` |
| **8.5 OpenAPI spec** — `/openapi.json` returns 200 and includes knowledge paths | ✅ Status 200; `/api/settings/knowledge` is in the spec. (`/mcp` is its own protocol, won't appear — expected) |

---

## Defects found

### D1 (Critical) — `/mcp` mount shadowed by FE catch-all route
**Severity**: Critical (blocks the entire feature)
**Location**: `dashboard/api.py:203`/`206` (the mount), interacting with `dashboard/api.py:237-244` (the FE catch-all `@app.api_route("/{path:path}", methods=["GET","HEAD"])`).
**Symptom**:
- `GET /mcp` returns 200 with the dashboard SPA HTML body (20 403 bytes), not the MCP server response
- `POST /mcp` returns `405 Method Not Allowed` with header `allow: GET, HEAD` (signature of the FE catch-all rejecting POST)

**Root cause**: When the user requests `/mcp` (no trailing slash), Starlette delegates to the matching route. The FE catch-all `methods=["GET","HEAD"]` matches all GETs/HEADs to *any* path including `/mcp` and serves the SPA before the Mount can handle it. The Mount itself only catches `/mcp/...` (with prefix-stripping), not the bare `/mcp` path.

**Engineer's coverage**: Misses entirely. `test_mcp_endpoint_mounted` does `client.get("/mcp")` and asserts `status_code != 404` — gets 200 back (from the FE catch-all, not the MCP server) and the test passes for the wrong reason.

**Suggested fix**:
- In the FE catch-all, skip paths starting with `mcp/` or equal to `mcp` (similar to the existing `path.startswith("api/")` skip).
- OR mount the MCP app at a path that doesn't collide (e.g. `/api/mcp` would also need the same skip), and mount with a trailing-slash-tolerant pattern.

### D2 (Critical) — FastMCP `streamable_http_app()` task-group not initialized
**Severity**: Critical (blocks the entire feature)
**Location**: `dashboard/api.py:206` (`app.mount("/mcp", _mcp_app)`); root cause in `dashboard/knowledge/mcp_server.py:375-389` (`get_mcp_app()` returns the bare `streamable_http_app()` without a lifespan handoff).
**Symptom**:
- After bypassing D1 (probing the actual inner path `/mcp/mcp`), POSTs respond with `500 Internal Server Error`
- Server logs: `RuntimeError: Task group is not initialized. Make sure to use run().` thrown from `mcp/server/streamable_http_manager.py:144`

**Root cause**: `FastMCP.streamable_http_app()` returns a Starlette ASGI app with its own `lifespan` that initializes the session manager's task group via `mcp.session_manager.run()`. When this app is mounted as a sub-app in FastAPI, **its lifespan is NOT executed** (FastAPI/Starlette do not propagate lifespans to sub-apps by default). The session manager's `_task_group` therefore remains `None`, and the first incoming request crashes when it tries to spawn handler tasks.

**Engineer's coverage**: Misses entirely. The integration test `test_full_import_query_lifecycle` invokes Python tool functions directly (`from ...mcp_server import knowledge_create_namespace; knowledge_create_namespace(ns)`) without going through the HTTP transport. So the broken transport surfaces only when an actual MCP client connects.

**Suggested fix** (one common pattern):
```python
from contextlib import asynccontextmanager

_mcp_app = get_mcp_app()  # the streamable_http_app

@asynccontextmanager
async def _combined_lifespan(app):
    async with _mcp_app.router.lifespan_context(app):
        yield

app.router.lifespan_context = _combined_lifespan  # or pass into FastAPI(lifespan=...)
```
OR construct the FastMCP server with `stateless_http=True` (skips the task group requirement, simpler for stateless tools).

### D3 (Major) — `test_mcp_endpoint_mounted` is a false-positive test
**Severity**: Major (masks D1 from CI)
**Location**: `dashboard/tests/test_knowledge_mcp.py:132-142`
**Symptom**: Asserts only `r.status_code != 404`. With FE static catch-all serving the SPA, every URL under `/` (except `/api/*`) returns 200. The test passes whether or not the MCP server is reachable.
**Suggested fix**: Probe the actual MCP protocol — assert the response content-type is `application/json` or `text/event-stream`, OR send a real `initialize` JSON-RPC payload and assert the response shape, OR connect via `streamablehttp_client` and `list_tools()` (the proper integration test).

### D4 (Minor) — `folder_path=None` returns `INTERNAL_ERROR` instead of `INVALID_FOLDER_PATH`
**Severity**: Minor
**Location**: `dashboard/knowledge/mcp_server.py` `knowledge_import_folder` — relies on the generic `try/except: return _err("INTERNAL_ERROR", str(e))` envelope.
**Symptom**: `knowledge_import_folder("any", folder_path=None)` returns `{"error": "expected str, bytes or os.PathLike object, not NoneType", "code": "INTERNAL_ERROR"}` — gracefully handled (no crash) but the code is misleading; a calling LLM should see `INVALID_FOLDER_PATH`.
**Suggested fix**: Add an early-return `if not folder_path: return _err("INVALID_FOLDER_PATH", "folder_path is required")` before the existing absolute-path check.

### D5 (Minor) — Engineer's done report claims `GET /mcp → 200` is proof the mount works
**Severity**: Minor (documentation accuracy)
**Location**: `docs/done-reports/EPIC-006-engineer.md` lines 122-130 ("`/mcp` endpoint reachable through the FastAPI app … `GET /mcp → 200`").
**Symptom**: The 200 is the FE SPA HTML, not an MCP server response. The done report propagates the false-positive narrative.
**Suggested fix**: After D1+D2 are fixed, update the done report's verification snippet to do a real MCP client roundtrip (or at least a POST with the init payload and assertion on JSON content-type).

---

## Recommendation: **REJECT (CHANGES-REQUESTED)**

The MCP server's tool layer is solid — 7 tools, structured errors, lazy imports, settings integration, image support, all confirmed end-to-end at the Python level. The auth wrapper is correctly implemented. CARRY-001/002/003 are all PASS.

But the headline deliverable — making the MCP server callable from opencode over streamable-HTTP — does not work. Two distinct critical bugs (D1 mount shadowing + D2 lifespan propagation) prevent any external client from reaching the tools. The engineer's "lifecycle" integration test is misleading because it bypasses the HTTP transport entirely; a real `streamablehttp_client` connection fails on every URL variant.

Mandatory fixes before approval:
1. Fix D1 (FE catch-all skip for `/mcp/*` OR change mount path) — verifiable by `POST /mcp` (or whichever path is chosen) returning a JSON-RPC response, not 405 / SPA HTML.
2. Fix D2 (lifespan propagation OR `stateless_http=True`) — verifiable by a successful `streamablehttp_client + ClientSession.initialize() + list_tools()` sequence against a uvicorn-spawned dashboard.
3. Fix D3 (replace the mount-sanity test with a real transport probe — Phase 5.3 of this report is reusable as the test body).
4. Fix D4 (early-return for falsy `folder_path`).
5. Fix D5 (correct the done report's verification narrative once D1+D2 are resolved).

Re-QA scope after fix: re-run Phase 5.3 (the transport probe) end-to-end. If it passes (initialize → list_tools → call_tool roundtrip), I will sign off.

---

## Return summary

1. **QA report path**: `/Users/paulaan/PycharmProjects/agent-os/dashboard/docs/qa-reports/EPIC-006-qa.md`
2. **One-line verdict**: CHANGES-REQUESTED — tools and carry-forwards solid, but MCP HTTP transport is unreachable (mount shadowed + missing lifespan).
3. **Defect counts**: critical 2 (D1, D2), major 1 (D3), minor 2 (D4, D5).
4. **Did Phase 5.3 transport probe work?** **NO.** Every URL variant failed — `POST /mcp` returns 405 (FE catch-all), `GET /mcp` returns SPA HTML, `POST /mcp/` returns 404, `POST /mcp/mcp` returns 500 with `RuntimeError: Task group is not initialized`.
5. **Did Phase 5.4 auth probe work?** **YES** — auth wrapper correctly returns 401 for missing/wrong token; the underlying transport remains broken (500) when auth passes.
6. **Boot time (3-run avg)**: **1.684 s** (1.743 + 1.596 + 1.714).
7. **Top 3 findings**: (i) `/mcp` mount shadowed by FE static catch-all → no external client can reach the server; (ii) FastMCP `streamable_http_app()` lifespan not propagated → 500 on all POSTs even at the right path; (iii) engineer's `test_mcp_endpoint_mounted` is a false-positive test that masks both bugs from CI.
8. **Recommendation**: **REJECT (CHANGES-REQUESTED)**.
