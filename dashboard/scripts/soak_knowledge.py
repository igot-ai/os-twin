#!/usr/bin/env python
"""Knowledge System Soak Test (EPIC-008, TASK-E-006).

Long-running test to validate stability under sustained load:
- 200-doc namespace
- 1000 mixed queries over 30 min
- Peak RSS < 2 GB
- Zero 5xx errors
- No memory drift > 100 MB

Outputs:
- RSS time series (JSON)
- Latency time series (JSON)
- Markdown report to stdout
- Full results to dashboard/docs/knowledge-soak-results.md

Usage:
    python dashboard/scripts/soak_knowledge.py [--duration-mins N] [--queries N]
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import os
import random
import shutil
import statistics
import sys
import time
import tracemalloc
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Ensure dashboard is importable
_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


@dataclass
class SoakSample:
    """Single measurement sample."""
    timestamp: float
    elapsed_sec: float
    rss_mb: float
    query_latency_ms: Optional[float] = None
    query_mode: Optional[str] = None
    query_success: Optional[bool] = None
    status_code: Optional[int] = None


@dataclass
class SoakReport:
    """Full soak test report."""
    timestamp: str
    namespace: str
    docs_count: int
    queries_count: int
    duration_sec: float
    target_duration_sec: float
    samples: list[SoakSample] = field(default_factory=list)
    peak_rss_mb: float = 0.0
    final_rss_mb: float = 0.0
    memory_drift_mb: float = 0.0
    queries_executed: int = 0
    queries_failed: int = 0
    errors_5xx: int = 0
    latency_samples_raw: list[float] = field(default_factory=list)
    latency_samples_graph: list[float] = field(default_factory=list)
    latency_samples_summarized: list[float] = field(default_factory=list)
    passes: dict[str, bool] = field(default_factory=dict)
    
    def to_markdown(self) -> str:
        """Convert to markdown report."""
        lines = [
            f"# Knowledge System Soak Test Results",
            f"",
            f"**Timestamp:** {self.timestamp}",
            f"**Namespace:** {self.namespace}",
            f"**Documents:** {self.docs_count}",
            f"**Queries Executed:** {self.queries_executed}",
            f"**Duration:** {self.duration_sec:.1f}s (target: {self.target_duration_sec:.1f}s)",
            f"",
            f"## Memory Metrics",
            f"",
            f"| Metric | Value | Threshold | Status |",
            f"|--------|-------|-----------|--------|",
            f"| Peak RSS | {self.peak_rss_mb:.1f} MB | < 2048 MB | {'✅ PASS' if self.peak_rss_mb < 2048 else '❌ FAIL'} |",
            f"| Final RSS | {self.final_rss_mb:.1f} MB | - | - |",
            f"| Memory Drift | {self.memory_drift_mb:.1f} MB | < 100 MB | {'✅ PASS' if abs(self.memory_drift_mb) < 100 else '❌ FAIL'} |",
            f"",
            f"## Query Metrics",
            f"",
            f"| Metric | Value | Threshold | Status |",
            f"|--------|-------|-----------|--------|",
            f"| Queries Executed | {self.queries_executed} | ≥ {self.queries_count} | {'✅ PASS' if self.queries_executed >= self.queries_count else '⚠️ PARTIAL'} |",
            f"| Queries Failed | {self.queries_failed} | - | - |",
            f"| 5xx Errors | {self.errors_5xx} | 0 | {'✅ PASS' if self.errors_5xx == 0 else '❌ FAIL'} |",
            f"",
            f"## Latency Statistics (ms)",
            f"",
            f"| Mode | P50 | P95 | P99 | Avg | Count |",
            f"|------|-----|-----|-----|-----|-------|",
        ]
        
        for mode, samples in [
            ("raw", self.latency_samples_raw),
            ("graph", self.latency_samples_graph),
            ("summarized", self.latency_samples_summarized),
        ]:
            if samples:
                sorted_s = sorted(samples)
                n = len(sorted_s)
                lines.append(
                    f"| {mode} | {sorted_s[n // 2]:.1f} | "
                    f"{sorted_s[int(n * 0.95)]:.1f} | {sorted_s[int(n * 0.99)]:.1f} | "
                    f"{statistics.mean(samples):.1f} | {n} |"
                )
            else:
                lines.append(f"| {mode} | N/A | N/A | N/A | N/A | 0 |")
        
        lines.extend([
            f"",
            f"## Pass/Fail Summary",
            f"",
        ])
        
        for criterion, passed in self.passes.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            lines.append(f"- {criterion}: {status}")
        
        lines.extend([
            f"",
            f"## RSS Time Series",
            f"",
            f"```",
        ])
        
        # Sample every 10th data point to keep output manageable
        for i, s in enumerate(self.samples[::10]):
            lines.append(f"t={s.elapsed_sec:.0f}s: RSS={s.rss_mb:.1f} MB")
        
        lines.append(f"```")
        lines.append(f"")
        
        return "\n".join(lines)


def create_soak_documents(target_dir: Path, count: int) -> int:
    """Create diverse test documents for soak testing.
    
    Returns total bytes written.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    
    topics = [
        "machine learning algorithms and neural networks",
        "database optimization and query performance",
        "software architecture patterns and best practices",
        "cloud infrastructure and deployment strategies",
        "security vulnerabilities and threat modeling",
        "api design and restful services",
        "testing strategies and quality assurance",
        "performance monitoring and observability",
        "data pipelines and etl processes",
        "microservices and distributed systems",
    ]
    
    for i in range(count):
        topic = topics[i % len(topics)]
        
        if i % 4 == 0:
            # Markdown
            content = f"""# Document {i}: {topic.title()}

This document discusses {topic} in the context of modern software development.

## Overview

Document ID: DOC-{i:04d}
Created: {datetime.now(timezone.utc).isoformat()}
Topic: {topic}

## Details

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor
incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam.

### Key Points

- Point 1 about {topic}
- Point 2 regarding implementation details
- Point 3 on best practices and patterns

## References

- See document {random.randint(0, count-1)} for related information
- Cross-reference with document {random.randint(0, count-1)}
"""
            ext = ".md"
        elif i % 4 == 1:
            # JSON
            data = {
                "id": f"DOC-{i:04d}",
                "type": "knowledge",
                "topic": topic,
                "title": f"Document {i}: {topic.title()}",
                "content": f"This document covers {topic}. " + "Extended content. " * 20,
                "tags": [topic.split()[0], "soak-test", f"doc-{i}"],
                "metadata": {
                    "created": datetime.now(timezone.utc).isoformat(),
                    "version": "1.0",
                    "priority": random.choice(["high", "medium", "low"]),
                },
                "references": [f"DOC-{random.randint(0, count-1):04d}" for _ in range(3)],
            }
            content = json.dumps(data, indent=2)
            ext = ".json"
        elif i % 4 == 2:
            # HTML
            content = f"""<!DOCTYPE html>
<html>
<head><title>Document {i}</title></head>
<body>
<h1>Document {i}: {topic.title()}</h1>
<p>This document discusses {topic}.</p>
<h2>Overview</h2>
<p>Document ID: DOC-{i:04d}</p>
<h2>Details</h2>
<p>{("Content about " + topic + ". ") * 10}</p>
</body>
</html>
"""
            ext = ".html"
        else:
            # Plain text
            content = f"""Document {i}: {topic.title()}

Topic: {topic}
ID: DOC-{i:04d}
Created: {datetime.now(timezone.utc).isoformat()}

Abstract:
This document provides detailed information about {topic}.
The content covers implementation details, best practices, and common pitfalls.

{'Content paragraph. ' * 30}
"""
            ext = ".txt"
        
        file_path = target_dir / f"doc_{i:04d}{ext}"
        file_path.write_text(content)
        total_bytes += len(content.encode('utf-8'))
    
    return total_bytes


