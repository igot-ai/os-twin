#!/usr/bin/env python
"""Knowledge System Benchmark CLI (EPIC-008).

Measures performance metrics for the Knowledge system:
- Ingestion throughput (docs/s, MB/s)
- Query latency (p50/p95/p99) per mode per top_k
- Backup duration
- Restore duration
- Peak RSS (memory usage)

Outputs:
- Markdown table to stdout
- Full results to dashboard/docs/knowledge-bench-results.md

Usage:
    python dashboard/scripts/bench_knowledge.py [--namespace NAME] [--docs N] [--queries N]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import statistics
import sys
import time
import tracemalloc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Ensure dashboard is importable
_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


@dataclass
class BenchmarkResult:
    """Container for benchmark results."""
    name: str
    value: float
    unit: str
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkReport:
    """Full benchmark report."""
    timestamp: str
    namespace: str
    docs_count: int
    total_bytes: int
    ingestion: list[BenchmarkResult]
    queries_raw: list[dict[str, float]]
    queries_graph: list[dict[str, float]]
    queries_summarized: list[dict[str, float]]
    backup: Optional[BenchmarkResult] = None
    restore: Optional[BenchmarkResult] = None
    peak_rss_mb: float = 0.0

    def to_markdown(self) -> str:
        """Convert to markdown table format."""
        lines = [
            f"# Knowledge System Benchmark Results",
            f"",
            f"**Timestamp:** {self.timestamp}",
            f"**Namespace:** {self.namespace}",
            f"**Documents:** {self.docs_count}",
            f"**Total Size:** {self.total_bytes / 1024 / 1024:.2f} MB",
            f"",
            f"## Ingestion Throughput",
            f"",
            f"| Metric | Value | Unit |",
            f"|--------|-------|------|",
        ]
        for r in self.ingestion:
            lines.append(f"| {r.name} | {r.value:.2f} | {r.unit} |")

        lines.extend([
            f"",
            f"## Query Latency (ms)",
            f"",
            f"| Mode | Top-K | P50 | P95 | P99 | Avg | Count |",
            f"|------|-------|-----|-----|-----|-----|-------|",
        ])

        for mode, queries in [
            ("raw", self.queries_raw),
            ("graph", self.queries_graph),
            ("summarized", self.queries_summarized),
        ]:
            for q in queries:
                lines.append(
                    f"| {mode} | {q.get('top_k', 'N/A')} | "
                    f"{q.get('p50', 0):.1f} | {q.get('p95', 0):.1f} | "
                    f"{q.get('p99', 0):.1f} | {q.get('avg', 0):.1f} | "
                    f"{q.get('count', 0)} |"
                )

        lines.extend([
            f"",
            f"## Backup & Restore",
            f"",
            f"| Operation | Duration (s) | Size (MB) |",
            f"|-----------|--------------|-----------|",
        ])

        if self.backup:
            lines.append(f"| Backup | {self.backup.value:.2f} | {self.backup.extra.get('size_mb', 0):.2f} |")
        if self.restore:
            lines.append(f"| Restore | {self.restore.value:.2f} | {self.restore.extra.get('size_mb', 0):.2f} |")

        lines.extend([
            f"",
            f"## Memory",
            f"",
            f"| Metric | Value | Unit |",
            f"|--------|-------|------|",
            f"| Peak RSS | {self.peak_rss_mb:.1f} | MB |",
            f"",
        ])

        return "\n".join(lines)


def create_test_documents(target_dir: Path, count: int) -> int:
    """Create test documents for benchmarking.

    Returns total bytes written.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    total_bytes = 0

    for i in range(count):
        # Create varied document types
        if i % 3 == 0:
            # Markdown file
            content = f"""# Document {i}

This is test document number {i} for benchmarking the Knowledge system.

## Section 1

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor
incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis
nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.

## Section 2

Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore
eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt
in culpa qui officia deserunt mollit anim id est laborum.

## Keywords

- benchmark
- testing
- knowledge-{i}
- document-{i}
"""
            ext = ".md"
        elif i % 3 == 1:
            # JSON file
            data = {
                "id": i,
                "type": "benchmark",
                "title": f"Benchmark Document {i}",
                "content": f"This is the content for benchmark document {i}. " * 10,
                "tags": ["benchmark", "testing", f"doc-{i}"],
                "metadata": {
                    "created": datetime.now(timezone.utc).isoformat(),
                    "version": "1.0",
                }
            }
            content = json.dumps(data, indent=2)
            ext = ".json"
        else:
            # Plain text
            content = f"""Benchmark Document {i}

This is a plain text document for testing the Knowledge system ingestion
pipeline. Document number: {i}

Content paragraph:
""" + ("Lorem ipsum dolor sit amet. " * 50)
            ext = ".txt"

        file_path = target_dir / f"doc_{i:04d}{ext}"
        file_path.write_text(content)
        total_bytes += len(content.encode('utf-8'))

    return total_bytes


