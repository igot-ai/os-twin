# DONE: EPIC-001 — Refactor Knowledge Package (de-app-ify, strip dead code)

> Status: complete — handing off to @qa
> Author: @engineer
> Date: 2026-04-19
> Branch: (uncommitted working tree)

## Importtime evidence (heavy deps NOT loaded)

`python -X importtime -c "import dashboard.knowledge" 2>&1 | tail -30`:

```
import time:       227 |        227 |       dashboard.knowledge.llm
import time:      1627 |     902331 |     dashboard.knowledge.graph.core.graph_rag_extractor
import time:      1105 |       1105 |             dashboard.knowledge.graph.index.kuzudb
import time:       122 |       1226 |           dashboard.knowledge.graph.index
import time:       217 |       1448 |       dashboard.knowledge.graph.core.graph_rag_store
import time:       254 |        254 |           dashboard.knowledge.graph.utils._utils
import time:       241 |        241 |             dashboard.knowledge.graph.prompt
import time:       214 |        455 |           dashboard.knowledge.graph.utils.rag
import time:       185 |        893 |         dashboard.knowledge.graph.utils
import time:       399 |       1291 |       dashboard.knowledge.graph.core.query_executioner
import time:       275 |        275 |       dashboard.knowledge.graph.core.track_vector_retriever
import time:      1174 |       4187 |     dashboard.knowledge.graph.core.graph_rag_query_engine
import time:       123 |        123 |           dashboard.knowledge.graph.parsers.base
import time:       236 |        358 |         dashboard.knowledge.graph.parsers.markitdown_reader
import time:       169 |        527 |       dashboard.knowledge.graph.parsers
import time:      1162 |       1689 |     dashboard.knowledge.graph.core.storage
import time:       249 |     908704 |   dashboard.knowledge.graph.core
import time:       303 |     917971 | dashboard.knowledge
```

`grep -E "(kuzu|chromadb|sentence_transformers|markitdown|anthropic)$"` against
the full importtime output: **none** of those module names appear. The only
"heavy" thing on the chain is `llama_index.core` (~870ms), which is required
by the existing graph code (per the EPIC-001 task list — llama-index-core was
explicitly added to `requirements.txt`).

The smoke test `test_lazy_imports_via_subprocess` formally checks this from a
clean interpreter and passes.

## What I built

- `dashboard/knowledge/config.py` — env-var-backed constants (`KNOWLEDGE_DIR`,
  `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`, `LLM_MODEL`, `PAGERANK_SCORE_THRESHOLD`,
  `KUZU_MIGRATE`), per-namespace path helpers (`namespace_dir`, `kuzu_db_path`,
  `chroma_dir`, `manifest_path`), file-type constants (`SUPPORTED_DOCUMENT_EXTENSIONS`,
  `IMAGE_EXTENSIONS`), and `GARBAGE_COLLECTION_FILE`.
- `dashboard/knowledge/llm.py` — `KnowledgeLLM` class wrapping the Anthropic SDK
  with lazy import. Methods: `is_available()`, `extract_entities()`, `plan_query()`,
  `aggregate_answers()`. Graceful no-op fallbacks when no API key.
- `dashboard/knowledge/embeddings.py` — `KnowledgeEmbedder` class wrapping
  sentence-transformers with lazy model load and a class-level model cache.
  Methods: `embed()`, `embed_one()`, `dimension()`.
- `dashboard/knowledge/__init__.py` — public package entry point. Exports
  `KnowledgeService` (placeholder), `KnowledgeLLM`, `KnowledgeEmbedder`,
  `KuzuLabelledPropertyGraph`, `RAGStorage`, `GraphRAGExtractor`,
  `GraphRAGQueryEngine`, `GraphRAGStore`, `TrackVectorRetriever`, plus the
  config constants. `KnowledgeService.__init__` raises `NotImplementedError`
  (placeholder for EPIC-002).
- `dashboard/tests/test_knowledge_smoke.py` — 15 tests covering all DoD smoke
  criteria (importability, placeholder-raises, config types, LLM degradation
  with/without key, embedder construction, lazy-load via subprocess).

## What I deleted

