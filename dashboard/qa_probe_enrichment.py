
import asyncio
from pathlib import Path
import os
import sys

# Add project root to sys.path
sys.path.insert(0, "/Users/paulaan/PycharmProjects/agent-os")

from dashboard.knowledge.metrics import get_metrics_registry
from dashboard.knowledge.service import KnowledgeService

async def test_metrics_enrichment():
    service = KnowledgeService()
    # Create a test namespace
    ns = "test-enrichment"
    try:
        service.create_namespace(ns)
        
        # Add some data (dummy)
        ns_dir = service._nm.namespace_dir(ns)
        test_file = ns_dir / "test.txt"
        test_file.write_text("hello world")
        
        # 1. Check get_namespace_stats directly
        stats = service.get_namespace_stats(ns)
        print(f"Enriched stats: {stats}")
        assert stats["disk_bytes"] > 0
        
        # 2. Check get_namespace (what the REST API uses)
        meta = service.get_namespace(ns)
        print(f"NamespaceMeta stats: {meta.stats}")
        # This is where I suspect it will fail to be enriched
        if meta.stats.disk_bytes == 0:
            print("FAILURE: get_namespace stats NOT enriched")
        else:
            print("SUCCESS: get_namespace stats enriched")
            
    finally:
        service.delete_namespace(ns)

if __name__ == "__main__":
    # Mock some env vars needed for initialization
    os.environ["OSTWIN_KNOWLEDGE_DIR"] = "/tmp/ostwin-knowledge-test"
    os.environ["OSTWIN_AUTH_KEY"] = "test-key"
    
    asyncio.run(test_metrics_enrichment())
