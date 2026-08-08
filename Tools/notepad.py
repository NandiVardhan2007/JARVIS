"""
Windows Notepad Automation Tools for VISION.
Moves mouse cursor to Windows Taskbar Search icon, clicks it, types 'notepad',
creates new tab (Ctrl+N), types content, and automatically saves text files in VISION_OUTPUTS/Text_Files.
"""

import logging
import os
import re
import subprocess
import time
from datetime import datetime
from typing import Literal
from Tools.function_tool import function_tool

logger = logging.getLogger(__name__)

# Output directory for saved text files
OUTPUT_DIR = os.path.join(os.getcwd(), "VISION_OUTPUTS", "Text_Files")

def _ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def _launch_notepad_via_taskbar_search():
    """
    Moves mouse cursor smoothly to the Windows Taskbar Search icon, clicks it,
    types 'notepad', launches Notepad, moves mouse into Notepad window,
    and presses Ctrl+N to open a new tab.
    """
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.05

    logger.info("Moving mouse to Windows taskbar search icon to launch Notepad...")
    sw, sh = pyautogui.size()

    # Step 1: Smoothly move mouse cursor to taskbar search icon position (bottom taskbar)
    search_x = max(80, min(140, int(sw * 0.07)))
    search_y = sh - 22

    # Drag / move mouse smoothly to the search icon on taskbar
    pyautogui.moveTo(search_x, search_y, duration=0.5, tween=pyautogui.easeInOutQuad)
    time.sleep(0.1)

    # Click taskbar search icon
    pyautogui.click(search_x, search_y)
    time.sleep(0.5)

    # Backup: Ensure search window focus
    pyautogui.hotkey("win", "s")
    time.sleep(0.3)

    # Step 2: Type 'notepad' into search bar
    pyautogui.typewrite("notepad", interval=0.05)
    time.sleep(0.6)

    # Step 3: Move mouse smoothly to search result and click to launch Notepad
    result_x = search_x + 60
    result_y = sh - 180
    pyautogui.moveTo(result_x, result_y, duration=0.3, tween=pyautogui.easeInOutQuad)
    time.sleep(0.1)
    pyautogui.click(result_x, result_y)
    pyautogui.press("enter")
    time.sleep(1.2)

    # Step 4: Move mouse smoothly into center of Notepad application window
    pyautogui.moveTo(sw // 2, sh // 2, duration=0.4, tween=pyautogui.easeInOutQuad)
    pyautogui.click()
    time.sleep(0.2)

    # Step 5: Hotkey Ctrl+N for a new tab in Notepad
    pyautogui.hotkey("ctrl", "n")
    time.sleep(0.5)

@function_tool
async def open_notepad() -> str:
    """
    Opens Windows Notepad by moving mouse to taskbar search icon, clicking it,
    typing 'notepad', launching Notepad, and pressing Ctrl+N to initialize a new tab.
    """
    try:
        _launch_notepad_via_taskbar_search()
        return "Moved mouse to taskbar search icon, clicked to open Notepad, and initialized a new tab with Ctrl+N, sir."
    except Exception as e:
        logger.error(f"Mouse taskbar search launch failed: {e}")
        try:
            import pyautogui
            subprocess.Popen(["notepad.exe"], shell=False, creationflags=subprocess.DETACHED_PROCESS)
            time.sleep(1.0)
            pyautogui.hotkey("ctrl", "n")
            return "Opened Windows Notepad and initialized a new tab with Ctrl+N, sir."
        except Exception as ex:
            return f"Failed to open Notepad: {ex}"

@function_tool
async def write_in_notepad(
    title: str,
    content: str,
    document_type: Literal["letter", "report", "notes", "email", "general"] = "general",
    save_file: bool = True,
) -> str:
    """
    Opens Notepad by moving mouse to taskbar search icon, creates a new tab (Ctrl+N),
    writes formatted content into it, and automatically saves the file to VISION_OUTPUTS/Text_Files.

    Args:
        title: Heading, topic, or document subject.
        content: Main text content to type into Notepad.
        document_type: Formatting template — letter, report, notes, email, or general.
        save_file: Whether to automatically save the document to VISION_OUTPUTS/Text_Files.
    """
    logger.info(f"Writing document to Windows Notepad: {title}")
    try:
        import pyautogui
        import pyperclip

        # 1. Open Notepad via Mouse Taskbar Search + Ctrl+N for new tab
        _launch_notepad_via_taskbar_search()

        date_str = datetime.now().strftime("%d %B %Y")

        templates = {
            "letter": (
                f"Date: {date_str}\n\n"
                f"Subject: {title}\n\n"
                "Dear Sir/Madam,\n\n"
                f"{content}\n\n"
                "Thank you for your time and consideration.\n\n"
                "Yours sincerely,\n\n"
            ),
            "report": (
                f"REPORT: {title.upper()}\n"
                f"{'=' * 50}\n"
                f"Date: {date_str}\n\n"
                f"{content}\n\n"
                f"{'=' * 50}\n"
                "End of Report\n"
            ),
            "email": f"Subject: {title}\nDate: {date_str}\n\n{content}\n",
            "notes": f"Notes — {title}\nDate: {date_str}\n\n{content}\n",
            "general": f"{title}\n{'=' * len(title)}\n\n{content}\n",
        }

        doc_text = templates.get(document_type.lower(), templates["general"])

        # 2. Inject text into Notepad tab via character-by-character typing animation
        from Tools.desktop_control import type_text_natively
        type_text_natively(doc_text)
        time.sleep(0.5)

        saved_info = ""
        if save_file:
            _ensure_output_dir()
            clean_title = re.sub(r'[^\w\s-]', '', title).strip().replace(" ", "_") or "Document"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{clean_title}_{timestamp}.txt"
            filepath = os.path.join(OUTPUT_DIR, filename)

            # Write file directly to disk
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(doc_text)

            # Trigger Ctrl+S in Notepad UI to save the tab
            pyautogui.hotkey("ctrl", "s")
            time.sleep(0.8)
            pyperclip.copy(filepath)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.3)
            pyautogui.press("enter")
            saved_info = f" Document saved to 'VISION_OUTPUTS/Text_Files/{filename}'."

        return f"Document '{title}' successfully written to Windows Notepad.{saved_info}"
    except Exception as e:
        logger.error(f"Notepad operation failed: {e}")
        return f"Notepad operation failed: {e}"

@function_tool
async def type_and_save_notepad(
    text: str,
    title: str = "Typed_Note",
) -> str:
    """
    Types specified text into a new tab in Windows Notepad and saves it in VISION_OUTPUTS/Text_Files.

    Args:
        text: The text content to type into Notepad.
        title: Optional document title or filename.
    """
    return await write_in_notepad(title=title, content=text, document_type="general", save_file=True)
