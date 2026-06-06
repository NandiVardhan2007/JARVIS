"""User Memory Tool using SQLite."""

import sqlite3
import os
import logging
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "jarvis_memory", "user_memory.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

init_db()

@function_tool
async def memorize_fact(fact: str) -> str:
    """
    Saves a fact or preference about the user into long-term memory.
    
    Args:
        fact: The piece of information to remember (e.g., 'User likes dark mode', 'User is a software engineer').
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT OR IGNORE INTO memory (fact) VALUES (?)", (fact.strip(),))
            conn.commit()
            
        try:
            from Tools.knowledge_base import save_note
            await save_note(title="User Fact", content=fact.strip())
        except Exception as ke:
            logger.warning(f"Fact saved to SQLite but failed to save to knowledge base: {ke}")
            
        return f"Memorized: {fact}"
    except Exception as e:
        logger.error(f"Failed to memorize fact: {e}")
        return f"Failed to memorize fact: {e}"

@function_tool
async def recall_memory(query: str = "") -> str:
    """
    Recalls all saved facts about the user.
    
    Args:
        query: Optional search keyword to filter facts.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            if query:
                cursor = conn.execute("SELECT id, fact FROM memory WHERE fact LIKE ?", (f"%{query}%",))
            else:
                cursor = conn.execute("SELECT id, fact FROM memory")
            rows = cursor.fetchall()
            if not rows:
                return "No matching memories found."
            return "Saved memories:\n" + "\n".join(f"{r[0]}. {r[1]}" for r in rows)
    except Exception as e:
        logger.error(f"Failed to recall memory: {e}")
        return f"Failed to recall memory: {e}"

@function_tool
async def forget_fact(fact_id: int) -> str:
    """
    Deletes a specific fact from memory using its ID.
    
    Args:
        fact_id: The ID of the fact to forget (obtained from recall_memory).
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("DELETE FROM memory WHERE id = ?", (fact_id,))
            conn.commit()
            if cursor.rowcount > 0:
                return f"Forgot fact ID {fact_id}."
            return f"Fact ID {fact_id} not found."
    except Exception as e:
        logger.error(f"Failed to forget fact: {e}")
        return f"Failed to forget fact: {e}"

def get_memory_summary() -> str:
    """Returns a formatted string of all memories for the system prompt."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("SELECT fact FROM memory")
            rows = cursor.fetchall()
            if not rows:
                return "No persistent memories saved yet."
            return "\n".join(f"- {r[0]}" for r in rows)
    except Exception:
        return "Memory system unavailable."
