"""Write formatted documents directly into Notepad."""

import logging
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
    Opens Notepad and types a formatted document into it.

    Args:
        title: Document heading or subject.
        content: Main body text (in English for best typing accuracy).
        document_type: Formatting template to use — letter, report, notes, email, or general.
    """
    logger.info(f"Writing to Notepad: {title}")
    try:
        import os
        import shutil
        import subprocess
        import pyautogui
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.1

        # Open Linux Text Editor
        editor_cmd = None
        for ed in ["gnome-text-editor", "gedit", "mousepad", "kate", "xed"]:
            if shutil.which(ed):
                editor_cmd = ed
                break

        if editor_cmd:
            subprocess.Popen([editor_cmd])
            time.sleep(1.5)
            # Clear pre-existing content
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
            "notes": f"Notes — {title}\n{date_str}\n\n{content}\n",
            "general": f"{title}\n{'=' * len(title)}\n\n{content}\n",
        }

        doc = templates.get(document_type, templates["general"])
        pyautogui.write(doc, interval=0.02)

        return f"Document '{title}' written to Notepad."
    except Exception as e:
        return f"Notepad writing failed: {e}"
