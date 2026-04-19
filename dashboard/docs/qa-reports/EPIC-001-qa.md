# QA REPORT: EPIC-001 — Refactor Knowledge Package (de-app-ify, strip dead code)

> Verifier: @qa
> Date: 2026-04-19
> Verifier environment: macOS darwin, Python 3.11.7, /opt/anaconda3/bin/python
> Method: independently re-ran every command from the engineer's done report from a fresh shell, plus 11 black-box probes the engineer did not run.

---

## Verdict: **PASS**

All Definition-of-Done items, all six acceptance criteria, all four QA-Gate checks, and all eleven black-box probes pass. Two **MINOR** observations noted; none block sign-off. The engineer's claims are accurate, including the deviation disclosures (deletion of `rag_service.py` and partial ADR-10 compliance).

---

## Test execution summary

| Suite | Pass | Fail | Skip | Notes |
|---|---|---|---|---|
| `test_knowledge_smoke.py` (15 tests) | **15** | 0 | 0 | wall: 1.46s; subprocess lazy-import probe included |
| `dashboard/tests -k "not knowledge"` (regression) | **568** | 88 | 1 | matches engineer's baseline of 568 — **zero regression**. 88 fails + 18 errors are pre-existing on this branch (`test_settings_resolver`, `test_amem_*`, `test_user_management`, etc.) and unrelated to EPIC-001. |
| `pip install --dry-run -r dashboard/requirements.txt` | resolved | 0 | – | resolver succeeded; would install chromadb-0.6.3, sentence-transformers-4.1.0, transformers-4.57.6, plus opentelemetry stack. **Engineer admitted they did not run this — I confirm it works.** |

---

## Acceptance-criteria check

| # | Criterion (from plan EPIC-001) | Status | Evidence |
|---|---|---|---|
| 1 | No file in `dashboard/knowledge/` references `app.*` | ✅ | `grep -rE "(from \|import )app\." dashboard/knowledge/` returns exactly **one** match — `dashboard/knowledge/config.py:57` — and that line begins with `#` (comment "moved from app.utils.constant"). Verified by inspection. |
| 2 | No `import dspy` anywhere in the codebase (in our code) | ✅ | `grep -rE "(from \|import )dspy" dashboard/knowledge/` returns empty. Case-insensitive `grep -rin "dspy" --include="*.py"` returns only docstring/comment mentions explaining the removal. No active code references `dspy`. |
| 3 | `dashboard/knowledge/__init__.py` exports the documented public symbols and only those | ✅ | `sorted(k.__all__)` = `['EMBEDDING_DIMENSION','EMBEDDING_MODEL','GraphRAGExtractor','GraphRAGQueryEngine','GraphRAGStore','KNOWLEDGE_DIR','KnowledgeEmbedder','KnowledgeLLM','KnowledgeService','KuzuLabelledPropertyGraph','LLM_MODEL','RAGStorage','TrackVectorRetriever']` — exact parity with TASK-010 spec (13 symbols). |
| 4 | Smoke-test imports complete in <3 s — confirms lazy-loading | ✅ | `time python -c "import dashboard.knowledge"` → **1.17 s** wall (340 % CPU). `time pytest tests/test_knowledge_smoke.py -q` → **2.08 s** total (1.37 s pytest + setup overhead). Both well under 3 s. |
| 5 | All deleted modules verified gone | ✅ | All 7 paths confirmed absent: `mem0/`, `processing/`, `parsers/{docx,sheet,raw}.py`, `core/significance_analyzer.py`, `core/rag_service.py`. |
| 6 | Engineer's done report enumerates every file deleted with one-line justification | ✅ | "What I deleted" table in done report covers all 7 deletions with reason; deviations are explicitly disclosed (rag_service.py + ADR-10 partial). |

---

## ADR-compliance check (independent judgement)

