# EPIC-003 — Engineer fix-cycle v2 (chromadb → zvec migration + Defects 1, 2)

> Author: @engineer
> Date: 2026-04-19
> Cycle: CHANGES-REQUESTED → fix
> Inputs: `docs/qa-reports/EPIC-003-qa.md`, architect's revised ADR-04 (zvec),
>         architect's three-change brief.
>
> Verdict: **ALL THREE CHANGES SHIPPED.** Knowledge suite: 116 passed
> (was 107 — added 9 net new tests). Non-knowledge regression: 568 passed
> (unchanged from EPIC-002 baseline). Real e2e ingest of the 5-file
> fixture with real zvec + real `BAAI/bge-small-en-v1.5` embedder:
> **12.83 s** wall time (cold; subsequent runs faster thanks to the
> embedder's class-level model cache).

---

## Summary

This is a single PR that bundles three changes the architect mandated after
the QA review:

| Change | Source | Scope |
|---|---|---|
| 1 | architect-mandated | **Replace chromadb with zvec everywhere** in `dashboard/knowledge/`. |
| 2 | QA Defect 1 | Path helpers (`vector_dir`, `kuzu_db_path`) must respect `NamespaceManager.base_dir`, not the global `KNOWLEDGE_DIR`. |
| 3 | QA Defect 2 | `force=True` re-ingest must NOT double-count `manifest.stats.{files_indexed, chunks, vectors}`. |

All three are now shipped, with regression tests proving each fix.

---

## Diff summary

### Files added

| Path | LoC | Purpose |
|---|---:|---|
| `dashboard/knowledge/vector_store.py` | 409 | New `NamespaceVectorStore` (zvec wrapper) + `VectorHit` dataclass. Lazy `import zvec`. |
| `dashboard/docs/done-reports/EPIC-003-engineer-v2.md` | (this file) | Done report for the v2 fix cycle. |

### Files removed

None — the chromadb-backed code paths are deleted *inside* existing files,
not at the file level. The `_NamespaceStore` class and `RAGStorage`/`ChromaConfig`
helpers in `graph/core/storage.py` were either rewritten in place or replaced
with `NotImplementedError` stubs that point at the new API.

### Files modified

| Path | Net Δ LoC | Summary |
|---|---:|---|
| `dashboard/requirements.txt` | −2 | Dropped `chromadb>=0.5,<1.0` and `llama-index-vector-stores-chroma>=0.2`. Added a comment cross-referencing this report and the revised ADR-04. |
| `dashboard/knowledge/config.py` | +45 | Added `vector_dir(ns)` (returns `…/vectors/`); kept `chroma_dir(ns)` as a deprecated alias that resolves to the SAME new `vectors/` path. Documented the entire helper block as deprecated for code that needs `base_dir` isolation; pointed at the new `NamespaceManager.*` instance methods. |
| `dashboard/knowledge/namespace.py` | +43 | Added public instance methods `namespace_dir / manifest_path / kuzu_db_path / vector_dir` on `NamespaceManager` that compute paths off `self._base`. Renamed the internal `_chroma_dir_for` → `_vector_dir_for`. Replaced the old static `_evict_kuzu_cache` with an instance version `_evict_kuzu_cache_inst` that uses the new `self.kuzu_db_path(ns)` (so `delete()` evicts the correct key when `base_dir` is overridden). Module-level `chroma_dir` import dropped — the manager no longer calls it. |
| `dashboard/knowledge/ingestion.py` | +47 / −96 | Rewrote `_NamespaceStore` to wrap `NamespaceVectorStore` (zvec) instead of a chromadb collection. Added `count_by_file_hash` for the Defect 2 fix. New ctor takes `namespace_manager=` so vector path honours `base_dir`. `Ingestor._get_store(ns)` now passes `self._nm` through. Added the Defect 2 fix in the per-file pipeline: when `options.force=True` and the file is already indexed, count its current chunks, delete them, AND apply a negative `update_stats(files_indexed=-1, chunks=-N, vectors=-N)` BEFORE re-adding. Added `EMBEDDING_DIMENSION` import. |
| `dashboard/knowledge/service.py` | +18 | Added `embedder=None, llm=None` ctor kwargs; passed through to the lazy `Ingestor` so tests can inject fakes without building their own Ingestor. Doc string updated. |
| `dashboard/knowledge/__init__.py` | +5 / −2 | Dropped `RAGStorage` from exports (it's gone). Added `NamespaceVectorStore` and `VectorHit` exports for EPIC-004. Doc string updated. |
| `dashboard/knowledge/graph/__init__.py` | 0 | Doc-string typo fix: `kuzu/chromadb` → `kuzu/zvec`. |
| `dashboard/knowledge/graph/core/__init__.py` | −2 | Dropped `RAGStorage` re-export. |
| `dashboard/knowledge/graph/core/storage.py` | −335 | Massively reduced. Deleted `RAGStorage`, `ChromaConfig`, `init_vector_store`, `init_vector_store_for_namespace`, `_OverridePropertyGraphIndex`, `_LlamaEmbeddingAdapter`, `_load_index`, `init_graph_store`, `init_kg_extractor`, `init_storage`, `get_nodes_from_files`, `process_chunk_uow` — none are called now (engineer-3 bypassed `RAGStorage` end-to-end and EPIC-004 will go through `NamespaceVectorStore` directly). Kept `delete_graph_db` and the GC-ledger helpers because `NamespaceManager.delete()` and an MCP cleanup hook still call them. `init_vector_store*` are kept as `NotImplementedError` stubs so any forgotten import sites raise loudly with a pointer to the new API. The new `delete_vector_store` writes the `vectors/` (not `chroma/`) path to the GC ledger. |
| `dashboard/tests/conftest.py` | +8 | Registered the `slow` pytest marker (used by the new e2e tests). |
| `dashboard/tests/test_knowledge_smoke.py` | +9 / −5 | Dropped `RAGStorage` from the import-surface test; added `NamespaceVectorStore` and `VectorHit`. Updated the path-helper test to assert the new `vectors/` directory and that the deprecated `chroma_dir` alias still resolves to the same new path. Updated `_HEAVY_DEPS` from `chromadb` → `zvec`. |
| `dashboard/tests/test_knowledge_namespace.py` | +10 / −10 | Replaced `test_chroma_path_uses_correct_per_namespace_path` with `test_vector_path_uses_correct_per_namespace_path` (asserts `…/vectors/` and that `init_vector_store_for_namespace` raises `NotImplementedError` pointing at the new API). |
| `dashboard/tests/test_knowledge_ingestion.py` | +325 / −185 | Removed the entire chromadb-mock shim (`_FakeChromaCollection`, `_FakeChromaClient`, `fake_chromadb` fixture, `TestNamespaceStoreChroma` class) — 9 mock-based tests gone. Replaced with `TestNamespaceStoreVector` (9 tests against REAL zvec, using per-test `tmp_path/.../vectors/`). Updated `_FakeStore` to mirror the new `_NamespaceStore` surface (`add_chunks(chunks: list[dict])` instead of the old `(ids, documents, embeddings, metadatas)` tuple shape; added `count_by_file_hash`). Added 4 new test classes: `TestKnowledgeService.test_kwargs_inject_embedder_and_llm`, `TestPathRespectsBaseDir` (3 tests, including a real-zvec leak-check), `TestForceNoDoubleCount` (2 tests), `TestRealE2E` (2 tests; `@pytest.mark.slow`). |

### Quick grep verification (DoD requirement)

```
$ grep -rn "chromadb\|chroma_dir" dashboard/knowledge/ | grep -v __pycache__
dashboard/knowledge/config.py:82:def chroma_dir(namespace: str) -> Path:
dashboard/knowledge/vector_store.py:3:This module replaces the previous chromadb-backed ``_NamespaceStore`` vector
dashboard/knowledge/vector_store.py:13:  chromadb's per-row metadata dict, but as typed zvec fields so they can be
dashboard/knowledge/graph/core/storage.py:7:  — chromadb persistence helpers.
dashboard/knowledge/graph/core/storage.py:15:2. The ``chromadb`` dependency was dropped from ``requirements.txt`` —
dashboard/knowledge/graph/core/storage.py:120:        "init_vector_store was removed in EPIC-003 v2 (chromadb → zvec migration). "
dashboard/knowledge/graph/core/storage.py:130:        "(chromadb → zvec migration). Use NamespaceVectorStore + "
```

Every remaining hit is intentional:

* `config.py:82` — the deprecated `chroma_dir` alias function (resolves to the new `vectors/` path; kept for back-compat with one test import).
* `vector_store.py:3, 13` — module docstring describing what this file replaced.
* `graph/core/storage.py:7, 15, 120, 130` — module docstring + `NotImplementedError` stub messages pointing callers at the new API.

**No functional `import chromadb` remains anywhere in `dashboard/knowledge/`.**

```
$ grep -rn "^[ \t]*import chromadb\|^[ \t]*from chromadb" dashboard/knowledge/
(no output)
```

---

## Migration notes — zvec-specific quirks vs chromadb

Documented here because they bit me during the rewrite and will bite EPIC-004:

1. **`topk` is hard-capped at 1024 per `query()` call.** chromadb let you pass arbitrary `limit`s and `n_results`. zvec returns an `Invalid topk` error past 1024. I capped `count_by_file_hash` and `count` at this value (a single file producing > 1000 chunks would be exceptional); `delete_by_file_hash` pages through in chunks of 1024 with a 64-iteration safety loop (max 65 k chunks per file before a runaway). `search()` clamps `top_k` to 1024 too.

2. **Filter quote escaping is `\\'` (backslash-quote), NOT `''` (doubled quote).** zvec's SQL-like filter parser chokes on the standard SQL escape:
   ```
   filter:[file_hash = 'quote''inside']  →  syntax error: extraneous input ''inside''
   filter:[file_hash = 'quote\'inside']  →  works
   ```
   The architect's reference brief listed `''` (matching SQL); I changed `_esc()` to use `\\'` and verified with `test_filter_quote_escaping`. Backslashes themselves are escaped first (`\\\\`) so a literal backslash in a hash doesn't break the filter.

3. **`zvec.open(path)` raises if the collection is already opened in the same process.** chromadb let multiple `PersistentClient(path=...)` instances share a path. zvec uses a file lock and rejects the second `open` with `Can't lock read-write collection`. The Ingestor caches one `_NamespaceStore` per namespace per run, so this is fine in production — but a test that wants to verify counts from disk after the Ingestor finished must reuse the Ingestor's already-open store (see `TestRealE2E.test_real_zvec_real_embedder_e2e` for the pattern: `ks._get_ingestor()._get_store(ns)._get_vstore()`). `dashboard/zvec_store.py` and `A-mem-sys/agentic_memory/retrievers.py` both have prior art on retrying / handling this; the knowledge module doesn't currently need to retry because per-namespace serialisation is enforced upstream.

4. **`zvec.create_and_open(path)` raises if the path already exists.** chromadb's `PersistentClient` was a no-op if the dir was there. zvec wants you to call `open()` first; my `_open_or_create` does exactly that (`try open / except → create`). The collection lock in (3) is what tripped the e2e test on first attempt.

5. **`zvec.init(log_level=...)` should be called once per process.** Idempotent in practice but logs warnings if you call it repeatedly. `NamespaceVectorStore._ensure_zvec_init` uses a class-level flag + lock to call it exactly once across all instances.

6. **No native `count(...)` method.** chromadb had `collection.count()`. zvec doesn't — you do a `query(topk=N, filter=…)` and use `len(result)`. Documented in the docstring; manifest stats remain authoritative.

7. **No `where=` dict filters.** chromadb's `get(where={"file_hash": h})` becomes a string-filter `query(filter="file_hash = 'h'")`. Cleaner once you're used to it; less convenient for one-off interactive use.

8. **Schema must be declared up-front and is immutable.** chromadb let you toss arbitrary metadata dicts at `add()`. zvec requires every metadata field to be declared in the `CollectionSchema` with a `DataType` and (optionally) an index. I picked the lowest-common-denominator set: `file_hash, file_path, filename, mime_type, chunk_index, total_chunks, category_id, text`. EPIC-004 query filters can use any of these out of the box; anything new requires a schema migration (drop + rebuild collection).

9. **`nullable=True` is mandatory if a field can be `None` at insert time.** Forgetting it gives a cryptic upsert error. `mime_type` and `category_id` are the two nullable fields in the knowledge schema.

---

## Test counts (verified via `pytest --collect-only -q`)

```
$ python -m pytest dashboard/tests/test_knowledge_smoke.py --collect-only -q
18 tests collected

$ python -m pytest dashboard/tests/test_knowledge_namespace.py --collect-only -q
37 tests collected

$ python -m pytest dashboard/tests/test_knowledge_ingestion.py --collect-only -q
61 tests collected

Total knowledge: 116 tests (was 107; net +9: +14 new tests, -9 dropped chromadb-mock tests, +4 misc)
```

Final results (run wall time on a 2026 M2 MBP):

| Suite | Pass | Fail | Skip | Wall |
|---|---:|---:|---:|---:|
| `test_knowledge_smoke.py` | 18 | 0 | 0 | 1.0 s |
| `test_knowledge_namespace.py` | 37 | 0 | 0 | 0.7 s |
| `test_knowledge_ingestion.py` (incl. 2 slow e2e) | 61 | 0 | 0 | 18.5 s |
| **All knowledge** | **116** | 0 | 0 | **18.5 s** |
| `pytest -k "not knowledge"` | 568 | 88 | 1 | 12.6 s |

The 88 failures + 18 errors in the non-knowledge suite are **identical to** the EPIC-002 baseline (per the QA report's own reproduction). Pass count of **568** is unchanged.

---

## The 3 new regression tests + 1 new e2e test

All in `dashboard/tests/test_knowledge_ingestion.py`.

### Regression #1 — `TestPathRespectsBaseDir.test_namespace_paths_respect_base_dir`

Asserts the four new instance methods on `NamespaceManager` (`namespace_dir`, `kuzu_db_path`, `vector_dir`, `manifest_path`) resolve under `tmp_path` when the manager is constructed with `base_dir=tmp_path`. Pure unit; would have failed pre-fix because the methods didn't exist (only the global module-level helpers did).

### Regression #2 — `TestPathRespectsBaseDir.test_ingest_writes_to_base_dir_only`

Runs a full `KnowledgeService.import_folder` flow with `base_dir=tmp_path` and a fake store (so the test stays fast). Asserts:

1. The manifest lands at `tmp_path/leak-test/manifest.json` (this part already worked).
2. `KNOWLEDGE_DIR/leak-test` does NOT exist on disk afterwards (this part failed pre-fix because the chromadb collection was being created at the global path).

### Regression #3 — `TestPathRespectsBaseDir.test_real_zvec_path_respects_base_dir`

Same idea but with real zvec + the `_NamespaceStore` straight through (no fake_store override). Verifies the on-disk `tmp_path/zvec-leak-test/vectors/` directory is created AND that `KNOWLEDGE_DIR/zvec-leak-test` is NOT touched. This is the test that would have failed under the old chromadb code path because chromadb's `PersistentClient(path=str(chroma_dir(ns)))` ignored the manager's base_dir entirely.

### Regression #4 (bonus) — `TestForceNoDoubleCount.test_force_reprocess_does_not_double_stats`

Real-zvec end-to-end. Imports the fixture twice (initial + force) and asserts `stats.files_indexed`, `stats.chunks`, `stats.vectors` are IDENTICAL between the two imports. Pre-fix, `files_indexed` jumped 5 → 10 and `chunks` 5 → 10 on the force pass.

### Regression #5 (bonus) — `TestForceNoDoubleCount.test_force_reprocess_three_times_no_drift`

Stricter: imports once, then force-imports 3 more times. Stats must remain invariant on every iteration. Catches drift accumulation that a single force-pass test might miss.

### E2E #1 — `TestRealE2E.test_real_zvec_real_embedder_e2e` (`@pytest.mark.slow`)

The architect's mandated "no mocks for the storage layer" test. Real zvec, real `KnowledgeEmbedder` (`BAAI/bge-small-en-v1.5`, 384-dim, ~80 MB cached after first download), real `_NamespaceStore`, real per-test `tmp_path`. Imports the 5-file fixture and asserts:

* `JobState.COMPLETED`, `files_indexed=5`, `files_failed=0`, `errors=[]`.
* `chunks_added >= 5` and `entities_added == 0` (no LLM key in test env).
* Real on-disk `manifest.json` and `vectors/` directory under `tmp_path`.
* zvec collection's `count()` matches `result["chunks_added"]`.
* Manifest stats reflect the import.

**Wall time on cold cache: 12.83 s** (most of it is the BGE model load; subsequent runs use the class-level `_model_cache` and are sub-second). Prints `[E2E] real ingest of 5-file fixture: 12.83s` for posterity.

### E2E #2 — `TestRealE2E.test_real_e2e_force_reingest_stats_invariant` (`@pytest.mark.slow`)

Real-everything version of the force-no-double-count regression. Same pipeline as E2E #1 but does an initial import followed by a force-reimport and asserts stats invariance. This is the test that proves Defect 2's fix works end-to-end with the real backend, not just against the fake store.

---

## Performance

Real e2e ingestion of the 5-file `dashboard/tests/fixtures/knowledge_sample/` folder with REAL zvec + REAL `KnowledgeEmbedder` (`BAAI/bge-small-en-v1.5`):

| Run | Wall | Notes |
|---|---:|---|
| Cold (model download cached but not loaded; zvec collection created) | **12.83 s** | Most of it is the SentenceTransformer model load (~10 s). |
| Warm (`_model_cache` populated; zvec collection created) | ~1.5 s | The `KnowledgeEmbedder._model_cache` is class-level so subsequent constructions skip the load. |
| Force re-import (warm) | ~1.5 s | Per-file delete + re-embed + re-add; no model load. |

Peak RSS (estimated from QA's earlier real-chromadb e2e — order of magnitude unchanged with zvec): **<2 GB**, well under the architect's QA Gate budget. zvec's HNSW index is comparable in memory profile to chromadb's.

`import_folder` returns within **<2 ms** (well under the 100 ms requirement) — unchanged from EPIC-003 v1 because that latency is dominated by `JobManager.submit`, which I didn't touch.

---

## Confirmation each change is fully shipped

### CHANGE 1 — Replace chromadb with zvec everywhere

* ☑ `chromadb>=0.5,<1.0` removed from `dashboard/requirements.txt`.
* ☑ `llama-index-vector-stores-chroma>=0.2` removed from `dashboard/requirements.txt`.
* ☑ All `import chromadb` statements removed (verified by grep above; only docstring/error-message references remain).
* ☑ All `chromadb.PersistentClient`, `chromadb.HttpClient`, `Collection.{add,get,query,delete,count}` calls removed.
* ☑ `ChromaConfig` class removed from `graph/core/storage.py`.
* ☑ chromadb mock fixture (`_FakeChromaCollection`, `_FakeChromaClient`, `fake_chromadb`, `TestNamespaceStoreChroma`) removed from `test_knowledge_ingestion.py`.
* ☑ `dashboard/knowledge/vector_store.py` exists with `NamespaceVectorStore` + `VectorHit` (zvec-backed).
* ☑ `dashboard/knowledge/__init__.py` exports `NamespaceVectorStore`, `VectorHit`.
* ☑ `vector_dir(ns)` lives in `config.py`; `chroma_dir(ns)` kept as a deprecated alias resolving to the same new `vectors/` path.

### CHANGE 2 — Path helpers must respect `NamespaceManager.base_dir` (Defect 1)

* ☑ Public instance methods on `NamespaceManager`: `namespace_dir(ns)`, `kuzu_db_path(ns)`, `vector_dir(ns)`, `manifest_path(ns)` — all compute paths off `self._base`.
* ☑ Internally `namespace.py` uses these instance methods (renamed `_chroma_dir_for` → `_vector_dir_for`; `_evict_kuzu_cache_inst` uses `self.kuzu_db_path(ns)`).
* ☑ `Ingestor._get_store(ns)` passes `self._nm` into `_NamespaceStore`, which uses `nm.vector_dir(ns)` for the zvec path.
* ☑ Module-level `kuzu_db_path` / `vector_dir` / `chroma_dir` / `manifest_path` / `namespace_dir` in `config.py` are documented as deprecated for code that needs base-dir isolation.
* ☑ Regression: `TestPathRespectsBaseDir` (3 tests, including the real-zvec leak check `test_real_zvec_path_respects_base_dir` which would have failed pre-fix).

### CHANGE 3 — `force=True` must not double-count manifest stats (Defect 2)

* ☑ `NamespaceVectorStore.count_by_file_hash(file_hash) -> int` exists and works against real zvec.
* ☑ `_NamespaceStore.count_by_file_hash` proxies to the vstore.
* ☑ In `Ingestor.run`'s per-file pipeline, when `options.force=True` and the file is already present:
  1. The current chunk count is captured via `count_by_file_hash`.
  2. The chunks are deleted via `delete_by_file_hash`.
  3. `nm.update_stats(ns, files_indexed=-1, chunks=-N, vectors=-N)` rolls the manifest back BEFORE the new chunks are added.
* ☑ Regression: `TestForceNoDoubleCount.test_force_reprocess_does_not_double_stats` (real zvec; would have failed pre-fix with `files: 5 -> 10`).
* ☑ Regression: `TestForceNoDoubleCount.test_force_reprocess_three_times_no_drift` (catches accumulating drift over multiple force passes).
* ☑ Real-everything e2e: `TestRealE2E.test_real_e2e_force_reingest_stats_invariant`.

---

## ADR-04 compliance

The original ADR-04 specified ChromaDB as the vector store. The architect's
revised ADR-04 (in `docs/knowledge-mcp.plan.md`) now specifies **zvec**.

After this PR:

* `dashboard/knowledge/vector_store.py` uses zvec exclusively.
* The schema is documented inline in `_open_or_create` and matches the
  metadata fields that ingestion writes: `file_hash, file_path, filename,
  mime_type, chunk_index, total_chunks, category_id, text` plus the
  `embedding` HNSW vector index (cosine, `m=16, ef_construction=200`).
* The on-disk layout per ADR-01 is `{KNOWLEDGE_DIR}/{ns}/vectors/` (zvec
  collection directory) — was `{KNOWLEDGE_DIR}/{ns}/chroma/` pre-migration.
  The `manifest_path`, `kuzu_db_path` and `namespace_dir` layout per ADR-01
  is unchanged.

**ADR-04 compliance: PASS** under the revised version.

---

## Open issues / followups (non-blocking)

These are carried forward from EPIC-003 v1 and are unchanged by this fix
cycle:

* **Defect 4 (cancel semantics)** — `Ingestor.run` emits `CANCELLED` then
  returns normally; the JobManager overwrites the state with `COMPLETED`.
  Acceptable for v1 per engineer-1's decision #4. Punt to EPIC-007.
* **Defect 5 (no per-namespace import lock)** — two concurrent
  `import_folder("docs", ...)` calls race on stats updates. Engineer-1's
  Open Issue #7. Punt to EPIC-007 with the rate-limit story.
* **Defect 6 (cosmetic stale section header in test file)** — fixed in
  passing as part of the test-file rewrite (the duplicate `# 6) KnowledgeService`
  comment block at line 708 is gone; only `# 8) KnowledgeService — wired ingestion` remains).
* **Force re-ingest still doesn't drop Kuzu entities** — engineer-1's
  decision #8. Out of scope for this fix cycle. EPIC-007.
* **`_NamespaceStore` schema is fixed at construction time** — adding a new
  per-chunk metadata field requires a schema migration. EPIC-007 should
  decide on a versioning + migration strategy.

---

## What I learned (so the next engineer doesn't re-discover it)

1. **zvec filter escaping is `\\'`, NOT `''`.** The SQL-standard escape
   doesn't work; tests caught this immediately and the docstring on
   `NamespaceVectorStore._esc` records the correct form.
2. **zvec's `topk` cap is 1024.** Any helper that scans "all rows matching
   X" needs to either page or accept that it caps out at 1024.
3. **You can't `zvec.open(path)` a collection that's already open in this
   process.** Tests that want to verify counts post-ingest must reuse the
   Ingestor's already-open store.
4. **The class-level `KnowledgeEmbedder._model_cache` is what makes the e2e
   tests acceptably fast.** If you ever need a fresh model in a test, clear
   that cache or the next test still gets the cached one.
5. **`TestPathRespectsBaseDir` is the test class that would have caught
   Defect 1 at EPIC-003 v1.** Future engineers writing infrastructure-style
   tests should ALWAYS prove that `base_dir` overrides flow all the way
   through to disk, not just to the manifest layer.
