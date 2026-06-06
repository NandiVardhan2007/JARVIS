"""
Scheduler — schedule tool executions at a future time.

Examples the user might say:
  "Schedule to open Chrome at 3 PM"
  "After 30 minutes, search for AI news"
  "At 6:00 PM, remind me to call mom"
"""

import asyncio
import logging
import re
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

# ── In-memory task store ──────────────────────────────────────────────────────
_scheduled_tasks: Dict[str, Dict[str, Any]] = {}
_task_counter = 0
_monitor_task: Optional[asyncio.Task] = None

DB_PATH = "jarvis_memory/scheduler.db"

def _ensure_db():
    os.makedirs("jarvis_memory", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS scheduled_tasks (
        id TEXT PRIMARY KEY,
        task_description TEXT,
        schedule_time TEXT,
        tool_name TEXT,
        tool_parameters TEXT,
        created_at TEXT
    )""")
    conn.commit()
    conn.close()

def _load_tasks_from_db():
    global _scheduled_tasks, _task_counter
    _ensure_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT id, task_description, schedule_time, tool_name, tool_parameters, created_at FROM scheduled_tasks").fetchall()
        conn.close()
        for row in rows:
            tid, desc, st, tn, tp, ca = row
            target = datetime.fromisoformat(st)
            _scheduled_tasks[tid] = {
                "task_description": desc,
                "schedule_time": target,
                "tool_name": tn,
                "tool_parameters": tp,
                "created_at": datetime.fromisoformat(ca),
            }
            try:
                num = int(tid.split("_")[1])
                if num > _task_counter:
                    _task_counter = num
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Failed to load scheduled tasks: {e}")

_load_tasks_from_db()


# ── Time parsing ──────────────────────────────────────────────────────────────

def _parse_time(time_str: str) -> datetime | None:
    """
    Parse natural time strings into a datetime.

    Supported formats:
      • "3:00 PM", "9:30 am"
      • "after 30 minutes", "in 2 hours"
      • "tomorrow at 9:00 AM"
    """
    s = time_str.lower().strip()
    now = datetime.now()

    # ── Relative: "after/in N minutes/hours" ──────────────────────────────
    for pattern, multiplier in [
        (r"(?:after|in)\s*(\d+)\s*minutes?", 60),
        (r"(?:after|in)\s*(\d+)\s*hours?", 3600),
        (r"(?:after|in)\s*(\d+)\s*seconds?", 1),
    ]:
        m = re.search(pattern, s)
        if m:
            return now + timedelta(seconds=int(m.group(1)) * multiplier)

    # ── Absolute time: "3:00 PM" / "15:30" ────────────────────────────────
    m = re.search(r"(\d{1,2}):(\d{2})\s*(am|pm)?", s)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        ampm = m.group(3)
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0

        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if "tomorrow" in s:
            target += timedelta(days=1)
        elif target <= now:
            target += timedelta(days=1)  # auto‑rollover
        return target

    return None


# ── Background monitor ────────────────────────────────────────────────────────

async def _monitor():
    """Background loop that fires tasks when their time arrives."""
    logger.info("Scheduler monitor started.")
    while True:
        now = datetime.now()
        fired: list[str] = []

        for tid, task in list(_scheduled_tasks.items()):
            if now >= task["schedule_time"]:
                logger.info(f"Firing scheduled task {tid}: {task['task_description']}")
                # Attempt to call the tool dynamically
                try:
                    from Tools import get_all_tools
                    tool_map = {t.__name__: t for t in get_all_tools()}
                    func = tool_map.get(task["tool_name"])
                    if func:
                        params = task.get("tool_parameters", "")
                        if params:
                            result = await func(params)
                        else:
                            result = await func()
                        logger.info(f"Task {tid} result: {str(result)[:120]}")
                        
                        # Send proactive Telegram notification
                        try:
                            from telegram_bot import send_message, ALLOWED_USERS_LIST
                            if ALLOWED_USERS_LIST:
                                msg = f"🔔 *Scheduled Task Executed*\n📝 {task['task_description']}\n🛠️ Tool: `{task['tool_name']}`\n\n*Result:*\n```text\n{str(result)}\n```"
                                send_message(ALLOWED_USERS_LIST[0], msg)
                        except Exception as e:
                            logger.error(f"Failed to send Telegram notification: {e}")
                    else:
                        logger.warning(f"Task {tid}: tool '{task['tool_name']}' not found.")
                except Exception as exc:
                    logger.error(f"Task {tid} execution error: {exc}")
                fired.append(tid)

        for tid in fired:
            _scheduled_tasks.pop(tid, None)
            try:
                conn = sqlite3.connect(DB_PATH)
                conn.execute("DELETE FROM scheduled_tasks WHERE id = ?", (tid,))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Failed to remove fired task from DB: {e}")

        if not _scheduled_tasks:
            await asyncio.sleep(10)
            continue

        await asyncio.sleep(10)


def _ensure_monitor():
    """Start the monitor if it isn't already running."""
    global _monitor_task
    if _monitor_task is None or _monitor_task.done():
        _monitor_task = asyncio.create_task(_monitor())


# ── Tools ─────────────────────────────────────────────────────────────────────

@function_tool
async def schedule_task(
    task_description: str,
    schedule_time: str,
    tool_name: str,
    tool_parameters: str = "",
) -> str:
    """
    Schedule a tool to run automatically at a specified time.

    Args:
        task_description: Human‑readable description (e.g., "Open Chrome").
        schedule_time:    When to execute — e.g., "3:00 PM", "after 30 minutes",
                          "in 2 hours", "tomorrow at 9:00 AM".
        tool_name:        Exact name of the JARVIS tool function to call
                          (e.g., "open_app", "search_web", "get_weather").
        tool_parameters:  A single string argument to pass to the tool (optional).
    """
    global _task_counter

    from Tools import get_all_tools
    valid_tools = {t.__name__ for t in get_all_tools()}
    if tool_name not in valid_tools:
        # Instead of failing silently, return a helpful error.
        # But wait, execute_multi_task is also valid. It's in get_all_tools().
        # So we just list some common ones or tell them it's invalid.
        return f"Error: '{tool_name}' is not a valid tool. Please check the tool name."

    target = _parse_time(schedule_time)
    if target is None:
        return (
            "Could not understand the time. "
            "Try formats like '3:00 PM', 'after 30 minutes', or 'tomorrow at 9:00 AM'."
        )

    _task_counter += 1
    tid = f"task_{_task_counter}"
    _scheduled_tasks[tid] = {
        "task_description": task_description,
        "schedule_time": target,
        "tool_name": tool_name,
        "tool_parameters": tool_parameters,
        "created_at": datetime.now(),
    }

    try:
        _ensure_db()
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO scheduled_tasks (id, task_description, schedule_time, tool_name, tool_parameters, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (tid, task_description, target.isoformat(), tool_name, tool_parameters, _scheduled_tasks[tid]["created_at"].isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to save scheduled task to DB: {e}")

    _ensure_monitor()

    delta = target - datetime.now()
    mins = int(delta.total_seconds() // 60)

    return (
        f"Task scheduled.\n"
        f"📝 {task_description}\n"
        f"🛠️ Tool: {tool_name}\n"
        f"⏰ Fires at: {target.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"⏳ In approximately {mins} minute(s).\n"
        f"🆔 ID: {tid}"
    )


@function_tool
async def view_scheduled_tasks() -> str:
    """List all pending scheduled tasks with countdown timers."""
    if not _scheduled_tasks:
        return "No scheduled tasks."

    lines: list[str] = []
    for tid, t in _scheduled_tasks.items():
        remaining = t["schedule_time"] - datetime.now()
        h, rem = divmod(int(remaining.total_seconds()), 3600)
        m, s = divmod(rem, 60)
        lines.append(
            f"🆔 {tid}\n"
            f"  📝 {t['task_description']}\n"
            f"  🛠️ Tool: {t['tool_name']}\n"
            f"  ⏰ {t['schedule_time'].strftime('%H:%M:%S')}\n"
            f"  ⏳ {h}h {m}m {s}s remaining\n"
        )
    return "Scheduled Tasks:\n\n" + "\n".join(lines)


@function_tool
async def cancel_scheduled_task(task_id: str) -> str:
    """
    Cancel a pending scheduled task by its ID.

    Args:
        task_id: The task identifier (e.g., "task_1").
    """
    if task_id in _scheduled_tasks:
        desc = _scheduled_tasks.pop(task_id)["task_description"]
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to delete scheduled task from DB: {e}")
        return f"Cancelled: {desc} ({task_id})"
    return f"No task found with ID '{task_id}'."
