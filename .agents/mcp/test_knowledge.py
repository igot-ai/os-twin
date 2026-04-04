import json
import os
import sqlite3
import tempfile
import sys
from unittest import mock
import pytest

# Add mcp dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import importlib
import memory_core as core

def test_knowledge_add_and_list(tmp_path):
    # Mock environment to use tmp_path
    with mock.patch.dict(os.environ, {"AGENT_OS_ROOT": str(tmp_path)}):
        # We need to reload or mock _knowledge_dir to use tmp_path if needed.
        # Luckily core uses AGENT_OS_ROOT on invocation if we override it properly.
        # But `core.AGENT_OS_ROOT` was already evaluated. Let's patch `core.AGENT_OS_ROOT`
        core.AGENT_OS_ROOT = str(tmp_path)
        
        ki_str = core.knowledge_add("test content", "test_source", ["tag1"])
        assert "added:ki-" in ki_str
        
        # Check list
        items_str = core.knowledge_list()
        items = json.loads(items_str)
        assert len(items) == 1
        assert items[0]["content"] == "test content"
        assert items[0]["source"] == "test_source"
        assert items[0]["tags"] == ["tag1"]
        
        # Check search
        search_str = core.knowledge_search("content")
        search_results = json.loads(search_str)
        assert len(search_results) == 1
        assert search_results[0]["source"] == "test_source"

def test_distill(tmp_path):
    with mock.patch.dict(os.environ, {"AGENT_OS_ROOT": str(tmp_path)}):
        core.AGENT_OS_ROOT = str(tmp_path)
        
        # publish some items
        core.publish("artifact", "Created users table", ["db"], "room-001", "backend", "EPIC-001")
        core.publish("decision", "Chose JWT", ["auth"], "room-001", "backend", "EPIC-001")
        
        # distill
        res_str = core.distill("room-001")
        res = json.loads(res_str)
        
        assert res["status"] == "success"
        assert res["source_entries"] == 2
        
        items_str = core.knowledge_list()
        items = json.loads(items_str)
        assert any("users table" in i["content"] for i in items)