| Path | Why |
|---|---|
| `dashboard/knowledge/graph/mem0/` (whole tree) | ADR-09 — dead code, unused. |
| `dashboard/knowledge/graph/parsers/docx.py` | ADR-09 — replaced by MarkItDown. |
| `dashboard/knowledge/graph/parsers/sheet.py` | ADR-09 — replaced by MarkItDown. |
| `dashboard/knowledge/graph/parsers/raw.py` | ADR-09 — replaced by MarkItDown. |
| `dashboard/knowledge/graph/core/significance_analyzer.py` | ADR-09 — overcomplicated; replaced by inline simple combined-score in `track_vector_retriever`. |
| `dashboard/knowledge/processing/` (whole tree, incl. `document_router.py`) | ADR-09 — `ReadResolver` now always uses MarkItDown; the routing layer is no longer needed. |
| `dashboard/knowledge/graph/core/rag_service.py` | **Deviation from EPIC-010** — the file depended on `app.middlewares.folder.FolderMiddleware`, `app.core.database.local_database.local_db`, and `app.i18n.translator`, none of which exist. The plan's `__init__.py` spec did NOT export `RAGService` (only `RAGStorage`), so its removal aligns with the new public API. EPIC-002 introduces `KnowledgeService` to replace it cleanly. |
| All `__pycache__/` directories under `knowledge/` | TASK-013. |
| `.DS_Store` files under `knowledge/` | TASK-013. |

## What I refactored

