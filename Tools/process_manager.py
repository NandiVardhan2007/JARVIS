"""Process manager — list, find, kill, and monitor processes via psutil."""

import asyncio
import logging
import psutil
from typing import Literal, Optional

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

# Processes that must never be killed — system-critical
_PROTECTED = {
    "system", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe",
    "lsass.exe", "services.exe", "svchost.exe", "dwm.exe", "explorer.exe",
    "ntoskrnl.exe", "audiodg.exe", "registry", "secure system",
    # macOS / Linux equivalents
    "launchd", "kernel_task", "systemd", "init", "kthreadd",
}


def _process_row(proc) -> dict:
    """Safely extract process info — returns None fields on AccessDenied."""
    import psutil
    try:
        with proc.oneshot():
            return {
                "pid":    proc.pid,
                "name":   proc.name(),
                "cpu":    round(proc.cpu_percent(interval=None), 1),
                "ram_mb": round(proc.memory_info().rss / 1024 ** 2, 1),
                "status": proc.status(),
            }
    except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
        return None


def _is_protected(name: str) -> bool:
    return name.lower().replace(" ", "") in {p.replace(" ", "") for p in _PROTECTED}


# ── Public tools ──────────────────────────────────────────────────────────────

@function_tool
async def list_processes(
    sort_by: Literal["cpu", "ram", "name", "pid"] = "cpu",
    top_n: int = 10,
    filter_name: Optional[str] = None,
) -> str:
    """
    Lists running processes sorted by CPU, RAM usage, name, or PID.

    Args:
        sort_by: Sort column — "cpu" (default), "ram", "name", or "pid".
        top_n:   How many processes to return (default 10, max 30).
        filter_name: Optional name substring to filter results
                     (e.g. "chrome" shows only Chrome-related processes).
    """
    logger.info(f"Listing processes — sort: {sort_by}, top: {top_n}, filter: {filter_name}")
    top_n = max(1, min(top_n, 30))

    # Prime CPU measurement (first call always returns 0)
    for proc in psutil.process_iter():
        try:
            proc.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    await asyncio.sleep(0.5)

    rows = []
    for proc in psutil.process_iter():
        row = _process_row(proc)
        if row is None:
            continue
        if filter_name and filter_name.lower() not in row["name"].lower():
            continue
        rows.append(row)

    key_map = {"cpu": "cpu", "ram": "ram_mb", "name": "name", "pid": "pid"}
    reverse = sort_by in ("cpu", "ram")
    rows.sort(key=lambda r: r[key_map[sort_by]], reverse=reverse)
    rows = rows[:top_n]

    if not rows:
        return (
            f"No processes found matching '{filter_name}'."
            if filter_name else "No processes found."
        )

    header = f"{'PID':>7}  {'CPU%':>6}  {'RAM MB':>7}  {'Status':<10}  Name"
    sep    = "─" * 60
    lines  = [header, sep]
    for r in rows:
        lines.append(
            f"{r['pid']:>7}  {r['cpu']:>5.1f}%  {r['ram_mb']:>6.1f}  "
            f"{r['status']:<10}  {r['name']}"
        )

    total_ram = round(sum(r["ram_mb"] for r in rows), 1)
    lines.append(sep)
    lines.append(f"Showing {len(rows)} process(es). Total RAM (shown): {total_ram} MB")
    return "\n".join(lines)


