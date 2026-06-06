import os
import sqlite3
import asyncio
import logging
import pyperclip
from datetime import datetime
from typing import Optional
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = "jarvis_memory/clipboard.db"
_monitor_task = None
_last_clipboard_content = ""

def _ensure_db():
    os.makedirs("jarvis_memory", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS clipboard_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        copied_at TEXT NOT NULL,
        labels TEXT
    )''')
    conn.commit()
    conn.close()

async def _clipboard_monitor():
    global _last_clipboard_content
    _ensure_db()
    logger.info("Clipboard monitor started.")
    while True:
        try:
            current_content = pyperclip.paste()
            if current_content and current_content != _last_clipboard_content:
                _last_clipboard_content = current_content
                conn = sqlite3.connect(DB_PATH)
                conn.execute("INSERT INTO clipboard_history (content, copied_at, labels) VALUES (?, ?, ?)",
                             (current_content, datetime.now().isoformat(), ""))
                conn.commit()
                conn.close()
        except Exception as e:
            pass
        await asyncio.sleep(2)

def start_clipboard_monitor():
    global _monitor_task
    if _monitor_task is None or _monitor_task.done():
        _monitor_task = asyncio.create_task(_clipboard_monitor())

# Auto-start on module import
try:
    loop = asyncio.get_running_loop()
    start_clipboard_monitor()
except RuntimeError:
    pass

@function_tool
async def get_recent_clipboard(limit: int = 5) -> str:
    """
    Retrieves recent items copied to the system clipboard.
    
    Args:
        limit: Number of recent items to return (default: 5)
    """
    try:
        _ensure_db()
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT id, content, copied_at FROM clipboard_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        conn.close()
        if not rows:
            return "Clipboard history is empty."
        
        result = "Recent Clipboard Items:\n\n"
        for row in rows:
            content_preview = row[1][:100].replace('\n', ' ') + ('...' if len(row[1]) > 100 else '')
            result += f"ID: {row[0]}\nTime: {row[2]}\nContent: {content_preview}\n---\n"
        return result
    except Exception as e:
        return f"Failed to get clipboard history: {e}"

@function_tool
async def search_clipboard(query: str) -> str:
    """
    Searches the clipboard history for a specific string.
    
    Args:
        query: The string to search for in clipboard history
    """
    try:
        _ensure_db()
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT id, content, copied_at FROM clipboard_history WHERE content LIKE ? ORDER BY id DESC LIMIT 10", (f"%{query}%",)).fetchall()
        conn.close()
        if not rows:
            return f"No clipboard items found matching '{query}'."
        
        result = f"Clipboard items matching '{query}':\n\n"
        for row in rows:
            content_preview = row[1][:100].replace('\n', ' ') + ('...' if len(row[1]) > 100 else '')
            result += f"ID: {row[0]}\nTime: {row[2]}\nContent: {content_preview}\n---\n"
        return result
    except Exception as e:
        return f"Failed to search clipboard: {e}"
