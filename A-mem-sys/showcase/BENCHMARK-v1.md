# A-mem-sys LongMemEval Benchmark Results

> **Run date:** 2026-04-09
> **Methodology:** LongMemEval (Wu et al., ICLR 2025; arXiv:2410.10813)
> **Dataset:** `longmemeval_s_cleaned.json` — 500 instances, ~47 sessions each

---

## 1. Headline Results

```
System:    A-mem-sys ChromaRetriever (in-memory)
Embedder:  all-MiniLM-L6-v2 (22M params, 384 dims)
Backend:   ChromaDB HNSW (cosine similarity)

session_recall@5:  85.9%
session_hit@1:     76.0%
Avg latency:       1.53 s/instance
Total wall time:   13.1 min (CPU)
Instances:         470 answerable (30 abstention excluded)
Avg sessions/instance: ~47 (only ~2 contain the answer)
```

### Comparison vs. LongMemEval Paper Baselines (Full S Split)

| System             | Embedder size | session_recall@5 |
|--------------------|------------:|----------------:|
| BM25               |           — |            ~70% |
| Contriever         |        110M |            ~76% |
| Stella V5          |        1.5B |            ~83% |
| GTE-Qwen2-7B       |          7B |            ~85% |
| **A-mem-sys**      |      **22M** |        **85.9%** |

A-mem-sys matches GTE-Qwen2-7B with a **320x smaller embedder**.

---

## 2. Per-Category Breakdown

| Question Type               |   n | recall@5 | hit@1 |
|-----------------------------|----:|---------:|------:|
| single-session-assistant    |  56 |   98.2%  | 98.2% |
| knowledge-update            |  72 |   87.5%  | 77.8% |
| multi-session               | 121 |   85.7%  | 86.0% |
| single-session-preference   |  30 |   83.3%  | 50.0% |
| temporal-reasoning          | 127 |   82.7%  | 73.2% |
| single-session-user         |  64 |   81.2%  | 53.1% |

### What the LongMemEval Abilities Test

| Ability                  | What it tests                                    |
|--------------------------|--------------------------------------------------|
| Information Extraction   | Recall a fact stated in one past session          |
| Multi-Session Reasoning  | Synthesize info scattered across many sessions    |
| Knowledge Updates        | Use the *latest* version of a changing fact       |
| Temporal Reasoning       | Time-relative queries ("last month", "after X")   |
| Abstention               | Refuse to answer when info was never given        |

---

## 3. Where Failures Live

### Weakest: `single-session-user` (81.2% recall, 53.1% hit@1)

The question targets a specific detail buried in a session whose dominant
topic is something else. The session's mean embedding is dominated by the
majority topic; the brief mention is washed out.

**Example failure pattern:**
- Question: *"Who gave me a new stand mixer as a birthday gift?"*
- Evidence session: a 12-turn conversation about caramel pastry recipes,
  with one user turn mentioning in passing: *"I actually got my new stand
  mixer as a birthday gift from my sister last month..."*
- The session embedding is dominated by caramel/pastry/baking terms;
  the gift mention ranks below five other dessert-related sessions.

### Knowledge-update: 87.5% recall, but 77.8% hit@1

Both the OLD fact and NEW fact rank highly. The system has no recency
awareness, so the outdated fact often ranks first.

### Temporal-reasoning: 82.7% recall, 73.2% hit@1

No temporal indexing exists. Queries like "what happened after X" rely
entirely on semantic similarity, which doesn't encode temporal order.

### Abstention: Not evaluated (N/A)

A-mem-sys has no similarity threshold — it always returns top-k results
regardless of confidence. Abstention requires a calibrated threshold
below which the system reports "I don't know."

---

## 4. Improvement Roadmap

Ten strategies prioritized by expected impact on the weakest categories.
Based on the LongMemEval paper's ablation studies and the existing
A-mem-sys codebase analysis.

### Priority 1: Fact-Augmented Key Expansion

**Target:** single-session-user (81.2%), single-session-preference (83.3%)
**Expected gain:** +6-10% recall@5
**Effort:** Medium

The LongMemEval paper's single largest retrieval improvement (+9.4%
recall@k). During indexing, an LLM extracts atomic factual assertions
from each session and appends them to the document before embedding.

**How it works:**
```
session text ──[LLM extraction]──> ["user's sister gave them a stand mixer",
                                    "user started making caramel pastries"]
                                       │
embedding = embed(session_text + " facts: " + "; ".join(facts))
```

The key insight: queries about specific facts match the extracted fact
strings far better than they match the session's overall topic embedding.

