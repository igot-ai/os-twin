"""
OS Twin Vector Log Store — zvec integration layer.

Indexes all war-room channel messages with embeddings for semantic search.
Stores room metadata for fast dashboard lookups (eliminates "UNKNOWN" task-ref).

Usage:
    store = OSTwinStore(Path("/project/.war-rooms"))
    store.ensure_collections()
    store.sync_from_disk()  # backfill existing JSONL
    results = store.search("authentication bug", limit=5)
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

import zvec

logger = logging.getLogger("zvec_store")

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2
MESSAGES_COLLECTION = "messages"
METADATA_COLLECTION = "metadata"
PLANS_COLLECTION = "plans"
EPICS_COLLECTION = "epics"


class OSTwinStore:
    """In-process vector store for OS Twin logs and metadata."""

    def __init__(self, warrooms_dir: Path, agents_dir: Path | None = None):
        self.warrooms_dir = warrooms_dir
        self.agents_dir = agents_dir  # .agents/ directory (for plans etc.)
        self.zvec_dir = warrooms_dir / ".zvec"
        self.zvec_dir.mkdir(parents=True, exist_ok=True)
        self._messages: Optional[zvec.Collection] = None
        self._metadata: Optional[zvec.Collection] = None
        self._plans: Optional[zvec.Collection] = None
        self._epics: Optional[zvec.Collection] = None
        self._embed_fn = None
        self._embed_available: Optional[bool] = None

    # ── Collections ────────────────────────────────────────────────────

    def ensure_collections(self) -> None:
        """Create or open all collections."""
        zvec.init(log_level=zvec.LogLevel.WARN)
        self._messages = self._open_or_create_messages()
        self._metadata = self._open_or_create_metadata()
        self._plans = self._open_or_create_plans()
        self._epics = self._open_or_create_epics()
        logger.info("zvec collections ready at %s", self.zvec_dir)

    def _open_or_create_messages(self) -> zvec.Collection:
        path = str(self.zvec_dir / MESSAGES_COLLECTION)
        try:
            return zvec.open(path)
        except Exception:
            schema = zvec.CollectionSchema(
                name=MESSAGES_COLLECTION,
                fields=[
                    zvec.FieldSchema("room_id", zvec.DataType.STRING,
                                     index_param=zvec.InvertIndexParam()),
                    zvec.FieldSchema("from_role", zvec.DataType.STRING,
                                     index_param=zvec.InvertIndexParam()),
                    zvec.FieldSchema("to_role", zvec.DataType.STRING,
                                     index_param=zvec.InvertIndexParam()),
                    zvec.FieldSchema("msg_type", zvec.DataType.STRING,
                                     index_param=zvec.InvertIndexParam()),
                    zvec.FieldSchema("ref", zvec.DataType.STRING,
                                     index_param=zvec.InvertIndexParam()),
                    zvec.FieldSchema("ts", zvec.DataType.STRING,
                                     index_param=zvec.InvertIndexParam()),
                    zvec.FieldSchema("body", zvec.DataType.STRING),
                ],
                vectors=zvec.VectorSchema(
                    "embedding",
                    zvec.DataType.VECTOR_FP32,
                    EMBEDDING_DIM,
                    index_param=zvec.HnswIndexParam(
                        metric_type=zvec.MetricType.COSINE,
                        m=16,
                        ef_construction=200,
                    ),
                ),
            )
            return zvec.create_and_open(path=path, schema=schema)

    def _open_or_create_metadata(self) -> zvec.Collection:
        path = str(self.zvec_dir / METADATA_COLLECTION)
        try:
            return zvec.open(path)
        except Exception:
            # zvec requires at least one vector field — use a 1-dim placeholder
            schema = zvec.CollectionSchema(
                name=METADATA_COLLECTION,
                fields=[
                    zvec.FieldSchema("task_ref", zvec.DataType.STRING,
                                     index_param=zvec.InvertIndexParam()),
                    zvec.FieldSchema("status", zvec.DataType.STRING,
                                     index_param=zvec.InvertIndexParam()),
                    zvec.FieldSchema("retries", zvec.DataType.INT32),
                    zvec.FieldSchema("message_count", zvec.DataType.INT32),
                    zvec.FieldSchema("last_activity", zvec.DataType.STRING, nullable=True),
                    zvec.FieldSchema("task_description", zvec.DataType.STRING, nullable=True),
                ],
                vectors=zvec.VectorSchema(
                    "_placeholder",
                    zvec.DataType.VECTOR_FP32,
                    1,
                    index_param=zvec.FlatIndexParam(metric_type=zvec.MetricType.L2),
                ),
            )
            return zvec.create_and_open(path=path, schema=schema)

    def _open_or_create_plans(self) -> zvec.Collection:
        path = str(self.zvec_dir / PLANS_COLLECTION)
        try:
            return zvec.open(path)
        except Exception:
            schema = zvec.CollectionSchema(
                name=PLANS_COLLECTION,
                fields=[
                    zvec.FieldSchema("title", zvec.DataType.STRING,
                                     index_param=zvec.InvertIndexParam()),
                    zvec.FieldSchema("content", zvec.DataType.STRING),
                    zvec.FieldSchema("status", zvec.DataType.STRING,
                                     index_param=zvec.InvertIndexParam()),
                    zvec.FieldSchema("epic_count", zvec.DataType.INT32),
                    zvec.FieldSchema("created_at", zvec.DataType.STRING,
                                     index_param=zvec.InvertIndexParam()),
                    zvec.FieldSchema("filename", zvec.DataType.STRING, nullable=True),
                ],
                vectors=zvec.VectorSchema(
                    "embedding",
                    zvec.DataType.VECTOR_FP32,
                    EMBEDDING_DIM,
                    index_param=zvec.HnswIndexParam(
                        metric_type=zvec.MetricType.COSINE,
                        m=16,
                        ef_construction=200,
                    ),
                ),
            )
            return zvec.create_and_open(path=path, schema=schema)

    def _open_or_create_epics(self) -> zvec.Collection:
        path = str(self.zvec_dir / EPICS_COLLECTION)
        try:
            return zvec.open(path)
        except Exception:
            schema = zvec.CollectionSchema(
                name=EPICS_COLLECTION,
                fields=[
                    zvec.FieldSchema("epic_ref", zvec.DataType.STRING,
                                     index_param=zvec.InvertIndexParam()),
                    zvec.FieldSchema("plan_id", zvec.DataType.STRING,
                                     index_param=zvec.InvertIndexParam()),
                    zvec.FieldSchema("title", zvec.DataType.STRING,
                                     index_param=zvec.InvertIndexParam()),
                    zvec.FieldSchema("body", zvec.DataType.STRING),
                    zvec.FieldSchema("room_id", zvec.DataType.STRING,
                                     index_param=zvec.InvertIndexParam()),
                    zvec.FieldSchema("status", zvec.DataType.STRING,
                                     index_param=zvec.InvertIndexParam()),
                    zvec.FieldSchema("working_dir", zvec.DataType.STRING, nullable=True),
                ],
                vectors=zvec.VectorSchema(
                    "embedding",
                    zvec.DataType.VECTOR_FP32,
                    EMBEDDING_DIM,
                    index_param=zvec.HnswIndexParam(
                        metric_type=zvec.MetricType.COSINE,
                        m=16,
                        ef_construction=200,
                    ),
                ),
            )
            return zvec.create_and_open(path=path, schema=schema)

    # ── Embedding ──────────────────────────────────────────────────────

    def _get_embed_fn(self):
        """Lazy-load embedding model on first use."""
        if self._embed_available is False:
            return None
        if self._embed_fn is not None:
            return self._embed_fn
        try:
            self._embed_fn = zvec.DefaultLocalDenseEmbedding()
            self._embed_available = True
            logger.info("Embedding model loaded (dim=%d)", EMBEDDING_DIM)
            return self._embed_fn
        except Exception as e:
            logger.warning("Embedding unavailable: %s. Vector search disabled.", e)
            self._embed_available = False
            return None

    def _embed_text(self, text: str) -> list[float] | None:
        fn = self._get_embed_fn()
        if fn is None:
            return None
        if not text or not isinstance(text, str) or not text.strip():
            return None
        # Truncate very long messages for embedding
        truncated = text[:2000] if len(text) > 2000 else text
        try:
            return fn.embed(truncated)
        except Exception as e:
            logger.debug("Embedding failed for text: %s", e)
            return None

    # ── Message Indexing ───────────────────────────────────────────────

    def index_message(self, room_id: str, msg: dict) -> bool:
        """Index a single channel message. Returns True on success."""
        if self._messages is None:
            return False
        msg_id = msg.get("id", "")
        if not msg_id:
            return False

        body = str(msg.get("body", ""))
        # Sanitize: zvec C++ layer can't handle some Unicode chars (emoji etc.)
        # Encode to ascii with replacement, then decode back
        body_clean = body.encode("ascii", errors="replace").decode("ascii")
        embedding = self._embed_text(body)

        # zvec requires the vector field — use zero vector as fallback
        if embedding is None:
            embedding = [0.0] * EMBEDDING_DIM

        doc = zvec.Doc(
            id=str(msg_id),
            fields={
                "room_id": str(room_id),
                "from_role": str(msg.get("from", "")),
                "to_role": str(msg.get("to", "")),
                "msg_type": str(msg.get("type", "")),
                "ref": str(msg.get("ref", "")),
                "ts": str(msg.get("ts", "")),
                "body": body_clean,
            },
            vectors={"embedding": embedding},
        )

        try:
            status = self._messages.upsert(doc)
            return status.ok()
        except Exception as e:
            logger.warning("Failed to index message %s: %s", msg_id, e)
            return False

    def index_messages_batch(self, room_id: str, msgs: list[dict]) -> int:
        """Index multiple messages. Returns count of successfully indexed."""
        count = 0
        for msg in msgs:
            if self.index_message(room_id, msg):
                count += 1
        return count

    # ── Room Metadata ──────────────────────────────────────────────────

    def upsert_room_metadata(self, room_id: str, data: dict) -> bool:
        """Store or update room metadata snapshot."""
        if self._metadata is None:
            return False

        doc = zvec.Doc(
            id=room_id,
            fields={
                "task_ref": data.get("task_ref", "UNKNOWN"),
                "status": data.get("status", "unknown"),
                "retries": data.get("retries", 0),
                "message_count": data.get("message_count", 0),
                "last_activity": data.get("last_activity", ""),
                "task_description": data.get("task_description", ""),
            },
            vectors={"_placeholder": [0.0]},
        )

        status = self._metadata.upsert(doc)
        return status.ok()

    def get_room_metadata(self, room_id: str) -> dict | None:
        """Fetch room metadata by room_id. Returns None if not found."""
        if self._metadata is None:
            return None
        try:
            result = self._metadata.fetch(room_id)
            if room_id not in result:
                return None
            doc = result[room_id]
            return {
                "room_id": room_id,
                "task_ref": doc.field("task_ref"),
                "status": doc.field("status"),
                "retries": doc.field("retries"),
                "message_count": doc.field("message_count"),
                "last_activity": doc.field("last_activity"),
                "task_description": doc.field("task_description"),
            }
        except Exception:
            return None

    def get_all_rooms_metadata(self) -> list[dict]:
        """Fetch all room metadata. Returns list of dicts."""
        if self._metadata is None:
            return []
        results = []
        # Query all rooms by scanning — metadata collection is small
        for room_dir in sorted(self.warrooms_dir.glob("room-*")):
            if room_dir.is_dir():
                meta = self.get_room_metadata(room_dir.name)
                if meta:
                    results.append(meta)
        return results

    # ── Plan & Epic Indexing ─────────────────────────────────────────────

    def index_plan(self, plan_id: str, title: str, content: str,
                   epic_count: int, filename: str = "",
                   status: str = "launched", created_at: str = "") -> bool:
        """Index a plan document. Returns True on success."""
        if self._plans is None:
            return False

        content_clean = content.encode("ascii", errors="replace").decode("ascii")
        embedding = self._embed_text(f"{title} {content_clean[:1000]}")
        if embedding is None:
            embedding = [0.0] * EMBEDDING_DIM

        doc = zvec.Doc(
            id=plan_id,
            fields={
                "title": title,
                "content": content_clean,
                "status": status,
                "epic_count": epic_count,
                "created_at": created_at or "",
                "filename": filename or "",
            },
            vectors={"embedding": embedding},
        )
        try:
            s = self._plans.upsert(doc)
            self._plans.flush()
            return s.ok()
        except Exception as e:
            logger.warning("Failed to index plan %s: %s", plan_id, e)
            return False

    def index_epic(self, epic_ref: str, plan_id: str, title: str,
                   body: str, room_id: str, working_dir: str = ".",
                   status: str = "pending") -> bool:
        """Index a single Epic from a plan. Returns True on success."""
        if self._epics is None:
            return False

        body_clean = body.encode("ascii", errors="replace").decode("ascii")
        embed_text = f"{epic_ref} {title} {body_clean[:1000]}"
        embedding = self._embed_text(embed_text)
        if embedding is None:
            embedding = [0.0] * EMBEDDING_DIM

        doc = zvec.Doc(
            id=f"{plan_id}--{epic_ref}",
            fields={
                "epic_ref": epic_ref,
                "plan_id": plan_id,
                "title": title,
                "body": body_clean,
                "room_id": room_id,
                "status": status,
                "working_dir": working_dir or ".",
            },
            vectors={"embedding": embedding},
        )
        try:
            s = self._epics.upsert(doc)
            self._epics.flush()
            return s.ok()
        except Exception as e:
            logger.warning("Failed to index epic %s: %s", epic_ref, e)
            return False

    def update_epic_status(self, plan_id: str, epic_ref: str, status: str) -> bool:
        """Update an epic's status (syncs from war-room status)."""
        if self._epics is None:
            return False
        doc_id = f"{plan_id}--{epic_ref}"
        try:
            result = self._epics.fetch(doc_id)
            if doc_id not in result:
                return False
            existing = result[doc_id]
            # Re-upsert with updated status
            doc = zvec.Doc(
                id=doc_id,
                fields={
                    "epic_ref": existing.field("epic_ref"),
                    "plan_id": existing.field("plan_id"),
                    "title": existing.field("title"),
                    "body": existing.field("body"),
                    "room_id": existing.field("room_id"),
                    "status": status,
                    "working_dir": existing.field("working_dir"),
                },
                vectors={"embedding": [0.0] * EMBEDDING_DIM},  # reuse placeholder
            )
            s = self._epics.upsert(doc)
            self._epics.flush()
            return s.ok()
        except Exception as e:
            logger.warning("Failed to update epic status %s: %s", doc_id, e)
            return False

    def get_plan(self, plan_id: str) -> dict | None:
        """Fetch a single plan by ID."""
        if self._plans is None:
            return None
        try:
            result = self._plans.fetch(plan_id)
            if plan_id not in result:
                return None
            doc = result[plan_id]
            return {
                "plan_id": plan_id,
                "title": doc.field("title"),
                "content": doc.field("content"),
                "status": doc.field("status"),
                "epic_count": doc.field("epic_count"),
                "created_at": doc.field("created_at"),
                "filename": doc.field("filename"),
            }
        except Exception:
            return None

    def get_all_plans(self) -> list[dict]:
        """Fetch all plans. Returns list sorted by created_at desc."""
        if self._plans is None:
            return []
        results = []
        # Scan plans directory on disk to discover plan IDs
        plans_dir = self._plans_dir()
        if not plans_dir.exists():
            return results
        for f in sorted(plans_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
            plan_id = f.stem
            plan = self.get_plan(plan_id)
            if plan:
                results.append(plan)
        return results

    def get_epics_for_plan(self, plan_id: str) -> list[dict]:
        """Get all epics belonging to a plan."""
        if self._epics is None:
            return []
        results = []
        # Use vector query with filter (any vector, just for filtering)
        try:
            docs = self._epics.query(
                vectors=zvec.VectorQuery("embedding", vector=[0.0] * EMBEDDING_DIM),
                topk=50,
                filter=f"plan_id = '{plan_id}'",
                output_fields=["epic_ref", "plan_id", "title", "body",
                               "room_id", "status", "working_dir"],
            )
            for doc in docs:
                results.append({
                    "id": doc.id,
                    "epic_ref": doc.field("epic_ref"),
                    "plan_id": doc.field("plan_id"),
                    "title": doc.field("title"),
                    "body": doc.field("body"),
                    "room_id": doc.field("room_id"),
                    "status": doc.field("status"),
                    "working_dir": doc.field("working_dir"),
                })
        except Exception as e:
            logger.warning("Failed to get epics for plan %s: %s", plan_id, e)
        return results

    def search_plans(self, query: str, limit: int = 10) -> list[dict]:
        """Semantic search across plans."""
        if self._plans is None:
            return []
        embedding = self._embed_text(query)
        if embedding is None:
            return []
        try:
            docs = self._plans.query(
                vectors=zvec.VectorQuery("embedding", vector=embedding),
                topk=limit,
                output_fields=["title", "status", "epic_count", "created_at", "filename"],
            )
            return [{
                "plan_id": doc.id,
                "score": doc.score,
                "title": doc.field("title"),
                "status": doc.field("status"),
                "epic_count": doc.field("epic_count"),
                "created_at": doc.field("created_at"),
                "filename": doc.field("filename"),
            } for doc in docs]
        except Exception as e:
            logger.error("Plan search failed: %s", e)
            return []

    def search_epics(self, query: str, plan_id: str | None = None,
                     limit: int = 20) -> list[dict]:
        """Semantic search across epics."""
        if self._epics is None:
            return []
        embedding = self._embed_text(query)
        if embedding is None:
            return []
        filter_str = f"plan_id = '{plan_id}'" if plan_id else None
        try:
            docs = self._epics.query(
                vectors=zvec.VectorQuery("embedding", vector=embedding),
                topk=limit,
                filter=filter_str,
                output_fields=["epic_ref", "plan_id", "title", "body",
                               "room_id", "status", "working_dir"],
            )
            return [{
                "id": doc.id,
                "score": doc.score,
                "epic_ref": doc.field("epic_ref"),
                "plan_id": doc.field("plan_id"),
                "title": doc.field("title"),
                "body": doc.field("body"),
                "room_id": doc.field("room_id"),
                "status": doc.field("status"),
            } for doc in docs]
        except Exception as e:
            logger.error("Epic search failed: %s", e)
            return []

    # ── Search ─────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        room_id: str | None = None,
        msg_type: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Semantic search across indexed messages. Returns ranked results."""
        if self._messages is None:
            return []

        embedding = self._embed_text(query)
        if embedding is None:
            return []

        # Build filter expression
        filters = []
        if room_id:
            filters.append(f"room_id = '{room_id}'")
        if msg_type:
            filters.append(f"msg_type = '{msg_type}'")
        filter_str = " AND ".join(filters) if filters else None

        try:
            docs = self._messages.query(
                vectors=zvec.VectorQuery("embedding", vector=embedding),
                topk=limit,
                filter=filter_str,
                output_fields=["room_id", "from_role", "to_role", "msg_type",
                               "ref", "ts", "body"],
            )

            results = []
            for doc in docs:
                results.append({
                    "id": doc.id,
                    "score": doc.score,
                    "room_id": doc.field("room_id"),
                    "from": doc.field("from_role"),
                    "to": doc.field("to_role"),
                    "type": doc.field("msg_type"),
                    "ref": doc.field("ref"),
                    "ts": doc.field("ts"),
                    "body": doc.field("body"),
                })
            return results
        except Exception as e:
            logger.error("Search failed: %s", e)
            return []

    # ── Disk Sync ──────────────────────────────────────────────────────

    def sync_from_disk(self) -> int:
        """
        Backfill zvec from all channel.jsonl files on disk.
        Idempotent — uses message ID as primary key (upsert).
        Also syncs room metadata from room files.
        Returns total messages indexed.
        """
        total = 0
        if not self.warrooms_dir.exists():
            return 0

        for room_dir in sorted(self.warrooms_dir.glob("room-*")):
            if not room_dir.is_dir():
                continue
            room_id = room_dir.name

            # Sync channel messages
            channel_file = room_dir / "channel.jsonl"
            if channel_file.exists():
                msgs = []
                for line in channel_file.read_text().splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msgs.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                total += self.index_messages_batch(room_id, msgs)

            # Sync room metadata from files
            task_ref = self._read_file(room_dir / "task-ref")
            if not task_ref:
                # Fallback: extract from TASKS.md
                tasks_md = room_dir / "TASKS.md"
                if tasks_md.exists():
                    header = tasks_md.read_text().split("\n", 1)[0]
                    m = re.search(r"(EPIC-\d+|TASK-\d+)", header)
                    if m:
                        task_ref = m.group(1)
            if not task_ref:
                # Fallback: derive from room-id
                m = re.match(r"room-(\d+)", room_id)
                task_ref = f"EPIC-{m.group(1)}" if m else "UNKNOWN"

            status = self._read_file(room_dir / "status") or "unknown"
            retries_str = self._read_file(room_dir / "retries") or "0"
            retries = int(retries_str) if retries_str.isdigit() else 0

            # Read description from brief.md or TASKS.md
            desc = None
            if (room_dir / "brief.md").exists():
                desc = (room_dir / "brief.md").read_text()
            elif (room_dir / "TASKS.md").exists():
                desc = (room_dir / "TASKS.md").read_text()

            channel_file = room_dir / "channel.jsonl"
            msg_count = 0
            last_activity = None
            if channel_file.exists():
                lines = [l for l in channel_file.read_text().splitlines() if l.strip()]
                msg_count = len(lines)
                if lines:
                    try:
                        last_msg = json.loads(lines[-1])
                        last_activity = last_msg.get("ts", "")
                    except json.JSONDecodeError:
                        pass

            self.upsert_room_metadata(room_id, {
                "task_ref": task_ref,
                "status": status,
                "retries": retries,
                "message_count": msg_count,
                "last_activity": last_activity or "",
                "task_description": desc or "",
            })

        # Sync plans from disk
        plans_synced = self._sync_plans_from_disk()

        if self._messages:
            self._messages.flush()
            # Build HNSW index for search after bulk insert
            try:
                self._messages.optimize()
            except Exception as e:
                logger.warning("optimize failed: %s", e)
        if self._metadata:
            self._metadata.flush()
        if self._plans:
            self._plans.flush()
            try:
                self._plans.optimize()
            except Exception:
                pass
        if self._epics:
            self._epics.flush()
            try:
                self._epics.optimize()
            except Exception:
                pass

        logger.info("zvec sync complete: %d messages, %d plans indexed", total, plans_synced)
        return total

    def _sync_plans_from_disk(self) -> int:
        """Backfill plans collection from .agents/plans/*.md files on disk."""
        plans_dir = self._plans_dir()
        if not plans_dir.exists():
            return 0

        count = 0
        for plan_file in sorted(plans_dir.glob("*.md")):
            plan_id = plan_file.stem
            if plan_id == "PLAN.template":
                continue

            content = plan_file.read_text()
            if not content.strip():
                continue

            # Extract title from "# Plan: ..." header
            title_match = re.search(r"^# Plan:\s*(.+)", content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else plan_id

            # Extract epics/tasks
            epics = self._parse_plan_epics(content, plan_id)

            # Determine status from war-rooms (if rooms exist, it was launched)
            status = "launched" if any(
                (self.warrooms_dir / f"room-{i+1:03d}").exists()
                for i in range(len(epics))
            ) else "stored"

            # Use file mtime as created_at
            from datetime import datetime, timezone
            mtime = plan_file.stat().st_mtime
            created_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

            self.index_plan(
                plan_id=plan_id,
                title=title,
                content=content,
                epic_count=len(epics),
                filename=plan_file.name,
                status=status,
                created_at=created_at,
            )

            # Index each epic
            for epic in epics:
                # Try to sync status from war-room
                room_dir = self.warrooms_dir / epic["room_id"]
                epic_status = "pending"
                if room_dir.exists():
                    s = self._read_file(room_dir / "status")
                    if s:
                        epic_status = s

                self.index_epic(
                    epic_ref=epic["task_ref"],
                    plan_id=plan_id,
                    title=epic["title"],
                    body=epic["body"],
                    room_id=epic["room_id"],
                    working_dir=epic.get("working_dir", "."),
                    status=epic_status,
                )

            count += 1

        return count

    @staticmethod
    def _parse_plan_epics(content: str, plan_id: str) -> list[dict]:
        """Parse a plan markdown into a list of epic/task dicts."""
        # Extract working dir
        config_match = re.search(r"working_dir:\s*(.+)", content)
        working_dir = config_match.group(1).strip() if config_match else "."

        # Detect format
        has_epics = bool(re.search(r"^## Epic:", content, re.MULTILINE))
        has_tasks = bool(re.search(r"^## Task:", content, re.MULTILINE))

        if has_epics:
            split_pattern = r"^## Epic:\s*"
            ref_pattern = r"(EPIC-\d+)\s*[—\-]\s*(.*)"
            default_prefix = "EPIC"
        elif has_tasks:
            split_pattern = r"^## Task:\s*"
            ref_pattern = r"(TASK-\d+)\s*[—\-]\s*(.*)"
            default_prefix = "TASK"
        else:
            return []

        items = []
        parts = re.split(split_pattern, content, flags=re.MULTILINE)

        for i, part in enumerate(parts[1:], 1):
            lines = part.strip().split("\n")
            header = lines[0].strip()

            ref_match = re.match(ref_pattern, header)
            if ref_match:
                item_ref = ref_match.group(1)
                item_title = ref_match.group(2).strip()
            else:
                item_ref = f"{default_prefix}-{i:03d}"
                item_title = header

            item_body = "\n".join(lines[1:]).strip()
            room_id = f"room-{i:03d}"

            items.append({
                "room_id": room_id,
                "task_ref": item_ref,
                "title": item_title,
                "body": item_body,
                "working_dir": working_dir,
            })

        return items

    def close(self) -> None:
        """Flush and close collections."""
        if self._messages:
            self._messages.flush()
        if self._metadata:
            self._metadata.flush()
        if self._plans:
            self._plans.flush()
        if self._epics:
            self._epics.flush()

    # ── Helpers ─────────────────────────────────────────────────────────

    def _plans_dir(self) -> Path:
        """Resolve the plans directory from agents_dir or fallback."""
        if self.agents_dir:
            return self.agents_dir / "plans"
        # Fallback: try common locations
        for candidate in [
            self.warrooms_dir.parent / ".agents" / "plans",
            self.warrooms_dir.parent.parent / ".agents" / "plans",
        ]:
            if candidate.exists():
                return candidate
        return self.warrooms_dir.parent / ".agents" / "plans"

    @staticmethod
    def _read_file(path: Path) -> str | None:
        try:
            return path.read_text().strip() if path.exists() else None
        except Exception:
            return None
