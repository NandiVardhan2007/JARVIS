"""
Automatic System Optimization.

Background monitor for RAM, CPU, storage, and thermal conditions. When RAM
or storage usage gets excessively high, it automatically:
  - Clears known-safe, fully-regenerable caches and temp files
  - Releases JARVIS's own idle resources (browser, gesture camera — see
    Tools/resource_optimizer.py)
  - Notifies the user (HUD + a queued suggestion JARVIS can mention next
    time it speaks, since there's no proactive-interruption mechanism in
    this codebase — see the "honest gap" note in start_system_optimizer's
    docstring)

Deliberate design choice: this module does NOT automatically kill user
processes/applications. "Terminate unnecessary background processes safely"
sounds simple but a process using a lot of RAM might have unsaved work in
it — auto-killing it risks exactly the data loss the file-management
deletion policy elsewhere in this codebase is built to avoid. Instead, high
-resource processes are surfaced as suggestions; actually closing one goes
through the existing, already-guarded kill_process tool once the user
agrees. The one exception: this module never terminates ANY process
automatically, full stop — only cache/temp files, which are safe by
definition (regenerable, not user data).
"""

import asyncio
import logging
import os
import shutil
import time
from typing import Optional

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

RAM_THRESHOLD_PCT     = float(os.getenv("JARVIS_RAM_OPTIMIZE_THRESHOLD", "85"))
DISK_THRESHOLD_PCT    = float(os.getenv("JARVIS_DISK_OPTIMIZE_THRESHOLD", "90"))
THERMAL_THRESHOLD_C   = float(os.getenv("JARVIS_THERMAL_THRESHOLD_C", "85"))
CHECK_INTERVAL_SEC    = float(os.getenv("JARVIS_OPTIMIZER_INTERVAL_SEC", "120"))
OPTIMIZATION_COOLDOWN_SEC = 600  # don't re-run cache clearing more than once per 10 min

_optimizer_task = None
_optimizer_active = False
_last_optimization_ts = 0.0
_last_optimization_summary: Optional[str] = None
_pending_suggestions: list[str] = []

MAX_PENDING_SUGGESTIONS = 5


def _queue_suggestion(text: str):
    if text not in _pending_suggestions:
        _pending_suggestions.append(text)
    while len(_pending_suggestions) > MAX_PENDING_SUGGESTIONS:
        _pending_suggestions.pop(0)


def get_pending_suggestions_text() -> str:
    """Plain-text accessor used by agent.py to fold suggestions into the system prompt."""
    if not _pending_suggestions:
        return ""
    return "Pending system optimization notes: " + " | ".join(_pending_suggestions)


def _get_thermal_celsius() -> Optional[float]:
    try:
        import psutil
        temps = psutil.sensors_temperatures()
        if temps:
            for label in ("coretemp", "cpu_thermal", "k10temp", "acpitz"):
                if label in temps and temps[label]:
                    return max(t.current for t in temps[label])
            # Fall back to whatever's first
            first_key = next(iter(temps))
            if temps[first_key]:
                return max(t.current for t in temps[first_key])
    except Exception:
        pass

    # Fallback: read the kernel thermal zone directly
    try:
        zone_path = "/sys/class/thermal/thermal_zone0/temp"
        if os.path.isfile(zone_path):
            with open(zone_path) as f:
                millidegrees = int(f.read().strip())
                return millidegrees / 1000.0
    except Exception:
        pass
    return None


def _get_top_consumers(n: int = 5) -> list[dict]:
    import psutil
    procs = []
    for p in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            info = p.info
            rss_mb = info["memory_info"].rss / (1024 * 1024) if info["memory_info"] else 0
            procs.append({"pid": info["pid"], "name": info["name"], "rss_mb": round(rss_mb, 1)})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda p: p["rss_mb"], reverse=True)
    return procs[:n]


def _dir_size_bytes(path: str) -> int:
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for f in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                continue
    return total


def _clear_dir_contents(path: str) -> int:
    """Removes files/subdirs inside `path` (not the dir itself). Returns bytes freed. Best-effort."""
    freed = 0
    if not os.path.isdir(path):
        return 0
    for entry in os.listdir(path):
        full = os.path.join(path, entry)
        try:
            if os.path.isfile(full) or os.path.islink(full):
                freed += os.path.getsize(full)
                os.remove(full)
            elif os.path.isdir(full):
                freed += _dir_size_bytes(full)
                shutil.rmtree(full, ignore_errors=True)
        except OSError:
            continue  # in-use or permission-denied — skip silently, not worth failing the whole pass
    return freed