| ADR | Status | Notes (independent of engineer's claims) |
|---|---|---|
| ADR-01 | ✅ | `config.KNOWLEDGE_DIR` = `Path.home()/.ostwin/knowledge` by default. `OSTWIN_KNOWLEDGE_DIR=/tmp/qa-test-kb python -c …` printed `/tmp/qa-test-kb` — env override **works**. |
| ADR-02 | ✅ | `KnowledgeLLM.is_available()` is `False` with no key (smoke test 7 verified), `True` with explicit key (smoke 8) or env (smoke 9). All 3 fallback methods (`extract_entities`, `plan_query`, `aggregate_answers`) return non-crashing values when key absent (smoke 10/11/12 + I re-ran by hand). With a *bad* key, construction succeeds; methods log + return `([], [])` — clean degradation. |
| ADR-03 | ✅ | `EMBEDDING_DIMENSION = 384`, `EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"`. I instantiated an embedder and called `.dimension()` → returned 384, matching the constant. |
| ADR-04 | ✅ | `dashboard/knowledge/graph/core/storage.py:258` shows `import chromadb` inside `init_vector_store` (function-scoped), not at module top. importtime confirms `chromadb` not loaded by `import dashboard.knowledge`. |
| ADR-05 | ✅ | `kuzudb.py:42` is `import kuzu` inside `if TYPE_CHECKING:` (NOT executed at runtime — only for static analysis). Lines 151/197/2192 are runtime imports inside methods. importtime confirms `kuzu` not loaded eagerly. |
| ADR-06 | ✅ | `markitdown_reader.py:73` is `from markitdown import MarkItDown` inside `_get_markitdown()`. importtime confirms `markitdown` not loaded eagerly. |
| ADR-07 | N/A | EPIC-006. |
| ADR-08 | N/A | EPIC-002/003. |
| ADR-09 | ✅ + extra | All 6 mandated deletions completed (`mem0/`, `parsers/{docx,sheet,raw}.py`, `significance_analyzer.py`, `processing/document_router.py`). Plus `rag_service.py` deleted as a disclosed deviation — its dependencies (`FolderMiddleware`, `local_db`, `app.i18n.translator`) all referenced non-existent modules; the new `__init__.py` does not export `RAGService` per spec, so deletion is consistent. |
| ADR-10 | ⚠️ Partial (engineer disclosed) | New `KnowledgeLLM` (`llm.py`) uses **English** prompts with `{language}` parameter at every callsite — verified in source. The legacy Vietnamese strings in `graph/prompt.py` remain on disk but are only consumed by `extract_KP_*` helpers in `graph/utils/rag.py`, which are no longer invoked by the refactored `GraphRAGExtractor` (which calls `KnowledgeLLM.extract_entities` directly). Engineer flagged this; full removal is queued for a later EPIC. **Acceptable for EPIC-001.** |
| ADR-11 | ✅ | `grep -rin "dspy" --include="*.py"` returns only documentation comments. No `import dspy` / `from dspy` / `DspyModel` / `DspyLlamaIndexAdapter` references exist in active code. |
| ADR-12 | N/A | EPIC-002. |
| ADR-13 | N/A | EPIC-006. |

---

## QA Gate — independent re-run

| Gate | Mandate | Status | Evidence |
|---|---|---|---|
| 1 | `pytest dashboard/tests/ -k "not knowledge"` → zero regressions | ✅ | 568 passed, identical to engineer's baseline. |
| 2 | `python -X importtime -c "import dashboard.knowledge"` MUST NOT contain kuzu, chromadb, sentence_transformers, markitdown, anthropic | ✅ | `grep -iE "(kuzu\$\|chromadb\$\|sentence_transformers\$\|markitdown\$\|anthropic\$)"` against full output returns **empty**. Only `llama_index_core` (mandated by TASK-011) appears in the heavy path. |
| 3 | `pip install --dry-run -r dashboard/requirements.txt` succeeds | ✅ | Resolver finished cleanly. Engineer skipped this; **I ran it.** |
| 4 | `KnowledgeService()` raises `NotImplementedError` | ✅ | `python -c "from dashboard.knowledge import KnowledgeService; KnowledgeService()"` → `NotImplementedError: KnowledgeService is implemented in EPIC-002`. |

---

## Black-box checks performed (Phase 3 + Phase 6 probes)

| # | Probe | Result |
|---|---|---|
| BB-1 | `inspect.signature(KnowledgeLLM.{extract_entities,plan_query,aggregate_answers,is_available})` | All four signatures match spec. `extract_entities(text, language="English", domain="") -> tuple[list[dict], list[dict]]` exact. |
| BB-2 | `inspect.signature(KnowledgeEmbedder.{embed,embed_one,dimension})` | All three match: `embed(texts: list[str]) -> list[list[float]]`, `embed_one(text: str) -> list[float]`, `dimension() -> int`. |
| BB-3 | `OSTWIN_KNOWLEDGE_DIR=/tmp/qa-test-kb python -c "from dashboard.knowledge.config import KNOWLEDGE_DIR; print(KNOWLEDGE_DIR)"` | Printed `/tmp/qa-test-kb` — env override works. |
| BB-4 | Vietnamese-diacritic scan of `config.py`/`llm.py`/`embeddings.py`/`__init__.py` | All clean. One match in `__init__.py` is `ç` from "façade" (French loanword in a docstring) — harmless, not Vietnamese. |
| BB-5 | Verify the single `app.` grep match is a comment, not an import | Confirmed: `dashboard/knowledge/config.py:57` line literally begins with `#`. |
| BB-6 | `to_json_graph` no longer references pyvis | Confirmed: source uses `import networkx as nx` lazily; output is plain `{nodes, edges}` dict. `grep -rn "pyvis" dashboard/knowledge/` returns empty. |
| BB-7 | `_run_async` exists in `graph_rag_query_engine.py` | Found at line 37. Implementation: tries `asyncio.get_event_loop()`, if loop is running, runs the coroutine in a fresh loop on a worker thread (via `concurrent.futures.ThreadPoolExecutor`); otherwise `asyncio.run(coro)`. **Robust against being invoked from a thread that already has a loop.** Caveat: uses deprecated `asyncio.get_event_loop()` API (DEPRECATIONS in Py 3.12+; in 3.11.7 it works). MINOR. |
| BB-8 | `grep -r "rag_service\|RAGService" dashboard/knowledge/` | Empty — no dangling references to the deleted module. |
| BB-9 | `graph/__init__.py` is a no-op | 9 lines: doc-string + `__all__: list[str] = []`. No imports. ✅ |
| BB-10 | `__all__` parity with TASK-010 spec | Exact match — 13 symbols. ✅ |
| BB-11 | Smoke-test wall time | `time pytest tests/test_knowledge_smoke.py -q` → **1.37 s pytest** wall (engineer claimed 1.45 s — close enough; second run was 1.37 s). |
| BB-12 | `from dashboard.knowledge.graph import *` | No exception, no side effects. |
| BB-13 | `KnowledgeLLM(api_key="bad-key").extract_entities("test")` | Construction succeeds. First method call attempts the API → `Anthropic call failed: Error code: 401 …` logged via `logger.error`, then returns `([], [])`. Graceful — no crash. |
| BB-14 | `KuzuLabelledPropertyGraph(database_path=tmpdir)` | Raises `TypeError: missing 2 required positional arguments: 'index' and 'ws_id'`. **This is the legacy class signature unchanged from before the refactor** — TASK-006 in EPIC-002 is explicitly tasked with re-wiring this. Not a regression. (A secondary `__del__` warning prints `Error closing KuzuDB connection: 'KuzuLabelledPropertyGraph' object has no attribute '__pydantic_fields_set__'` because `__init__` never completed — pre-existing artefact of the legacy class design.) |
| BB-15 | `storage.py` leftover refs to `local_db`/`FolderMiddleware`/`SettingService`/`FileHelper` | Only one match: a docstring at line 7 explaining what was removed. No active code references. |
| BB-16 | `rag.py` 5 retained helpers | All 5 (`_get_nodes_from_triplets`, `extract_KP_fn`, `extract_KP_json_fn`, `parse_fn`, `parse_json_fn`) are present, callable, with documented signatures. Sample calls of `parse_fn`/`parse_json_fn` on test inputs return correctly-shaped tuples. |
| BB-17 | `_utils.py` regex helpers (`find_first_json`, `find_json_block`, `json_parse_with_quotes`) functional | Tested on `'Some text {"key": [1,2,3], "nested": {"a": 1}} trailing'` — all three returned the correct parsed dict. The `regex` recursive `(?R)` rewrite to plain `re` is functional. |

---

## Smoke-test quality assessment

Read `dashboard/tests/test_knowledge_smoke.py` end-to-end (234 LOC, 15 tests). Observations:

- **Genuine tests, no `assert True` placeholders.** Every test makes a meaningful assertion (path equality, type checks, behavioural assertions on graceful degradation, subprocess output parsing).
- `test_lazy_imports_via_subprocess` is the most important test. **Robust:** uses `subprocess.run([sys.executable, "-c", code], cwd=…, timeout=30, env={**os.environ})` — fresh interpreter, can't be polluted by previously-cached `sys.modules`. Asserts `proc.returncode == 0` and parses `LOADED:…` to confirm the heavy-deps list is empty.
- **No hidden API-key dependency:** every LLM test uses `monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)` to enforce no-key state, or `monkeypatch.setenv` with a bogus key. None ever issue real API calls.
- The embedder tests cleverly verify `_model_cache` is **not** mutated by construction — proving model load is truly lazy.

---

## Performance measurements

| Operation | Sample | Wall time | Notes |
|---|---|---|---|
| Cold `import dashboard.knowledge` | n=1 | **1.17 s** | 340 % CPU (parallel module load). Target was <3 s. |
| `pytest test_knowledge_smoke.py -q` | 15 tests | **1.37 s** | Engineer claimed 1.45 s; close. |
| `pip install --dry-run -r dashboard/requirements.txt` | full resolve | ~30 s | Resolver succeeded; 17 packages would be installed. |
| `pytest dashboard/tests/ -k "not knowledge"` | 671 collected | 11.08 s | 568 pass / 88 pre-existing fail / 18 pre-existing error / 1 skip / 15 deselected. |

---

## Defects found

> **Note**: I held a high bar for severity. Nothing CRITICAL or MAJOR was found.

1. **[MINOR] `_run_async` uses deprecated `asyncio.get_event_loop()` API** — `dashboard/knowledge/graph/core/graph_rag_query_engine.py:40`. On Py 3.10+ this emits a `DeprecationWarning` when no current event loop is set; on Py 3.12+ it raises `DeprecationWarning` more aggressively (and Py 3.14 is removing the implicit-creation behaviour). Currently works on 3.11.7. *Suggested fix*: replace with `try: loop = asyncio.get_running_loop()` (which only succeeds when a loop is running) and unconditionally fall through to `asyncio.run(coro)` otherwise. Non-blocking for EPIC-001; engineer can address as a sweep in EPIC-002 or later.

2. **[MINOR] Vietnamese prompts still present in `graph/prompt.py`** — engineer disclosed this as the ADR-10 partial-compliance item. The strings are inert (no live callsite reaches them via the new `KnowledgeLLM` path) but they remain in the source tree. *Suggested fix*: remove the Vietnamese string literals from `graph/prompt.py` once `extract_KP_*_fn` helpers are confirmed unused (likely EPIC-003 or a later cleanup). Already documented in the engineer's "Open issues / known limits".

3. **[OBSERVATION, not a defect] Pydantic `UnsupportedFieldAttributeWarning`** appears at `import dashboard.knowledge` time. Engineer disclosed this as pre-existing (emitted by llama-index internals). Confirmed: warning persists across the codebase regardless of EPIC-001 changes. Not actionable here.

4. **[OBSERVATION, not a defect] `KuzuLabelledPropertyGraph(database_path=…)` requires `index` and `ws_id` positional args.** Engineer's done report flags this as preserved legacy behaviour ("Open issues #5") — TASK-006 in EPIC-002 is explicitly tasked with rewiring `database_path` to `KNOWLEDGE_DIR/{namespace}/graph.db`. Not in scope for EPIC-001.

5. **[OBSERVATION, not a defect] Deprecated `__del__` warning when constructing `KuzuLabelledPropertyGraph` fails:** `Error closing KuzuDB connection: 'KuzuLabelledPropertyGraph' object has no attribute '__pydantic_fields_set__'`. This is a side-effect of partial Pydantic init when `__init__` raises before `BaseModel.__init__` completes. Pre-existing class design artefact; not introduced by this EPIC.

---

## Recommendation

- **APPROVE.** The refactor is clean, the public API matches spec exactly, the lazy-import discipline is real (not theatrical), and the engineer's deviations were transparently disclosed and are defensible.
- **Action items for EPIC-002** (carry forward, do not block EPIC-001):
  - Replace `asyncio.get_event_loop()` in `_run_async` with `asyncio.get_running_loop()`-based detection.
  - Re-wire `KuzuLabelledPropertyGraph.database_path` to `kuzu_db_path(namespace)` per TASK-006 — this also fixes the constructor signature gap exposed by BB-14.
  - Remove the Vietnamese string literals from `graph/prompt.py` once the `extract_KP_*_fn` helpers are confirmed dead.
- **Note for the architect:** the engineer's claim "1 grep match is a comment, not an import" is verified; the engineer's regression-baseline number (568 passed) is verified; the engineer's importtime claim is verified. The engineer's done report is honest and accurate.
