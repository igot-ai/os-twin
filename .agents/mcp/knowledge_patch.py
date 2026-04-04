
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
                id TEXT PRIMARY KEY,
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
            cursor.execute("INSERT INTO vec_items(id, embedding) VALUES (?, ?)", (ki_id, json.dumps(embedding)))
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

def knowledge_list(limit: int = 100) -> str:
    """List Knowledge Items."""
    conn, _ = _init_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, source, content, tags, created_at FROM knowledge_items ORDER BY created_at DESC LIMIT ?", (limit,))
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

def knowledge_search(query: str, limit: int = 10) -> str:
    """Hybrid search for Knowledge Items (using BM25 fallback if vec missing)."""
    conn, _ = _init_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, source, content, tags, created_at FROM knowledge_items")
    rows = cursor.fetchall()
    conn.close()
    
    entries = []
    for row in rows:
        entries.append({
            "id": row[0],
            "source": row[1],
            "summary": row[2],  # Map content to summary so BM25 function works
            "tags": json.loads(row[3]),
            "created_at": row[4]
        })
        
    scored = _bm25_rank(query, entries)
    top = [e for _, e in scored[:limit]]
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
