# QA REPORT: EPIC-003 v2 — Fix-verification (chromadb → zvec + Defects 1, 2)

> Author: @qa
> Date: 2026-04-19
> Cycle: v2 — fix verification of CHANGES-REQUESTED from `EPIC-003-qa.md`
> Inputs: `docs/qa-reports/EPIC-003-qa.md` (v1), `docs/done-reports/EPIC-003-engineer-v2.md`,
>         `docs/knowledge-mcp.plan.md` (with revised ADR-04), `dashboard/knowledge/vector_store.py`,
>         full `dashboard/knowledge/` and `dashboard/tests/test_knowledge_*.py`.

---

## Verdict: **PASS**

All three mandated changes are shipped, all regression tests exist and actually
fail-when-they-should pass, and my independent end-to-end probe (real zvec +
real `BAAI/bge-small-en-v1.5` embedder, no mocks at all) reproduced the
correctness invariants the engineer claims:

- Idempotency holds (2nd import: 0 added, 5 skipped, 0.51s).
- Force does not double-count (3rd import: `files_indexed=5, chunks=5,
  vectors=5` — *not* 10).
- No leak: `~/.ostwin/knowledge/qa-real-test` was never created when
  `base_dir=tmp_path`.
- zvec on-disk store has the correct count via an independent `count()` call.

The two MAJOR defects from v1 (path-isolation and force-double-count) are
**closed**. The MAJOR chromadb-environment defect is **closed-by-removal**
(chromadb is gone). The remaining v1 minors are unchanged and explicitly
deferred to EPIC-007.

One **new minor defect** was found by Phase H (concurrent same-namespace
import raises uncaught `NamespaceExistsError`) — same root cause class as
v1 Minor 5; documented below for EPIC-007.

---

## CHANGE 1 — chromadb removed, zvec wired in

| Check | Command | Result |
|---|---|---|
| (A) chromadb gone from requirements | `grep -nE "chromadb\|llama-index-vector-stores-chroma" requirements.txt` | **EMPTY** ✅ (only a comment line referencing the removal) |
| (B) No live chromadb imports | `grep -rE "^[[:space:]]*(import chromadb\|from chromadb)" knowledge/` | **EMPTY** ✅ |
| (C) New module `vector_store.py` with documented surface | `inspect.signature(...)` for 6 methods | All present ✅ |
| (D) Public exports include `NamespaceVectorStore`, `VectorHit` | `dashboard.knowledge.__all__` | Both present ✅ |
| (E) Lazy zvec import (NOT loaded at module top) | `python -X importtime` filter `\| grep " zvec$"` | **EMPTY** ✅ — `import zvec` is inside method bodies (verified via reading `vector_store.py`) |

Method signatures confirmed:
```
add_chunks: (self, chunks: 'Iterable[dict]') -> 'int'
has_file_hash: (self, file_hash: 'str') -> 'bool'
delete_by_file_hash: (self, file_hash: 'str') -> 'int'
search: (self, query_embedding: 'list[float]', top_k: 'int' = 10,
         category_id: 'Optional[str]' = None) -> 'list[VectorHit]'
count: (self) -> 'int'
count_by_file_hash: (self, file_hash: 'str') -> 'int'
```

Public exports (sorted): `EMBEDDING_DIMENSION, EMBEDDING_MODEL, FileEntry,
GraphRAGExtractor, GraphRAGQueryEngine, GraphRAGStore, ImportRecord,
IngestOptions, Ingestor, InvalidNamespaceIdError, JobEvent, JobManager,
JobState, JobStatus, KNOWLEDGE_DIR, KnowledgeEmbedder, KnowledgeLLM,
KnowledgeService, KuzuLabelledPropertyGraph, LLM_MODEL, NamespaceError,
NamespaceExistsError, NamespaceManager, NamespaceMeta, NamespaceNotFoundError,
NamespaceStats, NamespaceVectorStore, TrackVectorRetriever, VectorHit`.

`RAGStorage` is correctly **dropped** from exports.

**CHANGE 1 verdict: ✅ PASS**

---

## CHANGE 2 — Path helpers respect `NamespaceManager.base_dir`