def get_rss_mb() -> float:
    """Get current process RSS in MB."""
    import resource
    import platform
    
    rss_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # On macOS, ru_maxrss is in bytes; on Linux, it's in kilobytes
    if platform.system() == "Darwin":
        return rss_bytes / 1024 / 1024  # bytes -> MB
    else:
        return rss_bytes / 1024  # KB -> MB


def run_soak_test(
    namespace: str,
    docs_count: int,
    queries_count: int,
    duration_sec: float,
    output_path: Optional[Path] = None,
) -> SoakReport:
    """Run the full soak test."""
    from dashboard.knowledge.service import KnowledgeService
    import tempfile
    
    # Start memory tracking
    tracemalloc.start()
    
    report = SoakReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        namespace=namespace,
        docs_count=docs_count,
        queries_count=queries_count,
        duration_sec=0,
        target_duration_sec=duration_sec,
    )
    
    # Query templates for variety
    query_templates = [
        "document {i}",
        "{topic}",
        "information about {topic}",
        "DOC-{i:04d}",
        "content related to {topic}",
        "overview of {topic}",
        "details on {topic}",
        "{topic} implementation",
        "{topic} best practices",
        "{topic} patterns",
    ]
    
    topics = [
        "machine learning", "database", "architecture", "cloud", "security",
        "api", "testing", "performance", "data pipelines", "microservices",
    ]
    
    start_time = time.perf_counter()
    initial_rss = get_rss_mb()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        docs_dir = Path(tmpdir) / "docs"
        kb_dir = Path(tmpdir) / "kb"
        
        os.environ["OSTWIN_KNOWLEDGE_DIR"] = str(kb_dir)
        
        print(f"[Soak Test] Creating {docs_count} documents...")
        total_bytes = create_soak_documents(docs_dir, docs_count)
        print(f"[Soak Test] Created {docs_count} documents ({total_bytes / 1024 / 1024:.2f} MB)")
        
        # Initialize service
        service = KnowledgeService()
        
        # Create namespace
        print(f"[Soak Test] Creating namespace: {namespace}")
        try:
            service.create_namespace(namespace)
        except Exception as e:
            if "already exists" not in str(e):
                raise
        
        # Import documents
        print(f"[Soak Test] Importing documents...")
        import_start = time.perf_counter()
        job_id = service.import_folder(namespace, str(docs_dir))
        print(f"[Soak Test] Import job: {job_id}")
        
        # Wait for import
        deadline = time.time() + 300
        while time.time() < deadline:
            status = service.get_job(job_id)
            if status and status.state.value in ("completed", "failed", "cancelled", "interrupted"):
                break
            time.sleep(0.5)
        
        import_time = time.perf_counter() - import_start
        if status and status.state.value == "completed":
            print(f"[Soak Test] Import completed in {import_time:.1f}s")
        else:
            print(f"[Soak Test] Import failed: {status.state if status else 'unknown'}")
            report.passes["Import completed"] = False
            return report
        
        # Record post-import RSS
        post_import_rss = get_rss_mb()
        print(f"[Soak Test] Post-import RSS: {post_import_rss:.1f} MB")
        
        # =================================================================
        # QUERY PHASE
        # =================================================================
        print(f"[Soak Test] Starting query phase ({queries_count} queries over {duration_sec}s)...")
        
        query_interval = duration_sec / queries_count
        query_count = 0
        errors_5xx = 0
        last_rss_sample = time.time()
        rss_samples = [post_import_rss]
        
        modes = ["raw", "graph", "summarized"]
        mode_weights = [0.6, 0.25, 0.15]  # Raw most common, summarized least
        
        while query_count < queries_count:
            # Check elapsed time
            elapsed = time.perf_counter() - start_time
            
            # Sample RSS periodically (every 5 seconds)
            if time.time() - last_rss_sample > 5:
                current_rss = get_rss_mb()
                rss_samples.append(current_rss)
                last_rss_sample = time.time()
                
                sample = SoakSample(
                    timestamp=time.time(),
                    elapsed_sec=elapsed,
                    rss_mb=current_rss,
                )
                report.samples.append(sample)
            
            # Select query mode
            mode = random.choices(modes, weights=mode_weights)[0]
            
            # Generate query
            template = random.choice(query_templates)
            topic = random.choice(topics)
            query_idx = random.randint(0, docs_count - 1)
            query = template.format(i=query_idx, topic=topic)
            
            # Execute query
            try:
                q_start = time.perf_counter()
                result = service.query(namespace, query, mode=mode, top_k=10)
                q_latency = (time.perf_counter() - q_start) * 1000
                
                # Record latency
                if mode == "raw":
                    report.latency_samples_raw.append(q_latency)
                elif mode == "graph":
                    report.latency_samples_graph.append(q_latency)
                else:
                    report.latency_samples_summarized.append(q_latency)
                
                query_count += 1
                report.queries_executed += 1
                
                if query_count % 100 == 0:
                    print(f"[Soak Test] {query_count}/{queries_count} queries completed...")
            
            except Exception as e:
                report.queries_failed += 1
                error_str = str(e).lower()
                # Check for 5xx-like errors
                if "500" in error_str or "internal" in error_str:
                    errors_5xx += 1
                    report.errors_5xx += 1
                # Graph/summarized may fail gracefully if kuzu/LLM unavailable
            
            # Sleep to maintain target rate
            elapsed_since_start = time.perf_counter() - start_time
            expected_queries = int(elapsed_since_start / query_interval) + 1
            
            if query_count < expected_queries - 5:
                # We're behind, skip sleep
                pass
            else:
                # Sleep a bit to maintain rate
                sleep_time = min(0.1, query_interval / 2)
                time.sleep(sleep_time)
        
        # Final RSS measurement
        final_rss = get_rss_mb()
        rss_samples.append(final_rss)
        
        # Calculate metrics
        report.peak_rss_mb = max(rss_samples)
        report.final_rss_mb = final_rss
        report.memory_drift_mb = final_rss - post_import_rss
        report.errors_5xx = errors_5xx
        report.duration_sec = time.perf_counter() - start_time
        
        # Cleanup
        print(f"[Soak Test] Cleaning up...")
        try:
            service.delete_namespace(namespace)
        except Exception:
            pass
    
    # Determine pass/fail
    report.passes = {
        "Peak RSS < 2 GB": report.peak_rss_mb < 2048,
        "Zero 5xx errors": report.errors_5xx == 0,
        "Memory drift < 100 MB": abs(report.memory_drift_mb) < 100,
        "All queries executed": report.queries_executed >= queries_count * 0.95,  # Allow 5% grace
    }
    
    tracemalloc.stop()
    
    # Write output
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report.to_markdown())
        print(f"\n[Soak Test] Results written to: {output_path}")
    
    return report


