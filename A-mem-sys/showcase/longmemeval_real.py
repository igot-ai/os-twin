#!/usr/bin/env python3
"""
LongMemEval Real Benchmark for A-mem-sys
==========================================

Two modes:
  --mode raw   Pure embedder baseline (no A-mem-sys features). Fast (~13min full).
  --mode full  Full AgenticMemorySystem: Gemini LLM analysis, Gemini embeddings,
               zvec backend, metadata-enhanced documents. Slower (~2-3min/instance).

Usage:
  # Raw baseline (embedder only, no API key)
  .venv/bin/python showcase/longmemeval_real.py --mode raw --slice 500 --seed 42

  # Full system, small validation slice (~20min)
  .venv/bin/python showcase/longmemeval_real.py --mode full --slice 10 --seed 42 --verbose

  # Full system, 25 instances (~60min)
  .venv/bin/python showcase/longmemeval_real.py --mode full --slice 25 --seed 42

  # Full system, 100 instances (~4h)
  .venv/bin/python showcase/longmemeval_real.py --mode full --slice 100 --seed 42 --json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys
import tempfile
import time
from collections import defaultdict
from typing import Any


# ---------------------------------------------------------------------------
# API key loading
# ---------------------------------------------------------------------------


def _load_api_key() -> str | None:
    """Load GOOGLE_API_KEY from env or .env files."""
    key = os.environ.get("GOOGLE_API_KEY", "")
    if key:
        return key
    for path in [
        os.path.expanduser("~/.ostwin/.env"),
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
        ),
        ".env",
    ]:
        if os.path.exists(path):
            for line in open(path):
                if line.startswith("GOOGLE_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    if key:
                        os.environ["GOOGLE_API_KEY"] = key
                        return key
    return None


# ---------------------------------------------------------------------------
# Adapter: Raw (pure embedder, no A-mem-sys features)
# ---------------------------------------------------------------------------


class RawAdapter:
    """Pure embedder baseline. Tests ONLY the embedding model + vector index.
    Identical results regardless of which memory system wraps it."""

    label = "raw"

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from agentic_memory.retrievers import ChromaRetriever

        self._model_name = model_name
        self.retriever = ChromaRetriever(
            model_name=model_name,
            embedding_backend="sentence-transformer",
        )

    def insert_batch(self, sessions, session_ids):
        documents = []
        metadatas = []
        unique_ids = []
        seen: dict[str, int] = {}
        for sid, session in zip(session_ids, sessions):
            text = "\n".join(f"{t['role']}: {t['content']}" for t in session)
            documents.append(text)
            metadatas.append({"session_id": sid})
            count = seen.get(sid, 0)
            seen[sid] = count + 1
            unique_ids.append(f"{sid}__{count}" if count > 0 else sid)
        self.retriever.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=unique_ids,
        )

    def retrieve(self, query: str, top_k: int = 5):
        results = self.retriever.search(query, k=top_k)
        ids = results["ids"][0]
        distances = results["distances"][0]
        metadatas = results["metadatas"][0]
        return [
            (
                meta.get("session_id", ids[i]) if isinstance(meta, dict) else ids[i],
                distances[i],
            )
            for i, meta in enumerate(metadatas)
        ]

    def clear(self):
        self.retriever.clear()

    def describe(self):
        return f"Raw embedder ({self._model_name}) + ChromaDB HNSW"


# ---------------------------------------------------------------------------
# Adapter: Full AgenticMemorySystem (Gemini LLM + Gemini embeddings + zvec)
# ---------------------------------------------------------------------------


class FullSystemAdapter:
    """Full A-mem-sys pipeline: Gemini LLM analysis generates keywords/tags/
    context for each session, Gemini embeddings encode the metadata-enhanced
    document, zvec stores and retrieves.

    This tests what A-mem-sys actually does in production.
    Requires GOOGLE_API_KEY.
    """

    label = "full"

    def __init__(
        self,
        embedding_model: str = "gemini-embedding-001",
        llm_model: str = "gemini-3-flash-preview",
    ):
        from agentic_memory.memory_system import AgenticMemorySystem

        self._embedding_model = embedding_model
        self._llm_model = llm_model
        self._tmpdir = tempfile.mkdtemp(prefix="longmemeval_full_")
        self._session_map: dict[str, str] = {}  # note_id -> session_id

        self.system = AgenticMemorySystem(
            model_name=embedding_model,
            embedding_backend="gemini",
            vector_backend="zvec",
            llm_backend="gemini",
            llm_model=llm_model,
            persist_dir=self._tmpdir,
            context_aware_analysis=False,  # skip context-aware for speed
            max_links=0,
        )
        # Skip evolution step entirely (no LLM call for should_evolve)
        # This halves per-note time without affecting retrieval quality
        self.system.process_memory = lambda note: (False, note)

    def insert_batch(self, sessions, session_ids):
        self._session_map.clear()
        seen: dict[str, int] = {}
        for sid, session in zip(session_ids, sessions):
            text = "\n".join(f"{t['role']}: {t['content']}" for t in session)
            try:
                note_id = self.system.add_note(text)
            except Exception as e:
                # Rate limit or transient error -- retry once after pause
                time.sleep(2.0)
                try:
                    note_id = self.system.add_note(text)
                except Exception:
                    sys.stderr.write(f"\n  WARN: skipped session {sid}: {e}\n")
                    continue

            # Handle duplicate session_ids
            count = seen.get(sid, 0)
            seen[sid] = count + 1
            self._session_map[note_id] = sid

    def retrieve(self, query: str, top_k: int = 5):
        results = self.system.search(query, k=top_k)
        out = []
        for r in results:
            note_id = r["id"]
            sid = self._session_map.get(note_id, note_id)
            score = r.get("score", 0.0)
            out.append((sid, score))
        return out

    def clear(self):
        self.system.memories.clear()
        self.system.retriever.clear()
        self._session_map.clear()

    def cleanup(self):
        """Remove temp directory."""
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def describe(self):
        return (
            f"A-mem-sys full pipeline: {self._llm_model} (LLM) "
            f"+ {self._embedding_model} (embedder) + zvec"
        )


# ---------------------------------------------------------------------------
# Evaluation core
# ---------------------------------------------------------------------------


def evaluate_instance(adapter, instance: dict[str, Any], top_k: int) -> dict[str, Any]:
    adapter.clear()

    sessions = instance["haystack_sessions"]
    session_ids = instance["haystack_session_ids"]
    evidence = set(instance["answer_session_ids"] or [])
    is_abstention = instance["question_id"].endswith("_abs")
    question = instance["question"]

    t0 = time.time()
    adapter.insert_batch(sessions, session_ids)
    t_index = time.time() - t0

    t0 = time.time()
    hits = adapter.retrieve(question, top_k)
    t_retrieve = time.time() - t0

    retrieved_ids = [sid for sid, _score in hits]

    result: dict[str, Any] = {
        "question_id": instance["question_id"],
        "question_type": instance["question_type"],
        "is_abstention": is_abstention,
        "n_sessions": len(sessions),
        "n_evidence": len(evidence),
        "latency_index_s": t_index,
        "latency_retrieve_s": t_retrieve,
        "latency_total_s": t_index + t_retrieve,
    }

    if is_abstention:
        result["recall"] = None
        result["hit_at_1"] = None
        result["correct_refusal"] = None
    else:
        found = set(retrieved_ids) & evidence
        result["recall"] = len(found) / len(evidence) if evidence else 0.0
        result["hit_at_1"] = int(retrieved_ids[0] in evidence) if retrieved_ids else 0
        result["n_found"] = len(found)

    return result


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------


def load_dataset(path: str) -> list[dict[str, Any]]:
    with open(path) as f:
        data = json.load(f)
    required = {
        "question_id",
        "question_type",
        "question",
        "answer",
        "haystack_session_ids",
        "haystack_sessions",
        "answer_session_ids",
    }
    if data:
        missing = required - set(data[0].keys())
        if missing:
            print(f"WARNING: dataset missing fields: {missing}", file=sys.stderr)
    return data


def select_slice(data, n, seed, exclude_abstention=False):
    if exclude_abstention:
        data = [d for d in data if not d["question_id"].endswith("_abs")]
    if n >= len(data):
        return data
    return random.Random(seed).sample(data, n)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_results(
    results, top_k, adapter_desc, dataset_path, wall_time_s, as_json=False
):
    answerable = [r for r in results if not r["is_abstention"]]
    abstention = [r for r in results if r["is_abstention"]]

    if not answerable:
        print("No answerable instances to evaluate.")
        return

    avg_recall = sum(r["recall"] for r in answerable) / len(answerable)
    avg_hit1 = sum(r["hit_at_1"] for r in answerable) / len(answerable)
    avg_latency = sum(r["latency_total_s"] for r in answerable) / len(answerable)
    avg_sessions = sum(r["n_sessions"] for r in answerable) / len(answerable)

    by_type: dict[str, list] = defaultdict(list)
    for r in answerable:
        by_type[r["question_type"]].append(r)

    type_stats = {}
    for qtype, rs in sorted(by_type.items()):
        n = len(rs)
        type_stats[qtype] = {
            "n": n,
            "recall": sum(r["recall"] for r in rs) / n,
            "hit_at_1": sum(r["hit_at_1"] for r in rs) / n,
        }

    if as_json:
        print(
            json.dumps(
                {
                    "system": adapter_desc,
                    "dataset": os.path.basename(dataset_path),
                    "top_k": top_k,
                    "n_total": len(results),
                    "n_answerable": len(answerable),
                    "n_abstention": len(abstention),
                    "session_recall_at_k": round(avg_recall, 4),
                    "session_hit_at_1": round(avg_hit1, 4),
                    "avg_latency_s": round(avg_latency, 3),
                    "avg_sessions_per_instance": round(avg_sessions, 1),
                    "wall_time_s": round(wall_time_s, 1),
                    "by_question_type": {
                        qt: {
                            "n": s["n"],
                            "recall": round(s["recall"], 4),
                            "hit_at_1": round(s["hit_at_1"], 4),
                        }
                        for qt, s in type_stats.items()
                    },
                },
                indent=2,
            )
        )
        return

    print()
    print("=" * 72)
    print("  LongMemEval Retrieval Benchmark — A-mem-sys")
    print("=" * 72)
    print()
    print(f"  System:    {adapter_desc}")
    print(f"  Dataset:   {os.path.basename(dataset_path)}")
    print(
        f"  Instances: {len(answerable)} answerable"
        f" ({len(abstention)} abstention excluded)"
    )
    print(f"  Avg sessions/instance: ~{avg_sessions:.0f}")
    print()
    print(f"  session_recall@{top_k}:  {avg_recall:.1%}")
    print(f"  session_hit@1:       {avg_hit1:.1%}")
    print(f"  Avg latency:         {avg_latency:.2f} s/instance")
    print(f"  Total wall time:     {wall_time_s:.0f}s ({wall_time_s / 60:.1f}min)")
    print()

    print(f"  {'Question Type':<35s} {'n':>4s}  {'recall':>8s}  {'hit@1':>8s}")
    print(f"  {'-' * 35} {'-' * 4}  {'-' * 8}  {'-' * 8}")
    for qtype in sorted(type_stats.keys()):
        s = type_stats[qtype]
        print(f"  {qtype:<35s} {s['n']:4d}  {s['recall']:7.1%}  {s['hit_at_1']:7.1%}")

    print()
    print("  Comparison vs. LongMemEval paper baselines (full S split):")
    print()
    print(f"  {'System':<35s} {'Embedder':>16s}  {'recall@5':>9s}")
    print(f"  {'-' * 35} {'-' * 16}  {'-' * 9}")
    for name, size, score in [
        ("BM25", "sparse", "~70%"),
        ("Contriever", "110M", "~76%"),
        ("Stella V5", "1.5B", "~83%"),
        ("GTE-Qwen2-7B", "7B", "~85%"),
    ]:
        print(f"  {name:<35s} {size:>16s}  {score:>9s}")
    label = f"A-mem-sys (this run, n={len(answerable)})"
    emb = "gemini-emb-001" if "gemini" in adapter_desc.lower() else "MiniLM-22M"
    print(f"  {label:<35s} {emb:>16s}  {avg_recall:8.1%}")

    if abstention:
        print()
        print(f"  Abstention: {len(abstention)} instances excluded (no threshold).")
    print()


def progress_bar(current, total, width=40, extra=""):
    frac = current / total if total else 0
    filled = int(width * frac)
    bar = "#" * filled + "-" * (width - filled)
    return f"\r  [{bar}] {current:4d}/{total} ({frac:.0%}) {extra}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="LongMemEval real benchmark for A-mem-sys",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  raw    Pure embedder baseline (MiniLM + ChromaDB). No API key needed. Fast.
  full   Full A-mem-sys: Gemini LLM + Gemini embeddings + zvec. Needs GOOGLE_API_KEY.
         ~2-3 min/instance due to LLM analysis per session.

Sample sizes for --mode full:
  --slice 10   Validation (~20min)
  --slice 25   Small benchmark (~60min)
  --slice 100  Medium benchmark (~4h)
""",
    )
    parser.add_argument(
        "--mode",
        choices=["raw", "full"],
        default="full",
        help="Adapter mode (default: full)",
    )
    parser.add_argument("--dataset", default="data/longmemeval_s_cleaned.json")
    parser.add_argument("--slice", type=int, default=25)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--model", type=str, default=None, help="Embedding model override"
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default="gemini-3-flash-preview",
        help="LLM model for full mode (default: gemini-3-flash-preview)",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--no-abstention", action="store_true")
    args = parser.parse_args()

    # Resolve dataset path
    dataset_path = args.dataset
    if not os.path.isabs(dataset_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        candidate = os.path.join(parent_dir, dataset_path)
        if os.path.exists(candidate):
            dataset_path = candidate
        elif not os.path.exists(dataset_path):
            print(
                f"ERROR: Dataset not found: {dataset_path}\n"
                f"Download: wget -P data/ https://huggingface.co/datasets/"
                f"xiaowu0162/longmemeval-cleaned/resolve/main/"
                f"longmemeval_s_cleaned.json",
                file=sys.stderr,
            )
            return 1

    # Load API key for full mode
    if args.mode == "full":
        key = _load_api_key()
        if not key:
            print(
                "ERROR: --mode full requires GOOGLE_API_KEY.\n"
                "Set it in env, ~/.ostwin/.env, or .env",
                file=sys.stderr,
            )
            return 1

    # Load dataset
    if not args.json:
        print(
            f"Loading dataset: {os.path.basename(dataset_path)}...", end=" ", flush=True
        )
    data = load_dataset(dataset_path)
    if not args.json:
        print(f"{len(data)} instances")

    subset = select_slice(data, args.slice, args.seed, args.no_abstention)
    n_abs = sum(1 for d in subset if d["question_id"].endswith("_abs"))
    if not args.json:
        print(
            f"Selected {len(subset)} instances (seed={args.seed}, {n_abs} abstention)"
        )

    # Create adapter
    if not args.json:
        print(f"Initializing [{args.mode}] adapter...", end=" ", flush=True)
    t0 = time.time()

    if args.mode == "raw":
        model = args.model or "all-MiniLM-L6-v2"
        adapter = RawAdapter(model_name=model)
    else:
        emb_model = args.model or "gemini-embedding-001"
        adapter = FullSystemAdapter(
            embedding_model=emb_model,
            llm_model=args.llm_model,
        )

    if not args.json:
        print(f"done ({time.time() - t0:.1f}s)")
        print(f"  {adapter.describe()}")
        print()

    # Evaluate
    results = []
    wall_start = time.time()

    for i, instance in enumerate(subset, 1):
        result = evaluate_instance(adapter, instance, args.top_k)
        results.append(result)

        if args.verbose and not args.json:
            status = ""
            if result["is_abstention"]:
                status = "abstention (N/A)"
            else:
                status = f"recall={result['recall']:.0%}  hit@1={result['hit_at_1']}"
            print(
                f"  [{i:4d}/{len(subset)}] {result['question_type']:30s} "
                f"sessions={result['n_sessions']:3d}  "
                f"t={result['latency_total_s']:.0f}s  {status}"
            )
        elif not args.json:
            latency = result["latency_total_s"]
            extra = f"{latency:.1f}s"
            print(progress_bar(i, len(subset), extra=extra), end="", flush=True)

    wall_time = time.time() - wall_start
    if not args.json and not args.verbose:
        print()

    # Cleanup
    if hasattr(adapter, "cleanup"):
        adapter.cleanup()

    print_results(
        results,
        top_k=args.top_k,
        adapter_desc=adapter.describe(),
        dataset_path=dataset_path,
        wall_time_s=wall_time,
        as_json=args.json,
    )

    answerable = [r for r in results if not r["is_abstention"]]
    if answerable:
        avg_recall = sum(r["recall"] for r in answerable) / len(answerable)
        return 0 if avg_recall >= 0.70 else 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
