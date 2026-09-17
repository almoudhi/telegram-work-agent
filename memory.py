from __future__ import annotations

import sqlite3
from pathlib import Path


class MemoryStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'telegram',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    extracted_text TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def add_memory(self, user_id: int, content: str, source: str = "telegram") -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO memories(user_id, content, source) VALUES (?, ?, ?)",
                (user_id, content.strip(), source),
            )
            return int(cur.lastrowid)

    def list_memories(self, user_id: int, limit: int = 50):
        with self.connect() as conn:
            return conn.execute(
                "SELECT id, content, source, created_at FROM memories WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()

    def delete_memory(self, user_id: int, memory_id: int) -> bool:
        with self.connect() as conn:
            cur = conn.execute(
                "DELETE FROM memories WHERE id=? AND user_id=?", (memory_id, user_id)
            )
            return cur.rowcount > 0

    def add_message(self, user_id: int, role: str, content: str):
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO messages(user_id, role, content) VALUES (?, ?, ?)",
                (user_id, role, content),
            )

    def recent_messages(self, user_id: int, limit: int = 12):
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return list(reversed(rows))

    def add_document(self, user_id: int, filename: str, stored_path: str, text: str) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO documents(user_id, filename, stored_path, extracted_text) VALUES (?, ?, ?, ?)",
                (user_id, filename, stored_path, text),
            )
            return int(cur.lastrowid)

    def search_context(self, user_id: int, query: str, limit: int = 6):
        terms = [t for t in query.replace("\n", " ").split() if len(t) > 2][:8]
        if not terms:
            return []
        where = " OR ".join(["content LIKE ?"] * len(terms))
        params = [user_id, *[f"%{t}%" for t in terms], limit]
        with self.connect() as conn:
            memories = conn.execute(
                f"SELECT 'memory' kind, id, source label, content text FROM memories WHERE user_id=? AND ({where}) ORDER BY id DESC LIMIT ?",
                params,
            ).fetchall()
            doc_where = " OR ".join(["extracted_text LIKE ?"] * len(terms))
            doc_params = [user_id, *[f"%{t}%" for t in terms], limit]
            docs = conn.execute(
                f"SELECT 'document' kind, id, filename label, substr(extracted_text,1,5000) text FROM documents WHERE user_id=? AND ({doc_where}) ORDER BY id DESC LIMIT ?",
                doc_params,
            ).fetchall()
        return [*memories, *docs][:limit]

