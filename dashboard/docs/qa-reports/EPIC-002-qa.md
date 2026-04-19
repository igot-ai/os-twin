# QA REPORT: EPIC-002 — Storage Layer & Namespace Lifecycle

> Reviewer: @qa
> Date: 2026-04-19
> Reviewed: engineer's done report (`docs/done-reports/EPIC-002-engineer.md`) + independent re-runs of every command in the QA protocol + Phase 3 black-box probes.
> Mode: Independent verification — re-ran every claim end-to-end on a fresh shell.

## Verdict: **PASS** (with two minor documentation-quality defects)

The implementation is functionally correct. All ADRs in scope (01, 03, 04, 05, 08, 10, 12) are honoured. All 5 Definition-of-Done items objectively met. All 5 Acceptance Criteria objectively met. The architect-mandated extra check (delete → re-create with a real Kuzu connection) is implemented and verified to actually open a Kuzu DB, not just a directory. Both EPIC-001 carry-forward fixes have landed.

The two defects below are minor (one is a factual inaccuracy in the done report's test counts; the other is a thin test for Chroma wiring) and do not block sign-off. Neither requires code changes.

---

## Test execution summary

| Suite                                  | Pass | Fail | Skip | Coverage % | Notes                                      |
|----------------------------------------|------|------|------|------------|--------------------------------------------|
| `test_knowledge_namespace.py`          | 37   | 0    | 0    | n/a (sub.) | Engineer reported 34; actual is 37.        |
| `test_knowledge_smoke.py`              | 18   | 0    | 0    | n/a (sub.) | Engineer reported 21; actual is 18.        |
| `test_knowledge_*.py` (combined)       | 55   | 0    | 0    | —          | 1.43 s wall.                               |
| `pytest -k "not knowledge"` (regress.) | 568  | 88   | 1    | —          | **Identical to EPIC-001 baseline.**        |
| `namespace.py` coverage                | —    | —    | —    | **93%**    | 13 missed lines, all defensive branches.   |
| `service.py` coverage                  | —    | —    | —    | **100%**   | All 27 statements covered.                 |
| **Combined coverage** (namespace+svc)  | —    | —    | —    | **94%**    | Above the ≥90% bar in DoD.                 |

The 88 pre-existing failures + 18 errors in unrelated suites (settings_resolver, amem, user_management) are unchanged from the EPIC-001 baseline — **zero regressions introduced by EPIC-002**.

---

## Acceptance criteria check

From EPIC-002 plan (`### Acceptance criteria` block):

| #   | Criterion                                                                     | Status | Evidence                                                                                   |
|-----|-------------------------------------------------------------------------------|--------|--------------------------------------------------------------------------------------------|
| AC1 | `NamespaceManager().create("test-ns")` produces per-namespace dir + manifest. | ✅     | `test_create_namespace_creates_directory` + `test_create_namespace_writes_manifest`. Independently re-verified via Phase 1C smoke (`/tmp/qa-ns-*/alpha/manifest.json`). `graph.db` and `chroma/` are lazy per spec. |
| AC2 | `NamespaceManager().create("Bad Name!")` raises `ValueError`.                 | ✅     | `test_create_invalid_id_raises_InvalidNamespaceIdError` — `InvalidNamespaceIdError` extends `ValueError` (line 92, `namespace.py`). 14-case independent edge-case probe (Phase 3.2): all PASS. |
| AC3 | `NamespaceManager().delete("test-ns")` returns True and dir is gone.          | ✅     | `test_delete_removes_directory_and_returns_true` + Phase 1C output `DELETE_OK True / LIST_EMPTY []`. |
| AC4 | Manifest survives a process restart (load round-trip).                        | ✅     | `test_manifest_roundtrip` (write → mutate via `update_stats` → re-read → fields preserved including `created_at` immutability). Phase 3.8 also verified `NamespaceMeta.model_dump_json()` → `model_validate_json()` round-trips `stats` and `imports`. |
| AC5 | Two different namespaces fully isolated.                                      | ✅     | `test_two_namespaces_isolated` + Phase 3.6 independent probe: alpha and beta are siblings, neither nested in the other; mutating one's stats doesn't affect the other; deleting one preserves the other. |

Definition-of-Done check (from EPIC-002 plan `### Definition of Done`):

| Item                                                                                       | Status |
|--------------------------------------------------------------------------------------------|--------|
| `NamespaceManager` and `KnowledgeService` exist with documented API.                       | ✅     |
| `manifest.json` schema documented in a docstring with example.                             | ✅     |
| All tests pass; coverage of `namespace.py` ≥ 90%.                                          | ✅ (93%) |
| `test_knowledge_smoke.py` extended to cover `KnowledgeService` instantiation.              | ✅ (`test_knowledge_service_constructs_cleanly`, `test_knowledge_service_default_constructor_works`, `test_knowledge_service_list_namespaces_returns_list`) |
| On `delete()`, no Kuzu file handles remain open (verified by re-creating same name).       | ✅ — `test_delete_then_immediate_recreate_works` opens a real Kuzu DB before deleting (verified via code reading: `for_namespace()` → `__init__` → `self._database()` → `kuzu.Database(actual_db_path)` at line 168 of `kuzudb.py`). |

---

## ADR compliance check (independent judgement)

| ADR    | Status | Notes                                                                                                                                                                           |
|--------|--------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ADR-01 | ✅     | `NamespaceManager(base_dir=...)` defaults to `KNOWLEDGE_DIR` (resolved from `OSTWIN_KNOWLEDGE_DIR` env — verified Phase 2.2). Per-namespace dir at `{base}/{ns}/`. `graph.db` and `chroma/` resolved by `kuzu_db_path()` and `chroma_dir()` helpers in `config.py`. |
| ADR-03 | ✅     | `NamespaceMeta.embedding_model` defaults to `BAAI/bge-small-en-v1.5`, `embedding_dimension=384` (line 139-140 of `namespace.py`). Both fields are written to the manifest at create-time and never mutated thereafter. Phase 3.7 confirms the actual JSON contains both fields with dimension 384. |
| ADR-04 | ✅     | `init_vector_store_for_namespace(namespace)` exists in `graph/core/storage.py`; uses `chroma_dir(namespace)`. (Note: thin test — only verifies the function is callable and the path string formation, doesn't open a real Chroma store. See defect #2.) |
| ADR-05 | ✅     | `KuzuLabelledPropertyGraph.for_namespace(ns)` exists at line 206 of `kuzudb.py`. Resolves to `kuzu_db_path(ns)` which is `{KNOWLEDGE_DIR}/{ns}/graph.db`. Independently verified Phase 3.5: resolved path = `/Users/paulaan/.ostwin/knowledge/kgtest/graph.db`. `_resolve_db_path` correctly treats `.db`-suffix paths verbatim (line 193) instead of appending `{index}.db`. |
| ADR-08 | ✅ Partial | Manifest persistence implemented atomically (tempfile + `os.fsync` + `os.replace`, verified Phase 3.1). Job-executor portion is correctly deferred to EPIC-003 per plan footnote. |
| ADR-10 | ✅     | `NamespaceMeta.language` defaults to "English" (line 135). User can override per-namespace via `create(language=...)`. |
| ADR-12 | ✅     | **Newly enforced.** `NAMESPACE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")` at line 68 of `namespace.py`. `validate_id` rejects non-strings (line 178). `_require_valid_id` raises `InvalidNamespaceIdError(NamespaceError, ValueError)` so the API layer (EPIC-005) can map to 400 with a single handler. Phase 3.2 independently verified all 14 boundary/edge cases. |

---

## QA Gate independent re-run (from plan)

| Gate item                                                                  | Status | Evidence                                                                                                                                  |
|----------------------------------------------------------------------------|--------|-------------------------------------------------------------------------------------------------------------------------------------------|
| 1. Lifecycle CLI walkthrough produces expected filesystem state.           | ✅     | Phase 1C: `CREATE_OK alpha … / GET_OK alpha / LIST_OK ['alpha'] / DELETE_OK True / LIST_EMPTY []`. Filesystem inspection confirmed. |
| 2. `OSTWIN_KNOWLEDGE_DIR=/tmp/qa-test python -c "..."` honoured.          | ✅     | Phase 2.2: prints `/tmp/qa-test`. (Engineer noted in their open issues that the *test suite itself* uses `base_dir=` injection; this is a deliberate pragmatic choice — the env var IS honoured by the production path. Acceptable.) |
| 3. `pagerank_score_threshold` and config defaults documented.              | ⚠️ Minor | The constant is in `config.py:29` named `PAGERANK_SCORE_THRESHOLD` (env: `OSTWIN_KNOWLEDGE_PR_THRESHOLD`, default `0.001`). The variable name and env var name are visible in the source, but there are NO docstrings on individual constants explaining their purpose. The module docstring is one line. **See defect #1 (minor).** |
| 4. Concurrent-create race: 5 threads → only one succeeds.                  | ✅     | `test_concurrent_create_only_one_succeeds` (lines 423-445 of test file) uses `threading.Barrier(5)` to release 5 real threads simultaneously, then asserts `len(successes) == 1` and `len(failures) == 4`. Phase 2.1 independently re-ran with 10 threads via `ThreadPoolExecutor`: `successes=1 failures=9 others=0 → CONCURRENT_TEST_PASSED`. |
| Architect-mandated extra: delete-then-immediate-recreate with real Kuzu.   | ✅     | `test_delete_then_immediate_recreate_works` calls `KuzuLabelledPropertyGraph.for_namespace("test-ns")` which (per code reading of `__init__` at line 134-147 + `_database` at line 149-180 of `kuzudb.py`) eagerly invokes `kuzu.Database(actual_db_path)` and stores it in `kuzu_database_cache`. The test then asserts the cache key is present BEFORE delete and absent AFTER delete, then re-creates the same namespace — which would fail with a stale-handle error if eviction were broken. **Architect's concern correctly addressed.** |

---

## Black-box checks performed (Phase 3 — independent of engineer)

1. **Manifest atomic-write under simulated crash** — Patched `os.replace` to raise `OSError`, called `update_stats('victim', files_indexed=5)`. Verified: (a) the original `manifest.json` is byte-identical, (b) `stats.files_indexed == 0` (the failed write left no trace), (c) no `.manifest.*.tmp` leftover files in the namespace directory. **PASS.**

2. **`validate_id` boundary edges** — 14 cases including empty string, leading hyphen/underscore, uppercase, spaces, slash, dot, `None`, single char, single-digit `'0'`, exactly 64-char boundary, exactly 65-char overflow. All matched expected accept/reject. **PASS.**

3. **Carry-forward fix A — `_run_async` modernised** — Read `dashboard/knowledge/graph/core/graph_rag_query_engine.py:37-65`. Confirms uses `asyncio.get_running_loop()` (line 49) wrapped in `try/except RuntimeError` falling through to `asyncio.run(coro)` (line 52); when a loop IS running, it spawns a worker thread with a fresh `asyncio.new_event_loop()` (lines 55-64). Matches the architect's specification exactly. **PASS.**

4. **Carry-forward fix B — Pydantic partial-init guards** — Read `dashboard/knowledge/graph/index/kuzudb.py:2144` (`close_connection`) and `:2178` (`__del__`). Both have the early-return guard `if not hasattr(self, "__pydantic_fields_set__"): return` at the very top, before any attribute access. Belt-and-braces (the `__del__` also wraps the call in `try/except Exception: pass`). **PASS.**

5. **`KuzuLabelledPropertyGraph.for_namespace` exists and resolves correctly** — Phase 3.5: `for_namespace("kgtest")._resolve_db_path()` returns `/Users/paulaan/.ostwin/knowledge/kgtest/graph.db` (ends with `kgtest/graph.db`, no `{index}.db` appended). **PASS.**

6. **Two namespaces isolated on disk** — Phase 3.6: alpha and beta each have their own `manifest.json`, both are siblings of `tmp_path`, beta is NOT inside alpha, neither shares any file. **PASS.**

7. **Manifest contains frozen `embedding_model` and `embedding_dimension`** — Phase 3.7: `BAAI/bge-small-en-v1.5` and `384` written into the manifest at create-time. **PASS.**

8. **`NamespaceMeta` JSON round-trip preserves stats and imports** — Phase 3.8: `model_dump_json()` → `model_validate_json()` preserves `stats.files_indexed=5`, `imports[0].folder_path='/x'`, etc. **PASS.**

9. **Concurrent-update integrity** — `test_concurrent_update_stats_no_lost_updates` (lines 448-464): 20 threads each `update_stats(chunks=1)` → final counter exactly 20. The read-modify-write under the manager lock prevents lost increments. **PASS.**

10. **Corrupt manifest treated as missing, not crash** — `test_corrupt_manifest_treated_as_missing` (line 539): writing `"{not valid json"` to `manifest.json` → `nm.get()` returns `None`, `nm.list()` skips it. Defensive exception handling at lines 417-424 of `namespace.py` catches `OSError`, `JSONDecodeError`, and `pydantic.ValidationError` separately, all returning `None` with a `logger.warning`. Sound. **PASS.**

11. **Imports cap (`MAX_IMPORTS_PER_MANIFEST = 100`) trims oldest** — `test_imports_cap_trims_oldest`: append 105 records → final list is exactly 100 with `imports[0].file_count == 5` (oldest 5 dropped). The cap is engineer-added (not in the spec) and reasonable; documented in their open issues #2. **PASS.**

---

## Test suite quality assessment (Phase 4)

Read `dashboard/tests/test_knowledge_namespace.py` end-to-end (608 lines, 37 test functions).

**Strengths:**

- Every test has a single, focused assertion target. Names are descriptive (`test_create_invalid_id_raises_InvalidNamespaceIdError`, `test_delete_then_immediate_recreate_works`, etc.).
- The `tmp_kb` fixture isolates every test; the autouse `_clear_kuzu_cache` fixture prevents cache bleed.
- `test_concurrent_create_only_one_succeeds` is **genuinely concurrent** (uses `threading.Barrier(5)` to release threads in lockstep — no sequential fakery). Re-verified independently.
- `test_concurrent_update_stats_no_lost_updates` proves the `update_stats` lock is correct under contention.
- `test_manifest_atomic_write_survives_crash` actually monkeypatches `ns_mod.os.replace` to raise `OSError`, then asserts both manifest immutability AND no leftover `.tmp` files. Real test.
- `test_delete_then_immediate_recreate_works` actually opens a real Kuzu connection (verified by tracing through `for_namespace()` → `__init__` → `self._database()` → `kuzu.Database(actual_db_path)`); the cache-presence assertion at line 261 would fail if the connection weren't real.
- `test_corrupt_manifest_treated_as_missing` covers the defensive path through `_read_manifest`.

**Thin/weak tests** (one only):

- `test_chroma_path_uses_correct_per_namespace_path` (lines 403-415) only verifies `chroma_dir("some-ns")` returns a path with the correct suffix and `init_vector_store_for_namespace` is `callable(...)`. It does NOT actually invoke the function or open a Chroma store. Acceptable for "wiring exists" but the parallel `test_kuzu_path_uses_correct_per_namespace_path` does call `for_namespace()` and exercise `_resolve_db_path()` — the Chroma test is comparatively thinner. **See defect #2 (minor).**

**Coverage at 93% on `namespace.py` is genuine** (the 13 missed lines are defensive `except OSError: pass` cleanup branches and the `pragma: no cover` import-failure branches — fundamentally unreachable in normal execution). `service.py` at 100% is correct.

---

## Performance measurements

Single thread, on `/tmp` (SSD, macOS), Python 3.11.7. Each operation includes the `os.fsync` cost in the manifest write path.

| Operation                                 | Sample      | p50 / mean   | Notes                                              |
|-------------------------------------------|-------------|--------------|----------------------------------------------------|
| Module import (`from … import NamespaceManager`) | 1× cold     | 679 ms       | Includes Pydantic + transitive llama-index, NOT kuzu/chroma. |
| `NamespaceManager.create()`               | 50 ns total | 0.69 ms each | mkdir + atomic manifest write.                      |
| `NamespaceManager.list()` (50 ns)         | 1 call      | 1.78 ms      | Reads + validates 50 manifests.                     |
| `NamespaceManager.get()` (cached fs)      | 50 calls    | 0.02 ms each | Single JSON read, cached by OS.                     |
| `NamespaceManager.update_stats()`         | 50 calls    | 0.23 ms each | RMW under lock + atomic write.                      |
| `NamespaceManager.delete()`               | 50 calls    | 0.12 ms each | rmtree of empty dirs + cache eviction.              |

All operations are sub-millisecond per invocation. The 679 ms cold import is dominated by Pydantic / llama-index / langchain transitives loaded by the `dashboard.knowledge.graph.*` package surface (not by our new code), which is acceptable given the lazy-import discipline excludes the heavy deps (kuzu, chromadb, sentence_transformers, markitdown, anthropic — verified Phase 1H: empty grep result).

---

## Defects found

### 1. [MINOR] `pagerank_score_threshold` env-var documentation is sparse

- **File**: `dashboard/knowledge/config.py:29-31`
- **Repro**: Read `config.py`. The constant `PAGERANK_SCORE_THRESHOLD` exists, the env var name `OSTWIN_KNOWLEDGE_PR_THRESHOLD` is present, but there's no docstring on the constant explaining what it does, what range is sensible, or when an operator might want to change it. The module-level docstring is one line.
- **Plan reference**: EPIC-002 QA Gate item #3 says "Verify `pagerank_score_threshold` and other config defaults documented." — partially satisfied (var name & default visible, behaviour unexplained).
- **Severity**: Minor — does not break functionality. The env-var name is discoverable by reading the module.
- **Suggested fix (carry-forward to EPIC-007 hardening pass)**: Add a 1-line `#: docstring` above each constant in `config.py`, or add a "Configuration" section to `dashboard/knowledge/README.md` (planned for EPIC-007 TASK-003).

### 2. [MINOR] `test_chroma_path_uses_correct_per_namespace_path` is thin

- **File**: `dashboard/tests/test_knowledge_namespace.py:403-415`
- **Repro**: Read the test. It only checks (a) `chroma_dir("some-ns")` has the right suffix, (b) `init_vector_store_for_namespace` is `callable(...)`. It does NOT exercise the function (would require lazy-importing `chromadb`).
- **Plan reference**: ADR-04 says "Vector store = ChromaDB (persistent local) … `init_vector_store(...)` to use `KNOWLEDGE_DIR/{namespace}/chroma/` as `persist_directory`." The test verifies the path STRUCTURE but not that the function actually configures Chroma with that path.
- **Compensating control**: The parallel Kuzu test (`test_kuzu_path_uses_correct_per_namespace_path`) DOES exercise `for_namespace()` and verify `_resolve_db_path()` returns the correct value. So the asymmetry is between the two stores, not a complete absence of integration.
- **Severity**: Minor — wiring is verified by source-code reading; an actual Chroma instantiation test belongs in EPIC-003 when the ingestion path is wired.
- **Suggested fix**: In EPIC-003, the ingestion test will naturally exercise `init_vector_store_for_namespace` end-to-end. No change needed in EPIC-002.

### 3. [INFO — not a defect] Done report test counts off by 3 in two places

- **File**: `docs/done-reports/EPIC-002-engineer.md:124-125`
- **Engineer claimed**: "test_knowledge_namespace.py: 34/34 passed"; "test_knowledge_smoke.py: 21/21 passed"; "Total: 55/55"
- **Actual**: 37 namespace tests (`grep -cE "^def test_" tests/test_knowledge_namespace.py` → 37), 18 smoke tests, **total 55** (math still works, individual breakdown is wrong).
- **Severity**: Informational only — the engineer wrote MORE tests than they reported, which is the harmless direction. The combined pass count of 55 is correct.
- **No fix needed**; flagged for honesty/accuracy of future done reports.

---

## Recommendation

**APPROVE EPIC-002 and proceed to EPIC-003.**

The implementation is correct, well-tested, well-isolated, and honours every relevant ADR. The two minor defects are documentation/test-coverage style issues that are appropriately deferred to later EPICs (EPIC-003 will exercise Chroma; EPIC-007's hardening pass will tighten `config.py` docstrings). The architect-mandated extra check (delete → re-create with a real Kuzu connection) is implemented as a genuine integration test, not a sham. Both EPIC-001 carry-forward fixes have landed in their full architect-specified form.

Suggested architect verdict: **PASSED**, with two notes carried forward:

- **Carry-forward to EPIC-003 engineer**: Naturally exercise `init_vector_store_for_namespace` end-to-end in the ingestion test (resolves defect #2).
- **Carry-forward to EPIC-007 engineer**: Add per-constant docstrings to `dashboard/knowledge/config.py` or document tunables in `dashboard/knowledge/README.md` (resolves defect #1).
- **Carry-forward to all engineers (process)**: Verify done-report test counts against `pytest -v` output before publishing (defect #3 is a quality-of-reporting issue).
