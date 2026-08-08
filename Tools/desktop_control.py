"""
Desktop Control, Keyboard Simulation, Typing, and OCR Click Tools (Windows Native).
"""

import logging
import os
import shutil
import time
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
    Controls Windows desktop UI — reveals desktop (win+d) or scrolls the active window.

    Args:
        action: "show" to reveal the desktop, "scroll" to scroll.
        direction: Scroll direction (required if action is "scroll").
        amount: Scroll distance in units (default: 3).
    """
    try:
        import pyautogui
        pyautogui.FAILSAFE = False

        if action == "show":
            pyautogui.hotkey("win", "d")
            return "Windows desktop revealed, sir."
        elif action == "scroll":
            dy = amount * 120 if direction == "up" else -amount * 120
            dx = -amount * 120 if direction == "left" else (amount * 120 if direction == "right" else 0)
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
    Simulates a keyboard key press or hotkey combination on Windows.

    Args:
        key: Single key ("enter", "tab", "esc") or combo ("ctrl+c", "win+d", "alt+tab", "ctrl+v").
    """
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        
        key_clean = key.lower().replace("super", "win")
        if "+" in key_clean:
            keys = [k.strip() for k in key_clean.split("+")]
            pyautogui.hotkey(*keys)
        else:
            pyautogui.press(key_clean)
        return f"Key combination '{key}' executed, sir."
    except Exception as e:
        return f"Key press failed: {e}"

@function_tool
async def type_user_message_auto(message: str) -> str:
    """
    Types or pastes a message into the currently active window on Windows.

    Args:
        message: The text to type.
    """
    if not message or not message.strip():
        return "No message provided to type."
    try:
        import pyautogui
        import pyperclip
        time.sleep(0.2)
        
        # Fast, unicode-safe typing via Windows clipboard paste
        pyperclip.copy(message)
        pyautogui.hotkey("ctrl", "v")
        
        preview = message[:60] + ("..." if len(message) > 60 else "")
        return f'Typed: "{preview}"'
    except Exception as e:
        return f"Typing failed: {e}"

@function_tool
async def click_on_text(target_text: str) -> str:
    """
    Locates and clicks on visible screen text on Windows using OCR (Tesseract).

    Args:
        target_text: The exact or partial text visible on screen to click.
    """
    try:
        import pyautogui
        import pytesseract

        # Windows Tesseract search locations
        tess_bin = shutil.which("tesseract") or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(tess_bin):
            pytesseract.pytesseract.tesseract_cmd = tess_bin

        screenshot = pyautogui.screenshot()
        data = pytesseract.image_to_data(screenshot, output_type=pytesseract.Output.DICT)

        for i, text in enumerate(data["text"]):
            if target_text.lower() in text.lower() and data["conf"][i] > 40:
                x = data["left"][i] + data["width"][i] // 2
                y = data["top"][i] + data["height"][i] // 2
                pyautogui.click(x, y)
                return f"Clicked on '{target_text}' at screen coordinates ({x}, {y})."

        return f"Could not find visible text '{target_text}' on screen."
    except Exception as e:
        return f"OCR click failed: {e}"

@function_tool
async def click_coordinates(x: int, y: int, clicks: int = 1, button: str = "left") -> str:
    """
    Clicks at specific screen pixel coordinates on Windows.

    Args:
        x: Horizontal screen pixel coordinate (e.g. 500).
        y: Vertical screen pixel coordinate (e.g. 300).
        clicks: Number of clicks (1 for single click, 2 for double click).
        button: Mouse button ("left", "right", "middle").
    """
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        pyautogui.click(x=int(x), y=int(y), clicks=int(clicks), button=button)
        return f"Successfully clicked ({x}, {y}) with {button} button {clicks} time(s)."
    except Exception as e:
        return f"Click coordinates failed: {e}"

@function_tool
async def smart_click_and_type(target_label: str, text_to_type: str, press_enter: bool = True) -> str:
    """
    Finds a UI input field or label on screen, clicks it, and types specified text.

    Args:
        target_label: Text label or placeholder near the input box (e.g. "Username", "Search", "Password").
        text_to_type: Text string to type into the field.
        press_enter: If True, presses Enter after typing (default: True).
    """
    try:
        import pyautogui
        import pyperclip
        pyautogui.FAILSAFE = False

        res = await click_on_text(target_label)
        if "Clicked" not in res:
            logger.info(f"Target text '{target_label}' not found by OCR. Typing directly into focused window.")

        time.sleep(0.15)
        pyperclip.copy(text_to_type)
        pyautogui.hotkey("ctrl", "v")
        if press_enter:
            time.sleep(0.1)
            pyautogui.press("enter")
        return f"Typed '{text_to_type}' into field '{target_label}' (Enter={'yes' if press_enter else 'no'})."
    except Exception as e:
        return f"Smart click and type failed: {e}"

@function_tool
async def fill_form_fields(fields_json: str, submit: bool = True) -> str:
    """
    Fills out a multi-field desktop or web form by auto-clicking labels, typing values, and submitting.

    Args:
        fields_json: JSON string mapping field labels/names to values, e.g.:
                     '{"Name": "Nandi", "Email": "nandu@example.com", "Message": "Hello world"}'
        submit: If True, presses Enter or clicks 'Submit' button on completion (default: True).
    """
    try:
        import json
        import pyautogui
        import pyperclip
        pyautogui.FAILSAFE = False

        data = json.loads(fields_json)
        if not isinstance(data, dict):
            return "fields_json must be a JSON object of field_label -> value pairs."

        filled_count = 0
        for label, val in data.items():
            val_str = str(val)
            ocr_res = await click_on_text(label)
            if "Clicked" in ocr_res:
                pyautogui.moveRel(50, 0)
                pyautogui.click()
            time.sleep(0.15)
            pyautogui.hotkey("ctrl", "a")
            pyperclip.copy(val_str)
            pyautogui.hotkey("ctrl", "v")
            pyautogui.press("tab")
            filled_count += 1

        if submit:
            time.sleep(0.2)
            sub_res = await click_on_text("submit")
            if "Clicked" not in sub_res:
                pyautogui.press("enter")

        return f"Successfully filled {filled_count} form field(s) (Submitted: {submit})."
    except Exception as e:
        return f"Form filling failed: {e}"
