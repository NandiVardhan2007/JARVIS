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
    "browser": ["msedge.exe", "chrome.exe", "firefox.exe", "brave.exe"],
    "chrome": ["chrome.exe"],
    "edge": ["msedge.exe"],
    "firefox": ["firefox.exe"],
    "brave": ["brave.exe"],
    "terminal": ["wt.exe", "cmd.exe", "powershell.exe"],
    "command prompt": ["cmd.exe"],
    "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "files": ["explorer.exe"],
    "file manager": ["explorer.exe"],
    "explorer": ["explorer.exe"],
    "calculator": ["calc.exe", "ms-calculator:"],
    "camera": ["microsoft.windows.camera:"],
    "webcam": ["microsoft.windows.camera:"],
    "paint": ["mspaint.exe"],
    "photos": ["ms-photos:"],
    "vscode": ["code.cmd", "code.exe"],
    "vs code": ["code.cmd", "code.exe"],
    "code": ["code.cmd", "code.exe"],
    "whatsapp": ["whatsapp.exe", "whatsapp:"],
    "spotify": ["spotify.exe", "spotify:"],
    "discord": ["discord.exe"],
    "vlc": ["vlc.exe"],
    "task manager": ["taskmgr.exe"],
    "word": ["winword.exe"],
    "excel": ["excel.exe"],
    "powerpoint": ["powerpnt.exe"],
    "settings": ["ms-settings:"],
    "control panel": ["control.exe"],
    "snipping tool": ["snippingtool.exe"],
    "zoom": ["zoom.exe"],
    "steam": ["steam.exe", "steam:"],
    "telegram": ["telegram.exe"],
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

def _search_app_execution_aliases(app_name: str) -> str | None:
    """Searches Windows App Execution Aliases in %LOCALAPPDATA%\\Microsoft\\WindowsApps."""
    local_app_data = os.getenv("LOCALAPPDATA", "")
    if not local_app_data:
        return None
    alias_dir = os.path.join(local_app_data, "Microsoft", "WindowsApps")
    if os.path.exists(alias_dir):
        clean = app_name.lower().replace(" ", "")
        for file in os.listdir(alias_dir):
            if file.lower().endswith(".exe"):
                clean_f = file.lower().replace(".exe", "").replace(" ", "")
                if clean in clean_f or clean_f in clean:
                    return os.path.join(alias_dir, file)
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

        # Check for notepad specifically to run taskbar search + Ctrl+N workflow
        if query in ("notepad", "text editor"):
            from .notepad import open_notepad
            return await open_notepad()

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

        # 5. Windows App Execution Alias search
        alias_path = _search_app_execution_aliases(query)
        if alias_path:
            subprocess.Popen([alias_path], shell=False, creationflags=subprocess.DETACHED_PROCESS)
            return f"Launched '{app_name}' via Windows App Alias, sir."

        # 6. Fallback: OS start command
        res = os.system(f'start "" "{query}"')
        if res == 0:
            return f"'{app_name}' launched successfully, sir."

        return f"I couldn't find an application matching '{app_name}' installed on your Windows system."
    except Exception as e:
        return f"Failed to open '{app_name}': {e}"
