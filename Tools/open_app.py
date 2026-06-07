"""Application launcher."""

import logging
import time
from livekit.agents import function_tool

logger = logging.getLogger(__name__)


@function_tool
async def open_app(app_name: str) -> str:
    """
    Launches an application via the Windows Start Menu search.

    Args:
        app_name: Name of the application to open (e.g., "chrome", "notepad", "whatsapp", "spotify"). Never append "desktop" or "app" to the name.
    """
    logger.info(f"Launching or activating app: {app_name}")
    try:
        import pyautogui
        import pygetwindow as gw
        
        # Check if already running
        # We search window titles for the app name
        matching_windows = []
        for win in gw.getAllWindows():
            if win.title and app_name.lower() in win.title.lower():
                matching_windows.append(win)
                
        if matching_windows:
            # Sort by most recently active or just pick the first
            win = matching_windows[0]
            try:
                if win.isMinimized:
                    win.restore()
                win.activate()
                
                # If it's a browser, open a new tab
                if any(b in app_name.lower() for b in ['chrome', 'edge', 'firefox', 'brave', 'safari', 'browser']):
                    time.sleep(0.5)
                    pyautogui.hotkey('ctrl', 't')
                    return f"Activated existing '{app_name}' window and opened a new tab."
                
                return f"Activated existing '{app_name}' window."
            except Exception as e:
                logger.warning(f"Found window but failed to activate: {e}")
                # Fall through to default launch behavior if activation fails

        # Default launch behavior
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.3
        pyautogui.press("win")
        time.sleep(0.8)
        pyautogui.write(app_name, interval=0.05)
        time.sleep(0.8)
        pyautogui.press("enter")
        time.sleep(1)
        return f"'{app_name}' has been launched, sir."
    except ImportError:
        return "Missing dependencies: please install pyautogui and pygetwindow."
    except Exception as e:
        return f"Failed to open '{app_name}': {e}"