**A-mem-sys leverage:** The `_build_enhanced_document()` function in
`retrievers.py:55` already appends metadata (context, keywords, tags)
to documents before embedding. Adding a `facts` field follows the same
pattern. The `analyze_content()` LLM prompt in `memory_system.py:361`
already extracts keywords and context — extending it to extract facts
is a prompt change, not an architecture change.

```python
# In _build_enhanced_document():
facts = _parse_json_field(metadata, "facts")
if facts:
    enhanced += f" facts: {'; '.join(facts)}"
```

### Priority 2: Time-Aware Query Expansion

**Target:** temporal-reasoning (82.7%)
**Expected gain:** +7-11% recall@5
**Effort:** Medium

When a query contains temporal references ("last month", "after I moved"),
use the LLM to infer a time range, then filter or boost results within
that range. The LongMemEval paper shows +6.8% for session-level indexing
and +11.3% for round-level.

**A-mem-sys leverage:** `MemoryNote` already stores `timestamp` (set at
creation in `memory_note.py:85`) and this timestamp is already passed
into vector metadata (`memory_system.py:510`). But no search method
reads it. The infrastructure is there — only the temporal filtering
logic is missing.

**Implementation sketch:**
1. Detect temporal references in query (LLM or regex)
2. Infer approximate date range
3. Retrieve top-k*3 candidates from vector search
4. Filter/boost by timestamp overlap with inferred range
5. Return top-k from filtered set

### Priority 3: Hybrid BM25 + Dense Retrieval

**Target:** single-session-user (81.2%), all categories
**Expected gain:** +2-4% recall@5
**Effort:** Medium

BM25 catches exact keyword matches that dense embeddings miss. The
A-mem-sys codebase already has `rank_bm25` imported and a tokenizer
ready (`simple_tokenize()` at `retrievers.py:18`) — but neither is
ever called. There's even a dead `_search()` method at
`memory_system.py:929` that calls the retriever twice, clearly a vestige
of an intended dual-retriever design.

**Implementation:** Build a BM25 index alongside the vector index.
At query time, run both, fuse results with Reciprocal Rank Fusion:

```python
rrf_score[doc] = alpha / (60 + dense_rank) + (1 - alpha) / (60 + bm25_rank)
```

