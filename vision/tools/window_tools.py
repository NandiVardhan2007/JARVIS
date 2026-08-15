"""
Window & Desktop Productivity Tools for VISION AI OS.
Provides control over desktop windows, minimizing, maximizing, snapping, switching, and closing applications.
"""

import time
import subprocess
from typing import Optional, List
import psutil
from vision.tools.registry import tool
from vision.logger import logger

try:
    import pyautogui
    import pygetwindow as gw
    if pyautogui:
        pyautogui.FAILSAFE = False
except ImportError:
    pyautogui = None
    gw = None


# Common process aliases mapping
PROCESS_ALIASES = {
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "notepad": "notepad.exe",
    "calculator": "CalculatorApp.exe",
    "calc": "CalculatorApp.exe",
    "vlc": "vlc.exe",
    "spotify": "Spotify.exe",
    "whatsapp": "WhatsApp.exe",
    "vs code": "Code.exe",
    "vscode": "Code.exe",
    "word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
    "powerpoint": "POWERPNT.EXE",
    "terminal": "WindowsTerminal.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
}


@tool(name="show_desktop", description="Toggle or show the Windows desktop by minimizing all open windows.")
def show_desktop() -> str:
    """Show the Windows desktop (Win + D)."""
    if pyautogui:
        pyautogui.hotkey("win", "d")
        logger.info("[WindowTool] Toggled Show Desktop.")
        return "Toggled Windows Desktop (minimized/restored all windows)."
    return "Error: PyAutoGUI is not available."


@tool(name="minimize_all_windows", description="Minimize all active application windows on the desktop.")
def minimize_all_windows() -> str:
    """Minimize all windows (Win + M)."""
    if pyautogui:
        pyautogui.hotkey("win", "m")
        logger.info("[WindowTool] Minimized all windows.")
        return "Minimized all open windows."
    return "Error: PyAutoGUI is not available."


@tool(name="restore_windows", description="Restore all previously minimized windows back to the screen.")
def restore_windows() -> str:
    """Restore minimized windows (Win + Shift + M)."""
    if pyautogui:
        pyautogui.hotkey("win", "shift", "m")
        logger.info("[WindowTool] Restored minimized windows.")
        return "Restored minimized windows."
    return "Error: PyAutoGUI is not available."


@tool(name="close_application", description="Close or terminate a running desktop application (e.g. 'chrome', 'notepad', 'whatsapp', 'spotify', 'edge').")
def close_application(app_name: str) -> str:
    """Close an application gracefully or terminate its process."""
    if not app_name:
        return "Error: Application name is required."

    target = app_name.lower().strip()
    target_proc = PROCESS_ALIASES.get(target, f"{target}.exe" if not target.endswith(".exe") else target)

    closed_count = 0
    # Try process termination
    for p in psutil.process_iter(['name', 'pid']):
        try:
            p_name = p.info['name']
            if p_name and (p_name.lower() == target_proc.lower() or target in p_name.lower()):
                p.terminate()
                closed_count += 1
        except Exception:
            pass

    if closed_count > 0:
        logger.info(f"[WindowTool] Terminated {closed_count} process instance(s) of '{app_name}'")
        return f"Successfully closed '{app_name}' ({closed_count} process instance(s) terminated)."

    # Fallback to Alt+F4 if window is focused
    if pyautogui:
        pyautogui.hotkey("alt", "f4")
        return f"Sent close command (Alt+F4) to active window for '{app_name}'."

    return f"No active process found matching '{app_name}'."


@tool(name="switch_to_window", description="Bring a specific open application window to the foreground and focus it.")
def switch_to_window(app_name: str) -> str:
    """Bring target application window to front."""
    if not app_name:
        return "Error: App name is required."

    target = app_name.lower().strip()
    if gw:
        try:
            for w in gw.getAllWindows():
                if w.title and target in w.title.lower():
                    if w.isMinimized:
                        w.restore()
                    w.activate()
                    logger.info(f"[WindowTool] Focused window: '{w.title}'")
                    return f"Switched to '{w.title}'."
        except Exception as e:
            logger.debug(f"[WindowTool] Window activate note: {e}")

    # Fallback: Alt+Tab
    if pyautogui:
        pyautogui.hotkey("alt", "tab")
        return f"Switched window context for '{app_name}'."

    return f"Could not find open window matching '{app_name}'."


@tool(name="maximize_window", description="Maximize the currently active window.")
def maximize_window() -> str:
    """Maximize current window (Win + Up)."""
    if pyautogui:
        pyautogui.hotkey("win", "up")
        logger.info("[WindowTool] Maximized active window.")
        return "Maximized active window."
    return "Error: PyAutoGUI not available."


@tool(name="snap_window", description="Snap the active window to the screen side (direction='left' or direction='right').")
def snap_window(direction: str = "left") -> str:
    """Snap active window left or right."""
    if not pyautogui:
        return "Error: PyAutoGUI not available."

    dir_clean = direction.lower().strip()
    if "left" in dir_clean:
        pyautogui.hotkey("win", "left")
        return "Snapped window to the left side."
    elif "right" in dir_clean:
        pyautogui.hotkey("win", "right")
        return "Snapped window to the right side."
    elif "up" in dir_clean or "top" in dir_clean:
        pyautogui.hotkey("win", "up")
        return "Maximized / snapped window up."
    elif "down" in dir_clean or "bottom" in dir_clean:
        pyautogui.hotkey("win", "down")
        return "Minimized / snapped window down."

    return f"Unsupported snap direction '{direction}'. Use 'left' or 'right'."


@tool(name="list_running_applications", description="List common user-facing applications currently running on your PC.")
def list_running_applications() -> str:
    """List running user apps."""
    found = set()
    for p in psutil.process_iter(['name']):
        try:
            name = p.info['name']
            if name:
                n_lower = name.lower()
                for alias, proc in PROCESS_ALIASES.items():
                    if n_lower == proc.lower():
                        found.add(alias.title())
        except Exception:
            pass

    if not found:
        return "No known user-facing apps currently detected in foreground processes."

    return "Running User Applications:\n" + "\n".join(f"- {app}" for app in sorted(found))
