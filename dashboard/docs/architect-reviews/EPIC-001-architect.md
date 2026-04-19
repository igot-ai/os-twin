# REVIEW: EPIC-001 — Refactor Knowledge Package

> Reviewer: @architect
> Date: 2026-04-19
> Reviewed: engineer's done report (`docs/done-reports/EPIC-001-engineer.md`) + qa report (`docs/qa-reports/EPIC-001-qa.md`) + independent re-runs of critical commands.

## Verdict: **PASSED**

Proceed to EPIC-002.

## Cross-checks performed (independent of engineer & QA)

- [x] **All ADRs honored.** ADR-01..06, 09, 11 fully complied. ADR-10 partially complied but transparently — the new `KnowledgeLLM` is fully English/parameterised (the live path); the legacy Vietnamese strings sit dormant in `graph/prompt.py`. Acceptable.
- [x] **No scope creep beyond EPIC's DoD.** Engineer deleted one extra file (`rag_service.py`) — disclosed, justified by impossible `app.*` deps + the file not being in TASK-010's export list. No silent additions.
- [x] **Acceptance criteria objectively met.** All 6 criteria in the plan verified by re-running the literal `grep` / `python -c` / `pytest` commands. Re-confirmed:
  - `grep -rE "(from |import )app\." dashboard/knowledge/` → **1 hit, comment line in `config.py:57`** (verified literally starts with `#`)
  - `grep -rE "(from |import )dspy" dashboard/knowledge/` → **empty**
  - All 5 dead-code paths absent (mem0/, processing/, parsers/{docx,sheet,raw}.py, significance_analyzer.py, rag_service.py)
  - `python -c "from dashboard.knowledge import KnowledgeService, KnowledgeLLM, KnowledgeEmbedder, KuzuLabelledPropertyGraph, RAGStorage, GraphRAGExtractor, GraphRAGQueryEngine, GraphRAGStore, TrackVectorRetriever"` succeeds
  - `__all__` = exact 13 symbols documented in TASK-010
- [x] **Test coverage adequate for the EPIC's risk surface.** 15 smoke tests cover: importability, placeholder behaviour, config types, LLM degradation (3 paths), embedder lazy-load (2 paths), and a subprocess test that proves heavy deps are NOT loaded at module import. `test_lazy_imports_via_subprocess` is the most important — it uses a fresh interpreter, so `sys.modules` pollution can't fake the result. **Pass: 15/15 in 1.31s.**
- [x] **Public API surface matches plan.** `inspect.signature` of every documented method matches the spec (verified via QA's BB-1, BB-2; I re-checked).
- [x] **No regressions in unrelated dashboard routes.** Re-ran (per QA) `pytest dashboard/tests/ -k "not knowledge" --no-header -q` — **568 passed**, identical to engineer's baseline. The 88 failures + 18 errors are pre-existing (settings_resolver, amem, user_management) and unrelated to this EPIC.
- [x] **Lazy-import discipline real, not theatrical.** `python -X importtime -c "import dashboard.knowledge" 2>&1 | grep -iE "( kuzu$| chromadb$| sentence_transformers$| markitdown$| anthropic$)"` returns **empty**. Cold import wall time **1.17s** (well under the 3s budget; well under the dashboard's <2s boot target after this single import is amortized).
- [x] **`pip install --dry-run -r dashboard/requirements.txt`** succeeds (QA ran this; engineer admitted skipping it). No dependency conflicts.

## Specific items requiring fix (none — all carry-forward to EPIC-002)

These are tracked but **do not block** sign-off:

1. **`graph_rag_query_engine.py:40` — `_run_async` uses deprecated `asyncio.get_event_loop()`.** Will deprecate hard in Py 3.14. Engineer should switch to `asyncio.get_running_loop()`-based detection in EPIC-002 (when the file is touched again for storage/namespace wiring).
2. **`graph/prompt.py` Vietnamese strings still on disk.** Inert (no live caller). Remove in EPIC-003 once the `extract_KP_*_fn` helpers in `graph/utils/rag.py` are confirmed dead via grep.
3. **`KuzuLabelledPropertyGraph(database_path=...)` requires `index` and `ws_id` positional args.** Pre-existing legacy signature. EPIC-002 TASK-006 already scopes the rewire to `kuzu_db_path(namespace)`.

## Blockers for next EPIC

None. EPIC-002 starts with a clean refactored base.

## Notes for the engineer (carry-forward to EPIC-002)

- When you touch `KuzuLabelledPropertyGraph.__init__` for TASK-006, also fix the `__del__` Pydantic-not-initialized warning that surfaces on construction failure. Trivial guard: `if not hasattr(self, '__pydantic_fields_set__'): return` at the top of `__del__` / `close_connection`.
- When you touch `graph_rag_query_engine.py`, replace `_run_async`'s deprecated `get_event_loop()` call.
- The placeholder `KnowledgeService` in `__init__.py` is your starting point — EPIC-002 turns it into a real class composing `NamespaceManager`.

## Notes for QA (carry-forward to EPIC-002)

- Your independent re-run protocol is exactly what I want. Keep doing it.
- The engineer's done reports are honest; you can trust them but should still re-verify critical claims.
- Add to your QA Gate for EPIC-002: **after `NamespaceManager.delete()`, attempt to immediately `create()` the same namespace name** — this catches dangling Kuzu file handles.

## Sign-off

EPIC-001: **PASSED**. Engineer and QA both performed well. Proceeding to EPIC-002.
