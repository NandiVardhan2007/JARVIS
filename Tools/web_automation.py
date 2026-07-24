"""
AI Web Automation Sub-Agent using Playwright.
Provides tools for JARVIS to autonomously navigate browsers, fill forms,
and read web content.
"""

import os
import asyncio
import logging
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

# Global browser instance
_browser = None
_page = None

async def _get_page():
    """Starts or retrieves the global Playwright browser page."""
    global _browser, _page
    if _page is not None and not _page.is_closed():
        return _page

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise ImportError("Playwright is not installed. Please run: pip install playwright && playwright install chromium")

    # We don't want to block the thread, so run this in an async-safe way
    p = await async_playwright().start()

    # Launch visible browser for the user to see the actions!
    _browser = await p.chromium.launch(headless=False)

    # Create context with saved session if desired
    context = await _browser.new_context(
        viewport={'width': 1280, 'height': 800},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'
    )

    _page = await context.new_page()
    return _page

@function_tool
async def open_webpage(url: str) -> str:
    """
    Opens a URL in a new browser window.

    Args:
        url: The website URL to navigate to (include https:// if possible).
    """
    if not url.startswith("http"):
        url = "https://" + url

    try:
        page = await _get_page()
        logger.info(f"Navigating to {url}")
        await page.goto(url, wait_until="networkidle", timeout=15000)
        title = await page.title()
        return f"Successfully opened {url}. Page title is '{title}'."
    except Exception as e:
        logger.error(f"Failed to open {url}: {e}")
        return f"Failed to open the website: {e}"

@function_tool
async def click_web_element(text_or_selector: str) -> str:
    """
    Clicks a button, link, or element on the currently active web page.

    Args:
        text_or_selector: The text of the button (e.g. 'Login', 'Submit') or css selector.
    """
    try:
        page = await _get_page()

        # Try finding by text first
        element = page.get_by_text(text_or_selector).first
        if await element.is_visible():
            await element.click()
            await page.wait_for_load_state("networkidle", timeout=3000)
            return f"Clicked element containing '{text_or_selector}'."

        # Fallback to selector
        element = page.locator(text_or_selector).first
        if await element.is_visible():
            await element.click()
            await page.wait_for_load_state("networkidle", timeout=3000)
            return f"Clicked element matching selector '{text_or_selector}'."

        return f"Could not find any clickable element matching '{text_or_selector}' on the page."
    except Exception as e:
        return f"Failed to click element: {e}"

@function_tool
async def type_into_form(field_name: str, value: str) -> str:
    """
    Types text into an input field or form on the currently active web page.

    Args:
        field_name: The placeholder text, label, or name of the input field.
        value: The text you want to type into the field.
    """
    try:
        page = await _get_page()

        # Try placeholder
        locator = page.get_by_placeholder(field_name).first
        if await locator.is_visible():
            await locator.fill(value)
            return f"Filled field '{field_name}' with '{value}'."

        # Try label
        locator = page.get_by_label(field_name).first
        if await locator.is_visible():
            await locator.fill(value)
            return f"Filled field '{field_name}' with '{value}'."

        # Generic role input
        locator = page.get_by_role("textbox", name=field_name).first
        if await locator.is_visible():
            await locator.fill(value)
            return f"Filled field '{field_name}' with '{value}'."

        return f"Could not find an input field named '{field_name}'."
    except Exception as e:
        return f"Failed to type into form: {e}"

@function_tool
async def scroll_webpage(direction: str) -> str:
    """
    Scrolls the active web page.

    Args:
        direction: Direction to scroll: 'down', 'up', 'top', 'bottom'.
    """
    try:
        page = await _get_page()
        if direction.lower() == 'down':
            await page.mouse.wheel(0, 800)
        elif direction.lower() == 'up':
            await page.mouse.wheel(0, -800)
        elif direction.lower() == 'bottom':
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        elif direction.lower() == 'top':
            await page.evaluate("window.scrollTo(0, 0)")
        return f"Scrolled page {direction}."
    except Exception as e:
        return f"Failed to scroll page: {e}"

@function_tool
async def close_browser() -> str:
    """Closes the AI web browsing session."""
    global _browser, _page
    try:
        if _browser:
            await _browser.close()
            _browser = None
            _page = None
            return "Browser closed."
        return "Browser is already closed."
    except Exception as e:
        return f"Failed to close browser: {e}"
