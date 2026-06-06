"""Error telemetry bus — logs tool failures to SQLite for pattern detection."""

import logging
import os
import sqlite3
import traceback
from datetime import datetime, timedelta
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "jarvis_memory", "error_log.db"
)


def _ensure_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tool_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT NOT NULL,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                args_summary TEXT,
                traceback TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tool_errors_ts
            ON tool_errors(timestamp)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tool_errors_name
            ON tool_errors(tool_name)
        """)
        conn.commit()


_ensure_db()


def log_tool_error(
    tool_name: str,
    error: Exception,
    args: dict | None = None,
) -> None:
    """
    Record a tool failure in the telemetry database.
    Call this from the tool execution loop (telegram_bot, agent, etc.).
    """
    try:
        args_summary = str(args)[:500] if args else ""
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        tb_str = "".join(tb)[-2000:]  # keep last 2000 chars

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """INSERT INTO tool_errors
                   (tool_name, error_type, error_message, args_summary, traceback, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    tool_name,
                    type(error).__name__,
                    str(error)[:1000],
                    args_summary,
                    tb_str,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
    except Exception as e:
        # Telemetry must never crash the host
        logger.error(f"Failed to log tool error: {e}")


@function_tool
async def get_error_summary(hours: int = 24) -> str:
    """
    Returns a summary of tool errors in the last N hours — top failing tools,
    error counts, and last occurrence.

    Args:
        hours: Look-back window in hours (default: 24).
    """
    hours = max(1, min(hours, 168))  # cap at 1 week
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

    try:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                """SELECT tool_name,
                          COUNT(*) as cnt,
                          MAX(timestamp) as last_seen,
                          GROUP_CONCAT(DISTINCT error_type) as error_types
                   FROM tool_errors
                   WHERE timestamp >= ?
                   GROUP BY tool_name
                   ORDER BY cnt DESC
                   LIMIT 10""",
                (cutoff,),
            ).fetchall()

        if not rows:
            return f"No tool errors in the last {hours} hours. All systems nominal."

        lines = [f"Tool error summary (last {hours}h):"]
        for name, cnt, last_seen, etypes in rows:
            last_short = last_seen.split("T")[1][:8] if "T" in last_seen else last_seen
            lines.append(f"• {name}: {cnt} error(s), types=[{etypes}], last at {last_short}")

        total = sum(r[1] for r in rows)
        lines.append(f"\nTotal: {total} errors across {len(rows)} tools.")
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to read error telemetry: {e}"


@function_tool
async def get_recent_errors(n: int = 10) -> str:
    """
    Returns the N most recent tool errors with details.

    Args:
        n: Number of recent errors to return (default: 10, max 25).
    """
    n = max(1, min(n, 25))

    try:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                """SELECT tool_name, error_type, error_message, args_summary, timestamp
                   FROM tool_errors
                   ORDER BY id DESC
                   LIMIT ?""",
                (n,),
            ).fetchall()

        if not rows:
            return "No tool errors recorded. Clean slate."

        lines = [f"Last {len(rows)} tool errors:"]
        for name, etype, emsg, args, ts in rows:
            ts_short = ts.split("T")[1][:8] if "T" in ts else ts
            line = f"• [{ts_short}] {name} → {etype}: {emsg[:120]}"
            if args:
                line += f"\n  args: {args[:100]}"
            lines.append(line)

        return "\n".join(lines)
    except Exception as e:
        return f"Failed to read recent errors: {e}"


__all__ = ["log_tool_error", "get_error_summary", "get_recent_errors"]
