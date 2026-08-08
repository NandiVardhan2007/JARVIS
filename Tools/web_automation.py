"""
AI Web Automation Sub-Agent using Playwright.

Provides tools for VISION to autonomously navigate browsers, manage multiple
tabs, fill forms, download/upload files, monitor pages for changes, and read
web content aloud.

Session model
-------------
A single Chromium browser + context is kept alive across calls (so cookies,
logins, etc. persist between tool calls, exactly like a human's browser
session would). Multiple tabs are tracked by name in `_tabs`, with one
tab marked "active" — tools that don't take an explicit tab_name operate on
the active tab, mirroring how a human says "click X" without specifying
which window they mean.
"""

import asyncio
import hashlib
import logging
import os
import time
from typing import Optional

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = os.path.expanduser("~/Downloads/vision")

# ── Session state ────────────────────────────────────────────────────────────
_browser = None
_context = None
_tabs: dict[str, "object"] = {}       # tab_name -> Page
_active_tab: Optional[str] = None
_next_tab_id = 1

# Auto-release: a visible Chromium instance is a real, ongoing RAM/GPU cost.
# Rather than leaving it running indefinitely after a single task, an idle
# watchdog closes it automatically after a period of no browser tool calls.
BROWSER_IDLE_TIMEOUT_SEC = float(os.getenv("VISION_BROWSER_IDLE_TIMEOUT_SEC", "600"))
_last_activity_ts = 0.0
_idle_watchdog_task = None

# ── Page-change watchers ─────────────────────────────────────────────────────
_watchers: dict[str, dict] = {}       # watch_id -> {url, interval, task, last_hash, changed, last_checked}
_next_watch_id = 1


def _touch_activity():
    """Marks the browser session as recently used, resetting the idle clock."""
    global _last_activity_ts
    _last_activity_ts = time.time()


async def _idle_watchdog():
    """Background loop: closes the browser after BROWSER_IDLE_TIMEOUT_SEC of no activity."""
    while True:
        await asyncio.sleep(30)
        if _browser is None:
            continue
        idle_for = time.time() - _last_activity_ts
        if idle_for > BROWSER_IDLE_TIMEOUT_SEC:
            logger.info(f"Browser idle for {idle_for:.0f}s — auto-closing to free memory.")
            try:
                from agent import send_hud_state
                send_hud_state({
                    "state": "notify",
                    "description": "Browser session closed (idle) to free up memory.",
                })
            except Exception as hud_err:
                logger.debug(f"send_hud_state notify failed in idle watchdog: {hud_err}")
            await close_browser()


async def _ensure_browser():
    """Starts the shared Playwright browser/context if not already running."""
    global _browser, _context, _idle_watchdog_task
    _touch_activity()

    if _browser is not None and _context is not None:
        try:
            # Cheap liveness check
            _ = _browser.is_connected()
            return
        except Exception as check_err:
            logger.debug(f"Playwright browser liveness check failed: {check_err}")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise ImportError("Playwright is not installed. Please run: pip install playwright --break-system-packages && playwright install chromium")

    p = await async_playwright().start()
    _browser = await p.chromium.launch(headless=False)
    _context = await _browser.new_context(
        viewport={'width': 1280, 'height': 800},
        user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        accept_downloads=True,
    )

    if _idle_watchdog_task is None or _idle_watchdog_task.done():
        _idle_watchdog_task = asyncio.create_task(_idle_watchdog())


async def _new_tab(name: Optional[str] = None) -> str:
    """Opens a new tab, registers it under `name` (or an auto-generated one), and returns its name."""
    global _active_tab, _next_tab_id
    await _ensure_browser()
    page = await _context.new_page()
    if not name:
        name = f"tab{_next_tab_id}"
        _next_tab_id += 1
    _tabs[name] = page
    _active_tab = name
    return name


async def _get_page(tab_name: Optional[str] = None):
    """Returns the requested (or active) tab's Page, opening a first tab if none exist yet."""
    global _active_tab
    await _ensure_browser()

    if tab_name:
        page = _tabs.get(tab_name)
        if page is None or page.is_closed():
            raise ValueError(f"No open tab named '{tab_name}'. Use list_browser_tabs to see open tabs.")
        _active_tab = tab_name
        return page

    if _active_tab and _active_tab in _tabs and not _tabs[_active_tab].is_closed():
        return _tabs[_active_tab]

    # No active tab yet — open one
    name = await _new_tab()
    return _tabs[name]