| File | One-line summary |
|---|---|
| `dashboard/knowledge/__init__.py` | New public surface per TASK-010; placeholder `KnowledgeService`. |
| `dashboard/knowledge/graph/__init__.py` | Stripped legacy re-exports; now just an empty doc-string module so the sub-package is importable without triggering heavy imports. |
| `dashboard/knowledge/graph/core/__init__.py` | Re-exports the 6 refactored classes from sibling modules under `dashboard.knowledge.*`. |
| `dashboard/knowledge/graph/core/graph_rag_extractor.py` | Removed DSPy + `DspyLlamaIndexAdapter`; now takes a `KnowledgeLLM` directly and calls `extract_entities()`. Uses `KnowledgeEmbedder` for batch embedding. |
| `dashboard/knowledge/graph/core/graph_rag_query_engine.py` | Removed llama-index `LLM` and `ChatMessage` deps; `aggregate_answers` now calls `KnowledgeLLM.aggregate_answers` directly. Replaced `run_async_in_thread` with inline `_run_async`. |
| `dashboard/knowledge/graph/core/graph_rag_store.py` | Removed `pyvis` (replaced with hand-built nodes/edges dicts); `networkx` lazy-imported in `to_json_graph`. |
| `dashboard/knowledge/graph/core/query_executioner.py` | Replaced `app.models.LLMChatMessage` with local Pydantic `ChatMessage`; planner now calls `KnowledgeLLM.plan_query`; Vietnamese-locked legacy prompts no longer drive the planning here. |
| `dashboard/knowledge/graph/core/storage.py` | Removed `app.env`, `app.utils.file_helper`, DSPy adapter, `app.core.llm.dspy`. Now takes/creates `KnowledgeLLM` + `KnowledgeEmbedder`. Added `_LlamaEmbeddingAdapter` to bridge our embedder to llama-index's `BaseEmbedding`-style API. ChromaDB lazy-imported inside `init_vector_store`. GC ledger uses `pathlib`+`json` directly. |
| `dashboard/knowledge/graph/core/track_vector_retriever.py` | Dropped `SignificanceAnalyzer`; significance filtering is now a no-op. `networkx` lazy-imported in `__init__`. |
| `dashboard/knowledge/graph/index/__init__.py` | Re-export now under `dashboard.knowledge.*`. |
| `dashboard/knowledge/graph/index/kuzudb.py` | `kuzu` and `networkx` lazy-imported inside methods that use them. Field types `kuzu.Database` → `Any`. `KUZU_DATABASE_PATH` defined locally as `str(KNOWLEDGE_DIR)`. `get_default_embedding_model()` calls replaced by module-level `_get_embedder()` → `KnowledgeEmbedder().embed_one(...)`. |
| `dashboard/knowledge/graph/parsers/__init__.py` | `ReadResolver` simplified — DocumentProcessingRouter dropped (always uses MarkItDown). |
| `dashboard/knowledge/graph/parsers/base.py` | Unchanged (no `app.*` imports). |
| `dashboard/knowledge/graph/parsers/markitdown_reader.py` | Massively simplified per TASK-009 guidance: drop `cache_result`, `FileExtraction`, `SettingService`, `local_db`. Local-file-only path; lazy `MarkItDown` import; inline 1024/200-overlap chunker; `Document(text=chunk, id_=uuid.uuid4(), metadata={...})` per chunk. ~553 → ~150 LOC. |
| `dashboard/knowledge/graph/utils/__init__.py` | Re-exports updated paths; dropped `read_file` (was a `requests`-using helper, not on the new public surface). |
| `dashboard/knowledge/graph/utils/_utils.py` | Dropped `PyPDF2`, `regex` (third-party), `fastapi_healthchecks`, `socket`. Kept the JSON/metadata/entity helpers. Replaced `regex` recursive `(?R)` patterns with linear-time `re` equivalents. |
| `dashboard/knowledge/graph/utils/rag.py` | Stripped Google GenAI / HuggingFace / DSPy / psutil / `app.env` / `app.core.database.local_database` deps. Kept `_get_nodes_from_triplets`, `extract_KP_fn`, `extract_KP_json_fn`, `parse_fn`, `parse_json_fn`. ~660 → ~205 LOC. |
| `dashboard/knowledge/graph/prompt.py` | Unchanged (it has zero imports; legacy Vietnamese strings remain — the new `KnowledgeLLM` does not consume them, so they're inert. Per ADR-10 the prompts inside `KnowledgeLLM` are English-with-language-parameter). |
| `dashboard/requirements.txt` | Added `kuzu`, `chromadb`, `markitdown`, `anthropic`, `networkx`, `pyyaml`, `tenacity`, `llama-index-core`, `llama-index-vector-stores-chroma` per TASK-011. |
| `dashboard/tests/test_knowledge_smoke.py` | New 15-test suite. |

## Files touched (summary)

| Path | Action |
|---|---|
| `dashboard/knowledge/__init__.py` | rewritten |
| `dashboard/knowledge/config.py` | new |
| `dashboard/knowledge/llm.py` | new |
| `dashboard/knowledge/embeddings.py` | new |
| `dashboard/knowledge/graph/__init__.py` | rewritten |
| `dashboard/knowledge/graph/prompt.py` | unchanged |
| `dashboard/knowledge/graph/core/__init__.py` | rewritten |
| `dashboard/knowledge/graph/core/graph_rag_extractor.py` | rewritten |
| `dashboard/knowledge/graph/core/graph_rag_query_engine.py` | rewritten |
| `dashboard/knowledge/graph/core/graph_rag_store.py` | rewritten |
| `dashboard/knowledge/graph/core/query_executioner.py` | rewritten |
| `dashboard/knowledge/graph/core/storage.py` | rewritten |
| `dashboard/knowledge/graph/core/track_vector_retriever.py` | rewritten |
| `dashboard/knowledge/graph/core/significance_analyzer.py` | **deleted** |
| `dashboard/knowledge/graph/core/rag_service.py` | **deleted** (deviation, see above) |
| `dashboard/knowledge/graph/index/__init__.py` | rewritten |
| `dashboard/knowledge/graph/index/kuzudb.py` | edited (lazy imports + path/embedder refactor) |
| `dashboard/knowledge/graph/parsers/__init__.py` | rewritten |
| `dashboard/knowledge/graph/parsers/base.py` | unchanged |
| `dashboard/knowledge/graph/parsers/markitdown_reader.py` | rewritten |
| `dashboard/knowledge/graph/parsers/docx.py` | **deleted** |
| `dashboard/knowledge/graph/parsers/raw.py` | **deleted** |
| `dashboard/knowledge/graph/parsers/sheet.py` | **deleted** |
| `dashboard/knowledge/graph/utils/__init__.py` | rewritten |
| `dashboard/knowledge/graph/utils/_utils.py` | rewritten |
| `dashboard/knowledge/graph/utils/rag.py` | rewritten |
| `dashboard/knowledge/graph/mem0/` | **deleted** (whole tree) |
| `dashboard/knowledge/processing/` | **deleted** (whole tree) |
| `dashboard/requirements.txt` | edited (+9 packages) |
| `dashboard/tests/test_knowledge_smoke.py` | new |

## How to verify

```bash
# Run from repo root: /Users/paulaan/PycharmProjects/agent-os

# 1) zero app.* imports
grep -rE "(from |import )app\." dashboard/knowledge/  # must return empty

# 2) zero dspy imports
grep -rE "(from |import )dspy"  dashboard/knowledge/  # must return empty

# 3) deleted modules confirmed gone
ls dashboard/knowledge/graph/mem0                                    # No such file
ls dashboard/knowledge/graph/parsers/docx.py                         # No such file
ls dashboard/knowledge/processing                                    # No such file
ls dashboard/knowledge/graph/core/significance_analyzer.py           # No such file

# 4) public API imports
python -c "from dashboard.knowledge import KnowledgeService, KnowledgeLLM, KnowledgeEmbedder, KuzuLabelledPropertyGraph, RAGStorage, GraphRAGExtractor, GraphRAGQueryEngine"

# 5) heavy deps not imported at module load
python -X importtime -c "import dashboard.knowledge" 2>&1 | tail -30 | grep -iE "(^.*kuzu$|chromadb$|sentence_transformers$|markitdown$|anthropic$)"  # empty

# 6) smoke test
cd dashboard && pytest tests/test_knowledge_smoke.py -v

# 7) regression baseline
cd dashboard && pytest tests/ -k "not knowledge" --no-header -q | tail -3
```

## Verification output captured

### grep app.* in `dashboard/knowledge/`

```
$ grep -rE "(from |import )app\." dashboard/knowledge/
dashboard/knowledge/config.py:# --- File-type constants (moved from app.utils.constant) -------------------
```

(One match — and it is a comment, not an import.)

### grep dspy in `dashboard/knowledge/`

```
$ grep -rE "(from |import )dspy" dashboard/knowledge/
(empty)
```

### Deleted-modules check

```
$ for p in knowledge/graph/mem0 knowledge/processing \
           knowledge/graph/parsers/docx.py knowledge/graph/parsers/sheet.py \
           knowledge/graph/parsers/raw.py knowledge/graph/core/significance_analyzer.py; do
    [ -e "$p" ] && echo "STILL EXISTS: $p" || echo "GONE: $p"
  done
GONE: knowledge/graph/mem0
GONE: knowledge/processing
GONE: knowledge/graph/parsers/docx.py
GONE: knowledge/graph/parsers/sheet.py
GONE: knowledge/graph/parsers/raw.py
GONE: knowledge/graph/core/significance_analyzer.py
```

### Smoke test output

```
$ pytest dashboard/tests/test_knowledge_smoke.py -v
======================= test session starts =======================
collected 15 items

tests/test_knowledge_smoke.py::test_top_level_package_imports                  PASSED [  6%]
tests/test_knowledge_smoke.py::test_knowledge_service_constructor_raises       PASSED [ 13%]
tests/test_knowledge_smoke.py::test_knowledge_service_constructor_raises_with_args PASSED [ 20%]
tests/test_knowledge_smoke.py::test_knowledge_dir_is_path                      PASSED [ 26%]
tests/test_knowledge_smoke.py::test_namespace_path_helpers_are_paths           PASSED [ 33%]
tests/test_knowledge_smoke.py::test_supported_extensions_are_sets              PASSED [ 40%]
tests/test_knowledge_smoke.py::test_llm_unavailable_without_api_key            PASSED [ 46%]
tests/test_knowledge_smoke.py::test_llm_available_with_explicit_api_key        PASSED [ 53%]
tests/test_knowledge_smoke.py::test_llm_available_via_env                      PASSED [ 60%]
tests/test_knowledge_smoke.py::test_extract_entities_returns_empty_when_no_key PASSED [ 66%]
tests/test_knowledge_smoke.py::test_plan_query_falls_back_when_no_key          PASSED [ 73%]
tests/test_knowledge_smoke.py::test_aggregate_answers_concatenates_when_no_key PASSED [ 80%]
tests/test_knowledge_smoke.py::test_embedder_instantiates_without_loading_model PASSED [ 86%]
tests/test_knowledge_smoke.py::test_embedder_accepts_explicit_model_name       PASSED [ 93%]
tests/test_knowledge_smoke.py::test_lazy_imports_via_subprocess                PASSED [100%]

================= 15 passed, 1 warning in 1.45s ==================
```

### Regression: baseline vs. after

Baseline (before any of my edits — captured with the same command):

```
$ pytest dashboard/tests/ -k "not knowledge" --no-header -q | tail -3
...
88 failed, 568 passed, 1 skipped, 14 warnings, 18 errors in 12.39s
```

After (post-EPIC-001):

```
$ pytest dashboard/tests/ -k "not knowledge" --no-header -q | tail -3
...
88 failed, 568 passed, 1 skipped, 15 deselected, 14 warnings, 18 errors in 12.13s
```

**568 passed in both runs — zero regressions.** The 88 failures + 18 errors
in non-knowledge tests are pre-existing on this branch (unrelated to this EPIC,
mostly `test_settings_resolver.py` AttributeErrors and other pre-existing
breaks in `test_amem_*`, `test_user_management`, etc.). The `15 deselected`
in the "after" run reflects the new `test_knowledge_smoke.py` tests being
correctly excluded by the `-k "not knowledge"` filter.

## Acceptance criteria self-check

- [x] No file in `dashboard/knowledge/` references `app.*` — verified via `grep`.
- [x] No `import dspy` anywhere in `dashboard/knowledge/` — verified via `grep`.
- [x] `dashboard/knowledge/__init__.py` exports the documented public symbols and
      only those — see `__all__` in the file.
- [x] Smoke test imports complete in <3 seconds — `test_lazy_imports_via_subprocess`
      enforces a 30s timeout and runs in ~1.5s end-to-end (15 tests in 1.45s wall
      clock per pytest output).
- [x] All deleted modules verified gone — see deleted-modules check above.
- [x] Engineer's done report enumerates every file deleted with one-line
      justification — see "What I deleted" table above.

## Definition of Done — explicit check

- [x] `python -c "from dashboard.knowledge import KnowledgeService, KnowledgeLLM, KnowledgeEmbedder, KuzuLabelledPropertyGraph, RAGStorage, GraphRAGExtractor, GraphRAGQueryEngine"` succeeds with no errors.
- [x] `pytest dashboard/tests/test_knowledge_smoke.py -v` passes — 15/15.
- [x] `grep -r "from app\." dashboard/knowledge/` returns zero matches (only the comment line, not an import).
- [x] `grep -r "import app\." dashboard/knowledge/` returns zero matches.
- [x] Deleted modules confirmed gone.
- [x] `dashboard/knowledge/config.py`, `llm.py`, `embeddings.py` exist with the documented APIs.
- [x] `dashboard/requirements.txt` updated with the 9 new packages.

(QA can run `pip install -r dashboard/requirements.txt` in a fresh venv to
confirm the dependency resolution gate; I did not run that here because the
local environment already has them.)

## Open issues / known limits

1. **Vietnamese prompts in `graph/prompt.py`** are still on disk (the file is
   unchanged). They are no longer consumed by the new `KnowledgeLLM` (which
   has its own English prompts with a `language` parameter), but they remain
   referenced by `extract_KP_fn`/`extract_KP_json_fn` in `graph/utils/rag.py`
   for back-compat. Consumers that build prompts via those helpers will still
   get Vietnamese text. ADR-10 calls for parameterisation; the new
   `KnowledgeLLM` is the parameterised path. Removing the old prompt module
   entirely is an EPIC-002+ cleanup.

2. **`SignificanceAnalyzer` was removed** — `track_vector_retriever`'s
   significance-filtering branch is now a no-op (set `use_significance_filtering=False`
   by default). All triplets are kept and scored via the simple combined score.
   This is acceptable for v1; the original logic was complex statistical
   analysis with adaptive baseline thresholds — porting it forward without the
   numpy/scipy stack it used was out of scope for EPIC-001.

3. **`pyvis` dependency removed** — `GraphRAGStore.to_json_graph()` no longer
   produces interactive HTML output; it returns a plain `{nodes, edges}` dict.
   Frontend consumers can render this however they like.

4. **`graph/core/rag_service.py` deleted** — see "What I deleted" table above.
   The new `KnowledgeService` (placeholder in this EPIC, fully built in EPIC-002)
   replaces it cleanly.

5. **`KuzuLabelledPropertyGraph` path semantics unchanged** — TASK-007 in
   EPIC-002 will rewire `database_path` to `KNOWLEDGE_DIR/{namespace}/graph.db`
   exactly. For now `KUZU_DATABASE_PATH = str(KNOWLEDGE_DIR)` and the legacy
   "treat path as directory + append `{index}.db`" behaviour is preserved so
   existing tests can still construct the class.

6. **Pre-existing pydantic warning** at import time:
   `UnsupportedFieldAttributeWarning: The 'validate_default' attribute ...`
   This warning predates the refactor; it's emitted by some llama-index
   internals. Not caused by EPIC-001 changes.

## ADR compliance

| ADR | Status | Notes |
|---|---|---|
| ADR-01 (`~/.ostwin/knowledge/{namespace}/`) | ✅ | `KNOWLEDGE_DIR` defaults to `~/.ostwin/knowledge`; per-namespace path helpers live in `config.py`. |
| ADR-02 (Direct Anthropic SDK + graceful degradation) | ✅ | `KnowledgeLLM` uses `anthropic.Anthropic` (lazy import); methods return empty/passthrough values when no key. Verified by 4 smoke tests. |
| ADR-03 (sentence-transformers + BAAI/bge-small-en-v1.5, 384-dim) | ✅ | Defaults in `config.py`. `KnowledgeEmbedder` lazy-loads the model. |
| ADR-04 (ChromaDB) | ✅ | `init_vector_store` lazy-imports `chromadb`. |
| ADR-05 (KuzuDB) | ✅ | `KuzuLabelledPropertyGraph` lazy-imports `kuzu`. |
| ADR-06 (MarkItDown) | ✅ | `MarkitdownReader` lazy-imports `markitdown.MarkItDown`. |
| ADR-07 (Streamable-HTTP MCP at `/mcp`) | N/A | EPIC-006. |
| ADR-08 (in-process executor + manifest persistence) | N/A | EPIC-002/003. |
| ADR-09 (drop mem0/, parsers/{docx,sheet,raw}, significance_analyzer) | ✅ | All deleted. **Plus** `processing/document_router.py` and `rag_service.py` (latter is a deviation — see "What I deleted"). |
| ADR-10 (drop Vietnamese-locked prompts → parameterise) | ⚠️ Partial | `KnowledgeLLM` is fully parameterised (English prompts + `language` param). The legacy Vietnamese prompts in `graph/prompt.py` remain on disk for back-compat with `extract_KP_*_fn` helpers but are no longer reachable from the new `KnowledgeLLM` path. EPIC-002+ should remove the legacy prompt module entirely once nothing references it. |
| ADR-11 (drop DSPy) | ✅ | Zero `dspy` imports anywhere in `dashboard/knowledge/`. |
| ADR-12 (namespace ID format) | N/A | EPIC-002 will enforce in `NamespaceManager.validate_id`. |
| ADR-13 (MCP bearer-token auth) | N/A | EPIC-006. |

## ADR deviations (explicit list)

1. **`graph/core/rag_service.py` deleted (not in TASK-001's deletion list).**
   Justification: the file's only entry point (`RAGService`) depended on
   `app.middlewares.folder.FolderMiddleware`, `app.core.database.local_database.local_db`,
   and `app.i18n.translator` — none of which exist in the dashboard. The plan's
   TASK-010 explicitly does NOT export `RAGService`, so the new public API
   already excludes it; removing the file rather than partial-stubbing it keeps
   the package coherent. EPIC-002's `KnowledgeService` is the proper successor.

2. **ADR-10 only partially honoured.** The new `KnowledgeLLM` uses
   English prompts parameterised by `language`. The old Vietnamese strings
   remain in `graph/prompt.py` for backwards compatibility with the
   `extract_KP_fn`/`extract_KP_json_fn` helpers in `graph/utils/rag.py`. These
   helpers are no longer used by the refactored `GraphRAGExtractor` (which
   calls `KnowledgeLLM.extract_entities` directly), but they're kept exported
   so external consumers don't break. Full removal is queued for an EPIC-002+
   cleanup.

No other deviations.
