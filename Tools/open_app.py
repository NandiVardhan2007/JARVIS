import logging
import os
import shutil
import subprocess
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

APP_MAP = {
    "text-editor": ["gnome-text-editor", "gedit", "mousepad", "kate", "xed", "leafpad"],
    "text-editor-app": ["gnome-text-editor", "gedit", "mousepad", "kate", "xed", "leafpad"],
    "notepad": ["gnome-text-editor", "gedit", "mousepad", "kate", "xed", "leafpad"],
    "editor": ["gnome-text-editor", "gedit", "mousepad", "kate", "xed", "leafpad"],
    "browser": ["google-chrome", "chromium-browser", "chromium", "firefox"],
    "chrome": ["google-chrome", "chromium-browser", "chromium"],
    "google-chrome": ["google-chrome", "chromium-browser", "chromium"],
    "terminal": ["gnome-terminal", "konsole", "xterm"],
    "command-prompt": ["gnome-terminal", "konsole", "xterm"],
    "files": ["nautilus", "thunar", "dolphin"],
    "file-manager": ["nautilus", "thunar", "dolphin"],
    "calculator": ["gnome-calculator", "kcalc", "galculator"],
    "settings": ["gnome-control-center"],
    "vscode": ["code"],
    "vs-code": ["code"],
}


@function_tool
async def open_app(app_name: str) -> str:
    """
    Launches an application natively on Linux/Ubuntu.

    Args:
        app_name: Name of the application to open (e.g., "text editor", "google chrome", "terminal", "spotify").
    """
    logger.info(f"Launching app: {app_name}")
    try:
        clean_name = app_name.lower().strip().replace(" ", "-")
        
        # Check map
        candidates = APP_MAP.get(clean_name, [clean_name, app_name.lower().strip()])
        for cand in candidates:
            binary = shutil.which(cand)
            if binary:
                subprocess.Popen([binary])
                return f"'{cand}' has been launched, sir."
        
        # Fallback to direct Popen / xdg-open
        subprocess.Popen(clean_name, shell=True)
        return f"'{app_name}' launched."
    except Exception as e:
        return f"Failed to open '{app_name}': {e}"
