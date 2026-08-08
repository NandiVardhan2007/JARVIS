"""
Window Management Tools for Windows Native.
Uses pygetwindow, win32gui, win32con, and pyautogui to manage active and named application windows,
enumerate open windows, and snap windows to sides of the screen.
"""

import logging
import os
import shutil
import subprocess
import time
from typing import Literal, Optional
from Tools.function_tool import function_tool

logger = logging.getLogger(__name__)

def _get_active_window():
    """Returns active window object via pygetwindow or None."""
    try:
        import pygetwindow as gw
        return gw.getActiveWindow()
    except Exception:
        return None

def _get_window_by_title(title: str):
    """Searches for open window matching title."""
    try:
        import pygetwindow as gw
        wins = gw.getWindowsWithTitle(title)
        if wins:
            return wins[0]
        # Partial match
        for w in gw.getAllWindows():
            if w.title and title.lower() in w.title.lower():
                return w
        return None
    except Exception:
        return None

@function_tool
async def manage_window(action: Literal["close", "minimize", "maximize", "restore"]) -> str:
    """
    Manages the currently active application window on Windows.

    Args:
        action: "close", "minimize", "maximize", or "restore".
    """
    win = _get_active_window()
    if not win:
        # Fallback to win32gui
        try:
            import win32gui, win32con
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                cmd_map = {
                    "close": lambda: win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0),
                    "minimize": lambda: win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE),
                    "maximize": lambda: win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE),
                    "restore": lambda: win32gui.ShowWindow(hwnd, win32con.SW_RESTORE),
                }
                cmd_map[action]()
                return f"Active window has been {action}d."
        except Exception as e:
            return f"Window management failed: {e}"
        return "No active window found."

    try:
        if action == "close":
            win.close()
        elif action == "minimize":
            win.minimize()
        elif action == "maximize":
            win.maximize()
        elif action == "restore":
            win.restore()
        return f"Active window '{win.title}' has been {action}d."
    except Exception as e:
        return f"Window management failed: {e}"

@function_tool
async def manage_window_state(
    action: Literal["maximize", "minimize", "restore", "close"],
    window_title: Optional[str] = None,
) -> str:
    """
    Manages the state of a specific or the currently active window on Windows.

    Args:
        action: Action to perform (maximize, minimize, restore, close).
        window_title: Title of the target window. Uses active window if not specified.
    """
    if window_title and window_title.lower() != "active window":
        win = _get_window_by_title(window_title)
        if not win:
            return f"No open window found with title matching '{window_title}'."
    else:
        win = _get_active_window()
        if not win:
            return "No active window found."

    try:
        if action == "close":
            win.close()
        elif action == "minimize":
            win.minimize()
        elif action == "maximize":
            win.maximize()
        elif action == "restore":
            win.restore()
        return f"Window '{win.title}' has been {action}d."
    except Exception as e:
        return f"Window state change failed: {e}"

@function_tool
async def list_active_windows() -> str:
    """
    Lists all visible application windows currently open on the Windows desktop.
    """
    try:
        import pygetwindow as gw
        windows = gw.getAllWindows()
        visible_titles = [w.title.strip() for w in windows if w.title and w.title.strip() and w.visible]
        
        if not visible_titles:
            return "No visible open windows found."

        unique_titles = list(dict.fromkeys(visible_titles))[:25]
        formatted = "\n".join([f"• {title}" for title in unique_titles])
        return f"Open Windows on Desktop:\n{formatted}"
    except Exception as e:
        # Fallback to win32gui enum
        try:
            import win32gui
            titles = []
            def _enum_cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    t = win32gui.GetWindowText(hwnd).strip()
                    if t:
                        titles.append(t)
            win32gui.EnumWindows(_enum_cb, None)
            unique = list(dict.fromkeys(titles))[:25]
            return "Open Windows:\n" + "\n".join([f"• {t}" for t in unique])
        except Exception:
            return f"Failed to retrieve open windows list: {e}"

@function_tool
async def open_app_on_screen(
    app_name: str,
    screen_side: Literal["left", "right", "full"] = "full",
) -> str:
    """
    Opens an application and snaps it to a specific side of the screen on Windows.

    Args:
        app_name: Name of the application to open.
        screen_side: "left", "right", or "full" (default: full).
    """
    try:
        from Tools.open_app import open_app
        launch_msg = await open_app(app_name)
        time.sleep(1.8)

        import pyautogui
        import pygetwindow as gw
        screen_w, screen_h = pyautogui.size()

        win = gw.getActiveWindow()
        if not win or not win.title:
            return f"{launch_msg} (Window snapping skipped — target window not focused.)"

        try:
            win.restore()
        except Exception as res_err:
            logger.debug(f"Window restore failed for '{win.title}': {res_err}")

        if screen_side == "left":
            win.moveTo(0, 0)
            win.resizeTo(screen_w // 2, screen_h)
        elif screen_side == "right":
            win.moveTo(screen_w // 2, 0)
            win.resizeTo(screen_w // 2, screen_h)
        else:
            win.maximize()

        return f"{app_name} opened and snapped to {screen_side} screen."
    except Exception as e:
        return f"Failed to snap {app_name}: {e}"