# ── Navigation & tabs ─────────────────────────────────────────────────────────

@function_tool
async def open_webpage(url: str, new_tab: bool = False, tab_name: Optional[str] = None) -> str:
    """
    Opens a URL in the browser.

    Args:
        url: The website URL to navigate to (include https:// if possible).
        new_tab: If True, opens the URL in a brand-new tab instead of reusing
            the active one — use this when the user wants to keep the
            current page open alongside the new one.
        tab_name: Optional name for the tab (auto-generated if omitted).
            Ignored if new_tab is False.
    """
    if not url.startswith("http"):
        url = "https://" + url

    try:
        if new_tab or not _tabs:
            name = await _new_tab(tab_name)
            page = _tabs[name]
        else:
            page = await _get_page(tab_name)
            name = tab_name or _active_tab

        logger.info(f"Navigating tab '{name}' to {url}")
        await page.goto(url, wait_until="networkidle", timeout=15000)
        title = await page.title()
        return f"Opened {url} in tab '{name}'. Page title is '{title}'."
    except Exception as e:
        logger.error(f"Failed to open {url}: {e}")
        return f"Failed to open the website: {e}"


@function_tool
async def list_browser_tabs() -> str:
    """Lists all currently open browser tabs, their titles/URLs, and which one is active."""
    if not _tabs:
        return "No browser tabs are open."
    lines = ["Open tabs:"]
    for name, page in list(_tabs.items()):
        if page.is_closed():
            continue
        marker = " (active)" if name == _active_tab else ""
        try:
            title = await page.title()
        except Exception:
            title = "?"
        lines.append(f"• {name}{marker} — {title} — {page.url}")
    return "\n".join(lines)


@function_tool
async def switch_browser_tab(tab_name: str) -> str:
    """
    Switches the active tab that subsequent browser actions (click, type, scroll, etc.) apply to.

    Args:
        tab_name: Name of the tab to switch to (see list_browser_tabs for names).
    """
    global _active_tab
    page = _tabs.get(tab_name)
    if page is None or page.is_closed():
        return f"No open tab named '{tab_name}'. Use list_browser_tabs to see open tabs."
    _active_tab = tab_name
    await page.bring_to_front()
    return f"Switched to tab '{tab_name}'."


@function_tool
async def close_browser_tab(tab_name: Optional[str] = None) -> str:
    """
    Closes a browser tab.

    Args:
        tab_name: Name of the tab to close. If omitted, closes the active tab.
    """
    global _active_tab
    name = tab_name or _active_tab
    page = _tabs.get(name) if name else None
    if page is None:
        return f"No open tab named '{name}'." if name else "No active tab to close."

    try:
        await page.close()
    except Exception as close_err:
        logger.debug(f"Error closing page in close_browser_tab: {close_err}")
    _tabs.pop(name, None)

    if _active_tab == name:
        _active_tab = next(iter(_tabs), None)

    return f"Closed tab '{name}'." + (f" Active tab is now '{_active_tab}'." if _active_tab else " No tabs remain open.")


# ── Interaction ───────────────────────────────────────────────────────────────

@function_tool
async def click_web_element(text_or_selector: str, tab_name: Optional[str] = None) -> str:
    """
    Clicks a button, link, or element on a web page.

    Args:
        text_or_selector: The text of the button (e.g. 'Login', 'Submit') or css selector.
        tab_name: Optional tab to act on (defaults to the active tab).
    """
    try:
        page = await _get_page(tab_name)

        element = page.get_by_text(text_or_selector).first
        if await element.is_visible():
            await element.click()
            await page.wait_for_load_state("networkidle", timeout=3000)
            return f"Clicked element containing '{text_or_selector}'."

        element = page.locator(text_or_selector).first
        if await element.is_visible():
            await element.click()
            await page.wait_for_load_state("networkidle", timeout=3000)
            return f"Clicked element matching selector '{text_or_selector}'."

        return f"Could not find any clickable element matching '{text_or_selector}' on the page."
    except Exception as e:
        return f"Failed to click element: {e}"


