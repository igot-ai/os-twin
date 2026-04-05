import os
import json
import uuid
import asyncio
from typing import List, Literal, Optional
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from dashboard.api_utils import AGENTS_DIR

class PlanningMessage(BaseModel):
    id: str = Field(..., min_length=8, max_length=8)
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1)
    created_at: str
    images: Optional[List[dict]] = None

class PlanningThread(BaseModel):
    id: str = Field(..., min_length=15, max_length=15)
    title: str = "New Idea"
    status: Literal["active", "promoted", "archived"] = "active"
    plan_id: Optional[str] = None
    created_at: str
    updated_at: str
    message_count: int = 0

class PlanningThreadStore:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or (AGENTS_DIR / "conversations" / "plans")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.base_dir / "index.json"
        self._lock = asyncio.Lock()
        
        if not self.index_file.exists():
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _read_index(self) -> List[dict]:
        if not self.index_file.exists():
            return []
        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

    def _write_index(self, index_data: List[dict]):
        temp_file = self.index_file.with_suffix(".json.tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2)
        os.replace(temp_file, self.index_file)

    def create(self, title: str = "New Idea") -> PlanningThread:
        thread_id = f"pt-{uuid.uuid4().hex[:12]}"
        now = self._now_iso()
        
        thread = PlanningThread(
            id=thread_id,
            title=title,
            status="active",
            created_at=now,
            updated_at=now,
            message_count=0
        )
        
        thread_file = self.base_dir / f"{thread_id}.json"
        with open(thread_file, "w", encoding="utf-8") as f:
            f.write(thread.model_dump_json(indent=2))
            
        index_data = self._read_index()
        index_data.append({
            "id": thread.id,
            "title": thread.title,
            "status": thread.status,
            "plan_id": thread.plan_id,
            "updated_at": thread.updated_at,
            "message_count": thread.message_count
        })
        self._write_index(index_data)
        
        return thread

    def get(self, thread_id: str) -> Optional[PlanningThread]:
        thread_file = self.base_dir / f"{thread_id}.json"
        if not thread_file.exists():
            return None
        try:
            with open(thread_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return PlanningThread.model_validate(data)
        except (json.JSONDecodeError, OSError):
            return None

    def list_threads(self, limit: int = 20, offset: int = 0) -> List[dict]:
        index_data = self._read_index()
        # Sort by updated_at descending
        index_data.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return index_data[offset:offset + limit]

    async def append_message(self, thread_id: str, role: Literal["user", "assistant"], content: str, images: Optional[List[dict]] = None) -> Optional[PlanningMessage]:
        thread = self.get(thread_id)
        if not thread:
            return None

        msg_id = uuid.uuid4().hex[:8]
        now = self._now_iso()

        msg = PlanningMessage(
            id=msg_id,
            role=role,
            content=content,
            created_at=now,
            images=images if images else None,
        )
        
        jsonl_file = self.base_dir / f"{thread_id}.jsonl"
        
        async with self._lock:
            # Append to JSONL
            with open(jsonl_file, "a", encoding="utf-8") as f:
                f.write(msg.model_dump_json() + "\n")
                
            # Update thread
            thread.message_count += 1
            thread.updated_at = now
            
            thread_file = self.base_dir / f"{thread_id}.json"
            temp_thread = thread_file.with_suffix(".json.tmp")
            with open(temp_thread, "w", encoding="utf-8") as f:
                f.write(thread.model_dump_json(indent=2))
            os.replace(temp_thread, thread_file)
            
            # Update index
            index_data = self._read_index()
            for item in index_data:
                if item.get("id") == thread_id:
                    item["message_count"] = thread.message_count
                    item["updated_at"] = thread.updated_at
                    break
            self._write_index(index_data)
            
        return msg

    def get_messages(self, thread_id: str) -> List[PlanningMessage]:
        jsonl_file = self.base_dir / f"{thread_id}.jsonl"
        if not jsonl_file.exists():
            return []
            
        messages = []
        try:
            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        messages.append(PlanningMessage.model_validate_json(line))
        except OSError:
            pass
        return messages

    def update_title(self, thread_id: str, title: str) -> Optional[PlanningThread]:
        thread = self.get(thread_id)
        if not thread:
            return None
            
        now = self._now_iso()
        thread.title = title
        thread.updated_at = now
        
        thread_file = self.base_dir / f"{thread_id}.json"
        temp_thread = thread_file.with_suffix(".json.tmp")
        with open(temp_thread, "w", encoding="utf-8") as f:
            f.write(thread.model_dump_json(indent=2))
        os.replace(temp_thread, thread_file)
        
        index_data = self._read_index()
        for item in index_data:
            if item.get("id") == thread_id:
                item["title"] = thread.title
                item["updated_at"] = thread.updated_at
                break
        self._write_index(index_data)
        
        return thread

    def set_promoted(self, thread_id: str, plan_id: str) -> Optional[PlanningThread]:
        thread = self.get(thread_id)
        if not thread:
            return None
            
        now = self._now_iso()
        thread.status = "promoted"
        thread.plan_id = plan_id
        thread.updated_at = now
        
        thread_file = self.base_dir / f"{thread_id}.json"
        temp_thread = thread_file.with_suffix(".json.tmp")
        with open(temp_thread, "w", encoding="utf-8") as f:
            f.write(thread.model_dump_json(indent=2))
        os.replace(temp_thread, thread_file)
        
        index_data = self._read_index()
        for item in index_data:
            if item.get("id") == thread_id:
                item["status"] = thread.status
                item["plan_id"] = thread.plan_id
                item["updated_at"] = thread.updated_at
                break
        self._write_index(index_data)
        
        return thread
