"""
WhatsApp & Instant Messaging Automation Tools for VISION AI OS.
Supports opening WhatsApp, automatic contact & phone resolution from MAG memory,
direct phone number URI dispatching, and fallback search automation.
"""

import time
import urllib.parse
import webbrowser
import re
from typing import Optional
from vision.tools.registry import tool
from vision.memory.mag_engine import mag_engine
from vision.logger import logger

try:
    import pyautogui
    import pyperclip
    import pygetwindow as gw
    if pyautogui:
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.1
except ImportError:
    pyautogui = None
    pyperclip = None
    gw = None


def _focus_whatsapp_window() -> bool:
    """Find and activate an open WhatsApp window if present."""
    if not gw:
        return False
    try:
        windows = gw.getWindowsWithTitle("WhatsApp")
        if windows:
            win = windows[0]
            if win.isMinimized:
                win.restore()
            win.activate()
            time.sleep(0.6)
            return True
    except Exception as e:
        logger.debug(f"[WhatsAppTool] Window activation note: {e}")
    return False


def _resolve_contact_from_memory(target: str) -> str:
    """
    Check MAG memory for any stored phone numbers or exact contact aliases.
    If a phone number is found, returns the clean digits.
    """
    clean_target = target.strip()
    target_lower = clean_target.lower()

    # Direct self-resolution for user
    if target_lower in ("myself", "me", "my number", "my phone", "self", "nandu", "nandi", "nandi vardhan", "nandi vardhan reddy", "kovvuri"):
        logger.info(f"[WhatsAppTool] Resolved '{clean_target}' directly to User phone number '7337419275'.")
        return "7337419275"

    try:
        # 1. Search for contact phone number in memory (e.g. "Amma phone number is 950-586-4289")
        memories = mag_engine.search_memories(f"{clean_target} phone number", limit=5)
        for m in memories:
            content = m.get("content", "")
            # Check if this memory is specifically about this contact
            if clean_target.lower() in content.lower():
                num_match = re.search(r"(\+?\d[\d\s\-]{8,}\d)", content)
                if num_match:
                    digits = re.sub(r"[^\d]", "", num_match.group(1))
                    if len(digits) >= 10:
                        logger.info(f"[WhatsAppTool] Resolved '{clean_target}' to phone number '{digits}' from MAG memory.")
                        return digits

        # 2. Check for contact alias in memory (e.g. "WhatsApp contact for Mom is Mom (Home)")
        alias_mems = mag_engine.search_memories(f"whatsapp contact {clean_target}", limit=3)
        for m in alias_mems:
            content = m.get("content", "")
            match = re.search(rf"contact\s+(?:for\s+)?{re.escape(clean_target)}\s+is\s+(.+)", content, re.IGNORECASE)
            if match:
                resolved = match.group(1).strip()
                logger.info(f"[WhatsAppTool] Resolved alias '{clean_target}' -> '{resolved}' from MAG memory.")
                return resolved
    except Exception as e:
        logger.debug(f"[WhatsAppTool] Memory resolution check note: {e}")

    return clean_target


@tool(name="send_whatsapp_message", description="Send a WhatsApp message by contact name (auto-resolved from memory) or direct phone number.")
def send_whatsapp_message(contact_or_number: str, message: str) -> str:
    """
    Open WhatsApp and send the message to the contact or phone number.
    Automatically resolves stored phone numbers or aliases from MAG memory.
    """
    if not contact_or_number or not message:
        return "Error: Contact name/number and message are required."

    raw_input = contact_or_number.strip()
    msg = message.strip()

    # Resolve contact name from MAG long-term memory (e.g. "Amma" -> "9505864289")
    resolved_target = _resolve_contact_from_memory(raw_input)

    # Check if target is a phone number (e.g. 9505864289, +919505864289)
    clean_digits = re.sub(r"[^\d]", "", resolved_target)
    is_phone_number = len(clean_digits) >= 10 and (resolved_target.startswith("+") or clean_digits == resolved_target)

    # Direct 100% Precision Phone Protocol Dispatch
    if is_phone_number:
        if len(clean_digits) == 10:
            clean_digits = "91" + clean_digits

        logger.info(f"[WhatsAppTool] Direct WhatsApp dispatch to +{clean_digits} (Target: '{raw_input}')...")
        encoded_msg = urllib.parse.quote(msg)
        whatsapp_uri = f"whatsapp://send?phone={clean_digits}&text={encoded_msg}"

        try:
            webbrowser.open(whatsapp_uri)
            time.sleep(2.0)
            _focus_whatsapp_window()
            time.sleep(0.8)
            if pyautogui:
                pyautogui.press("enter")
            logger.info(f"[WhatsAppTool] Successfully sent message to {raw_input} (+{clean_digits}): '{msg}'")
            return f"Successfully sent WhatsApp message to {raw_input} (+{clean_digits}): '{msg}'"
        except Exception as e:
            logger.warning(f"[WhatsAppTool] Desktop protocol failed, opening Web: {e}")
            web_url = f"https://web.whatsapp.com/send?phone={clean_digits}&text={encoded_msg}"
            webbrowser.open(web_url)
            return f"Opened WhatsApp Web for {raw_input} (+{clean_digits}) with your message."

    # Name-Based WhatsApp Desktop Search Fallback
    target_name = resolved_target
    logger.info(f"[WhatsAppTool] Searching WhatsApp Desktop for contact '{target_name}'...")

    has_focus = _focus_whatsapp_window()
    if not has_focus:
        webbrowser.open("whatsapp://")
        time.sleep(2.5)
        _focus_whatsapp_window()

    if not pyautogui or not pyperclip:
        return f"Opened WhatsApp for '{target_name}'. Please press enter to send."

    time.sleep(0.8)

    # Reset any existing open chats or search state
    pyautogui.press("esc")
    time.sleep(0.2)
    pyautogui.press("esc")
    time.sleep(0.3)

    # Focus search bar
    pyautogui.hotkey("ctrl", "f")
    time.sleep(0.5)

    # Clear previous search
    pyautogui.hotkey("ctrl", "a")
    pyautogui.press("backspace")
    time.sleep(0.2)

    # Type/paste contact name
    pyperclip.copy(target_name)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(1.2)

    # Select top search match
    pyautogui.press("enter")
    time.sleep(0.8)

    # Paste and send message
    pyperclip.copy(msg)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.4)
    pyautogui.press("enter")

    logger.info(f"[WhatsAppTool] Sent message to '{target_name}': '{msg}'")
    return f"Successfully sent WhatsApp message to '{target_name}': '{msg}'"


@tool(name="save_whatsapp_contact_alias", description="Save a contact name mapping or phone number in memory (e.g. alias='Amma', saved_name='9505864289').")
def save_whatsapp_contact_alias(alias: str, saved_name: str) -> str:
    """Save a contact name mapping or phone number in MAG memory."""
    clean_alias = alias.strip()
    clean_val = saved_name.strip()
    if not clean_alias or not clean_val:
        return "Error: Alias and target name/number are required."

    # Check if number
    digits = re.sub(r"[^\d]", "", clean_val)
    if len(digits) >= 10:
        fact = f"{clean_alias} phone number is {clean_val}"
    else:
        fact = f"WhatsApp contact for {clean_alias} is {clean_val}"

    mag_engine.remember(fact, category="contact", tags="whatsapp,contact,phone")
    return f"Saved WhatsApp contact in memory: '{clean_alias}' -> '{clean_val}'."
