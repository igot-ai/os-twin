#!/usr/bin/env python3
"""
Agent OS — Memory Core Logic

Pure-Python functions for the shared memory layer.
No MCP dependency — importable by tests and CLI tools.

Storage:
    {AGENT_OS_ROOT}/.agents/memory/ledger.jsonl
    {AGENT_OS_ROOT}/.agents/memory/index.json
"""

import fcntl
import json
import math
import os
import re
import time
from datetime import datetime, timezone
from typing import Optional

# ── Constants ────────────────────────────────────────────────────────────────

VALID_KINDS = {"artifact", "decision", "interface", "convention", "warning", "code"}
MAX_SUMMARY_BYTES = 4096
MAX_DETAIL_BYTES = 16384
MAX_SEARCH_RESULTS = 20

# ── Module-level state ───────────────────────────────────────────────────────

AGENT_OS_ROOT: str = os.environ.get("AGENT_OS_ROOT", ".")


# ── Helpers ──────────────────────────────────────────────────────────────────


def _memory_dir() -> str:
    """Return the shared memory directory path, creating it if needed.

    If AGENT_OS_ROOT was explicitly set (not default "."), trusts it and
    creates .agents/memory/ under it. If it was left as the default "."
    and no .agents/ directory exists in cwd, falls back to the project
    root inferred from this script's location.
    """
    root = AGENT_OS_ROOT
    agents_dir = os.path.join(root, ".agents")

    # Only fall back when AGENT_OS_ROOT was never set (still default ".")
    # and the cwd doesn't look like a project root.
    if root == "." and not os.path.isdir(agents_dir):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # script_dir is typically <project>/.agents/mcp/
        candidate = os.path.dirname(os.path.dirname(script_dir))
        if os.path.isdir(os.path.join(candidate, ".agents")):
            root = candidate
            agents_dir = os.path.join(root, ".agents")

    d = os.path.join(agents_dir, "memory")
    os.makedirs(d, exist_ok=True)
    return d


def _knowledge_dir() -> str:
    root = AGENT_OS_ROOT
    agents_dir = os.path.join(root, ".agents")
    if root == "." and not os.path.isdir(agents_dir):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidate = os.path.dirname(os.path.dirname(script_dir))
        if os.path.isdir(os.path.join(candidate, ".agents")):
            root = candidate
            agents_dir = os.path.join(root, ".agents")
    d = os.path.join(agents_dir, "knowledge")
    os.makedirs(d, exist_ok=True)
    os.makedirs(os.path.join(d, "items"), exist_ok=True)
    return d

def _knowledge_index_path() -> str:
    return os.path.join(_knowledge_dir(), "index.json")

def _knowledge_db_path() -> str:
    return os.path.join(_knowledge_dir(), "embeddings.db")

def _ledger_path() -> str:
    return os.path.join(_memory_dir(), "ledger.jsonl")


def _index_path() -> str:
    return os.path.join(_memory_dir(), "index.json")


def _read_ledger() -> list[dict]:
    """Read all entries from the ledger."""
    path = _ledger_path()
    if not os.path.exists(path):
        return []
    entries = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _get_live(entries: list[dict]) -> list[dict]:
    """Filter out superseded entries (read-only, no disk writes)."""
    superseded_ids: set[str] = set()
    for entry in entries:
        sup = entry.get("supersedes")
        if sup:
            superseded_ids.add(sup)
    return [e for e in entries if e["id"] not in superseded_ids]


