# REVIEW: EPIC-002 — Storage Layer & Namespace Lifecycle

> Reviewer: @architect
> Date: 2026-04-19
> Reviewed: engineer's done report + qa report + independent re-runs.

## Verdict: **PASSED**

Proceed to EPIC-003.

## Cross-checks performed (independent of engineer & QA)

- [x] **All ADRs honored.** ADR-01, 03, 04, 05, 12 all enforced as planned. ADR-12 boundary cases (uppercase, leading hyphen, leading underscore, length 64+) all correctly rejected by `validate_id`.
- [x] **No scope creep.** Engineer stuck to EPIC-002 surface. Carry-forward fixes from EPIC-001 included as expected.
- [x] **Acceptance criteria objectively met.** Re-ran the full lifecycle independently:
  - `create_namespace("archtest")` → ok, `embedding_model="BAAI/bge-small-en-v1.5"`, `embedding_dimension=384` (frozen at create time per spec)
  - duplicate → `NamespaceExistsError` (409 candidate)
  - `"Bad Name!"` → `InvalidNamespaceIdError` (400 candidate)
  - `list_namespaces()` reflects state
  - `delete_namespace()` → `True`; immediate re-create succeeds (Kuzu cache eviction works)
  - `import_folder` and `query` both raise `NotImplementedError` (placeholders for EPIC-003/004)
- [x] **Test coverage adequate.** 37 namespace tests + 18 smoke tests = **55 passing in 1.73s**. Coverage of `namespace.py` 93%, `service.py` 100% (per QA's measurement).
- [x] **Carry-forward fix A confirmed.** `dashboard/knowledge/graph/core/graph_rag_query_engine.py:49` uses `asyncio.get_running_loop()` with explanatory comments. Old `get_event_loop()` is gone.
- [x] **Carry-forward fix B confirmed.** `dashboard/knowledge/graph/index/kuzudb.py:2149` and `:2183` both have `if not hasattr(self, "__pydantic_fields_set__"): return` guards in `close_connection` and `__del__`.
- [x] **No regressions.** `pytest dashboard/tests/ -k "not knowledge" --no-header -q` → **568 passed** (identical to EPIC-001 baseline; 88 failures + 18 errors are pre-existing).
- [x] **Lazy imports preserved.** `python -X importtime -c "from dashboard.knowledge.namespace import NamespaceManager"` does NOT load kuzu/chromadb/sentence_transformers/markitdown/anthropic.

## Specific items requiring fix (none)

The two MINOR defects QA flagged are appropriately deferred:

1. **`pagerank_score_threshold` env var underdocumented.** Defer to EPIC-007 (documentation pass).
2. **Chroma per-namespace path test is path-only (no real Chroma instantiation).** Defer to EPIC-003 — ingestion will actually exercise Chroma writes, providing the integration coverage automatically.

## Process note (for the engineer)

QA caught that your done report stated "34 namespace tests + 21 smoke = 55" but the actual breakdown is **37 + 18 = 55**. Total is correct; breakdown was inverted. **For EPIC-003, when you cite test counts, run `pytest --collect-only -q | tail -5` to get the exact number per file before quoting.** This isn't a credibility issue — the work is sound — but accurate reporting builds trust faster.

## Blockers for next EPIC

None. EPIC-003 starts with:
- A working `NamespaceManager.create/get/list/delete/update_stats/append_import` API
- A working `KnowledgeService` with namespace lifecycle wired
- `KuzuLabelledPropertyGraph.for_namespace(ns)` resolves to the right path
- `init_vector_store_for_namespace(ns)` resolves to the right path

## Notes for engineer (carry-forward to EPIC-003)

- The `Ingestor` you build will call `NamespaceManager.update_stats(...)` and `append_import(...)` — both already implemented and tested. Use them.
- `JobManager` should persist job state to `~/.ostwin/knowledge/{ns}/jobs/{job_id}.jsonl` (per ADR-08). When the dashboard restarts mid-job, jobs in `running` state should be marked `interrupted` on next startup (minor — can ship in EPIC-007 hardening).
- The fixture pattern `NamespaceManager(base_dir=tmp_path)` you established is the correct approach for test isolation. Use it consistently for ingestion tests.

## Notes for QA (carry-forward to EPIC-003)

- Your independent concurrent-create probe (using `ThreadPoolExecutor`) is exactly the kind of black-box check I want — duplicating engineer's tests with a different mechanism. Keep doing this.
- For EPIC-003: add a probe that **kills the dashboard mid-import** (subprocess kill) and verifies the job is correctly marked `interrupted` on restart. This is the rentrancy gate.
- Always re-run the regression suite (`-k "not knowledge"`) every EPIC. If pass count regresses below 568, it's a hard fail.

## Sign-off

EPIC-002: **PASSED**. Storage layer is solid. Proceeding to EPIC-003 (Ingestion Pipeline).