def main():
    parser = argparse.ArgumentParser(description="Knowledge System Soak Test")
    parser.add_argument(
        "--namespace",
        default="soak-test",
        help="Namespace name for soak testing",
    )
    parser.add_argument(
        "--docs",
        type=int,
        default=200,
        help="Number of test documents to create",
    )
    parser.add_argument(
        "--queries",
        type=int,
        default=1000,
        help="Number of queries to run",
    )
    parser.add_argument(
        "--duration-mins",
        type=float,
        default=30.0,
        help="Target duration in minutes",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path (default: dashboard/docs/knowledge-soak-results.md)",
    )

    args = parser.parse_args()

    output_path = (
        Path(args.output)
        if args.output
        else Path(__file__).parent.parent / "docs" / "knowledge-soak-results.md"
    )

    duration_sec = args.duration_mins * 60

    print(f"[Soak Test] Knowledge System Soak Test")
    print(f"  Namespace: {args.namespace}")
    print(f"  Documents: {args.docs}")
    print(f"  Queries: {args.queries}")
    print(f"  Duration: {args.duration_mins:.1f} minutes")
    print(f"  Output: {output_path}")
    print()

    report = run_soak_test(
        namespace=args.namespace,
        docs_count=args.docs,
        queries_count=args.queries,
        duration_sec=duration_sec,
        output_path=output_path,
    )

    print("\n" + "=" * 60)
    print(report.to_markdown())
    
    # Return exit code based on pass/fail
    all_passed = all(report.passes.values())
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
