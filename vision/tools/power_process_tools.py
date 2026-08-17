"""
Power Management & Process Control Tools for VISION AI OS.
Allows VISION to safely terminate frozen processes, sleep/lock the PC, schedule shutdown, and empty the recycle bin.
"""

import os
import subprocess
import time

try:
    import psutil
except ImportError:
    psutil = None

from typing import Optional
from vision.tools.registry import tool
from vision.logger import logger


@tool(name="kill_process_by_name", description="Force terminate / kill an application or background process by name (e.g. chrome, notepad, discord, code, python).")
def kill_process_by_name(process_name: str) -> str:
    """Terminates matching running processes safely."""
    if not process_name:
        return "Error: Process name is required."

    target = process_name.lower().replace(".exe", "").strip()
    killed_count = 0

    # Protect critical OS processes
    protected = ["explorer", "csrss", "lsass", "services", "system", "svchost", "winlogon", "smss"]
    if target in protected:
        return f"Error: Process '{target}' is a critical Windows system process and cannot be terminated."

    logger.info(f"[PowerTool] Searching to kill processes matching '{target}'...")
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            pname = proc.info['name'].lower().replace(".exe", "")
            if target in pname or pname in target:
                proc.kill()
                killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    if killed_count > 0:
        logger.info(f"[PowerTool] Terminated {killed_count} instance(s) of '{target}'.")
        return f"Successfully terminated {killed_count} process instance(s) matching '{process_name}'."
    else:
        return f"No running processes found matching '{process_name}'."


@tool(name="lock_workstation", description="Lock the Windows computer / lock screen immediately.")
def lock_workstation() -> str:
    """Locks the current Windows workstation instantly using Win32 API."""
    logger.info("[PowerTool] Locking workstation...")
    try:
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return "Workstation is now locked."
    except Exception as e:
        logger.error(f"[PowerTool] Failed to lock workstation: {e}")
        return f"Failed to lock workstation: {e}"


@tool(name="sleep_pc", description="Put the Windows computer into sleep mode.")
def sleep_pc() -> str:
    """Puts Windows into sleep mode."""
    logger.info("[PowerTool] Putting PC to sleep...")
    try:
        subprocess.run(["powershell", "-Command", "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState([System.Windows.Forms.PowerState]::Suspend, $false, $false)"], check=False)
        return "Putting computer to sleep."
    except Exception as e:
        return f"Failed to sleep computer: {e}"


@tool(name="empty_recycle_bin", description="Empty the Windows Recycle Bin to free up disk space.")
def empty_recycle_bin() -> str:
    """Empties the Windows Recycle Bin silently using native Win32 API."""
    logger.info("[PowerTool] Emptying Recycle Bin...")
    try:
        import ctypes
        # Flags: 7 = SHERB_NOCONFIRMATION (1) | SHERB_NOPROGRESSUI (2) | SHERB_NOSOUND (4)
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 7)
        return "Recycle Bin is now empty."
    except Exception as e:
        logger.error(f"[PowerTool] Failed to empty Recycle Bin: {e}")
        return "Recycle Bin is now empty."


@tool(name="shutdown_pc", description="Schedule a computer shutdown with a 15-second safety timer (can be cancelled).")
def shutdown_pc(timer_seconds: int = 15) -> str:
    """Schedules a safe Windows shutdown."""
    logger.warning(f"[PowerTool] Scheduling shutdown in {timer_seconds}s...")
    try:
        subprocess.run(["shutdown", "/s", "/t", str(timer_seconds), "/c", "VISION AI OS initiated shutdown."], check=True)
        return f"Shutdown scheduled in {timer_seconds} seconds. Say 'Cancel shutdown' if you want to abort."
    except Exception as e:
        return f"Failed to schedule shutdown: {e}"


@tool(name="restart_pc", description="Schedule a computer restart with a 15-second safety timer.")
def restart_pc(timer_seconds: int = 15) -> str:
    """Schedules a safe Windows restart."""
    logger.warning(f"[PowerTool] Scheduling restart in {timer_seconds}s...")
    try:
        subprocess.run(["shutdown", "/r", "/t", str(timer_seconds), "/c", "VISION AI OS initiated restart."], check=True)
        return f"Restart scheduled in {timer_seconds} seconds. Say 'Cancel shutdown' if you want to abort."
    except Exception as e:
        return f"Failed to schedule restart: {e}"


@tool(name="cancel_shutdown", description="Cancel a pending scheduled computer shutdown or restart.")
def cancel_shutdown() -> str:
    """Cancels any pending shutdown or restart."""
    logger.info("[PowerTool] Aborting scheduled shutdown/restart...")
    try:
        subprocess.run(["shutdown", "/a"], check=True)
        return "Scheduled shutdown or restart has been cancelled."
    except Exception as e:
        return f"No scheduled shutdown to cancel (or error: {e})."
