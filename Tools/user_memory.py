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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS episodic_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS personality (
                trait TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        # Insert default personality if empty
        cursor = conn.execute("SELECT COUNT(*) FROM personality")
        if cursor.fetchone()[0] == 0:
            conn.execute("INSERT INTO personality (trait, value) VALUES ('identity', 'You are JARVIS, a real-time voice AI assistant with full desktop control, built for speed and precision. You speak with calm confidence, dry wit, and zero filler. Think Tony Stark''s AI — competent, sharp, and effortlessly helpful.')")
            conn.execute("INSERT INTO personality (trait, value) VALUES ('voice_rules', 'Be extremely concise. No markdown or emoji. Lead with the answer. Never narrate your actions.')")
            conn.execute("INSERT INTO personality (trait, value) VALUES ('behavior', 'Decisive, proactive, and protective. Only ask for clarification when genuinely ambiguous.')")

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

@function_tool
async def update_personality(trait: str, value: str) -> str:
    """
    Updates or adds a personality trait for JARVIS.
    
    Args:
        trait: The trait to update (e.g., 'identity', 'voice_rules', 'behavior', 'humor').
        value: The new value or description for that trait.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT OR REPLACE INTO personality (trait, value) VALUES (?, ?)", (trait.strip(), value.strip()))
            conn.commit()
        return f"Personality trait '{trait}' updated to: {value}"
    except Exception as e:
        logger.error(f"Failed to update personality: {e}")
        return f"Failed to update personality: {e}"

def save_episodic_summary(summary: str):
    """Saves a session conversation summary to episodic memory."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO episodic_memory (summary) VALUES (?)", (summary.strip(),))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to save episodic summary: {e}")

def get_memory_summary() -> str:
    """Returns a formatted string of all memories, personality, and episodes for the system prompt."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # 1. Facts
            cursor = conn.execute("SELECT fact FROM memory")
            rows = cursor.fetchall()
            facts_str = "\n".join(f"- {r[0]}" for r in rows) if rows else "No persistent memories saved yet."
            
            # 2. Personality
            cursor = conn.execute("SELECT trait, value FROM personality")
            p_rows = cursor.fetchall()
            personality_str = "\n".join(f"- {r[0].capitalize()}: {r[1]}" for r in p_rows) if p_rows else ""
            
            # 3. Episodic Memory (last 5)
            cursor = conn.execute("SELECT datetime(created_at, 'localtime'), summary FROM episodic_memory ORDER BY id DESC LIMIT 5")
            e_rows = cursor.fetchall()
            episodes_str = "\n".join(f"[{r[0]}] {r[1]}" for r in reversed(e_rows)) if e_rows else "No previous sessions recorded."
            
            return f"## PERSONALITY PROFILE\n{personality_str}\n\n## PERSISTENT FACTS\n{facts_str}\n\n## PREVIOUS SESSIONS\n{episodes_str}"
    except Exception as e:
        return f"Memory system unavailable: {e}"
