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
    logger.info(f"Launching app: {app_name}")
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.3
        pyautogui.press("win")
        time.sleep(0.8)
        pyautogui.write(app_name, interval=0.05)
        time.sleep(0.8)
        pyautogui.press("enter")
        time.sleep(1)
        return f"'{app_name}' has been launched, sir."
    except Exception as e:
        return f"Failed to open '{app_name}': {e}"
