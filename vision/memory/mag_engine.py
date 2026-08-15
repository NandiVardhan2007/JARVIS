"""
Memory-Augmented Generation (MAG) Engine for VISION.
Provides persistent multi-tier memory storage (Semantic Profile, Episodic Timeline, Procedural Habits)
with SQLite backend, fast BM25/keyword retrieval, and contextual prompt injection.
"""

import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from vision.logger import logger


class MAGEngine:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            data_dir = Path("data")
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(data_dir / "memory.db")
        else:
            self.db_path = db_path

        self._init_db()
        self._seed_default_profile()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Create SQLite tables for multi-tier MAG memory."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Semantic Memory (Facts, Preferences, Profiles)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS semantic_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT DEFAULT 'general',
                    content TEXT NOT NULL,
                    tags TEXT,
                    confidence REAL DEFAULT 1.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. Episodic Memory (Events, Actions, Chronological history)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS episodic_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 3. Procedural Memory (Habits, Preferences, Rules)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS procedural_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trigger_context TEXT NOT NULL,
                    rule_action TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _seed_default_profile(self):
        """Seed essential environment knowledge if memory is empty."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM semantic_memories")
            row = cursor.fetchone()
            if row["cnt"] == 0:
                user_home = Path.home()
                defaults = [
                    ("profile", f"User profile username is '{user_home.name}'.", "user,profile,name"),
                    ("hardware", "Connected physical printer is Pantum P2500 Series.", "printer,hardware,pantum"),
                    ("preference", "Default document printing format is plain A4 paper with 1.5 cm border margins.", "document,print,margin,a4"),
                    ("workspace", f"Primary development workspace is located at 'D:\\VISION'.", "workspace,code,project"),
                ]
                for cat, content, tags in defaults:
                    cursor.execute(
                        "INSERT INTO semantic_memories (category, content, tags) VALUES (?, ?, ?)",
                        (cat, content, tags)
                    )
                conn.commit()

    # ── Semantic Memory CRUD ───────────────────────────────────

    def remember(self, content: str, category: str = "user_preference", tags: str = "") -> int:
        """Store a fact or preference in semantic memory."""
        clean = content.strip()
        if not clean:
            return -1

        # Check for duplicates or updates
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, content FROM semantic_memories WHERE content = ?", (clean,))
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    "UPDATE semantic_memories SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (existing["id"],)
                )
                conn.commit()
                return existing["id"]

            cursor.execute(
                "INSERT INTO semantic_memories (category, content, tags) VALUES (?, ?, ?)",
                (category, clean, tags)
            )
            conn.commit()
            mem_id = cursor.lastrowid
            logger.info(f"[MAG] Stored new semantic memory #{mem_id}: '{clean}'")
            return mem_id

    def forget(self, query: str) -> int:
        """Delete memories matching query or keyword."""
        clean = query.strip()
        if not clean:
            return 0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM semantic_memories WHERE content LIKE ? OR tags LIKE ?",
                (f"%{clean}%", f"%{clean}%")
            )
            deleted = cursor.rowcount
            conn.commit()
            logger.info(f"[MAG] Deleted {deleted} memories matching '{clean}'")
            return deleted

    def list_all(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve all active semantic memories."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM semantic_memories ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    # ── Episodic Memory ────────────────────────────────────────

    def record_event(self, event_type: str, description: str, metadata: str = ""):
        """Log a timeline event to episodic memory."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO episodic_memories (event_type, description, metadata) VALUES (?, ?, ?)",
                (event_type, description, metadata)
            )
            conn.commit()

    def get_recent_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve recent episodic events."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM episodic_memories ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    # ── Search & Context Retrieval ─────────────────────────────

    def search_memories(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Rank and return relevant memories matching user query."""
        clean_words = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 2]
        if not clean_words:
            return self.list_all(limit=limit)

        memories = self.list_all(limit=100)
        scored: List[tuple] = []

        for m in memories:
            text = f"{m['category']} {m['content']} {m.get('tags', '')}".lower()
            score = 0
            for word in clean_words:
                if word in text:
                    score += 1
            if score > 0:
                scored.append((score, m))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:limit]]

    def get_mag_prompt_injection(self, user_query: str) -> str:
        """Generate formatted dynamic long-term memory context for LLM prompt injection."""
        q_lower = user_query.lower()
        # If user asks for comprehensive info about themselves
        broad_keywords = ["everything", "all", "know about me", "who am i", "about me", "my details", "full profile", "my profile"]
        is_broad = any(kw in q_lower for kw in broad_keywords)

        if is_broad:
            relevant = self.list_all(limit=40)
        else:
            relevant = self.search_memories(user_query, limit=15)
            if not relevant:
                # Fallback to key profile facts
                relevant = self.list_all(limit=8)

        if not relevant:
            return ""

        seen = set()
        lines = ["\n[LONG-TERM USER MEMORY & PREFERENCES (MAG)]"]
        for m in relevant:
            c = m["content"].strip()
            if c.lower() not in seen:
                seen.add(c.lower())
                lines.append(f"• [{m['category'].upper()}] {c}")

        return "\n".join(lines) + "\n"

    # ── Background Autonomous Fact Extraction ──────────────────

    def auto_extract_facts(self, user_text: str, assistant_text: str):
        """Heuristic and pattern extractor that automatically captures user facts and preferences."""
        patterns = [
            r"my (?:favorite|preferred) ([\w\s]+) is ([\w\s\.-]+)",
            r"i (?:prefer|like|always use) ([\w\s\.-]+)",
            r"remember that ([\w\s\.-]+)",
            r"my (?:name|id|email|phone|city) is ([\w\s\.-@]+)",
        ]

        lower_user = user_text.lower()
        for p in patterns:
            match = re.search(p, lower_user)
            if match:
                fact = match.group(0).strip()
                if "remember that" in fact:
                    fact = fact.replace("remember that", "").strip()
                self.remember(fact.capitalize(), category="auto_learned", tags="auto,preference")
                break


# Global MAG Engine Singleton
mag_engine = MAGEngine()