BM25 is especially strong for entity-name queries ("What breed is my
dog?") where the exact word "breed" appears in the evidence but the
embedding captures only general "pet/animal" semantics.

### Priority 4: Query Decomposition for Multi-Session

**Target:** multi-session (85.7%)
**Expected gain:** +5-8% recall@5
**Effort:** Low

Multi-session queries need information from 2-6 different sessions.
A single query vector can't match all of them equally.

**Implementation:** Use the LLM to decompose complex queries into
2-3 sub-queries, retrieve for each, and merge results:

```
"What programming languages do I know and what am I learning?"
   ├──> "programming languages the user knows"     → retrieves session A
   └──> "programming language currently learning"   → retrieves session B
```

### Priority 5: Recency-Weighted Scoring

**Target:** knowledge-update (87.5% recall, 77.8% hit@1)
**Expected gain:** +3-5% hit@1
**Effort:** Low

Add a time-decay factor to retrieval scores so newer facts rank higher
when multiple sessions match equally:

```python
combined_score = (1 - w) * cosine_sim + w * recency_factor
```

**A-mem-sys leverage:** `timestamp` and `last_accessed` fields exist on
every note but are **never used in retrieval ranking** and `last_accessed`
is never updated after creation. `retrieval_count` is initialized to 0
and **never incremented** — it's a dead field.

Fix: increment `retrieval_count` on every search hit, update
`last_accessed`, and use both for scoring.

### Priority 6: Round-Level Indexing

**Target:** single-session-user (81.2%)
**Expected gain:** +3-5% recall@5
**Effort:** Low (benchmark change only)

Instead of embedding an entire session as one vector, split into
individual rounds (one user message + one assistant response). Each
round gets its own vector. The evidence turn is no longer diluted by
the surrounding session context.

**Tradeoff:** 3-5x more vectors per instance. At ~47 sessions with
~4 rounds each, that's ~188 vectors per instance instead of ~47.
Storage and indexing cost increase, but retrieval precision improves.

The LongMemEval paper shows round-level is strictly better than
session-level for most question types.

### Priority 7: Abstention Threshold

**Target:** abstention (currently N/A)
**Expected gain:** New capability
**Effort:** Low

**Calibration method:**
1. Run the benchmark, collect `(query, best_distance, is_answerable)`
2. Plot distance distributions for answerable vs. abstention instances
3. Find the threshold that maximizes F1 between correct abstentions
   and correct retrievals
4. Apply as a configurable parameter

### Priority 8: Embedding Model Upgrade

**Target:** all categories
**Expected gain:** +2-5% recall@5
**Effort:** Very low (config change)

Options already supported by A-mem-sys:
- `gemini-embedding-001` — already implemented in `GeminiEmbeddingFunction`,
  zero code changes, but adds API latency/cost
- `nomic-embed-text-v1.5` (137M) — ~3% better than MiniLM on MTEB
- `Stella V5` (1.5B) — the paper's primary retriever

Current MiniLM-L6-v2 already matches 7B-param baselines, so this is
low priority unless other improvements plateau.

### Priority 9: Chain-of-Note Reading Strategy

**Target:** all categories (QA accuracy, not retrieval recall)
**Expected gain:** +5-10% QA accuracy
**Effort:** Low (prompt change)

The LongMemEval paper shows Chain-of-Note + JSON format improves
end-to-end QA accuracy by up to 10 points. Instead of returning raw
results, structure the `search_memory` MCP tool output to guide the
calling agent:

```json
{
  "instruction": "For each memory below, extract the specific information
                  relevant to the query, then synthesize across all notes.",
  "memories": [...]
}
```

### Priority 10: User-Side Key Extraction

**Target:** single-session-user (81.2%)
**Expected gain:** +1-3% recall@5
**Effort:** Low

The paper recommends keeping only user-side utterances in the embedding
key. Assistant responses dilute the signal when the query targets
something the user said. For A-mem-sys notes (which are usually
agent-written, not raw conversations), this matters less — but for any
conversation-log ingestion, filtering to user turns before embedding
would help.

---

## 5. Existing Untapped Infrastructure

The A-mem-sys codebase has several features that are partially built but
not connected to the retrieval path:

| Feature | Status | Where |
|---------|--------|-------|
| BM25 index | Imported, never used | `retrievers.py:3`, `memory_system.py:35` |
| `simple_tokenize()` | Defined, never called | `retrievers.py:18` |
| Dead `_search()` method | Dual-retriever skeleton | `memory_system.py:929` |
| `timestamp` field | Stored, never ranked by | `memory_note.py:85`, `memory_system.py:510` |
| `retrieval_count` | Always 0, never incremented | `memory_note.py:90` |
| `last_accessed` | Set once, never updated | `memory_note.py:87` |
| `search_agentic()` | Graph traversal, not exposed via MCP | `memory_system.py:994` |
| Evolution `process_memory()` | Links notes, doesn't extract facts | `memory_system.py:1144` |
| Summary-based embedding | Uses summary instead of full text for long notes | `retrievers.py:57-58` |

---

## 6. Combined Impact Estimate

Based on the LongMemEval paper's demonstrated gains being largely additive:

| Strategies Combined | Estimated recall@5 |
|---------------------|-------------------:|
| Current baseline | 85.9% |
| + Fact-augmented keys (#1) | ~92% |
| + Temporal query expansion (#2) | ~94% |
| + Hybrid BM25 (#3) | ~95% |
| + Query decomposition (#4) | ~96% |

The paper's best combined system (round-level + fact-expanded key +
time-aware query + CoN reading) achieves the highest numbers across all
categories.

---

## 7. Reproducing These Results

### Synthetic smoke test (~30s, no downloads)
```bash
cd A-mem-sys
.venv/bin/python showcase/longmemeval_bench.py --verbose
```

### Real benchmark — 5% slice (~40s, pipeline validation)
```bash
.venv/bin/python showcase/longmemeval_real.py --slice 25 --seed 42
```

### Real benchmark — full run (~13min, publishable number)
```bash
.venv/bin/python showcase/longmemeval_real.py --slice 500 --seed 42 --top-k 5
```

### JSON output for downstream processing
```bash
.venv/bin/python showcase/longmemeval_real.py --slice 500 --seed 42 --json
```

### Dataset download
```bash
mkdir -p data/
wget -P data/ https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_s_cleaned.json
wget -P data/ https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_oracle.json
```

---

## 8. References

- Wu et al., *LongMemEval: Benchmarking Chat Assistants on Long-Term
  Interactive Memory*, ICLR 2025. https://arxiv.org/abs/2410.10813
- LongMemEval code: https://github.com/xiaowu0162/LongMemEval
- Cleaned datasets: https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned
- Harness code: `showcase/longmemeval_bench.py`, `showcase/longmemeval_real.py`