def _clear_old_tmp_files(max_age_hours: float = 24) -> int:
    """Removes files under /tmp owned by the current user and older than max_age_hours. Best-effort."""
    freed = 0
    cutoff = time.time() - max_age_hours * 3600
    uid = os.getuid() if hasattr(os, "getuid") else None
    try:
        for entry in os.listdir("/tmp"):
            full = os.path.join("/tmp", entry)
            try:
                st = os.stat(full)
                if uid is not None and st.st_uid != uid:
                    continue
                if st.st_mtime > cutoff:
                    continue
                if os.path.isfile(full) or os.path.islink(full):
                    freed += st.st_size
                    os.remove(full)
                elif os.path.isdir(full):
                    freed += _dir_size_bytes(full)
                    shutil.rmtree(full, ignore_errors=True)
            except OSError:
                continue
    except OSError:
        pass
    return freed


async def _clear_safe_caches() -> tuple[int, list[str]]:
    """
    Clears ONLY well-known, fully-regenerable cache/temp locations — never
    anything that could be user data (documents, browser cookies/sessions,
    trash contents). Returns (bytes_freed, actions_taken).
    """
    home = os.path.expanduser("~")
    actions = []
    total_freed = 0

    safe_targets = [
        ("thumbnail cache", os.path.join(home, ".cache", "thumbnails")),
        ("pip package cache", os.path.join(home, ".cache", "pip")),
        ("npm cache", os.path.join(home, ".cache", "npm")),
        ("fontconfig cache", os.path.join(home, ".cache", "fontconfig")),
    ]

    loop = asyncio.get_event_loop()
    for label, path in safe_targets:
        if os.path.isdir(path):
            freed = await loop.run_in_executor(None, _clear_dir_contents, path)
            if freed > 0:
                total_freed += freed
                actions.append(f"cleared {label} ({freed / (1024*1024):.1f} MB)")

    tmp_freed = await loop.run_in_executor(None, _clear_old_tmp_files, 24)
    if tmp_freed > 0:
        total_freed += tmp_freed
        actions.append(f"removed old temp files (>24h) from /tmp ({tmp_freed / (1024*1024):.1f} MB)")

    return total_freed, actions


async def _run_optimization_pass(trigger: str) -> str:
    global _last_optimization_ts, _last_optimization_summary
    _last_optimization_ts = time.time()

    freed_bytes, actions = await _clear_safe_caches()

    # Also release JARVIS's own idle resources (browser/gesture camera + gc)
    try:
        from Tools.resource_optimizer import release_idle_resources
        jarvis_summary = await release_idle_resources()
        actions.append(f"JARVIS self-cleanup: {jarvis_summary}")
    except Exception as e:
        logger.warning(f"Could not run JARVIS self-cleanup during optimization: {e}")

    if not actions:
        actions.append("no safe caches or idle resources needed clearing")

    summary = f"System optimization ({trigger}): " + "; ".join(actions) + f". Freed about {freed_bytes / (1024*1024):.1f} MB total."
    _last_optimization_summary = summary
    logger.info(summary)

    try:
        from agent import send_hud_state
        send_hud_state({"state": "notify", "description": summary})
    except Exception:
        pass

    return summary


