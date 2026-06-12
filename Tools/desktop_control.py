"""Desktop control, keyboard simulation, typing, and OCR click tools."""

import logging
import time
import asyncio
from typing import Literal, Optional
from livekit.agents import function_tool

logger = logging.getLogger(__name__)


@function_tool
async def desktop_control(
    action: Literal["show", "scroll"],
    direction: Optional[Literal["up", "down", "left", "right"]] = None,
    amount: int = 3,
) -> str:
    """
    Controls desktop UI — show the desktop or scroll the active window.

    Args:
        action: "show" to reveal the desktop, "scroll" to scroll.
        direction: Scroll direction (required if action is "scroll").
        amount: Scroll distance in units (default: 3).
    """
    try:
        import pyautogui
        if action == "show":
            pyautogui.hotkey("win", "d")
            return "Desktop revealed."
        elif action == "scroll":
            dy = amount * 100 if direction == "up" else -amount * 100
            dx = -amount * 100 if direction == "left" else (amount * 100 if direction == "right" else 0)
            if direction in ("up", "down"):
                pyautogui.scroll(dy)
            else:
                pyautogui.hscroll(dx)
            return f"Scrolled {direction} by {amount} units."
        return f"Unknown action: {action}"
    except Exception as e:
        return f"Desktop control failed: {e}"


@function_tool
async def press_key(key: str) -> str:
    """
    Simulates a keyboard key press or hotkey combination.

    Args:
        key: Single key ("enter", "tab") or combo ("ctrl+c", "win+d", "ctrl+alt+del").
    """
    try:
        import pyautogui
        if "+" in key:
            pyautogui.hotkey(*key.split("+"))
        else:
            pyautogui.press(key)
        return f"Key '{key}' pressed."
    except Exception as e:
        return f"Key press failed: {e}"


@function_tool
async def type_user_message_auto(message: str) -> str:
    """
    Types a message into the currently active window.

    Args:
        message: The text to type.
    """
    if not message or not message.strip():
        return "No message provided to type."
    try:
        import pyautogui
        await asyncio.sleep(0.3)
        pyautogui.write(message, interval=0.04)
        preview = message[:60] + ("..." if len(message) > 60 else "")
        return f'Typed: "{preview}"'
    except Exception as e:
        return f"Typing failed: {e}"


@function_tool
async def click_on_text(target_text: str) -> str:
    """
    Locates and clicks on visible screen text using OCR (Tesseract).

    Args:
        target_text: The exact or partial text visible on screen to click.
    """
    try:
        import pyautogui
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        )
        screenshot = pyautogui.screenshot()
        data = pytesseract.image_to_data(screenshot, output_type=pytesseract.Output.DICT)

        for i, text in enumerate(data["text"]):
            if target_text.lower() in text.lower() and data["conf"][i] > 50:
                x = data["left"][i] + data["width"][i] // 2
                y = data["top"][i] + data["height"][i] // 2
                pyautogui.click(x, y)
                return f"Clicked on '{target_text}' at ({x}, {y})."

        return f"Could not find '{target_text}' on the screen."
    except Exception as e:
        return f"OCR click failed: {e}"