| Check | Result |
|---|---|
| (A) Instance methods exist on `NamespaceManager` | All 4 present ✅ |
| (B) Paths actually rooted at `base_dir` | `PATHS_OK` ✅ |

Signatures:
```
namespace_dir(self, namespace: 'str') -> 'Path'
kuzu_db_path(self, namespace: 'str') -> 'Path'
vector_dir(self, namespace: 'str') -> 'Path'
manifest_path(self, namespace: 'str') -> 'Path'
```

For `NamespaceManager(base_dir=tmp_path)`:
- `nm.namespace_dir('a')` → `tmp_path/a`
- `nm.kuzu_db_path('a')` → `tmp_path/a/graph.db`
- `nm.vector_dir('a')` → `tmp_path/a/vectors`
- `nm.manifest_path('a')` → `tmp_path/a/manifest.json`

Three regression tests in `TestPathRespectsBaseDir` exercise this end-to-end:
1. `test_namespace_paths_respect_base_dir` — pure unit on the four methods.
2. `test_ingest_writes_to_base_dir_only` — `KnowledgeService.import_folder` flow,
   asserts `not (KNOWLEDGE_DIR / "leak-test").exists()` after the run.
3. `test_real_zvec_path_respects_base_dir` — real `_NamespaceStore` + real zvec,
   asserts `tmp_path / "zvec-leak-test" / "vectors"` exists AND
   `KNOWLEDGE_DIR / "zvec-leak-test"` does NOT.

All 3 PASS in 1.56s. Test #3 is the test that would have failed pre-fix.

**CHANGE 2 verdict: ✅ PASS**

---

## CHANGE 3 — `force=True` does not double-count

Two regression tests in `TestForceNoDoubleCount`:
1. `test_force_reprocess_does_not_double_stats` — initial + force, asserts
   `s1.files_indexed == s2.files_indexed`, same for `chunks` and `vectors`.
2. `test_force_reprocess_three_times_no_drift` — initial + 3 force-passes,
   asserts invariance on every iteration.

Both PASS in 2.53s.

`count_by_file_hash` exists on both `NamespaceVectorStore` and the wrapping
`_NamespaceStore`, signature `(file_hash: str) -> int`. The Ingestor's
per-file pipeline (see `ingestion.py`) calls it before delete + re-add to
roll back manifest stats by the right amount (`update_stats(files_indexed=-1,
chunks=-N, vectors=-N)`).

The fix is not just a manifest patch — it accurately removes the chunks
from zvec and recomputes them, so the on-disk store stays in sync with the
manifest counts (verified via the e2e probe — final count is 5 not 10).

**CHANGE 3 verdict: ✅ PASS**

---

## Phase A — Full suite + counts

| Suite | Pass | Fail | Skip | Wall | Notes |
|---|---:|---:|---:|---:|---|
| `test_knowledge_smoke.py` | 18 | 0 | 0 | 1.0s | Engineer's claim verified |
| `test_knowledge_namespace.py` | 37 | 0 | 0 | 0.7s | Engineer's claim verified |
| `test_knowledge_ingestion.py` (incl. 2 slow e2e) | 61 | 0 | 0 | 18.5s | +9 vs v1's 52 |
| **Total knowledge** | **116** | 0 | 0 | **19.0s** | Matches engineer's claim |
| `pytest -k "not knowledge"` (regression) | **568** | 88 | 1 | 11.8s | **Identical to EPIC-002 baseline** ✅ |

The 88 failures + 18 errors in the non-knowledge suite are pre-existing
(per v1 QA report; confirmed by re-reading the failure traces — settings
resolver, dashboard plan unrelated tests). No regression.

**Phase A verdict: ✅ PASS**

---

## Phase B — No-leak regression test

Exists, real, and actually checks the leak:

```
tests/test_knowledge_ingestion.py::TestPathRespectsBaseDir::test_namespace_paths_respect_base_dir PASSED
tests/test_knowledge_ingestion.py::TestPathRespectsBaseDir::test_ingest_writes_to_base_dir_only PASSED
tests/test_knowledge_ingestion.py::TestPathRespectsBaseDir::test_real_zvec_path_respects_base_dir PASSED
```

