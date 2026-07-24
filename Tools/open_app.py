import logging
import os
import shutil
import subprocess
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

# Basic fallback mapping for aliases
APP_MAP = {
    "text editor": ["gedit", "gnome-text-editor", "mousepad", "kate"],
    "notepad": ["gedit", "gnome-text-editor", "mousepad", "kate"],
    "browser": ["google-chrome", "firefox", "chromium"],
    "chrome": ["google-chrome"],
    "terminal": ["gnome-terminal", "alacritty", "konsole", "xterm"],
    "command prompt": ["gnome-terminal", "alacritty", "konsole", "xterm"],
    "files": ["nautilus", "thunar", "dolphin"],
    "file manager": ["nautilus", "thunar", "dolphin"],
    "calculator": ["gnome-calculator", "kcalc", "galculator"],
    "settings": ["gnome-control-center"],
    "vscode": ["code"],
    "vs code": ["code"],
    "whatsapp": ["whatsapp-for-linux", "whatsapp-desktop", "whatsapp"],
    "spotify": ["spotify"],
    "discord": ["discord"]
}

def _find_desktop_file_exec(app_name: str) -> str | None:
    """Search through standard .desktop locations to find the executable for an app."""
    search_dirs = [
        "/usr/share/applications/",
        "/usr/local/share/applications/",
        os.path.expanduser("~/.local/share/applications/"),
        "/var/lib/flatpak/exports/share/applications/"
    ]

    clean_name = app_name.lower().replace(" ", "")

    for d in search_dirs:
        if not os.path.exists(d): continue
        for root, dirs, files in os.walk(d):
            for file in files:
                if not file.endswith(".desktop"): continue

                # Check filename match
                filename_clean = file.lower().replace(".desktop", "").replace(" ", "")
                if clean_name in filename_clean or filename_clean in clean_name:
                    return _extract_exec_from_desktop(os.path.join(root, file))

                # Dig into file contents for Name= match
                try:
                    with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        for line in lines:
                            if line.startswith("Name="):
                                name_val = line[5:].strip().lower()
                                if clean_name in name_val.replace(" ", "") or name_val.replace(" ", "") in clean_name:
                                    return _extract_exec_from_desktop(os.path.join(root, file))
                except Exception:
                    pass
    return None

def _extract_exec_from_desktop(filepath: str) -> str | None:
    """Extracts the Exec= line from a .desktop file, stripping %U, %f etc."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith("Exec="):
                    exec_val = line[5:].strip()
                    # Strip out %U, %f, etc
                    import re
                    exec_val = re.sub(r'\%[a-zA-Z]', '', exec_val).strip()
                    return exec_val
    except Exception:
        pass
    return None

@function_tool
async def open_app(app_name: str) -> str:
    """
    Intelligently launches a desktop application on Linux.
    Searches aliases, PATH binaries, and .desktop files.

    Args:
        app_name: Name of the application to open (e.g., "text editor", "whatsapp", "terminal", "spotify").
    """
    logger.info(f"Intelligently launching app: {app_name}")
    try:
        query = app_name.lower().strip()

        # 1. Alias map check
        candidates = APP_MAP.get(query, [])
        for cand in candidates:
            binary = shutil.which(cand)
            if binary:
                subprocess.Popen(binary, shell=True, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return f"'{cand}' has been launched, sir."

        # 2. Direct binary check
        dashed_name = query.replace(" ", "-")
        under_name = query.replace(" ", "_")
        for cand in [query, dashed_name, under_name]:
            binary = shutil.which(cand)
            if binary:
                subprocess.Popen(binary, shell=True, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return f"'{cand}' has been launched."

        # 3. .desktop file deep search
        exec_cmd = _find_desktop_file_exec(query)
        if exec_cmd:
            subprocess.Popen(exec_cmd, shell=True, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"Found and launched '{app_name}' via system shortcuts."

        return f"I couldn't find an application matching '{app_name}' installed on your system."
    except Exception as e:
        return f"Failed to open '{app_name}': {e}"
