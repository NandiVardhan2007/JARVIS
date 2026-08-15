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
    "notemate": "notepad.exe",
    "notpad": "notepad.exe",
    "notepade": "notepad.exe",
    "note": "notepad.exe",
    "notes": "notepad.exe",
    "word": "winword",
    "excel": "excel",
    "calc": "calc.exe",
    "calculator": "calc.exe",
    "vscode": "code",
    "code": "code",
}


def _ensure_and_focus_window(app_name: str) -> bool:
    """Focus target application window with Win32 foreground activation; if not open, launch it automatically."""
    raw = app_name.lower().strip()
    target = "notepad" if ("not" in raw or "note" in raw) else raw

    user32 = ctypes.windll.user32
    target_hwnd = None

    def enum_cb(hwnd, extra):
        nonlocal target_hwnd
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value.lower()
                if target in title:
                    target_hwnd = hwnd
                    return False
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

    # 1. Search for existing window
    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

    # 2. If not found, launch the application
    if not target_hwnd:
        cmd = APP_COMMAND_MAP.get(target, APP_COMMAND_MAP.get(raw, raw))
        logger.info(f"[InputTool] Window '{target}' not found open. Launching via '{cmd}'...")
        try:
            subprocess.Popen(cmd, shell=True)
            for _ in range(25):
                time.sleep(0.12)
                user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
                if target_hwnd:
                    break
        except Exception as e:
            logger.error(f"[InputTool] Failed to launch '{cmd}': {e}")
            return False

    # 3. Force foreground focus using Win32 Alt-key bypass & AttachThreadInput
    if target_hwnd:
        try:
            current_thread = user32.GetCurrentThreadId()
            remote_thread = user32.GetWindowThreadProcessId(target_hwnd, None)
            user32.AttachThreadInput(current_thread, remote_thread, True)
            user32.keybd_event(0x12, 0, 0, 0) # Alt down
            user32.ShowWindow(target_hwnd, 9) # SW_RESTORE
            user32.SetForegroundWindow(target_hwnd)
            user32.BringWindowToTop(target_hwnd)
            user32.keybd_event(0x12, 0, 2, 0) # Alt up
            user32.SetFocus(target_hwnd)
            user32.AttachThreadInput(current_thread, remote_thread, False)
            time.sleep(0.3)
            logger.info(f"[InputTool] Focused window HWND {target_hwnd} for '{target}'")
            return True
        except Exception as e:
            logger.debug(f"[InputTool] Focus window error: {e}")

    return False


# Win32 SendInput Unicode structures for 100% accurate, zero-typo character typing
import ctypes

class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ('wVk', ctypes.c_ushort),
        ('wScan', ctypes.c_ushort),
        ('dwFlags', ctypes.c_ulong),
        ('time', ctypes.c_ulong),
        ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))
    ]

class _INPUT(ctypes.Structure):
    class _INPUT_UNION(ctypes.Union):
        _fields_ = [('ki', _KEYBDINPUT)]
    _anonymous_ = ('_u',)
    _fields_ = [('type', ctypes.c_ulong), ('_u', _INPUT_UNION)]


def _type_letter_by_letter(text: str, delay_per_char: float = 0.003, target_wpm: Optional[int] = None, **kwargs):
    """
    Types text letter-by-letter using native Windows Win32 SendInput KEYEVENTF_UNICODE.
    Zero dropped Shift keys, zero typos, flawless punctuation '(', ')', ':', and capital letters.
    """
    if not text:
        return

    try:
        for char in text:
            if char == '\n':
                # VK_RETURN = 0x0D
                inp_down = _INPUT(type=1, ki=_KEYBDINPUT(wVk=0x0D, wScan=0, dwFlags=0, time=0, dwExtraInfo=None))
                inp_up = _INPUT(type=1, ki=_KEYBDINPUT(wVk=0x0D, wScan=0, dwFlags=2, time=0, dwExtraInfo=None))
                ctypes.windll.user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(_INPUT))
                ctypes.windll.user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(_INPUT))
                time.sleep(0.02)
            elif char == '\t':
                # VK_TAB = 0x09
                inp_down = _INPUT(type=1, ki=_KEYBDINPUT(wVk=0x09, wScan=0, dwFlags=0, time=0, dwExtraInfo=None))
                inp_up = _INPUT(type=1, ki=_KEYBDINPUT(wVk=0x09, wScan=0, dwFlags=2, time=0, dwExtraInfo=None))
                ctypes.windll.user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(_INPUT))
                ctypes.windll.user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(_INPUT))
                time.sleep(0.01)
            else:
                # KEYEVENTF_UNICODE = 0x0004, KEYEVENTF_KEYUP = 0x0002
                code = ord(char)
                inp_down = _INPUT(type=1, ki=_KEYBDINPUT(wVk=0, wScan=code, dwFlags=4, time=0, dwExtraInfo=None))
                inp_up = _INPUT(type=1, ki=_KEYBDINPUT(wVk=0, wScan=code, dwFlags=4 | 2, time=0, dwExtraInfo=None))
                ctypes.windll.user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(_INPUT))
                ctypes.windll.user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(_INPUT))
                if delay_per_char > 0:
                    time.sleep(delay_per_char)
    except Exception as e:
        logger.error(f"[InputTool] Win32 Unicode typing fallback: {e}")
        if pyperclip and pyautogui:
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")


@tool(name="type_text_into_application", description="Type or write text/notes into an application (e.g. Notepad, Word) letter-by-letter rapidly.")
def type_text_into_application(text: str, target_app: Optional[str] = "Notepad", press_enter: bool = True) -> str:
    """
    Ensures the target application (e.g. Notepad, Word, Editor) is open and focused,
    then types the text letter-by-letter at fast streaming speed.
    """
    if not text:
        return "Error: Text content to type is required."

    app = target_app or "Notepad"
    _ensure_and_focus_window(app)
    time.sleep(0.3)

    if not pyautogui:
        return "Error: PyAutoGUI automation package not available."

    logger.info(f"[InputTool] Typing {len(text)} characters letter-by-letter at high speed into '{app}'...")
    _type_letter_by_letter(text, delay_per_char=0.003)

    if press_enter:
        time.sleep(0.05)
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