I read the source of `test_ingest_writes_to_base_dir_only` (lines 1043–1075):

```python
nm = NamespaceManager(base_dir=tmp_path)
ing = Ingestor(namespace_manager=nm, embedder=fake_embedder, llm=no_llm)
ing._get_store = lambda namespace: fake_store_factory(namespace)
jm = JobManager(base_dir=nm._base)
ks = KnowledgeService(namespace_manager=nm, job_manager=jm, ingestor=ing)
job_id = ks.import_folder("leak-test", str(FIXTURES))
_wait_for_state(jm, job_id, JobState.COMPLETED)
assert not (KNOWLEDGE_DIR / "leak-test").exists(), ...  # the leak check
assert (tmp_path / "leak-test" / "manifest.json").exists()
```

This test legitimately uses `base_dir=tmp_path`, runs an ingest, and
asserts no global leak. It would have failed pre-fix because chromadb's
`PersistentClient(path=str(chroma_dir(ns)))` ignored the manager's base_dir.
Test #3 (`test_real_zvec_path_respects_base_dir`) goes one step further
and uses the **real** `_NamespaceStore` (not a fake), which is the
strongest possible variant of this test.

**Phase B verdict: ✅ PASS — test exists, checks the real thing, and passes.**

---

## Phase C — Real e2e test

`TestRealE2E` exists with two `@pytest.mark.slow` tests:

```
tests/test_knowledge_ingestion.py::TestRealE2E::test_real_zvec_real_embedder_e2e PASSED
tests/test_knowledge_ingestion.py::TestRealE2E::test_real_e2e_force_reingest_stats_invariant PASSED
================ 3 passed, 58 deselected, 2 warnings in 13.68s =================
```

