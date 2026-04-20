import os
import sys
from pathlib import Path

# Add the agentic_memory path
sys.path.insert(0, str(Path("../.agents/memory").absolute()))
sys.path.insert(0, str(Path("../.agents/memory/agentic_memory").absolute()))

from agentic_memory.memory_system import AgenticMemorySystem

def test_invalid_link_validation():
    persist_dir = "/tmp/test_validation"
    os.makedirs(persist_dir, exist_ok=True)
    
    # Initialize system
    mem = AgenticMemorySystem(persist_dir=persist_dir)
    
    # Try to add a note with an invalid link (namespace doesn't exist)
    # Note: save_memory MCP tool doesn't support links, but add_note does
    note_id = mem.add_note(
        "This note has an invalid knowledge link",
        links=["knowledge://nonexistent/hash#0"]
    )
    
    note = mem.read(note_id)
    print(f"Note added with ID: {note_id}")
    print(f"Links in note: {note.links}")
    
    # If validation was implemented, we should have seen a warning in the logs
    # or the link should have been rejected.

if __name__ == "__main__":
    test_invalid_link_validation()
