"""
WhatsApp Web Remote Reader and Responder using Playwright.
Uses a visible browser to scan active chats, read recent messages,
and reply under local user session command.
"""

import logging
import asyncio
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

# We reuse the same page session from web_automation if active
from .web_automation import _get_page

@function_tool
async def open_whatsapp_web() -> str:
    """
    Launches WhatsApp Web in your visible chrome window.
    Users can scan the QR code (first time) or immediately see chats if already authenticated.
    """
    try:
        page = await _get_page()
        logger.info("Opening WhatsApp Web...")
        await page.goto("https://web.whatsapp.com", wait_until="load", timeout=30000)
        return "Opened WhatsApp Web. If it is your first time, please scan the QR code shown on screen."
    except Exception as e:
        logger.error(f"WhatsApp Web open failed: {e}")
        return f"Failed to open WhatsApp Web: {e}"

@function_tool
async def read_unreads_on_whatsapp() -> str:
    """
    Scans the currently loaded WhatsApp Web interface for unread chats and recent texts.
    Returns a text overview of who message you.
    """
    try:
        page = await _get_page()
        if "web.whatsapp.com" not in page.url:
            return "WhatsApp Web is not currently open. Run 'open_whatsapp_web' first."

        # Wait to ensure chat panel loads
        await page.wait_for_selector("span[aria-label*='unread']", timeout=6000)

        # Grab list items of unread chats
        unreads = await page.locator("span[aria-label*='unread']").all()
        if not unreads:
            return "No unread chat badges found on screen, sir."

        output = [f"Found {len(unreads)} unread chat thread(s):"]

        # Loop through container tags to find sender name and text excerpt
        for idx in range(min(5, len(unreads))):
            try:
                badge = unreads[idx]
                # Find container text
                parent = badge.locator("xpath=../../../../..")
                text_content = await parent.inner_text()
                lines = [l.strip() for l in text_content.split("\n") if l.strip()]
                if len(lines) >= 2:
                    sender = lines[0]
                    # Guess some typical spacing layout
                    msg_preview = lines[-2] if len(lines) > 2 else lines[-1]
                    output.append(f"- From '{sender}': \"{msg_preview}\"")
            except Exception as parse_err:
                logger.debug(f"WhatsApp Web unread thread element parsing error: {parse_err}")

        return "\n".join(output)
    except Exception as e:
        return f"Could not count unreads: {e}. Check if you need to authenticate."

@function_tool
async def send_whatsapp_reply(chat_name: str, message: str) -> str:
    """
    Clicks on a chat contact by name on WhatsApp Web, types a reply, and sends it.

    Args:
        chat_name: Name of the contact or group to search (e.g. 'nandu', 'Family').
        message: Text reply string to send.
    """
    try:
        page = await _get_page()
        if "web.whatsapp.com" not in page.url:
            return "WhatsApp Web is not open page. Run 'open_whatsapp_web' first."

        # 1. Search contact. Locate Search bar box:
        search_box = page.locator("div[contenteditable='true']").first
        await search_box.click()
        await search_box.fill(chat_name)
        await asyncio.sleep(1)
        await page.keyboard.press("Enter")
        await asyncio.sleep(1)

        # 2. Focus Message input box
        # WhatsApp Web message input is targetable by role or class:
        msg_box = page.locator("div[title='Type a message']").first
        if not await msg_box.is_visible():
            msg_box = page.locator("div[contenteditable='true']").nth(1)

        if await msg_box.is_visible():
            await msg_box.click()
            await msg_box.fill(message)
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")
            return f"Successfully sent WhatsApp message to '{chat_name}': \"{message}\""

        return f"Could not focus the message input field for '{chat_name}'."
    except Exception as e:
        return f"Failed to send reply: {e}"
