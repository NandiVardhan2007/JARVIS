"""WhatsApp message and media sender via WAHA (WhatsApp HTTP API)."""

import logging
import os
import re
import requests
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

WAHA_URL = os.getenv("WAHA_URL", "http://localhost:3000")
WHATSAPP_API_KEY = os.getenv("WHATSAPP_API_KEY", "")
USE_WAHA = os.getenv("USE_WAHA", "true").lower() == "true"

# ── Contact resolution helper ────────────────────────────────────────────────

async def _resolve_contact(contact_str: str) -> str:
    """
    Resolve a contact identifier to a phone number.
    Handles translation of non-ASCII names and Google Contacts lookup.
    Returns the numeric phone string, or raises ValueError on failure.
    """
    # Translate non-ASCII names (e.g., Hindi) to English for contact lookup
    try:
        from Tools.translation import translate_to_english, is_ascii
        if not is_ascii(contact_str):
            translated = await translate_to_english(contact_str)
            logger.info(f"Translated contact name: '{contact_str}' → '{translated}'")
            contact_str = translated
    except ImportError:
        logger.debug("Translation module not available, using original contact string.")

    # If the string has letters, look up in Google Contacts
    if any(c.isalpha() for c in contact_str):
        logger.info(f"'{contact_str}' looks like a name. Looking up in Google Contacts...")
        from Tools.google_contacts import search_google_contact
        lookup_result = await search_google_contact(contact_str)

        match = re.search(r'\+?\d{8,}', lookup_result)
        if match:
            contact_str = match.group(0)
            logger.info(f"Resolved name to number: {contact_str}")
        else:
            raise ValueError(
                f"Could not resolve name to a phone number. "
                f"Contact lookup said: {lookup_result}"
            )

    # Remove all non-numeric characters
    numeric_only = re.sub(r'\D', '', contact_str)
    if not numeric_only:
        raise ValueError("Could not extract a valid phone number from the contact provided.")

    return numeric_only


# ── WhatsApp text message ─────────────────────────────────────────────────────

@function_tool
async def send_whatsapp_message(contact_number: str, message: str) -> str:
    """
    Sends a WhatsApp message via WAHA (WhatsApp HTTP API).
    The API must be running in Docker or Render.

    Args:
        contact_number: The phone number of the contact (with country code, e.g., +1234567890).
                        CRITICAL: If the user provides a name, PASS THE NAME EXACTLY AS A STRING (e.g., "Amma"). 
                        DO NOT hallucinate a fake phone number like +1234567890. The system will auto-resolve the name to a number.
        message: Message content to send.
    """
    logger.info(f"Sending WhatsApp via WAHA to: {contact_number}")

    contact_str = str(contact_number)

    # Resolve contact name → phone number (with translation support)
    try:
        numeric_only = await _resolve_contact(contact_str)
    except ValueError as e:
        return f"Error: {e}"

    chat_id = f"{numeric_only}@c.us"

    if USE_WAHA:
        try:
            url = f"{WAHA_URL.rstrip('/')}/api/sendText"
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            
            if WHATSAPP_API_KEY:
                headers["X-Api-Key"] = WHATSAPP_API_KEY
                
            data = {
                "chatId": chat_id,
                "text": message,
                "session": "default"
            }

            response = requests.post(url, json=data, headers=headers, timeout=15)
            response.raise_for_status()
            
            return f"Message successfully sent to {contact_number} via WAHA API."
            
        except requests.exceptions.ConnectionError:
            logger.warning("WAHA connection failed. Falling back to manual UI automation...")
    else:
        logger.info("USE_WAHA is false. Using manual UI automation directly.")

    # Manual UI automation fallback (or if USE_WAHA is false)
    try:
        import pyautogui
        import time
        
        # 1. Open Windows Search and open WhatsApp
        pyautogui.press("win")
        time.sleep(1)
        pyautogui.write("WhatsApp", interval=0.05)
        time.sleep(1)
        pyautogui.press("enter")
        
        # Wait for WhatsApp to open
        time.sleep(5)
        
        # 2. Search for the contact (Ctrl+F focuses search in WhatsApp Desktop)
        pyautogui.hotkey("ctrl", "f")
        time.sleep(1)
        # Type the contact name or number
        pyautogui.write(contact_str, interval=0.05)
        time.sleep(2)
        
        # Press enter to select the contact and open chat
        pyautogui.press("enter")
        time.sleep(1)
        
        # 3. Type the message and send
        pyautogui.write(message, interval=0.04)
        time.sleep(0.5)
        pyautogui.press("enter")
        
        return (
            "Could not connect to the WAHA API. "
            f"I have manually opened WhatsApp on your desktop, searched for {contact_number}, "
            "and sent the message for you."
        )
    except Exception as e:
        return f"WhatsApp send failed: {e}"


# ── WhatsApp media / file sending ─────────────────────────────────────────────

@function_tool
async def send_whatsapp_media(contact_name: str) -> str:
    """
    Send the currently selected/copied file or image to a WhatsApp contact.
    
    Before calling this, the user should have the file selected or copied
    in File Explorer (Ctrl+C). This tool opens WhatsApp Desktop, finds the
    contact, and pastes the file to send it.

    Args:
        contact_name: The name or phone number of the WhatsApp contact.
                      CRITICAL: If the user provides a name, PASS THE NAME EXACTLY AS A STRING.
                      DO NOT hallucinate a fake phone number.
    """
    import pyautogui
    import time

    logger.info(f"Sending WhatsApp media to: {contact_name}")

    contact_str = str(contact_name)

    # Translate non-ASCII names if needed
    try:
        from Tools.translation import translate_to_english, is_ascii
        if not is_ascii(contact_str):
            translated = await translate_to_english(contact_str)
            logger.info(f"Translated contact name: '{contact_str}' → '{translated}'")
            contact_str = translated
    except ImportError:
        pass



    try:
        # Step 1: Copy currently selected file (user should have it selected)
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.5)

        # Step 2: Open WhatsApp via Start Menu
        pyautogui.press("win")
        time.sleep(1)
        pyautogui.write("WhatsApp", interval=0.05)
        time.sleep(1)
        pyautogui.press("enter")
        time.sleep(5)  # Wait for WhatsApp to open

        # Step 3: Search for the contact
        pyautogui.hotkey("ctrl", "f")
        time.sleep(1)
        pyautogui.write(contact_str, interval=0.05)
        time.sleep(2)
        pyautogui.press("enter")
        time.sleep(1)

        # Step 4: Paste the copied file/image
        pyautogui.hotkey("ctrl", "v")
        time.sleep(2)  # Wait for media preview to load

        # Step 5: Send
        pyautogui.press("enter")
        time.sleep(1)

        return (
            f"Media sent to {contact_name} on WhatsApp. "
            "I copied the selected file, opened WhatsApp, found the contact, "
            "and pasted the media."
        )

    except Exception as e:
        logger.exception("WhatsApp media send failed")
        return f"WhatsApp media send failed: {e}"


