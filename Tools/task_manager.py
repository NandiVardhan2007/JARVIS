"""Task Manager Tool using SQLite."""

import sqlite3
import os
import logging
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "jarvis_memory", "tasks.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                priority TEXT DEFAULT 'normal',
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

init_db()

@function_tool
async def add_task(title: str, priority: str = "normal") -> str:
    """
    Adds a new task to the persistent task queue.
    
    Args:
        title: Description of the task.
        priority: Priority of the task ('low', 'normal', 'high').
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO tasks (title, priority) VALUES (?, ?)", (title, priority.lower()))
            conn.commit()
        return f"Task added: '{title}' (Priority: {priority})"
    except Exception as e:
        logger.error(f"Failed to add task: {e}")
        return f"Failed to add task: {e}"

@function_tool
async def complete_task(task_id: int) -> str:
    """
    Marks a task as completed.
    
    Args:
        task_id: The ID of the task.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("UPDATE tasks SET status = 'completed' WHERE id = ?", (task_id,))
            conn.commit()
            if cursor.rowcount > 0:
                return f"Task ID {task_id} marked as completed."
            return f"Task ID {task_id} not found."
    except Exception as e:
        logger.error(f"Failed to complete task: {e}")
        return f"Failed to complete task: {e}"

@function_tool
async def list_tasks(status: str = "pending") -> str:
    """
    Lists tasks from the task queue.
    
    Args:
        status: Filter by status ('pending', 'completed', 'all').
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            if status == 'all':
                cursor = conn.execute("SELECT id, title, priority, status FROM tasks ORDER BY created_at DESC")
            else:
                cursor = conn.execute("SELECT id, title, priority FROM tasks WHERE status = ? ORDER BY priority = 'high' DESC, priority = 'normal' DESC, created_at ASC", (status.lower(),))
            
            rows = cursor.fetchall()
            if not rows:
                return f"No {status} tasks found."
                
            res = [f"=== {status.upper()} TASKS ==="]
            for row in rows:
                if status == 'all':
                    res.append(f"[{row[0]}] ({row[2]}) {row[1]} - {row[3]}")
                else:
                    res.append(f"[{row[0]}] ({row[2]}) {row[1]}")
            return "\n".join(res)
    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        return f"Failed to list tasks: {e}"

@function_tool
async def prioritize_task(task_id: int, priority: str) -> str:
    """
    Changes the priority of a task.
    
    Args:
        task_id: The ID of the task.
        priority: New priority ('low', 'normal', 'high').
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("UPDATE tasks SET priority = ? WHERE id = ?", (priority.lower(), task_id))
            conn.commit()
            if cursor.rowcount > 0:
                return f"Task ID {task_id} priority set to {priority}."
            return f"Task ID {task_id} not found."
    except Exception as e:
        logger.error(f"Failed to prioritize task: {e}")
        return f"Failed to prioritize task: {e}"
