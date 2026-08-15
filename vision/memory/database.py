"""
SQLite Persistent Storage for user preferences, memory facts, and conversation history.
"""

import sqlite3
from typing import List, Dict, Any, Optional
from pathlib import Path
from vision.logger import logger

DB_PATH = Path("vision_data.sqlite")


class Database:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE,
                    value TEXT,
                    category TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def set_memory(self, key: str, value: str, category: str = "general"):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO memories (key, value, category)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, category=excluded.category
            """, (key, value, category))
            conn.commit()

    def get_memory(self, key: str) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT value FROM memories WHERE key = ?", (key,))
            row = cur.fetchone()
            return row[0] if row else None

    def get_all_memories(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT key, value, category, created_at FROM memories")
            return [{"key": r[0], "value": r[1], "category": r[2], "created_at": r[3]} for r in cur.fetchall()]


db = Database()