(13.68s includes one of the path tests + both e2e tests; the e2e portion
itself is ~12s on this MBP, matching engineer's claimed 12.83s.)

Both use real `BAAI/bge-small-en-v1.5` embedder, real zvec, real
`_NamespaceStore`, real per-test `tmp_path`. The first asserts state +
file count + zvec count match; the second proves Defect 2 is fixed
end-to-end against real backends.

**Phase C verdict: ✅ PASS**

---

## Phase D — Independent end-to-end probe

I wrote my own probe (not the engineer's) that exercises the full
`KnowledgeService.import_folder` API against real zvec + real embedder,
then verifies counts, leak, idempotency, and force-no-double-count.

Output (with HF/torch noise stripped):

```
tmp=/var/folders/.../qa-v2-real-_6zaj9tl
KNOWLEDGE_DIR=/Users/paulaan/.ostwin/knowledge
Importing from .../tests/fixtures/knowledge_sample
Job: 5e04004e422c46eea3a73be4182b0ef8

1st import: state=completed elapsed=15.23s
  result={files_total: 5, files_indexed: 5, files_skipped: 0,
          files_failed: 0, chunks_added: 5, entities_added: 0,
          relations_added: 0, errors: [], elapsed_seconds: 14.784}
zvec count (via Ingestor store): 5
leak check: KNOWLEDGE_DIR/qa-real-test exists=False
NO_LEAK_OK

2nd import (idempotent): state=completed elapsed=0.51s
  result={files_indexed: 0, files_skipped: 5, chunks_added: 0,
          elapsed_seconds: 0.007}

3rd import (force): state=completed elapsed=2.02s
  After force: files_indexed=5 chunks=5 vectors=5
PROBE_DONE
```

All four invariants verified independently:
- ✅ 1st import completes, count > 0 (5)
- ✅ 2nd import completes, all skipped (5/5), count unchanged
- ✅ 3rd import (force) completes, files_indexed/chunks/vectors NOT doubled (still 5)
- ✅ No leak to `~/.ostwin/knowledge/qa-real-test`

**Wall time:** 15.23s cold (includes BGE model download/load), 0.51s
idempotent, 2.02s force re-import. Total probe wall time ~18s.

**Phase D verdict: ✅ PASS**

---

## Phase E — RAGStorage / chromadb residue check

```
$ grep -n "init_vector_store\|RAGStorage" knowledge/graph/core/storage.py
5:* ``RAGStorage`` — a llama-index ``PropertyGraphIndex`` orchestrator.
6:* ``ChromaConfig`` + ``init_vector_store`` / ``init_vector_store_for_namespace``
14:   in the codebase still calls ``RAGStorage`` end-to-end.
117:def init_vector_store(*args: Any, **kwargs: Any):  # pragma: no cover
120:        "init_vector_store was removed in EPIC-003 v2 (chromadb → zvec migration). "
126:def init_vector_store_for_namespace(*args: Any, **kwargs: Any):  # pragma: no cover
129:        "init_vector_store_for_namespace was removed in EPIC-003 v2 ...
```

All references are either:
1. Module docstring (lines 5, 6, 14) describing the removed surface.
2. The `NotImplementedError` stubs themselves (lines 117, 126) — these stubs
   intentionally remain so any forgotten import sites raise loudly.

```
$ grep -rn "init_vector_store\|RAGStorage" knowledge/ | grep -v "\.md:"
knowledge/graph/core/storage.py:5: ... (docstring)
knowledge/graph/core/storage.py:6: ... (docstring)
knowledge/graph/core/storage.py:14: ... (docstring)
knowledge/graph/core/storage.py:117: def init_vector_store(*args, ...):  (stub)
knowledge/graph/core/storage.py:120: ... (error message)
knowledge/graph/core/storage.py:126: def init_vector_store_for_namespace(*args, ...):  (stub)
knowledge/graph/core/storage.py:129: ... (error message)
```

**No live caller of `RAGStorage` or `init_vector_store*` anywhere in
`dashboard/knowledge/`.** Confirmed engineer's claim.

```
$ grep -rE "import zvec|from zvec" knowledge/
knowledge/vector_store.py:        import zvec  # noqa: WPS433 — lazy   (× 8 method-local imports)
```

zvec is correctly used and lazily imported.

**Phase E verdict: ✅ PASS — no residual chromadb or RAGStorage callers.**

---

## Phase F — Test fidelity (no chromadb mocks)

```
$ grep -n "chromadb\|sys.modules\|monkeypatch.setattr.*chromadb" tests/test_knowledge_ingestion.py
1:    """EPIC-003 — ingestion + jobs tests (post v2 — chromadb → zvec migration)."""
15:    cleanly in this venv, unlike chromadb pre-fix). The store class
1081: ... (docstring referencing removed chromadb path)
1195: ... (docstring referencing chromadb-mock-only suites)
```

All four hits are in **comments / docstrings**. No `sys.modules['chromadb']
= ...` patches, no `MagicMock(spec=chromadb.something)` mocks, no
`monkeypatch.setattr(...chromadb...)` calls. The chromadb mock shim
(`_FakeChromaCollection`, `_FakeChromaClient`, `fake_chromadb` fixture,
`TestNamespaceStoreChroma` class) has been entirely removed.

The new `TestNamespaceStoreVector` (line 740) exercises the real
`_NamespaceStore` against real zvec via per-test `tmp_path`.

**Phase F verdict: ✅ PASS — no chromadb mocks remain; tests use real zvec.**

---

## Phase G — ADR compliance recheck

| ADR | Status | Evidence |
|---|---|---|
| ADR-01 (`~/.ostwin/knowledge/{ns}/`) | ✅ | Real e2e wrote to `{tmp}/{ns}/{vectors,manifest.json}` correctly. |
| ADR-02 (Direct Anthropic SDK + graceful degradation) | ✅ | Phase D probe with invalid key: 401 errors logged, `entities_added=0`, state `completed`. |
| ADR-03 (sentence-transformers BGE 384-dim) | ✅ | Real e2e loaded the model and produced 5 chunks. |
| **ADR-04 (REVISED to zvec)** | ✅ | Plan line 88 confirms revision; `vector_store.py` uses zvec exclusively; chromadb gone from requirements; on-disk path is `{ns}/vectors/`. |
| ADR-05 (KuzuDB) | ✅ | `nm.kuzu_db_path(ns)` resolves under `base_dir`; v1's isolation bug fixed. |
| ADR-06 (MarkItDown) | ✅ | Real e2e parsed all 5 fixture files. |
| ADR-08 (in-process executor + manifest persistence) | ✅ | Phase H1 verified manifest survives service restart. |
| ADR-10 (English / parameterised language) | ✅ | Unchanged from v1. |
| ADR-12 (namespace ID format) | ✅ | Unchanged from v1. |

**Phase G verdict: ✅ PASS — ADR-04 revision honored; all others unchanged.**

---

## Phase H — Defect probes

| # | Probe | Result | Notes |
|---|---|---|---|
| H1 | Manifest survives `KnowledgeService` instance restart | ✅ | After 1st service: `files_indexed=5, chunks=5`; after 2nd service (fresh instance, same `base_dir`): same. Manifest persistence works correctly. |
| H2 | **Concurrent imports into SAME namespace** | ⚠️ **NEW MINOR** | One thread won; the other crashed with uncaught `NamespaceExistsError`. The auto-create path in `KnowledgeService.import_folder` (`service.py:136`) is not protected against concurrent first-time creation. Same root cause class as v1 Minor 5; documented for EPIC-007. |
| H3 | `force=True` on fresh namespace (no prior chunks) | ✅ | Completes normally, `files_indexed=5, chunks_added=5`, no errors. The force-rollback path correctly skips the negative `update_stats` when `count_by_file_hash` returns 0. |
| H4 | Empty folder import | ✅ | `state=completed, files_total=0, files_indexed=0, elapsed=0.002s` |
| H5 | Folder with only hidden files | ✅ | `state=completed, files_total=0, files_indexed=0, elapsed=0.002s`. Confirms hidden files are filtered before reaching the embedder. |
| H6 | zvec collection survives `NamespaceVectorStore` instance restart | ✅ | After ingest, dropped service, GC'd, opened a new `NamespaceVectorStore(vector_path=tmp/vectors, dim=384)` → `count() == 5`. zvec persistence is durable across instance lifetimes. |

**Phase H verdict: ✅ PASS, with one new MINOR finding (H2).**

---

## Defects found

### NEW MINOR — Concurrent same-namespace `import_folder` raises `NamespaceExistsError`

**Severity**: MINOR (carry-forward of v1 Minor 5 with concrete reproduction).

**Location**: `dashboard/knowledge/service.py:104–147` (`import_folder`),
specifically the auto-create path that calls `self._nm.create(namespace)`
without checking whether another thread already created it.

**Reproduction** (Phase H2):

```python
nm = NamespaceManager(base_dir=tmp)
ks = KnowledgeService(namespace_manager=nm)
def submit(): ks.import_folder('concurrent-test', str(FIXTURES))
threads = [threading.Thread(target=submit) for _ in range(2)]
for t in threads: t.start()
for t in threads: t.join()

# Result: one thread succeeds, the other dies with:
# NamespaceExistsError: Namespace 'concurrent-test' already exists
```

The thread that loses the race propagates the exception out of
`import_folder`. The winner's job runs to completion. End state is
sane (1 import record, correct stats), but a caller submitting two
concurrent requests will see one of them crash with an uncaught
`NamespaceExistsError`.

**Fix sketch** (deferred to EPIC-007 per the plan):
- Wrap `self._nm.create(namespace)` in a try/except that swallows
  `NamespaceExistsError` (intent: "create if missing").
- Or, add a per-namespace lock at the service layer (the same lock that
  EPIC-007's "rate limiting → 409 Conflict" story will need).

**Why MINOR not MAJOR**: same-namespace concurrent imports are not a
documented use-case in EPIC-003's DoD. The v1 QA report flagged the same
class of issue (Minor 5) and the plan explicitly defers concurrency
hardening to EPIC-007.

### Closed from v1

| v1 Defect | v1 Severity | v2 Status |
|---|---|---|
| 1. `chroma_dir`/`kuzu_db_path` ignore `NamespaceManager.base_dir` | MAJOR | ✅ **CLOSED** — instance methods on `NamespaceManager` now compute paths off `self._base`; verified by 3 regression tests including a real-zvec leak check. |
| 2. `force=True` re-ingest double-counts manifest stats | MAJOR | ✅ **CLOSED** — `count_by_file_hash` + per-file negative `update_stats` rollback before re-add; verified by 2 regression tests + 1 real e2e. |
| 3. chromadb broken in venv (opentelemetry mismatch) | MAJOR | ✅ **CLOSED-BY-REMOVAL** — chromadb is no longer a dependency. |
| 4. Cooperative cancel: final state always `completed` | MINOR | ⚠️ **UNCHANGED** — engineer flagged in done-report as deferred to EPIC-007. |
| 5. No protection against two concurrent imports into same ns | MINOR | ⚠️ **CONFIRMED + REPRODUCED** in Phase H2 (`NamespaceExistsError`); deferred to EPIC-007. |
| 6. Cosmetic stale section header in test file | MINOR | ✅ **FIXED** in passing during the test-file rewrite (per engineer's done-report; spot-checked — no duplicate `# 6) KnowledgeService` header remains). |

---

## Real e2e test result with timing

```
$ pytest tests/test_knowledge_ingestion.py -k "e2e or real" -v
tests/test_knowledge_ingestion.py::TestPathRespectsBaseDir::test_real_zvec_path_respects_base_dir PASSED
tests/test_knowledge_ingestion.py::TestRealE2E::test_real_zvec_real_embedder_e2e PASSED
tests/test_knowledge_ingestion.py::TestRealE2E::test_real_e2e_force_reingest_stats_invariant PASSED
================ 3 passed, 58 deselected, 2 warnings in 13.68s =================
```

Independent Phase D probe (full `import_folder` API, real backends, my own
script not the engineer's): **15.23s cold + 0.51s idempotent + 2.02s
force = ~18s wall.** All correctness invariants hold.

---

## Test count summary

| Suite | v1 | v2 | Δ |
|---|---:|---:|---:|
| `test_knowledge_smoke.py` | 18 | 18 | 0 |
| `test_knowledge_namespace.py` | 37 | 37 | 0 |
| `test_knowledge_ingestion.py` | 52 | 61 | +9 (4 new defect-fix tests, 2 new e2e, 3 misc; offset by 9 deleted chromadb-mock tests) |
| **Total knowledge** | **107** | **116** | **+9** |
| Non-knowledge regression | 568 pass | 568 pass | 0 (baseline preserved) |

---

## Quality observations

1. **Test honesty improved.** v1 used `_FakeChromaCollection` to mock the
   storage layer; v2 uses **real zvec** via per-test `tmp_path`. This is
   the correct direction — mocks let v1 ship two MAJOR defects that real
   integration tests catch immediately.
2. **Lazy `import zvec`** in 8 different methods of `NamespaceVectorStore`.
   Module-level import would have been simpler but breaks the
   `test_knowledge_smoke._HEAVY_DEPS` gate. Engineer's choice is correct.
3. **`_esc` quote-escaping documented inline** with the bug it prevents
   (zvec's SQL-like parser rejects standard `''` escape; needs `\\'`).
   Future engineers will not re-discover this.
4. **`_ZVEC_MAX_TOPK = 1024` cap is documented** with the loop bound
   (64 × 1024 = 65k chunks per file ceiling). Reasonable for any
   realistic file size.
5. **`storage.py` reduced by ~335 LoC** of dead chromadb/RAGStorage
   plumbing. The `NotImplementedError` stubs at lines 117, 126 are the
   right pattern — they'd raise loudly if any forgotten caller still
   exists.

---

## Recommendation

**APPROVE.**

All three changes ship correctly. The two MAJOR defects from v1 are closed
with credible regression tests that exercise the real backend. The
chromadb-environment defect is closed by the migration itself. The new
MINOR defect (concurrent same-namespace) is the same root cause class as
v1 Minor 5 and is explicitly deferred to EPIC-007's rate-limiting work.

Recommend merging EPIC-003 v2 and proceeding to EPIC-004 (query layer),
which can now build on a clean `NamespaceVectorStore.search(...)` API
without worrying about chromadb's opentelemetry footgun or the path-
isolation bug.

EPIC-007 should pick up:
- v1 Minor 4 (cancel semantics).
- v1 Minor 5 / v2 H2 (concurrent same-namespace import lock).
- Force-re-ingest also drops Kuzu entities (engineer-1 decision #8).
- Per-namespace import serialisation more generally.
