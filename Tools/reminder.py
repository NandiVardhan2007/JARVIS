"""Reminder tools with local SQLite persistence."""

import logging
import os
import sqlite3
from datetime import datetime
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = "jarvis_memory/reminders.db"


def _ensure_db():
    os.makedirs("jarvis_memory", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )""")
    conn.commit()
    conn.close()


@function_tool
async def say_reminder(msg: str) -> str:
    """
    Creates a reminder and saves it to the local database.

    Args:
        msg: The reminder content.
    """
    logger.info(f"Reminder set: {msg}")
    try:
        _ensure_db()
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO reminders (content, timestamp) VALUES (?, ?)",
            (msg, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Could not save reminder: {e}")
    return f"Reminder set: {msg}"


@function_tool
async def get_today_reminder_message_from_db() -> str:
    """
    Retrieves all reminders set for today from the local database.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    logger.info(f"Fetching reminders for {today}")
    try:
        _ensure_db()
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT content, timestamp FROM reminders WHERE timestamp LIKE ?",
            (f"{today}%",),
        ).fetchall()
        conn.close()

        if not rows:
            return "No reminders scheduled for today, sir."

        lines = ["Today's reminders:"]
        for content, ts in rows:
            try:
                t = datetime.fromisoformat(ts).strftime("%I:%M %p")
                lines.append(f"• {content} (set at {t})")
            except Exception:
                lines.append(f"• {content}")
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to retrieve reminders: {e}"
