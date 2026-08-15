"""
Keyboard, Typing & Desktop Input Automation Tools for VISION AI OS.
Allows VISION to type text letter-by-letter naturally at 70-100 Words Per Minute (WPM),
open editors, save documents, and execute keyboard shortcuts.
"""

import time
import random
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


def _type_letter_by_letter(text: str, target_wpm: int = 85):
    """
    Types text letter-by-letter at human typing speed (70-100 Words Per Minute).
    1 Word = 5 characters on average.
    At 85 WPM = ~7.1 chars/sec -> base delay ~0.11 - 0.14s per character.
    """
    if not pyautogui:
        return

    # Calculate delay per character based on requested WPM
    base_delay = 60.0 / (max(40, min(140, target_wpm)) * 5.0)

    for char in text:
        # Natural human variance (+/- 20%)
        char_delay = random.uniform(base_delay * 0.8, base_delay * 1.2)

        if char == "\n":
            pyautogui.press("enter")
            time.sleep(base_delay * 1.5)
        elif char == "\t":
            pyautogui.press("tab")
            time.sleep(base_delay)
        else:
            try:
                if ord(char) < 128:
                    pyautogui.write(char)
                else:
                    # Unicode / emoji glyph
                    pyperclip.copy(char)
                    pyautogui.hotkey("ctrl", "v")
                time.sleep(char_delay)
            except Exception:
                if pyperclip:
                    pyperclip.copy(char)
                    pyautogui.hotkey("ctrl", "v")
                time.sleep(char_delay)


@tool(name="type_text_into_application", description="Type or write text/notes into an application (e.g. Notepad, Word) letter-by-letter at 70-100 words per minute.")
def type_text_into_application(text: str, target_app: Optional[str] = "Notepad", press_enter: bool = True) -> str:
    """
    Ensures the target application (e.g. Notepad, Word, Editor) is open and focused,
    then types the text letter-by-letter at natural 70-100 WPM speed.
    """
    if not text:
        return "Error: Text content to type is required."

    app = target_app or "Notepad"
    _ensure_and_focus_window(app)
    time.sleep(0.3)

    if not pyautogui:
        return "Error: PyAutoGUI automation package not available."

    logger.info(f"[InputTool] Typing {len(text)} characters letter-by-letter at ~85 WPM into '{app}'...")
    _type_letter_by_letter(text, target_wpm=85)

    if press_enter:
        time.sleep(0.2)
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


@tool(name="save_active_document", description="Save the currently open document/note in Notepad, Word, or an editor via Ctrl+S, specifying a file name and folder (e.g. Downloads, Desktop).")
def save_active_document(file_name: str = "note.txt", folder: str = "Downloads", target_app: Optional[str] = "Notepad") -> str:
    """Focuses the active editor, triggers Ctrl+S, inputs path, and saves the file."""
    if target_app:
        _ensure_and_focus_window(target_app)
        time.sleep(0.4)

    if not pyautogui or not pyperclip:
        return "Error: PyAutoGUI/Pyperclip not available."

    # Build full destination path
    from vision.tools.file_tools import _resolve_user_path
    dest_dir = _resolve_user_path(folder, find_existing_file=False)
    dest_dir.mkdir(parents=True, exist_ok=True)
    full_path = str(dest_dir / file_name)

    # 1. Trigger Save shortcut
    pyautogui.hotkey("ctrl", "s")
    time.sleep(0.8)

    # 2. In case a 'Save As' dialog opened, paste destination path and press Enter
    pyperclip.copy(full_path)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.4)
    pyautogui.press("enter")
    time.sleep(0.5)

    logger.info(f"[InputTool] Saved active document as '{full_path}'")
    return f"Successfully saved active document to '{full_path}'."
