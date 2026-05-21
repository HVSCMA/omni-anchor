"""
ClawMem Local Semantic Memory Engine — OMNI-ANCHOR v4.3
100% local. Zero cloud. All data stays on KVM4.

Storage  : /root/omni-anchor/.clawmem/episodic.db
Embeddings: Gemini Embedding-2 (3072-dim, via Google AI API)
Search   : Cosine similarity via numpy
"""

import json
import os
import sqlite3
import struct
import time
from datetime import datetime, timezone
from typing import Optional

import numpy as np

DB_PATH     = os.getenv("CLAWMEM_PATH", "/root/omni-anchor/.clawmem") + "/episodic.db"
GOOGLE_KEY  = os.getenv("GOOGLE_API_KEY", "")
EMBED_MODEL = "gemini-embedding-2"
EMBED_DIM   = 3072

# ── DB init ────────────────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS semantic_memories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            content     TEXT NOT NULL,
            memory_type TEXT DEFAULT 'fact',
            embedding   BLOB NOT NULL,
            metadata    TEXT DEFAULT '{}',
            source      TEXT DEFAULT 'conversation',
            confidence  REAL DEFAULT 1.0,
            created_at  TEXT NOT NULL,
            session_id  TEXT
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_sm_type ON semantic_memories(memory_type)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_sm_ts   ON semantic_memories(created_at)")
    con.commit()
    return con

# ── Embedding ──────────────────────────────────────────────────────────────────

def embed(text: str) -> np.ndarray:
    from google import genai
    client = genai.Client(api_key=GOOGLE_KEY)
    result = client.models.embed_content(model=EMBED_MODEL, contents=text.strip()[:8000])
    return np.array(result.embeddings[0].values, dtype=np.float32)

def _vec_to_blob(v: np.ndarray) -> bytes:
    return struct.pack(f"{len(v)}f", *v)

def _blob_to_vec(b: bytes) -> np.ndarray:
    n = len(b) // 4
    return np.array(struct.unpack(f"{n}f", b), dtype=np.float32)

def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))

# ── Store ──────────────────────────────────────────────────────────────────────

def store(content: str, memory_type: str = "fact", source: str = "conversation",
          metadata: dict = None, session_id: str = None, confidence: float = 1.0) -> int:
    content = content.strip()
    if not content or len(content) < 10:
        return -1

    # Dedup — skip if near-identical memory exists (cosine > 0.97)
    vec = embed(content)
    con = _get_db()
    rows = con.execute("SELECT id, embedding, content FROM semantic_memories WHERE memory_type=?",
                       (memory_type,)).fetchall()
    for row_id, blob, existing in rows:
        existing_vec = _blob_to_vec(blob)
        if _cosine(vec, existing_vec) > 0.97:
            con.close()
            return row_id  # already stored

    ts = datetime.now(timezone.utc).isoformat()
    cur = con.execute(
        "INSERT INTO semantic_memories(content,memory_type,embedding,metadata,source,confidence,created_at,session_id) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (content, memory_type, _vec_to_blob(vec),
         json.dumps(metadata or {}), source, confidence, ts, session_id)
    )
    con.commit()
    new_id = cur.lastrowid
    con.close()
    return new_id

# ── Recall ─────────────────────────────────────────────────────────────────────

def recall(query: str, top_k: int = 6, min_score: float = 0.65,
           memory_type: str = None) -> list[dict]:
    query_vec = embed(query)
    con = _get_db()
    sql = "SELECT id, content, memory_type, metadata, source, confidence, created_at, embedding FROM semantic_memories"
    params = []
    if memory_type:
        sql += " WHERE memory_type=?"
        params.append(memory_type)
    rows = con.execute(sql, params).fetchall()
    con.close()

    scored = []
    for row in rows:
        row_id, content, mtype, meta, source, conf, ts, blob = row
        vec = _blob_to_vec(blob)
        score = _cosine(query_vec, vec) * conf
        if score >= min_score:
            scored.append({
                "id": row_id, "content": content, "memory_type": mtype,
                "score": round(score, 4), "source": source,
                "metadata": json.loads(meta or "{}"), "created_at": ts,
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]

# ── Extract memories from a conversation turn ──────────────────────────────────

def extract_from_turn(user_msg: str, assistant_reply: str,
                      session_id: str = None) -> list[str]:
    """Use Gemini to extract key facts worth remembering from a conversation turn."""
    from google import genai
    client = genai.Client(api_key=GOOGLE_KEY)

    prompt = f"""Extract 0-5 concise, standalone facts worth remembering from this conversation.
Rules:
- Only extract facts about people, preferences, decisions, business context, or important events
- Skip small-talk, greetings, or transient info
- Each fact must be self-contained (readable without the conversation)
- Format: one fact per line, no bullets, no numbering
- If nothing worth remembering: output only the word NONE

User said: {user_msg[:600]}
Assistant replied: {assistant_reply[:600]}

Facts to remember:"""

    r = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    text = r.text.strip()
    if text.upper() == "NONE" or not text:
        return []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and ln.upper() != "NONE"]
    return lines[:5]

# ── Bulk store extracted facts ─────────────────────────────────────────────────

def store_turn(user_msg: str, assistant_reply: str, session_id: str = None) -> int:
    facts = extract_from_turn(user_msg, assistant_reply, session_id)
    stored = 0
    for fact in facts:
        result = store(fact, memory_type="fact", source="conversation", session_id=session_id)
        if result > 0:
            stored += 1
    return stored

# ── Format recalled memories for injection ────────────────────────────────────

def format_recall(memories: list[dict]) -> str:
    if not memories:
        return ""
    lines = ["[WILLOW MEMORY RECALL — relevant context from past interactions]"]
    for m in memories:
        lines.append(f"• {m['content']}  (confidence: {m['score']:.2f})")
    lines.append("[END RECALL]")
    return "\n".join(lines)

# ── Stats ──────────────────────────────────────────────────────────────────────

def stats() -> dict:
    con = _get_db()
    total = con.execute("SELECT COUNT(*) FROM semantic_memories").fetchone()[0]
    by_type = con.execute(
        "SELECT memory_type, COUNT(*) FROM semantic_memories GROUP BY memory_type"
    ).fetchall()
    con.close()
    return {"total": total, "by_type": dict(by_type)}