@function_tool
async def type_into_form(field_name: str, value: str, tab_name: Optional[str] = None) -> str:
    """
    Types text into an input field or form on a web page.

    Args:
        field_name: The placeholder text, label, or name of the input field.
        value: The text you want to type into the field.
        tab_name: Optional tab to act on (defaults to the active tab).
    """
    try:
        page = await _get_page(tab_name)

        for locator in (
            page.get_by_placeholder(field_name).first,
            page.get_by_label(field_name).first,
            page.get_by_role("textbox", name=field_name).first,
        ):
            if await locator.is_visible():
                await locator.fill(value)
                return f"Filled field '{field_name}' with '{value}'."

        return f"Could not find an input field named '{field_name}'."
    except Exception as e:
        return f"Failed to type into form: {e}"


@function_tool
async def scroll_webpage(direction: str, tab_name: Optional[str] = None) -> str:
    """
    Scrolls a web page.

    Args:
        direction: Direction to scroll: 'down', 'up', 'top', 'bottom'.
        tab_name: Optional tab to act on (defaults to the active tab).
    """
    try:
        page = await _get_page(tab_name)
        d = direction.lower()
        if d == 'down':
            await page.mouse.wheel(0, 800)
        elif d == 'up':
            await page.mouse.wheel(0, -800)
        elif d == 'bottom':
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        elif d == 'top':
            await page.evaluate("window.scrollTo(0, 0)")
        return f"Scrolled page {direction}."
    except Exception as e:
        return f"Failed to scroll page: {e}"


# ── Downloads & uploads ───────────────────────────────────────────────────────

@function_tool
async def download_file_from_page(text_or_selector: str, tab_name: Optional[str] = None) -> str:
    """
    Clicks a download link/button on the page and saves the resulting file locally.

    Args:
        text_or_selector: Text or CSS selector of the download link/button to click.
        tab_name: Optional tab to act on (defaults to the active tab).
    """
    try:
        page = await _get_page(tab_name)
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

        element = page.get_by_text(text_or_selector).first
        if not await element.is_visible():
            element = page.locator(text_or_selector).first
            if not await element.is_visible():
                return f"Could not find a download element matching '{text_or_selector}'."

        async with page.expect_download(timeout=20000) as download_info:
            await element.click()
        download = await download_info.value

        suggested = download.suggested_filename or f"download_{int(time.time())}"
        dest = os.path.join(DOWNLOAD_DIR, suggested)
        await download.save_as(dest)
        return f"Downloaded '{suggested}' to {dest}."
    except Exception as e:
        return f"Download failed: {e}"


@function_tool
async def upload_file_to_page(file_path: str, field_name: str = "", tab_name: Optional[str] = None) -> str:
    """
    Uploads a local file into a file-input field on the current page.

    Args:
        file_path: Absolute path to the local file to upload.
        field_name: Label/placeholder of the file input, if the page has more
            than one. Leave empty to use the first file input found.
        tab_name: Optional tab to act on (defaults to the active tab).
    """
    if not os.path.isfile(file_path):
        return f"File not found: {file_path}"

    try:
        page = await _get_page(tab_name)

        locator = None
        if field_name:
            for candidate in (page.get_by_label(field_name).first, page.get_by_placeholder(field_name).first):
                try:
                    if await candidate.count() > 0:
                        locator = candidate
                        break
                except Exception:
                    continue
        if locator is None:
            locator = page.locator("input[type='file']").first

        await locator.set_input_files(file_path)
        return f"Uploaded '{os.path.basename(file_path)}'."
    except Exception as e:
        return f"Upload failed: {e}"


# ── Reading content aloud ─────────────────────────────────────────────────────

@function_tool
async def read_page_aloud(max_chars: int = 1500, tab_name: Optional[str] = None) -> str:
    """
    Extracts the visible text of the current page so it can be read aloud.
    The returned text should be spoken back to the user close to verbatim,
    not summarized, since the user explicitly asked to have the page read.

    Args:
        max_chars: Maximum characters of page text to read (default 1500, to
            keep speech from running on indefinitely).
        tab_name: Optional tab to act on (defaults to the active tab).
    """
    try:
        page = await _get_page(tab_name)
        text = await page.inner_text("body")
        text = " ".join(text.split())  # collapse whitespace
        if not text:
            return "This page doesn't appear to have any readable text content."
        truncated = text[:max_chars]
        suffix = "... (page continues; ask me to keep reading if you'd like more)" if len(text) > max_chars else ""
        return truncated + suffix
    except Exception as e:
        return f"Couldn't read the page: {e}"


