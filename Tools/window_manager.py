"""Window management tools."""

import logging
import time
from typing import Literal, Optional
from livekit.agents import function_tool

logger = logging.getLogger(__name__)


@function_tool
async def manage_window(action: Literal["close", "minimize", "maximize", "restore"]) -> str:
    """
    Manages the currently active application window.

    Args:
        action: "close", "minimize", "maximize", or "restore".
    """
    try:
        import pygetwindow as gw
        window = gw.getActiveWindow()
        if not window:
            return "No active window found."
        title = window.title or "Unknown Window"
        getattr(window, action)()
        return f"'{title}' has been {action}d."
    except Exception as e:
        return f"Window management failed: {e}"


@function_tool
async def manage_window_state(
    action: Literal["maximize", "minimize", "restore", "close"],
    window_title: Optional[str] = None,
) -> str:
    """
    Manages the state of a specific or the currently active window.

    Args:
        action: Action to perform (maximize, minimize, restore, close).
        window_title: Title of the target window. Uses active window if not specified.
    """
    try:
        import pygetwindow as gw
        if window_title and window_title.lower() != "active window":
            windows = gw.getWindowsWithTitle(window_title)
            if not windows:
                return f"No window with title '{window_title}' found."
            window = windows[0]
        else:
            window = gw.getActiveWindow()
            if not window:
                return "No active window found."
        title = window.title or "Unknown Window"
        getattr(window, action)()
        return f"'{title}' has been {action}d."
    except Exception as e:
        return f"Window state change failed: {e}"


@function_tool
async def list_active_windows() -> str:
    """
    Lists all visible application windows and their current states.
    """
    try:
        import pygetwindow as gw
        windows = [w for w in gw.getAllWindows() if w.title and w.isVisible]
        if not windows:
            return "No open windows found."
        lines = ["Open Windows:\n"]
        for w in windows[:20]:
            state = "Minimized" if w.isMinimized else ("Maximized" if w.isMaximized else "Normal")
            lines.append(f"• {w.title} [{state}]")
        return "\n".join(lines)
    except Exception as e:
        return f"Window detection failed: {e}"


@function_tool
async def open_app_on_screen(
    app_name: str,
    screen_side: Literal["left", "right", "full"] = "full",
) -> str:
    """
    Opens an application and snaps it to a specific side of the screen.

    Args:
        app_name: Name of the application to open.
        screen_side: "left", "right", or "full" (default: full).
    """
    import subprocess, time
    try:
        import pyautogui, pygetwindow as gw
        subprocess.Popen(["start", app_name], shell=True)
        time.sleep(2)
        screen_w, screen_h = pyautogui.size()
        wins = gw.getWindowsWithTitle(app_name)
        if not wins:
            return f"{app_name} launched. (Could not reposition — window not found by name.)"
        w = wins[0]
        if screen_side == "left":
            w.moveTo(0, 0); w.resizeTo(screen_w // 2, screen_h)
        elif screen_side == "right":
            w.moveTo(screen_w // 2, 0); w.resizeTo(screen_w // 2, screen_h)
        else:
            w.maximize()
        return f"{app_name} opened on the {screen_side} side of the screen."
    except Exception as e:
        return f"Failed to open {app_name}: {e}"

@function_tool
async def apply_window_layout(layout: dict) -> str:
    """
    Applies a window layout preset by moving applications to specific screen regions.
    
    Args:
        layout: A dictionary mapping screen regions ('left', 'right', 'top', 'bottom', 'full') to application window titles. Example: {"left": "Visual Studio Code", "right": "Google Chrome"}
    """
    try:
        import pyautogui
        import pygetwindow as gw
        import time
        
        screen_w, screen_h = pyautogui.size()
        results = []
        
        for region, app_title in layout.items():
            wins = gw.getWindowsWithTitle(app_title)
            if not wins:
                results.append(f"Window '{app_title}' not found.")
                continue
                
            w = wins[0]
            if w.isMinimized:
                w.restore()
                
            region = region.lower()
            if region == "left":
                w.moveTo(0, 0)
                w.resizeTo(screen_w // 2, screen_h)
            elif region == "right":
                w.moveTo(screen_w // 2, 0)
                w.resizeTo(screen_w // 2, screen_h)
            elif region == "top":
                w.moveTo(0, 0)
                w.resizeTo(screen_w, screen_h // 2)
            elif region == "bottom":
                w.moveTo(0, screen_h // 2)
                w.resizeTo(screen_w, screen_h // 2)
            elif region == "full":
                w.maximize()
            else:
                results.append(f"Unknown region '{region}' for '{app_title}'.")
                continue
                
            results.append(f"Moved '{app_title}' to {region}.")
            time.sleep(0.5) # Give the OS time to apply changes
            
        return "\n".join(results)
    except Exception as e:
        return f"Failed to apply window layout: {e}"
