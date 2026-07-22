"""Window management tools for Linux (Ubuntu)."""

import logging
import os
import subprocess
import time
from typing import Literal, Optional
from livekit.agents import function_tool

logger = logging.getLogger(__name__)


def _get_active_window_id() -> Optional[str]:
    try:
        res = subprocess.check_output(["xdotool", "getactivewindow"]).decode().strip()
        return res
    except Exception:
        return None


def _get_window_id_by_title(title: str) -> Optional[str]:
    try:
        lines = subprocess.check_output(["wmctrl", "-l"]).decode().splitlines()
        for line in lines:
            if title.lower() in line.lower():
                return line.split()[0]
        return None
    except Exception:
        return None


@function_tool
async def manage_window(action: Literal["close", "minimize", "maximize", "restore"]) -> str:
    """
    Manages the currently active application window.

    Args:
        action: "close", "minimize", "maximize", or "restore".
    """
    wid = _get_active_window_id()
    if not wid:
        return "No active window found (requires xdotool)."
    
    try:
        if action == "close":
            os.system(f"xdotool windowclose {wid}")
        elif action == "minimize":
            os.system(f"xdotool windowminimize {wid}")
        elif action == "maximize":
            os.system(f"wmctrl -i -r {wid} -b add,maximized_vert,maximized_horz")
        elif action == "restore":
            os.system(f"wmctrl -i -r {wid} -b remove,maximized_vert,maximized_horz")
        return f"Active window has been {action}d."
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
    if window_title and window_title.lower() != "active window":
        wid = _get_window_id_by_title(window_title)
        if not wid:
            return f"No window with title '{window_title}' found."
    else:
        wid = _get_active_window_id()
        if not wid:
            return "No active window found."
            
    try:
        if action == "close":
            os.system(f"wmctrl -i -c {wid}")
        elif action == "minimize":
            os.system(f"xdotool windowminimize {wid}")
        elif action == "maximize":
            os.system(f"wmctrl -i -r {wid} -b add,maximized_vert,maximized_horz")
        elif action == "restore":
            os.system(f"wmctrl -i -r {wid} -b remove,maximized_vert,maximized_horz")
        return f"Window has been {action}d."
    except Exception as e:
        return f"Window state change failed: {e}"


@function_tool
async def list_active_windows() -> str:
    """
    Lists all visible application windows and their current states.
    """
    try:
        output = subprocess.check_output(["wmctrl", "-l"]).decode().splitlines()
        if not output:
            return "No open windows found."
        
        lines = ["Open Windows:\n"]
        for line in output[:20]:
            parts = line.split(maxsplit=3)
            if len(parts) >= 4:
                title = parts[3]
                lines.append(f"• {title}")
        return "\n".join(lines)
    except Exception as e:
        return f"Window detection failed (requires wmctrl): {e}"


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
    try:
        # Launching the app
        subprocess.Popen(app_name, shell=True)
        time.sleep(2)
        
        wid = _get_active_window_id()
        if not wid:
            return f"{app_name} launched. (Could not reposition — window not found.)"
            
        # Get screen size via xdpyinfo
        try:
            dpy_info = subprocess.check_output(["xdpyinfo"]).decode()
            import re
            m = re.search(r'dimensions:\s+(\d+)x(\d+) pixels', dpy_info)
            if m:
                screen_w, screen_h = int(m.group(1)), int(m.group(2))
            else:
                screen_w, screen_h = 1920, 1080
        except:
            screen_w, screen_h = 1920, 1080
            
        if screen_side == "left":
            os.system(f"wmctrl -i -r {wid} -b remove,maximized_vert,maximized_horz")
            os.system(f"wmctrl -i -r {wid} -e 0,0,0,{screen_w//2},{screen_h}")
        elif screen_side == "right":
            os.system(f"wmctrl -i -r {wid} -b remove,maximized_vert,maximized_horz")
            os.system(f"wmctrl -i -r {wid} -e 0,{screen_w//2},0,{screen_w//2},{screen_h}")
        else:
            os.system(f"wmctrl -i -r {wid} -b add,maximized_vert,maximized_horz")
            
        return f"{app_name} opened on the {screen_side} side of the screen."
    except Exception as e:
        return f"Failed to open {app_name}: {e}"