async def _optimizer_loop():
    import psutil

    while _optimizer_active:
        await asyncio.sleep(CHECK_INTERVAL_SEC)
        try:
            ram_pct = psutil.virtual_memory().percent
            disk_pct = psutil.disk_usage("/").percent
            temp_c = _get_thermal_celsius()

            needs_cleanup = ram_pct >= RAM_THRESHOLD_PCT or disk_pct >= DISK_THRESHOLD_PCT
            cooled_down = (time.time() - _last_optimization_ts) > OPTIMIZATION_COOLDOWN_SEC

            if needs_cleanup and cooled_down:
                trigger = f"RAM at {ram_pct:.0f}%" if ram_pct >= RAM_THRESHOLD_PCT else f"disk at {disk_pct:.0f}%"
                await _run_optimization_pass(trigger)

                # Even after clearing safe caches, if RAM is still high, surface
                # top consumers as a SUGGESTION (never auto-killed) for the user
                # to decide on.
                new_ram_pct = psutil.virtual_memory().percent
                if new_ram_pct >= RAM_THRESHOLD_PCT:
                    top = _get_top_consumers(3)
                    top_str = ", ".join(f"{p['name']} ({p['rss_mb']:.0f} MB)" for p in top)
                    _queue_suggestion(
                        f"RAM is still at {new_ram_pct:.0f}% after clearing caches. "
                        f"Heaviest processes right now: {top_str}. Want me to close any of these?"
                    )

            if temp_c is not None and temp_c >= THERMAL_THRESHOLD_C:
                _queue_suggestion(
                    f"CPU temperature is running high ({temp_c:.0f}°C). "
                    f"You might want to check ventilation, or I can pause gesture control/close the browser to reduce load."
                )
                try:
                    from agent import send_hud_state
                    send_hud_state({"state": "alert", "description": f"High CPU temperature: {temp_c:.0f}°C"})
                except Exception:
                    pass

        except Exception as e:
            logger.warning(f"System optimizer check failed: {e}")


@function_tool
async def get_system_health_report() -> str:
    """
    Reports current RAM, CPU, storage, and thermal status, plus the top
    memory-consuming processes — the "should something be optimized right
    now" view, distinct from get_system_info's general diagnostic report.
    """
    try:
        import psutil
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        cpu_pct = psutil.cpu_percent(interval=0.5)
        temp_c = _get_thermal_celsius()
        top = _get_top_consumers(5)

        lines = [
            f"RAM: {ram.percent:.0f}% used ({ram.used / 1024**3:.1f} GB of {ram.total / 1024**3:.1f} GB)",
            f"CPU: {cpu_pct:.0f}% used",
            f"Storage: {disk.percent:.0f}% used ({disk.free / 1024**3:.1f} GB free of {disk.total / 1024**3:.1f} GB)",
        ]
        lines.append(f"Temperature: {temp_c:.0f}°C" if temp_c is not None else "Temperature: sensor not available")
        lines.append("Top RAM consumers: " + ", ".join(f"{p['name']} ({p['rss_mb']:.0f} MB)" for p in top))

        if _pending_suggestions:
            lines.append("\n" + get_pending_suggestions_text())

        return "\n".join(lines)
    except Exception as e:
        return f"Couldn't gather system health report: {e}"


@function_tool
async def optimize_system_now() -> str:
    """
    Immediately clears safe caches/temp files and releases JARVIS's own idle
    resources, regardless of current usage thresholds. Use when the user
    explicitly asks to "clean up" or "optimize" the system right now. Never
    closes applications — see get_system_health_report for suggestions on that.
    """
    return await _run_optimization_pass("manual request")


@function_tool
async def get_pending_optimization_suggestions() -> str:
    """Returns any queued optimization suggestions (e.g. heavy processes worth closing) from recent automatic monitoring."""
    if not _pending_suggestions:
        return "No pending optimization suggestions right now — everything looks fine."
    return get_pending_suggestions_text()


@function_tool
async def start_system_optimizer() -> str:
    """
    Starts the background system optimizer, which periodically checks RAM,
    CPU, storage, and temperature, and automatically clears safe caches/temp
    files (never user documents) when usage gets high. Heavy processes are
    only ever suggested, never auto-closed — closing an application
    automatically risks losing unsaved work, so that step always waits for
    you to say yes.
    """
    global _optimizer_task, _optimizer_active
    if _optimizer_active:
        return "System optimizer is already running."
    _optimizer_active = True
    _optimizer_task = asyncio.create_task(_optimizer_loop())
    return f"System optimizer started — checking every {CHECK_INTERVAL_SEC:.0f}s (RAM/disk threshold {RAM_THRESHOLD_PCT:.0f}%)."


@function_tool
async def stop_system_optimizer() -> str:
    """Stops the background system optimizer."""
    global _optimizer_active, _optimizer_task
    if not _optimizer_active:
        return "System optimizer is not running."
    _optimizer_active = False
    if _optimizer_task:
        _optimizer_task.cancel()
    _optimizer_task = None
    return "System optimizer stopped."