def measure_latency_samples(
    service: Any,
    namespace: str,
    mode: str,
    top_k: int,
    queries: list[str],
) -> list[float]:
    """Run queries and return latency samples in milliseconds."""
    samples = []
    for query in queries:
        start = time.perf_counter()
        try:
            service.query(namespace, query, mode=mode, top_k=top_k)
            elapsed = (time.perf_counter() - start) * 1000
            samples.append(elapsed)
        except Exception:
            pass  # Skip failed queries
    return samples


def compute_percentiles(samples: list[float]) -> dict[str, float]:
    """Compute p50, p95, p99, and avg from samples."""
    if not samples:
        return {"p50": 0, "p95": 0, "p99": 0, "avg": 0, "count": 0}

    sorted_samples = sorted(samples)
    n = len(sorted_samples)

    return {
        "p50": sorted_samples[n // 2],
        "p95": sorted_samples[int(n * 0.95)] if n > 1 else sorted_samples[0],
        "p99": sorted_samples[int(n * 0.99)] if n > 1 else sorted_samples[0],
        "avg": statistics.mean(samples),
        "count": n,
        "top_k": 10,  # Default top_k for this measurement
    }


def run_benchmark(
    namespace: str,
    docs_count: int,
    queries_count: int,
    output_path: Optional[Path] = None,
) -> BenchmarkReport:
    """Run the full benchmark suite."""
    from dashboard.knowledge.service import KnowledgeService
    from dashboard.knowledge.backup import backup_namespace, restore_namespace
    import tempfile

    # Start memory tracking
    tracemalloc.start()

    report = BenchmarkReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        namespace=namespace,
        docs_count=docs_count,
        total_bytes=0,
        ingestion=[],
        queries_raw=[],
        queries_graph=[],
        queries_summarized=[],
    )

    # Create temp directory for test documents
    with tempfile.TemporaryDirectory() as tmpdir:
        docs_dir = Path(tmpdir) / "docs"
        kb_dir = Path(tmpdir) / "kb"

        # Override knowledge directory
        os.environ["OSTWIN_KNOWLEDGE_DIR"] = str(kb_dir)

        print(f"Creating {docs_count} test documents...")
        total_bytes = create_test_documents(docs_dir, docs_count)
        report.total_bytes = total_bytes
        print(f"Created {docs_count} documents ({total_bytes / 1024 / 1024:.2f} MB)")

        # Initialize service
        service = KnowledgeService()

        # ================================================================
        # STEP 1: Create namespace
        # ================================================================
        print(f"Creating namespace: {namespace}")
        try:
            service.create_namespace(namespace)
        except Exception as e:
            if "already exists" not in str(e):
                raise

        # ================================================================
        # STEP 2: Ingestion benchmark
        # ================================================================
        print("Benchmarking ingestion...")
        start_time = time.perf_counter()
        job_id = service.import_folder(namespace, str(docs_dir))
        print(f"  Job ID: {job_id}")

        # Poll for completion
        deadline = time.time() + 300  # 5 minute timeout
        while time.time() < deadline:
            status = service.get_job(job_id)
            if status and status.state.value in ("completed", "failed", "cancelled", "interrupted"):
                break
            time.sleep(0.5)

        ingestion_time = time.perf_counter() - start_time

        if status and status.state.value == "completed":
            report.ingestion.append(BenchmarkResult(
                name="Throughput (docs/s)",
                value=docs_count / ingestion_time,
                unit="docs/s",
            ))
            report.ingestion.append(BenchmarkResult(
                name="Throughput (MB/s)",
                value=(total_bytes / 1024 / 1024) / ingestion_time,
                unit="MB/s",
            ))
            report.ingestion.append(BenchmarkResult(
                name="Total Duration",
                value=ingestion_time,
                unit="s",
            ))
            print(f"  Ingestion completed in {ingestion_time:.1f}s")
        else:
            print(f"  Ingestion failed: {status.state if status else 'unknown'}")

        # ================================================================
        # STEP 3: Query benchmarks
        # ================================================================
        print("Benchmarking queries...")

        # Generate query strings
        query_strings = [f"document {i}" for i in range(min(queries_count, docs_count))]
        if len(query_strings) < queries_count:
            query_strings.extend(["benchmark", "testing", "knowledge", "content"] * ((queries_count // 4) + 1))
            query_strings = query_strings[:queries_count]

        # Raw mode queries
        print("  Raw mode...")
        raw_samples = measure_latency_samples(service, namespace, "raw", 10, query_strings)
        report.queries_raw.append(compute_percentiles(raw_samples))

        # Graph mode queries (may fail without kuzu)
        print("  Graph mode...")
        try:
            graph_samples = measure_latency_samples(service, namespace, "graph", 10, query_strings[:10])
            if graph_samples:
                report.queries_graph.append(compute_percentiles(graph_samples))
        except Exception as e:
            print(f"    Skipped: {e}")

        # Summarized mode queries (may fail without LLM)
        print("  Summarized mode...")
        try:
            summ_samples = measure_latency_samples(service, namespace, "summarized", 5, query_strings[:5])
            if summ_samples:
                report.queries_summarized.append(compute_percentiles(summ_samples))
        except Exception as e:
            print(f"    Skipped: {e}")

        # ================================================================
        # STEP 4: Backup benchmark
        # ================================================================
        print("Benchmarking backup...")
        try:
            start_time = time.perf_counter()
            archive_path = backup_namespace(namespace, None, service._nm)
            backup_time = time.perf_counter() - start_time
            backup_size = archive_path.stat().st_size

            report.backup = BenchmarkResult(
                name="Backup Duration",
                value=backup_time,
                unit="s",
                extra={"size_mb": backup_size / 1024 / 1024, "path": str(archive_path)},
            )
            print(f"  Backup completed in {backup_time:.2f}s ({backup_size / 1024 / 1024:.2f} MB)")
        except Exception as e:
            print(f"  Backup failed: {e}")
            archive_path = None

        # ================================================================
        # STEP 5: Restore benchmark
        # ================================================================
        if archive_path and archive_path.exists():
            print("Benchmarking restore...")
            try:
                # Delete namespace first
                service.delete_namespace(namespace)

                start_time = time.perf_counter()
                restore_namespace(archive_path, namespace, service._nm, service, overwrite=True)
                restore_time = time.perf_counter() - start_time

                report.restore = BenchmarkResult(
                    name="Restore Duration",
                    value=restore_time,
                    unit="s",
                    extra={"size_mb": backup_size / 1024 / 1024},
                )
                print(f"  Restore completed in {restore_time:.2f}s")
            except Exception as e:
                print(f"  Restore failed: {e}")

        # ================================================================
        # STEP 6: Memory usage
        # ================================================================
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        report.peak_rss_mb = peak / 1024 / 1024
        print(f"Peak RSS: {report.peak_rss_mb:.1f} MB")

        # ================================================================
        # Cleanup
        # ================================================================
        try:
            service.delete_namespace(namespace)
        except Exception:
            pass

        if archive_path and archive_path.exists():
            try:
                archive_path.unlink()
            except Exception:
                pass

    # Write output
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report.to_markdown())
        print(f"\nResults written to: {output_path}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Knowledge System Benchmark")
    parser.add_argument(
        "--namespace",
        default="bench-test",
        help="Namespace name for benchmarking",
    )
    parser.add_argument(
        "--docs",
        type=int,
        default=50,
        help="Number of test documents to create",
    )
    parser.add_argument(
        "--queries",
        type=int,
        default=100,
        help="Number of queries to run per mode",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path (default: dashboard/docs/knowledge-bench-results.md)",
    )

    args = parser.parse_args()

    output_path = Path(args.output) if args.output else Path(__file__).parent.parent / "docs" / "knowledge-bench-results.md"

    print(f"Running Knowledge benchmark...")
    print(f"  Namespace: {args.namespace}")
    print(f"  Documents: {args.docs}")
    print(f"  Queries: {args.queries}")
    print(f"  Output: {output_path}")
    print()

    report = run_benchmark(
        namespace=args.namespace,
        docs_count=args.docs,
        queries_count=args.queries,
        output_path=output_path,
    )

    print("\n" + "=" * 60)
    print(report.to_markdown())

    return 0


if __name__ == "__main__":
    sys.exit(main())