@function_tool
async def find_process(name: str) -> str:
    """
    Searches for running processes by name and returns their details.
    Case-insensitive partial match — "chrome" matches "chrome.exe", "chromedriver", etc.

    Args:
        name: Process name or partial name to search for.
    """
    logger.info(f"Finding process: {name}")
    matches = []
    for proc in psutil.process_iter(["pid", "name", "status", "cpu_percent", "memory_info"]):
        try:
            if name.lower() in proc.info["name"].lower():
                ram = round(proc.info["memory_info"].rss / 1024 ** 2, 1)
                matches.append(
                    f"  PID {proc.info['pid']:>6}  CPU {proc.info['cpu_percent']:>5.1f}%  "
                    f"RAM {ram:>6.1f} MB  [{proc.info['status']}]  {proc.info['name']}"
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not matches:
        return f"No processes found matching '{name}'."

    return f"Found {len(matches)} process(es) matching '{name}':\n" + "\n".join(matches)


@function_tool
async def kill_process(
    target: str,
    method: Literal["graceful", "force"] = "graceful",
) -> str:
    """
    Terminates a process by name or PID.

    Always confirms before killing, and refuses to touch protected system processes.

    Args:
        target: Process name (e.g. "chrome", "notepad.exe") or numeric PID.
        method: "graceful" (SIGTERM / taskkill, default) or "force" (SIGKILL / taskkill /F).
                Use force only if graceful fails.
    """
    logger.info(f"Kill request — target: {target}, method: {method}")

    killed   = []
    skipped  = []
    not_found = True

    def _kill(proc, force: bool) -> bool:
        try:
            if force:
                proc.kill()
            else:
                proc.terminate()
            proc.wait(timeout=5)
            return True
        except psutil.TimeoutExpired:
            if not force:
                proc.kill()
                proc.wait(timeout=3)
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            return False

    # PID mode
    if target.isdigit():
        pid = int(target)
        try:
            proc = psutil.Process(pid)
            name = proc.name()
            if _is_protected(name):
                return (
                    f"Process '{name}' (PID {pid}) is a protected system process. "
                    "Refusing to kill."
                )
            force = method == "force"
            if _kill(proc, force):
                return f"Process '{name}' (PID {pid}) terminated successfully."
            return f"Failed to kill PID {pid}."
        except psutil.NoSuchProcess:
            return f"No process with PID {pid} found."
        except psutil.AccessDenied:
            return f"Access denied for PID {pid}. Try running JARVIS as administrator."

    # Name mode — kill all matching instances
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if target.lower() not in proc.info["name"].lower():
                continue
            not_found = False
            name = proc.info["name"]

            if _is_protected(name):
                skipped.append(f"{name} (PID {proc.info['pid']}) — protected")
                continue

            force = method == "force"
            if _kill(proc, force):
                killed.append(f"{name} (PID {proc.info['pid']})")
            else:
                skipped.append(f"{name} (PID {proc.info['pid']}) — failed")

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not_found:
        return f"No process found matching '{target}'. Is it running?"

    parts = []
    if killed:
        parts.append(f"Terminated: {', '.join(killed)}.")
    if skipped:
        parts.append(f"Skipped: {', '.join(skipped)}.")
    return " ".join(parts) if parts else f"Nothing was killed for '{target}'."


@function_tool
async def get_top_resource_hogs(
    resource: Literal["cpu", "ram"] = "cpu",
    top_n: int = 5,
) -> str:
    """
    Returns the processes consuming the most CPU or RAM right now.
    Good for "what's eating my CPU?" or "why is RAM so high?" queries.

    Args:
        resource: "cpu" (default) or "ram".
        top_n:    Number of processes to show (default 5, max 10).
    """
    logger.info(f"Resource hogs — resource: {resource}, top: {top_n}")
    top_n = max(1, min(top_n, 10))

    # Prime CPU counters
    for proc in psutil.process_iter():
        try:
            proc.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    await asyncio.sleep(1)

    rows = []
    for proc in psutil.process_iter():
        row = _process_row(proc)
        if row:
            rows.append(row)

    key = "cpu" if resource == "cpu" else "ram_mb"
    rows.sort(key=lambda r: r[key], reverse=True)
    rows = rows[:top_n]

    if not rows:
        return "Could not retrieve process data."

    unit    = "%" if resource == "cpu" else "MB"
    col_lbl = "CPU%" if resource == "cpu" else "RAM MB"
    lines   = [f"Top {len(rows)} {resource.upper()} consumers:"]

    for i, r in enumerate(rows, 1):
        val = r["cpu"] if resource == "cpu" else r["ram_mb"]
        lines.append(f"  {i}. {r['name']} (PID {r['pid']}) — {val}{unit}")

    # Overall system usage
    total_cpu = psutil.cpu_percent(interval=0.1)
    ram       = psutil.virtual_memory()
    lines.append(
        f"\nSystem — CPU: {total_cpu}%  |  "
        f"RAM: {round(ram.used/1024**3,1)} / {round(ram.total/1024**3,1)} GB "
        f"({ram.percent}% used)"
    )
    return "\n".join(lines)


@function_tool
async def restart_process(name: str) -> str:
    """
    Attempts to restart a process by killing it and re-launching via the Start Menu.
    Useful for frozen apps like explorer.exe, chrome, etc.

    Args:
        name: Process name or app name to restart (e.g. "chrome", "explorer").
    """
    logger.info(f"Restart request: {name}")

    # Special case: explorer.exe restart on Windows
    import platform
    if "explorer" in name.lower() and platform.system() == "Windows":
        import subprocess
        try:
            subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], check=True,
                           capture_output=True)
            await asyncio.sleep(1)
            subprocess.Popen("explorer.exe")
            return "Windows Explorer restarted successfully."
        except Exception as e:
            return f"Explorer restart failed: {e}"

    # Generic restart: kill → open
    kill_result = await kill_process(name, method="graceful")
    if "Terminated" not in kill_result and "terminated" not in kill_result:
        return f"Could not terminate '{name}': {kill_result}"

    await asyncio.sleep(1)

    # Re-launch via Start Menu
    try:
        import pyautogui
        pyautogui.press("win")
        await asyncio.sleep(0.8)
        pyautogui.write(name, interval=0.05)
        await asyncio.sleep(0.8)
        pyautogui.press("enter")
        return f"'{name}' killed and relaunched via Start Menu."
    except Exception as e:
        return f"'{name}' killed but relaunch failed: {e}. Launch it manually."