def _write_index(live: list[dict]) -> None:
    """Write the materialized index to disk for dashboard/external consumption."""
    index_path = _index_path()
    with open(index_path, "w") as f:
        json.dump(
            {
                "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "count": len(live),
                "entries": live,
            },
            f,
            indent=2,
        )


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase words (preserves duplicates for TF)."""
    return re.findall(r"[a-z0-9_-]+", text.lower())


# Half-life in seconds per kind — how fast each kind loses relevance
# relative to the newest entry in the set.
_HALF_LIFE: dict[str, float] = {
    "code": 7200,        # 2 hours
    "interface": 7200,   # 2 hours
    "decision": 3600,    # 1 hour
    "artifact": 1800,    # 30 min
    "convention": 86400, # 24 hours
    "warning": 86400,    # 24 hours
}
_DEFAULT_HALF_LIFE = 3600.0


def _parse_ts(ts_str: str) -> Optional[datetime]:
    """Parse an entry timestamp string, returning None on failure."""
    if not ts_str:
        return None
    try:
        return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _newest_ts(entries: list[dict]) -> Optional[datetime]:
    """Find the most recent timestamp across a set of entries."""
    latest = None
    for e in entries:
        t = _parse_ts(e.get("ts", ""))
        if t and (latest is None or t > latest):
            latest = t
    return latest


# Scoring weights: final_score = W_RELEVANCE * norm_relevance + W_RECENCY * decay
# Capped at 1.0. Relevance dominates, recency is a tiebreaker.
W_RELEVANCE = 0.7
W_RECENCY = 0.3


def _time_decay(entry: dict, reference: Optional[datetime] = None) -> float:
    """Return a recency score in (0, 1.0] based on age relative to `reference`.

    Uses exponential decay: 0.5 ^ (age / half_life).
    Newest entry = 1.0, older entries decay toward 0.
    `reference` should be the newest entry's timestamp.
    """
    if reference is None:
        return 1.0
    entry_time = _parse_ts(entry.get("ts", ""))
    if entry_time is None:
        return 1.0
    age_seconds = max(0, (reference - entry_time).total_seconds())
    if age_seconds == 0:
        return 1.0
    half_life = _HALF_LIFE.get(entry.get("kind", ""), _DEFAULT_HALF_LIFE)
    return math.pow(0.5, age_seconds / half_life)


def _compute_scores(scored_raw: list[tuple[float, float, dict]]) -> list[tuple[float, dict]]:
    """Normalize relevance and combine with recency into final scores.

    Input:  [(raw_relevance, recency, entry), ...]
    Output: [(final_score, entry), ...] sorted descending

    final_score = 0.7 * (relevance / max_relevance) + 0.3 * recency, capped at 1.0
    """
    if not scored_raw:
        return []
    max_rel = max(r for r, _, _ in scored_raw)
    if max_rel == 0:
        max_rel = 1.0
    result = []
    for rel, rec, entry in scored_raw:
        score = min(1.0, W_RELEVANCE * (rel / max_rel) + W_RECENCY * rec)
        result.append((score, entry))
    result.sort(key=lambda x: x[0], reverse=True)
    return result


# ── BM25 scoring ─────────────────────────────────────────────────────────────

# BM25 parameters
_BM25_K1 = 1.5   # term frequency saturation
_BM25_B = 0.75   # length normalization strength


def _build_searchable(entry: dict) -> str:
    """Build the searchable text from an entry."""
    return " ".join([
        entry.get("summary", ""),
        " ".join(entry.get("tags", [])),
        entry.get("ref", ""),
        entry.get("kind", ""),
        entry.get("detail", ""),
    ])


def _bm25_score(query_tokens: list[str], doc_tokens: list[str],
                df: dict[str, int], n_docs: int, avgdl: float) -> float:
    """Compute BM25 relevance score for a single document.

    query_tokens: tokenized query (list, may have dupes)
    doc_tokens:   tokenized document (list, preserves TF)
    df:           document frequency — df[term] = number of docs containing term
    n_docs:       total number of documents in the corpus
    avgdl:        average document length across corpus
    """
    doc_len = len(doc_tokens)
    if doc_len == 0 or avgdl == 0:
        return 0.0

    # Term frequency in this document
    tf: dict[str, int] = {}
    for t in doc_tokens:
        tf[t] = tf.get(t, 0) + 1

    score = 0.0
    seen_query_terms: set[str] = set()
    for qt in query_tokens:
        if qt in seen_query_terms:
            continue
        seen_query_terms.add(qt)

        # Exact match
        freq = tf.get(qt, 0)

        # Partial match: if no exact match, check if query token is substring of any doc token
        if freq == 0:
            for dt, dt_freq in tf.items():
                if qt in dt:
                    freq = dt_freq
                    break

        if freq == 0:
            continue

        # IDF: log((N - df + 0.5) / (df + 0.5) + 1)
        doc_freq = df.get(qt, 0)
        # Also count partial: docs where qt is substring of a token
        if doc_freq == 0:
            doc_freq = 1  # at least this doc matched
        idf = math.log((n_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)

        # BM25 TF component: (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * dl/avgdl))
        tf_component = (freq * (_BM25_K1 + 1.0)) / (freq + _BM25_K1 * (1.0 - _BM25_B + _BM25_B * doc_len / avgdl))

        score += idf * tf_component

    return score


def _bm25_rank(query: str, entries: list[dict]) -> list[tuple[float, dict]]:
    """Rank entries by BM25 relevance to query. Returns [(score, entry), ...]."""
    if not entries:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    # Build corpus
    docs: list[list[str]] = []
    for entry in entries:
        docs.append(_tokenize(_build_searchable(entry)))

    n_docs = len(docs)
    avgdl = sum(len(d) for d in docs) / n_docs if n_docs > 0 else 1.0

    # Document frequency: for each unique term, how many docs contain it
    df: dict[str, int] = {}
    for doc in docs:
        unique_terms = set(doc)
        for t in unique_terms:
            df[t] = df.get(t, 0) + 1
    # Also compute df for partial matches (query token is substring of doc token)
    for qt in set(query_tokens):
        if qt not in df:
            count = 0
            for doc in docs:
                if any(qt in dt for dt in set(doc)):
                    count += 1
            if count > 0:
                df[qt] = count

    scored = []
    for entry, doc_tokens in zip(entries, docs):
        score = _bm25_score(query_tokens, doc_tokens, df, n_docs, avgdl)
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


# ── Tool functions ───────────────────────────────────────────────────────────


def publish(
    kind: str,
    summary: str,
    tags: list[str],
    room_id: str,
    author_role: str,
    ref: str,
    detail: Optional[str] = None,
    supersedes: Optional[str] = None,
) -> str:
    """Publish a memory entry to the shared memory ledger."""
    if kind not in VALID_KINDS:
        return f"error:invalid kind '{kind}'. Must be one of: {', '.join(sorted(VALID_KINDS))}"

    if len(summary.encode("utf-8")) > MAX_SUMMARY_BYTES:
        summary = summary[:MAX_SUMMARY_BYTES] + "\n[TRUNCATED]"

    if detail and len(detail.encode("utf-8")) > MAX_DETAIL_BYTES:
        detail = detail[:MAX_DETAIL_BYTES] + "\n[TRUNCATED]"

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mem_id = f"mem-{kind[:3]}-{time.time_ns()}-{os.getpid()}"

    entry = {
        "id": mem_id,
        "ts": ts,
        "kind": kind,
        "room_id": room_id,
        "author_role": author_role,
        "ref": ref,
        "tags": [t.lower().strip() for t in tags],
        "summary": summary,
    }
    if detail:
        entry["detail"] = detail
    if supersedes:
        entry["supersedes"] = supersedes

    # Append to ledger with exclusive lock
    ledger = _ledger_path()
    with open(ledger, "a") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(json.dumps(entry) + "\n")
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    # Rebuild index (only publish writes to disk)
    all_entries = _read_ledger()
    live = _get_live(all_entries)
    _write_index(live)

    return f"published:{mem_id}"


def query(
    tags: Optional[list[str]] = None,
    kind: Optional[str] = None,
    ref: Optional[str] = None,
    room_id: Optional[str] = None,
    author_role: Optional[str] = None,
    exclude_room: Optional[str] = None,
    last_n: Optional[int] = None,
) -> str:
    """Query shared memory with optional filters."""
    all_entries = _read_ledger()
    live = _get_live(all_entries)

    results = []
    for entry in live:
        if kind and entry.get("kind") != kind:
            continue
        if ref and entry.get("ref") != ref:
            continue
        if room_id and entry.get("room_id") != room_id:
            continue
        if author_role and entry.get("author_role") != author_role:
            continue
        if exclude_room and entry.get("room_id") == exclude_room:
            continue
        if tags:
            entry_tags = set(entry.get("tags", []))
            query_tags = set(t.lower().strip() for t in tags)
            if not entry_tags & query_tags:
                continue
        results.append(entry)

    if last_n is not None:
        results = results[-last_n:]

    return json.dumps(results[:MAX_SEARCH_RESULTS])


def search(
    text: str,
    kind: Optional[str] = None,
    exclude_room: Optional[str] = None,
    max_results: Optional[int] = 10,
) -> str:
    """Full-text search across shared memory."""
    all_entries = _read_ledger()
    live = _get_live(all_entries)

    query_tokens = _tokenize(text)
    if not query_tokens:
        return "[]"

    # Filter candidates
    candidates = []
    for entry in live:
        if kind and entry.get("kind") != kind:
            continue
        if exclude_room and entry.get("room_id") == exclude_room:
            continue
        candidates.append(entry)

    # BM25 relevance
    bm25_results = _bm25_rank(text, candidates)

    # Combine with time decay: 0.7 * relevance + 0.3 * recency, cap at 1
    ref_ts = _newest_ts(candidates)
    scored_raw = [(rel, _time_decay(entry, ref_ts), entry) for rel, entry in bm25_results]
    scored = _compute_scores(scored_raw)
    results = [entry for _, entry in scored[:max_results]]
    return json.dumps(results)


def get_context(
    room_id: str,
    brief_keywords: Optional[list[str]] = None,
    max_entries: Optional[int] = 15,
) -> str:
    """Generate a curated cross-room context summary for a specific war-room."""
    all_entries = _read_ledger()
    live = _get_live(all_entries)

    candidates = [e for e in live if e.get("room_id") != room_id]

    if brief_keywords:
        query_text = " ".join(brief_keywords)
        bm25_results = _bm25_rank(query_text, candidates)

        ref_ts = _newest_ts(candidates)
        scored_raw = [(rel, _time_decay(entry, ref_ts), entry) for rel, entry in bm25_results]
        scored = _compute_scores(scored_raw)
        candidates = [e for _, e in scored[:max_entries]]
    else:
        candidates = candidates[-max_entries:]

    if not candidates:
        return "No cross-room context available yet."

    by_kind: dict[str, list[dict]] = {}
    for entry in candidates:
        k = entry.get("kind", "other")
        by_kind.setdefault(k, []).append(entry)

    kind_labels = {
        "code": "Code (files, imports, snippets you can use directly)",
        "interface": "Interfaces (API contracts & schemas)",
        "artifact": "Artifacts (what other rooms built)",
        "decision": "Decisions (why choices were made)",
        "convention": "Conventions (team standards)",
        "warning": "Warnings (things to watch out for)",
    }

    lines = ["## Cross-Room Context (auto-generated)\n"]
    for k in ["code", "interface", "artifact", "decision", "convention", "warning"]:
        entries = by_kind.get(k, [])
        if not entries:
            continue
        lines.append(f"### {kind_labels.get(k, k)}\n")
        for entry in entries:
            entry_ref = entry.get("ref", "?")
            room = entry.get("room_id", "?")
            lines.append(f"- **[{entry_ref}]** ({room}): {entry['summary']}")
            if entry.get("detail"):
                detail_preview = entry["detail"][:500]
                if len(entry["detail"]) > 500:
                    detail_preview += "..."
                lines.append(f"  ```\n  {detail_preview}\n  ```")
        lines.append("")

    return "\n".join(lines)


def list_memories(
    kind: Optional[str] = None,
) -> str:
    """List all live memory entries (lightweight index view)."""
    all_entries = _read_ledger()
    live = _get_live(all_entries)

    results = []
    for entry in live:
        if kind and entry.get("kind") != kind:
            continue
        results.append(
            {
                "id": entry["id"],
                "ts": entry.get("ts"),
                "kind": entry.get("kind"),
                "room_id": entry.get("room_id"),
                "ref": entry.get("ref"),
                "tags": entry.get("tags", []),
            }
        )
    return json.dumps(results)

# -- KNOWLEDGE EXTENSION --
import sqlite3

def _init_db():
    db_path = _knowledge_db_path()
    conn = sqlite3.connect(db_path)
    # Enable sqlite_vec if available
    has_vec = False
    try:
        import sqlite_vec
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        has_vec = True
    except Exception:
        pass

    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_items (
            id TEXT PRIMARY KEY,
            source TEXT,
            content TEXT,
            tags TEXT,
            created_at TEXT
        )
    """)
    if has_vec:
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_items USING vec0(
                embedding float[1536]
            )
        """)
    conn.commit()
    return conn, has_vec

def _mock_embed(text: str):
    vec = [0.0] * 1536
    val = (len(text) % 100) / 100.0
    vec[0] = val
    return vec

def knowledge_add(content: str, source: str, tags: list[str]) -> str:
    """Add a Knowledge Item (KI) to Long Memory."""
    conn, has_vec = _init_db()
    cursor = conn.cursor()
    
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ki_id = f"ki-{int(time.time()*1000)}"
    
    # Save to items/ki-XXX.json
    items_dir = os.path.join(_knowledge_dir(), "items")
    ki_path = os.path.join(items_dir, f"{ki_id}.json")
    item = {
        "id": ki_id,
        "content": content,
        "source": source,
        "tags": tags,
        "created_at": ts
    }
    with open(ki_path, "w") as f:
        json.dump(item, f, indent=2)

    # Save to DB
    cursor.execute(
        "INSERT INTO knowledge_items (id, source, content, tags, created_at) VALUES (?, ?, ?, ?, ?)",
        (ki_id, source, content, json.dumps(tags), ts)
    )
    if has_vec:
        embedding = _mock_embed(content)
        try:
            cursor.execute("INSERT INTO vec_items(rowid, embedding) VALUES (?, ?)", (cursor.lastrowid, json.dumps(embedding)))
        except Exception:
            pass
            
    conn.commit()
    conn.close()
    
    # Update index
    _update_knowledge_index()
    return f"added:{ki_id}"

def _update_knowledge_index():
    idx_path = _knowledge_index_path()
    conn, _ = _init_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, source, tags, created_at FROM knowledge_items")
    rows = cursor.fetchall()
    conn.close()
    
    items = []
    for row in rows:
        items.append({
            "id": row[0],
            "source": row[1],
            "tags": json.loads(row[2]),
            "created_at": row[3]
        })
        
    with open(idx_path, "w") as f:
        json.dump({
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), 
            "count": len(items), 
            "items": items
        }, f, indent=2)

def knowledge_list(max_results: int = 100) -> str:
    """List Knowledge Items."""
    conn, _ = _init_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, source, content, tags, created_at FROM knowledge_items ORDER BY created_at DESC LIMIT ?", (max_results,))
    rows = cursor.fetchall()
    conn.close()
    
    items = []
    for row in rows:
        items.append({
            "id": row[0],
            "source": row[1],
            "content": row[2],
            "tags": json.loads(row[3]),
            "created_at": row[4]
        })
    return json.dumps(items)

def knowledge_search(query: str, max_results: int = 10) -> str:
    """Hybrid search for Knowledge Items (using BM25 and semantic search)."""
    conn, has_vec = _init_db()
    cursor = conn.cursor()

    # Fetch all items for BM25
    cursor.execute("SELECT id, source, content, tags, created_at FROM knowledge_items")
    rows = cursor.fetchall()
    
    entries = []
    entry_map = {}
    for row in rows:
        e = {
            "id": row[0],
            "source": row[1],
            "summary": row[2],  # Map content to summary for _bm25_rank
            "tags": json.loads(row[3]),
            "created_at": row[4]
        }
        entries.append(e)
        entry_map[e["id"]] = e
        
    # BM25 ranking
    bm25_scored = _bm25_rank(query, entries)
    bm25_ranks = {e["id"]: rank for rank, (score, e) in enumerate(bm25_scored)}
    
    vec_ranks = {}
    if has_vec:
        try:
            embedding = _mock_embed(query)
            cursor.execute("""
                SELECT ki.id
                FROM vec_items v
                JOIN knowledge_items ki ON v.rowid = ki.rowid
                WHERE v.embedding MATCH ? AND v.k = ?
            """, (json.dumps(embedding), max_results * 5))
            vec_rows = cursor.fetchall()
            vec_ranks = {row[0]: rank for rank, row in enumerate(vec_rows)}
        except Exception:
            pass
            
    conn.close()
    
    if not vec_ranks:
        # Fallback to pure BM25
        top = [e for _, e in bm25_scored[:max_results]]
        return json.dumps(top)
        
    # Hybrid ranking (Reciprocal Rank Fusion)
    rrf_scores = []
    for e in entries:
        eid = e["id"]
        r_bm25 = bm25_ranks.get(eid, 1000)
        r_vec = vec_ranks.get(eid, 1000)
        
        if r_bm25 < 1000 or r_vec < 1000:
            score = 1.0 / (r_bm25 + 60) + 1.0 / (r_vec + 60)
            rrf_scores.append((score, e))
            
    rrf_scores.sort(key=lambda x: x[0], reverse=True)
    top = [e for _, e in rrf_scores[:max_results]]
    return json.dumps(top)

def distill(room_id: Optional[str] = None) -> str:
    """
    Distiller: Summarizes and extracts from the session ledger.
    Produces Long Memory items.
    """
    ledger = _read_ledger()
    if room_id:
        ledger = [e for e in ledger if e.get("room_id") == room_id]
        
    if not ledger:
        return "No entries to distill."
        
    texts = [e.get("summary", "") for e in ledger if "summary" in e]
    combined = "\\n".join(texts)
    
    distilled_content = f"Distilled knowledge from {len(ledger)} entries. Summary: {combined[:100]}..."
    
    ki_id_str = knowledge_add(content=distilled_content, source=f"room:{room_id or 'all'}", tags=["distilled"])
    ki_id = ki_id_str.split(":")[1]
    
    return json.dumps({"status": "success", "ki_id": ki_id, "source_entries": len(ledger)})