# ── Page-change monitoring ────────────────────────────────────────────────────

async def _watch_loop(watch_id: str, url: str, interval: float):
    """Background task: polls a URL's rendered text and flags when it changes."""
    from playwright.async_api import async_playwright

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            while watch_id in _watchers:
                try:
                    await page.goto(url, wait_until="networkidle", timeout=20000)
                    text = await page.inner_text("body")
                    digest = hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()

                    entry = _watchers.get(watch_id)
                    if entry is None:
                        break
                    entry["last_checked"] = time.time()
                    if entry["last_hash"] is not None and digest != entry["last_hash"]:
                        entry["changed"] = True
                        logger.info(f"Watched page changed: {url}")
                        try:
                            from agent import send_hud_state
                            send_hud_state({
                                "state": "notify",
                                "description": f"Page changed: {url}",
                            })
                        except Exception as hud_err:
                            logger.debug(f"HUD notification for page change failed: {hud_err}")
                    entry["last_hash"] = digest
                except Exception as e:
                    logger.warning(f"Watch tick failed for {url}: {e}")

                await asyncio.sleep(interval)
            await browser.close()
    except Exception as e:
        logger.error(f"Watcher for {url} crashed: {e}")


@function_tool
async def start_watching_page(url: str, interval_seconds: int = 300) -> str:
    """
    Starts monitoring a webpage for content changes in the background
    (e.g. price drops, restock notices, new posts). Runs its own headless
    browser tab independent of your active browsing session.

    Args:
        url: The URL to monitor.
        interval_seconds: How often to re-check, in seconds (default 300 = 5 min; minimum 30).
    """
    global _next_watch_id
    if not url.startswith("http"):
        url = "https://" + url
    interval = max(30, interval_seconds)

    watch_id = f"watch{_next_watch_id}"
    _next_watch_id += 1
    _watchers[watch_id] = {
        "url": url, "interval": interval, "last_hash": None,
        "changed": False, "last_checked": None,
    }
    task = asyncio.create_task(_watch_loop(watch_id, url, interval))
    _watchers[watch_id]["task"] = task

    return f"Now watching {url} for changes every {interval}s (watch id: {watch_id})."


@function_tool
async def list_watched_pages() -> str:
    """Lists all pages currently being monitored for changes, and whether each has changed since it was last checked."""
    if not _watchers:
        return "No pages are currently being watched."
    lines = ["Watched pages:"]
    for wid, w in _watchers.items():
        status = "CHANGED" if w["changed"] else "no change yet"
        lines.append(f"• {wid}: {w['url']} (every {w['interval']}s) — {status}")
    return "\n".join(lines)


@function_tool
async def check_page_changes(watch_id: str) -> str:
    """
    Checks whether a watched page has changed since monitoring started, and
    clears the changed flag after reporting it.

    Args:
        watch_id: The watch id returned by start_watching_page (see list_watched_pages).
    """
    w = _watchers.get(watch_id)
    if w is None:
        return f"No watch with id '{watch_id}'. Use list_watched_pages to see active watches."
    if w["changed"]:
        w["changed"] = False
        return f"Yes — {w['url']} has changed since it was last checked."
    return f"No changes detected yet for {w['url']}."


@function_tool
async def stop_watching_page(watch_id: str) -> str:
    """
    Stops monitoring a previously-watched page.

    Args:
        watch_id: The watch id to stop (see list_watched_pages).
    """
    w = _watchers.pop(watch_id, None)
    if w is None:
        return f"No watch with id '{watch_id}'."
    task = w.get("task")
    if task:
        task.cancel()
    return f"Stopped watching {w['url']}."


# ── Session teardown ──────────────────────────────────────────────────────────

@function_tool
async def close_browser() -> str:
    """Closes the entire AI web browsing session (all tabs)."""
    global _browser, _context, _tabs, _active_tab
    try:
        if _browser:
            await _browser.close()
        _browser = None
        _context = None
        _tabs = {}
        _active_tab = None
        return "Browser closed."
    except Exception as e:
        return f"Failed to close browser: {e}"
