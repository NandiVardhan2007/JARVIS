"""
System and OS automation tools for Windows/Desktop control.
Handles Windows UWP apps, protocol handlers, Start Menu search, system metrics, and real-time clock.
"""

import os
import subprocess
from datetime import datetime
from typing import Optional
from pathlib import Path
from vision.tools.registry import tool
from vision.perception.vision.screen import screen_capture
from vision.perception.vision.gemini_vision import gemini_vision
from vision.logger import logger

try:
    import psutil
except ImportError:
    psutil = None

# Known Windows protocol and executable map
APP_PROTOCOL_MAP = {
    "whatsapp": "whatsapp:",
    "whatsapp beta": "whatsapp:",
    "spotify": "spotify:",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "notepad": "notepad.exe",
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "settings": "ms-settings:",
    "camera": "microsoft.windows.camera:",
    "photos": "ms-photos:",
    "mail": "mailto:",
    "vscode": "code",
    "vs code": "code",
    "code": "code",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
    "terminal": "wt.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "microsoft store": "ms-windows-store:",
    "microsoftstore": "ms-windows-store:",
    "ms store": "ms-windows-store:",
    "store": "ms-windows-store:",
    "paint": "mspaint.exe",
    "wordpad": "wordpad.exe",
    "snipping tool": "ms-screenclip:",
    "snip": "ms-screenclip:",
    "control panel": "control.exe",
    "clock": "ms-clock:",
    "alarms": "ms-clock:",
    "weather": "bingweather:",
    "news": "bingnews:",
    "maps": "bingmaps:",
    "xbox": "xbox:",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "discord": "discord:",
    "telegram": "telegram:",
}


def _find_in_start_menu(app_name: str) -> Optional[Path]:
    """Search for matching .lnk shortcut in Windows Start Menu directories."""
    app_name_lower = app_name.lower().replace(" ", "")
    search_dirs = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("ProgramData", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("USERPROFILE", "")) / "Desktop",
        Path(os.environ.get("PUBLIC", "")) / "Desktop",
    ]

    for sdir in search_dirs:
        if sdir.exists():
            for lnk in sdir.rglob("*.lnk"):
                clean_stem = lnk.stem.lower().replace(" ", "")
                if app_name_lower in clean_stem or clean_stem in app_name_lower:
                    return lnk
    return None


@tool(name="open_application", description="Launch an installed desktop application, Windows Store app, or open a URL.")
def open_application(app_name: str) -> str:
    """Launch an application on Windows OS."""
    clean_name = app_name.strip().lower()

    # 1. Check known protocol map (e.g. WhatsApp, Spotify, Calculator, Settings)
    if clean_name in APP_PROTOCOL_MAP:
        target = APP_PROTOCOL_MAP[clean_name]
        try:
            os.system(f'start "" "{target}"')
            logger.info(f"[SystemTool] Launched via protocol/command: {target}")
            return f"Successfully opened {app_name}."
        except Exception as e:
            logger.warning(f"[SystemTool] Protocol launch failed for {target}: {e}")

    # 2. Check Start Menu shortcuts
    lnk_path = _find_in_start_menu(app_name)
    if lnk_path:
        try:
            os.startfile(str(lnk_path))
            logger.info(f"[SystemTool] Launched via Start Menu shortcut: {lnk_path}")
            return f"Successfully opened {lnk_path.stem}."
        except Exception as e:
            logger.warning(f"[SystemTool] Start Menu shortcut launch failed: {e}")

    # 3. Try protocol scheme (e.g. appname:)
    try:
        os.system(f'start "" "{clean_name}:"')
        logger.info(f"[SystemTool] Attempted protocol scheme: {clean_name}:")
        return f"Attempted to launch {app_name}."
    except Exception:
        pass

    # 4. Fallback to start command / executable
    try:
        subprocess.Popen(f'start "" "{app_name}"', shell=True)
        return f"Successfully launched {app_name}."
    except Exception as e:
        return f"Failed to launch {app_name}: {e}"


@tool(name="get_current_time_and_date", description="Get the exact current local system time, day of the week, and date.")
def get_current_time_and_date() -> str:
    """Get the current live local time and date."""
    now = datetime.now()
    return f"Current Local Time: {now.strftime('%I:%M:%S %p')}\nCurrent Date: {now.strftime('%A, %B %d, %Y')}"


@tool(name="get_system_stats", description="Get CPU, memory, and battery status of the host computer.")
def get_system_stats() -> str:
    """Retrieve host performance statistics."""
    if not psutil:
        return "psutil package is not installed; system metrics unavailable."
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    battery = psutil.sensors_battery()
    bat_str = f"{battery.percent}% ({'Plugged in' if battery.power_plugged else 'On Battery'})" if battery else "No battery detected"
    return f"CPU Usage: {cpu}%\nRAM Usage: {mem.percent}% ({mem.used // (1024*1024)}MB / {mem.total // (1024*1024)}MB)\nBattery: {bat_str}"


@tool(name="read_screen", description="Take a screenshot and use vision AI to describe the current desktop contents.")
async def read_screen(query: str = "Describe what is currently visible on the screen") -> str:
    """Inspect and analyze the screen visually."""
    img_bytes = screen_capture.capture_screen()
    if not img_bytes:
        return "Failed to capture desktop screenshot."
    try:
        analysis = await gemini_vision.analyze_image(img_bytes, prompt=query)
        return analysis
    except Exception as e:
        return f"Failed to analyze screen with Vision AI: {e}"
