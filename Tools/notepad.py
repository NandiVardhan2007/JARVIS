"""
Write Formatted Documents directly into Windows Notepad.
"""

import logging
import os
import subprocess
import time
from datetime import datetime
from typing import Literal
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

@function_tool
async def write_in_notepad(
    title: str,
    content: str,
    document_type: Literal["letter", "report", "notes", "email", "general"] = "general",
) -> str:
    """
    Opens Windows Notepad and writes a formatted document into it.

    Args:
        title: Document heading or subject.
        content: Main body text.
        document_type: Formatting template to use — letter, report, notes, email, or general.
    """
    logger.info(f"Writing document to Windows Notepad: {title}")
    try:
        import pyautogui
        import pyperclip
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.05

        # Launch Windows Notepad
        subprocess.Popen(["notepad.exe"], shell=False, creationflags=subprocess.DETACHED_PROCESS)
        time.sleep(1.2)

        # Clear existing text in active Notepad window
        pyautogui.hotkey("ctrl", "a")
        pyautogui.press("delete")

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

        doc_text = templates.get(document_type, templates["general"])

        # Inject formatted document instantly via Windows Clipboard
        pyperclip.copy(doc_text)
        pyautogui.hotkey("ctrl", "v")

        return f"Document '{title}' successfully written to Windows Notepad, sir."
    except Exception as e:
        return f"Notepad writing failed: {e}"
