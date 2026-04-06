import pytest
import os
import json
import asyncio
from pathlib import Path
from dashboard.planning_thread_store import PlanningThreadStore, PlanningThread, PlanningMessage

@pytest.fixture
def temp_store(tmp_path):
    store = PlanningThreadStore(base_dir=tmp_path)
    return store

def test_create_thread(temp_store):
    thread = temp_store.create(title="My Test Idea")
    assert thread.id.startswith("pt-")
    assert len(thread.id) == 15
    assert thread.title == "My Test Idea"
    assert thread.status == "active"
    assert thread.plan_id is None
    
    # Verify .json exists
    thread_file = temp_store.base_dir / f"{thread.id}.json"
    assert thread_file.exists()
    
    # Verify index.json exists
    index_file = temp_store.base_dir / "index.json"
    assert index_file.exists()
    
    with open(index_file, "r") as f:
        index_data = json.load(f)
        assert len(index_data) == 1
        assert index_data[0]["id"] == thread.id
        assert index_data[0]["title"] == "My Test Idea"

def test_get_thread(temp_store):
    thread = temp_store.create()
    
    # roundtrip create -> get -> verify
    fetched = temp_store.get(thread.id)
    assert fetched is not None
    assert fetched.id == thread.id
    assert fetched.title == thread.title
    assert fetched.status == thread.status
    
    # Nonexistent
    assert temp_store.get("nonexistent") is None

def test_list_threads(temp_store):
    threads = []
    for i in range(5):
        t = temp_store.create(title=f"Idea {i}")
        threads.append(t)
        # Add a tiny delay or just rely on the order of creation if times are same, 
        # wait, ISO 8601 has microseconds so it's fine.
    
    listed = temp_store.list_threads()
    assert len(listed) == 5
    # Should be sorted by updated_at desc, so latest first
    assert listed[0]["id"] == threads[4].id
    assert listed[4]["id"] == threads[0].id
    
    # Pagination
    paginated = temp_store.list_threads(limit=2, offset=1)
    assert len(paginated) == 2
    assert paginated[0]["id"] == threads[3].id
    assert paginated[1]["id"] == threads[2].id

@pytest.mark.asyncio
async def test_append_and_get_messages(temp_store):
    thread = temp_store.create()
    
    msg1 = await temp_store.append_message(thread.id, "user", "Hello")
    assert msg1 is not None
    assert len(msg1.id) == 8
    assert msg1.role == "user"
    assert msg1.content == "Hello"
    
    msg2 = await temp_store.append_message(thread.id, "assistant", "World")
    msg3 = await temp_store.append_message(thread.id, "user", "unicode 🤖")
    
    # Get messages
    messages = temp_store.get_messages(thread.id)
    assert len(messages) == 3
    assert messages[0].content == "Hello"
    assert messages[1].content == "World"
    assert messages[2].content == "unicode 🤖"
    
    # Verify metadata updates
    fetched_thread = temp_store.get(thread.id)
    assert fetched_thread.message_count == 3
    
    # Verify index updates
    listed = temp_store.list_threads()
    assert listed[0]["message_count"] == 3

def test_update_title(temp_store):
    thread = temp_store.create()
    
    updated = temp_store.update_title(thread.id, "New Title")
    assert updated is not None
    assert updated.title == "New Title"
    
    # Verify .json updated
    fetched = temp_store.get(thread.id)
    assert fetched.title == "New Title"
    
    # Verify index.json updated
    listed = temp_store.list_threads()
    assert listed[0]["title"] == "New Title"

def test_set_promoted(temp_store):
    thread = temp_store.create()
    
    promoted = temp_store.set_promoted(thread.id, "plan-123")
    assert promoted is not None
    assert promoted.status == "promoted"
    assert promoted.plan_id == "plan-123"
    
    # Verify .json updated
    fetched = temp_store.get(thread.id)
    assert fetched.status == "promoted"
    assert fetched.plan_id == "plan-123"
    
    # Verify index.json updated
    listed = temp_store.list_threads()
    assert listed[0]["status"] == "promoted"
    assert listed[0]["plan_id"] == "plan-123"

@pytest.mark.asyncio
async def test_edge_cases(temp_store):
    # Empty store
    assert len(temp_store.list_threads()) == 0
    assert temp_store.get_messages("nonexistent") == []
    
    # Nonexistent IDs
    assert temp_store.update_title("nonexistent", "Title") is None
    assert temp_store.set_promoted("nonexistent", "plan-123") is None
    assert await temp_store.append_message("nonexistent", "user", "Hello") is None
