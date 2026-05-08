# REVIEW: EPIC-003 — Ingestion Pipeline (with v2 fix cycle)

> Reviewer: @architect
> Date: 2026-04-19
> Reviewed: engineer-v1 done report + qa-v1 report + engineer-v2 done report + qa-v2 report + my own independent re-runs.

## Verdict: **PASSED** (after one fix cycle)

Proceed to EPIC-004.

## Cycle summary

| Round | Engineer outcome | QA outcome | Verdict |
|---|---|---|---|
| v1 | All tasks complete; 107 knowledge tests pass; bypass-RAGStorage decision; chromadb mocked due to broken env | 3 MAJOR defects (path helpers ignore base_dir; force=True doubles stats; chromadb env broken) + APPROVE-WITH-NOTES | architect: **CHANGES-REQUESTED** combined with user-mandated chromadb→zvec swap |
| v2 (fix) | All 3 changes shipped; chromadb gone; new `vector_store.py` with zvec; instance methods on NamespaceManager; force-no-double-count regression test added | All v1 majors closed; 1 new MINOR (concurrent auto-create race, deferred to EPIC-007); APPROVE | architect: **PASSED** |

## Cross-checks performed (independent of engineer & QA)

- [x] **chromadb gone from `requirements.txt`** — verified.
- [x] **No live `import chromadb` anywhere in `dashboard/knowledge/`** — only docstring/comment references explaining the migration.
- [x] **All 116 knowledge tests pass** in 21.72s (smoke 18 + namespace 37 + ingestion 61).
- [x] **Zero regressions** — `pytest -k "not knowledge"` still 568 passed, identical to EPIC-002 baseline.
- [x] **Real end-to-end ingestion works with real zvec + real `BAAI/bge-small-en-v1.5` embedder** — independent run completed in 17.2s; result `{files_total: 5, files_indexed: 5, chunks_added: 5, errors: []}`.
- [x] **NO_LEAK: OK** — independent verification confirms `~/.ostwin/knowledge/arch-test` is NOT created when `base_dir=tmp_path`.
- [x] **`NamespaceManager` instance methods** (`namespace_dir`, `kuzu_db_path`, `vector_dir`, `manifest_path`) exist and resolve relative to `self._base`.
- [x] **`force=True` no longer doubles stats** — engineer's regression test plus QA's three-times-no-drift test both pass.
- [x] **ADR-04 (REVISED to zvec)** correctly implemented — zvec used; chromadb dep dropped.

## NEW issue found by my own probe (not blocking, but flag for EPIC-004)

**ZVEC-LIVE-1 (HIGH for EPIC-004)**: Opening a *second* `NamespaceVectorStore` pointing at the same `vector_dir` while the first instance is still alive in the same process fails with `ValueError: path validate failed: path[...] is existed`. This happens because:

1. `_open_or_create` tries `zvec.open(path)` first — but `zvec.open` may raise on some condition (handle conflict, lock mismatch) other than "path missing"
2. The catch falls through to `zvec.create_and_open(path, schema)` which then fails because the path already exists on disk

**Why QA missed it**: QA's e2e probe and the engineer's tests reuse the same `Ingestor._stores[namespace]` cached instance, so they only ever exercise the single-handle path.

**Why it matters for EPIC-004**: The query engine will want a `NamespaceVectorStore` for the same path used by the Ingestor. Three options:

1. **Share the Ingestor's cache** — query engine asks `Ingestor` for its store. Tightly couples them, but simple.
2. **Centralize the cache in `KnowledgeService`** — both `Ingestor` and the query path pull from `service._vector_stores[ns]`. Cleaner.
3. **Implement open-on-demand, close-after-use pattern** — costly per query, simplest from a state perspective.

**Recommend Option 2** for EPIC-004. Also fix `_open_or_create` to be more discriminating: only fall through to `create_and_open` when `zvec.open` raised because the path doesn't exist, not on every `Exception`.

Additionally, on temp-dir cleanup (`shutil.rmtree`), zvec emits RocksDB "No such file or directory" errors. This is a `__del__` race — the handle isn't closed before the directory is removed. Add an explicit `close()` method on `NamespaceVectorStore` and call it from a `KnowledgeService.shutdown()` (and from test fixtures' teardown).

## Specific items requiring fix (none — all carry-forward)

1. **ZVEC-LIVE-1** (above) — must address in EPIC-004 design before query engine gets cached store.
2. **Concurrent auto-create race** in `import_folder` (QA v2 Minor 1) — same root-cause class as EPIC-003 v1 Minor 5; defer to EPIC-007 hardening.
3. **Vietnamese strings in `graph/prompt.py`** — still inert; EPIC-007 cleanup.
4. **`asyncio.get_event_loop` deprecation** — already fixed in EPIC-002, just monitor.

## Process notes

- **Engineer v1 → v2 transition was clean.** Engineer correctly (a) accepted all QA feedback, (b) implemented the user-mandated zvec swap, (c) added new regression tests proving the fix. No defensiveness, no scope creep beyond the fix list.
- **QA caught both v1 majors with targeted probes** (mock-fidelity audit + manifest-state inspection). The Phase 2 chromadb-env fix attempt was particularly useful — it proved chromadb COULD work with an opentelemetry upgrade, which informed the user's decision to swap to zvec entirely (cleaner path).
- **My own architect probe surfaced ZVEC-LIVE-1** that neither engineer nor QA caught. This validates the three-layer review model: even with thorough QA, the architect's independent probe finds new failure modes. Keep this discipline.

## Notes for engineer (carry-forward to EPIC-004)

- Implement the centralized `_vector_stores` cache in `KnowledgeService` (Option 2 above). Both `Ingestor` and the new query engine pull from this cache.
- Add `NamespaceVectorStore.close()` and call it from `KnowledgeService.shutdown()`.
- Tighten `_open_or_create`: distinguish "path doesn't exist" (genuine create-needed) from "open failed for another reason" (re-raise).
- For multi-step query planning: the current `query_executioner.py` has the right shape but currently calls `engine.get_nodes(...)`. Wire that to your new `NamespaceVectorStore.search(...)` in EPIC-004.
- Anthropic-mocked test pattern from EPIC-003 (mock `KnowledgeLLM.extract_entities`) generalizes — use it for `KnowledgeLLM.plan_query` and `KnowledgeLLM.aggregate_answers` in EPIC-004 tests.

## Notes for QA (carry-forward to EPIC-004)

- Write your own independent e2e probe with a fresh `NamespaceVectorStore` instance (not the cached one) — that's how I caught ZVEC-LIVE-1. Do this for the query path too: run a query, then instantiate a fresh `NamespaceVectorStore` and try `count()`.
- Performance budget for EPIC-004: `mode=raw` p95 < 500ms on a 50–100 chunk namespace.
- Verify `mode=summarized` returns a non-empty `answer` ONLY when Anthropic available. With unset key: `answer=None`, `warning` field present. No crash.
- Test the cache-eviction story: `delete_namespace(ns)` MUST evict from `_vector_stores[ns]` AND from any Kuzu cache. Otherwise the next `create_namespace(ns)` re-imports into the still-cached old vectors.

## Sign-off

EPIC-003: **PASSED** (post-fix). Ingestion pipeline is solid, real-zvec-backed, regression-tested. Proceeding to EPIC-004 (Query Engine).
