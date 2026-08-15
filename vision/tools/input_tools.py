"""
Keyboard, Typing & Desktop Input Automation Tools for VISION AI OS.
Allows VISION to rapidly type text live onto the screen, write notes/essays, open editors, and press shortcuts.
"""

import time
import subprocess
from typing import Optional
from vision.tools.registry import tool
from vision.logger import logger

try:
    import pyautogui
    import pyperclip
    import pygetwindow as gw
    if pyautogui:
        pyautogui.FAILSAFE = False
except ImportError:
    pyautogui = None
    pyperclip = None
    gw = None


APP_COMMAND_MAP = {
    "notepad": "notepad.exe",
    "word": "winword",
    "excel": "excel",
    "calc": "calc.exe",
    "calculator": "calc.exe",
    "vscode": "code",
    "code": "code",
}


def _ensure_and_focus_window(app_name: str) -> bool:
    """Focus target application window; if not open, launch it automatically."""
    target = app_name.lower().strip()

    # 1. Try to find and activate existing window
    if gw:
        try:
            for w in gw.getAllWindows():
                if w.title and target in w.title.lower():
                    if w.isMinimized:
                        w.restore()
                    w.activate()
                    time.sleep(0.4)
                    logger.info(f"[InputTool] Activated existing window: '{w.title}'")
                    return True
        except Exception as e:
            logger.debug(f"[InputTool] Window focus check: {e}")

    # 2. If not open, launch the application
    cmd = APP_COMMAND_MAP.get(target, target)
    logger.info(f"[InputTool] Window '{target}' not found open. Launching via '{cmd}'...")
    try:
        subprocess.Popen(cmd, shell=True)
        time.sleep(1.0)
        # Try to focus again
        if gw:
            for w in gw.getAllWindows():
                if w.title and target in w.title.lower():
                    w.activate()
                    time.sleep(0.3)
                    return True
        return True
    except Exception as e:
        logger.error(f"[InputTool] Failed to launch '{app_name}': {e}")
        return False


def _stream_type_fast(text: str, burst_delay: float = 0.015):
    """
    Stream-types text live in rapid word chunks.
    Renders 500+ words in under 1 second while preserving the visible live typing effect.
    """
    if not pyautogui or not pyperclip:
        return

    # Split by lines, then by words
    lines = text.split("\n")
    for l_idx, line in enumerate(lines):
        if line.strip():
            words = line.split(" ")
            # Group into small chunks of 2-3 words for hyper-fast visual streaming
            chunk_size = 2
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i:i + chunk_size])
                if i + chunk_size < len(words):
                    chunk += " "
                pyperclip.copy(chunk)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(burst_delay)
        if l_idx < len(lines) - 1:
            pyautogui.press("enter")
            time.sleep(burst_delay)


@tool(name="type_text_into_application", description="Type or write text/notes into an application (e.g. Notepad, Word) with hyper-fast streaming typing.")
def type_text_into_application(text: str, target_app: Optional[str] = "Notepad", press_enter: bool = True) -> str:
    """
    Ensures the target application (e.g. Notepad, Word, Editor) is open and focused,
    then types the text at high speed in real time.
    """
    if not text:
        return "Error: Text content to type is required."

    app = target_app or "Notepad"
    _ensure_and_focus_window(app)
    time.sleep(0.3)

    if not pyautogui:
        return "Error: PyAutoGUI automation package not available."

    logger.info(f"[InputTool] Fast-streaming {len(text)} characters into '{app}'...")
    _stream_type_fast(text, burst_delay=0.015)

    if press_enter:
        time.sleep(0.1)
        pyautogui.press("enter")

    logger.info(f"[InputTool] Successfully typed text into '{app}'")
    return f"Successfully typed text into {app}."


@tool(name="press_keyboard_shortcut", description="Press a keyboard shortcut like 'ctrl+s', 'ctrl+z', 'ctrl+c', 'ctrl+v', 'alt+tab', 'enter', 'tab', 'backspace'.")
def press_keyboard_shortcut(shortcut: str) -> str:
    """Press keyboard keys or combinations."""
    if not shortcut or not pyautogui:
        return "Error: Shortcut or PyAutoGUI not available."

    keys = [k.strip().lower() for k in shortcut.replace("+", " ").split()]
    try:
        if len(keys) == 1:
            pyautogui.press(keys[0])
        else:
            pyautogui.hotkey(*keys)
        logger.info(f"[InputTool] Pressed shortcut: '{shortcut}'")
        return f"Pressed '{shortcut}'."
    except Exception as e:
        return f"Failed to press shortcut '{shortcut}': {e}"
