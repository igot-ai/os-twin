"""
Agent OS Vector Log Store — zvec integration layer.

Indexes all war-room channel messages with embeddings for semantic search.
Stores room metadata for fast dashboard lookups (eliminates "UNKNOWN" task-ref).

Usage:
    store = AgentOSStore(Path("/project/.war-rooms"))
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


class AgentOSStore:
    """In-process vector store for Agent OS logs and metadata."""

    def __init__(self, warrooms_dir: Path):
        self.warrooms_dir = warrooms_dir
        self.zvec_dir = warrooms_dir / ".zvec"
        self.zvec_dir.mkdir(parents=True, exist_ok=True)
        self._messages: Optional[zvec.Collection] = None
        self._metadata: Optional[zvec.Collection] = None
        self._embed_fn = None
        self._embed_available: Optional[bool] = None

    # ── Collections ────────────────────────────────────────────────────

    def ensure_collections(self) -> None:
        """Create or open both collections."""
        zvec.init(log_level=zvec.LogLevel.WARN)
        self._messages = self._open_or_create_messages()
        self._metadata = self._open_or_create_metadata()
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
            filters.append(f"room_id == '{room_id}'")
        if msg_type:
            filters.append(f"msg_type == '{msg_type}'")
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

        if self._messages:
            self._messages.flush()
            # Build HNSW index for search after bulk insert
            try:
                self._messages.optimize()
            except Exception as e:
                logger.warning("optimize failed: %s", e)
        if self._metadata:
            self._metadata.flush()

        logger.info("zvec sync complete: %d messages indexed", total)
        return total

    def close(self) -> None:
        """Flush and close collections."""
        if self._messages:
            self._messages.flush()
        if self._metadata:
            self._metadata.flush()

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _read_file(path: Path) -> str | None:
        try:
            return path.read_text().strip() if path.exists() else None
        except Exception:
            return None
