"""
Intelligent Windows Application Launcher for VISION.
Searches Windows alias mappings, Start Menu shortcuts, PATH binaries, App Execution Aliases,
and UWP URI protocol schemes.
"""

import logging
import os
import shutil
import subprocess
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

# Windows App Mapping & Fallback Executables / Protocols
APP_MAP = {
    "notepad": ["notepad.exe"],
    "text editor": ["notepad.exe"],
    "browser": ["msedge.exe", "chrome.exe", "firefox.exe"],
    "chrome": ["chrome.exe"],
    "edge": ["msedge.exe"],
    "terminal": ["wt.exe", "cmd.exe", "powershell.exe"],
    "command prompt": ["cmd.exe"],
    "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "files": ["explorer.exe"],
    "file manager": ["explorer.exe"],
    "explorer": ["explorer.exe"],
    "calculator": ["calc.exe", "ms-calculator:"],
    "paint": ["mspaint.exe"],
    "vscode": ["code.cmd", "code.exe"],
    "vs code": ["code.cmd", "code.exe"],
    "code": ["code.cmd", "code.exe"],
    "whatsapp": ["whatsapp.exe", "whatsapp:"],
    "spotify": ["spotify.exe"],
    "discord": ["discord.exe"],
    "task manager": ["taskmgr.exe"],
    "word": ["winword.exe"],
    "excel": ["excel.exe"],
    "powerpoint": ["powerpnt.exe"],
    "settings": ["ms-settings:"],
    "control panel": ["control.exe"],
    "snipping tool": ["snippingtool.exe"],
}

def _search_start_menu_shortcuts(app_name: str) -> str | None:
    """Searches Windows Start Menu directories for .lnk shortcuts matching app_name."""
    search_dirs = [
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs")
    ]

    clean_query = app_name.lower().replace(" ", "")

    for sdir in search_dirs:
        if not os.path.exists(sdir):
            continue
        for root, _, files in os.walk(sdir):
            for file in files:
                if file.lower().endswith(".lnk"):
                    clean_file = file.lower().replace(".lnk", "").replace(" ", "")
                    if clean_query in clean_file or clean_file in clean_query:
                        return os.path.join(root, file)
    return None

@function_tool
async def open_app(app_name: str) -> str:
    """
    Intelligently launches a desktop application on Windows.
    Searches Windows app maps, Start Menu shortcuts, PATH binaries, and UWP schemes.

    Args:
        app_name: Name of the application to open (e.g., "notepad", "chrome", "vscode", "calculator", "whatsapp", "cmd").
    """
    logger.info(f"Launching Windows app: {app_name}")
    try:
        query = app_name.lower().strip()

        # 1. Check direct protocol URI scheme (e.g., ms-settings:, whatsapp:)
        if query in ("settings", "ms-settings"):
            os.system("start ms-settings:")
            return "Windows Settings opened, sir."

        # 2. Alias map check
        candidates = APP_MAP.get(query, [])
        for cand in candidates:
            if cand.startswith("ms-") or cand.endswith(":"):
                os.system(f"start {cand}")
                return f"'{app_name}' launched via Windows protocol, sir."
            
            binary = shutil.which(cand)
            if binary:
                subprocess.Popen([binary], shell=False, creationflags=subprocess.DETACHED_PROCESS)
                return f"'{cand.replace('.exe', '')}' has been launched, sir."

        # 3. Direct binary check on PATH
        for test_name in [query, f"{query}.exe", query.replace(" ", "")]:
            binary = shutil.which(test_name)
            if binary:
                subprocess.Popen([binary], shell=False, creationflags=subprocess.DETACHED_PROCESS)
                return f"'{query}' has been launched, sir."

        # 4. Windows Start Menu shortcut (.lnk) search
        shortcut_path = _search_start_menu_shortcuts(query)
        if shortcut_path:
            os.startfile(shortcut_path)
            return f"Launched '{app_name}' via Windows Start Menu shortcut, sir."

        # 5. Fallback: OS start command
        res = os.system(f'start "" "{query}"')
        if res == 0:
            return f"'{app_name}' launched successfully, sir."

        return f"I couldn't find an application matching '{app_name}' installed on your Windows system."
    except Exception as e:
        return f"Failed to open '{app_name}': {e}"
