"""
Playwright-based Interactive Web Browser Control for VISION AI OS.
Provides autonomous browser automation (navigation, element clicking, form filling,
text extraction, DOM element inspection, and screenshot capture) in a visible browser window.
"""

import os
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
from vision.tools.registry import tool
from vision.logger import logger

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

try:
    from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page
except ImportError:
    async_playwright = None
    Playwright = None
    Browser = None
    BrowserContext = None
    Page = None


class BrowserController:
    """Singleton controller managing the live Playwright browser session."""
    _instance: Optional["BrowserController"] = None

    def __init__(self):
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._lock = asyncio.Lock()
        self._screenshots_dir = DATA_DIR / "screenshots"
        self._screenshots_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_instance(cls) -> "BrowserController":
        if cls._instance is None:
            cls._instance = BrowserController()
        return cls._instance

    async def ensure_page(self, headless: bool = False) -> Page:
        """Ensure an active Playwright browser page is running and return it."""
        if async_playwright is None:
            raise RuntimeError("Playwright is not installed. Please install with 'pip install playwright' and 'playwright install chromium'.")

        async with self._lock:
            # Check if page is alive and not closed
            if self._page is not None and not self._page.is_closed() and self._browser is not None and self._browser.is_connected():
                return self._page

            logger.info(f"[BrowserController] Launching visible Chromium browser (headless={headless})...")
            if self._pw is None:
                self._pw = await async_playwright().start()

            self._browser = await self._pw.chromium.launch(
                headless=headless,
                args=[
                    "--start-maximized",
                    "--disable-blink-features=AutomationControlled",
                    "--no-default-browser-check"
                ]
            )

            self._context = await self._browser.new_context(
                viewport=None,  # Match window size
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )

            self._page = await self._context.new_page()
            self._page.set_default_timeout(15000)
            return self._page

    async def get_current_page(self) -> Optional[Page]:
        if self._page is not None and not self._page.is_closed():
            return self._page
        return None

    async def close(self) -> str:
        """Close active browser session and cleanup resources."""
        async with self._lock:
            try:
                if self._context:
                    await self._context.close()
                if self._browser:
                    await self._browser.close()
                if self._pw:
                    await self._pw.stop()
            except Exception as e:
                logger.warning(f"[BrowserController] Cleanup note: {e}")
            finally:
                self._page = None
                self._context = None
                self._browser = None
                self._pw = None
            logger.info("[BrowserController] Browser session closed.")
            return "Browser closed successfully."


controller = BrowserController.get_instance()


@tool(name="browser_open", description="Launch a visible Chromium web browser window and open the specified URL (e.g. Google, YouTube, GitHub, portals).")
async def browser_open(url: str = "https://www.google.com") -> str:
    """Launch visible browser window and navigate to a URL."""
    try:
        if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("about:"):
            url = "https://" + url

        page = await controller.ensure_page(headless=False)
        logger.info(f"[BrowserControl] Navigating to '{url}'...")
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        title = await page.title()
        return f"Browser opened successfully to '{url}'. Page Title: '{title}'."
    except Exception as e:
        logger.error(f"[BrowserControl] browser_open failed: {e}")
        return f"Error opening browser at '{url}': {e}"


@tool(name="browser_navigate", description="Navigate the current active browser page to a new web URL.")
async def browser_navigate(url: str) -> str:
    """Navigate current browser tab to URL."""
    try:
        if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("about:"):
            url = "https://" + url

        page = await controller.ensure_page(headless=False)
        logger.info(f"[BrowserControl] Navigating active tab to '{url}'...")
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        title = await page.title()
        return f"Navigated to '{url}'. Page Title: '{title}'."
    except Exception as e:
        logger.error(f"[BrowserControl] browser_navigate failed: {e}")
        return f"Error navigating to '{url}': {e}"


@tool(name="browser_click", description="Click on an element in the active web browser page using a CSS selector, button/link text (e.g. text='Sign in'), or role.")
async def browser_click(selector: str) -> str:
    """Click on a webpage element matching the selector or text."""
    try:
        page = await controller.get_current_page()
        if not page:
            return "Error: No active browser window is open. Use 'browser_open' first."

        logger.info(f"[BrowserControl] Clicking element: '{selector}'")
        
        # Try direct selector / text matching
        loc = page.locator(selector).first
        await loc.wait_for(state="visible", timeout=8000)
        await loc.click()
        await page.wait_for_timeout(1000)  # Brief settle time
        title = await page.title()
        return f"Successfully clicked on '{selector}'. Current Page Title: '{title}', URL: {page.url}"
    except Exception as e:
        logger.error(f"[BrowserControl] browser_click failed: {e}")
        return f"Error clicking element '{selector}': {e}. Try inspecting interactive elements using 'browser_get_interactive_elements'."


@tool(name="browser_type", description="Type text into an input field, search box, or textarea on the active web page.")
async def browser_type(selector: str, text: str, press_enter: bool = False, clear_first: bool = True) -> str:
    """Fill or type text into a designated element."""
    try:
        page = await controller.get_current_page()
        if not page:
            return "Error: No active browser window is open. Use 'browser_open' first."

        logger.info(f"[BrowserControl] Typing into '{selector}': '{text}' (press_enter={press_enter})")
        loc = page.locator(selector).first
        await loc.wait_for(state="visible", timeout=8000)
        
        if clear_first:
            await loc.fill("")
            await loc.fill(text)
        else:
            await loc.type(text, delay=50)

        if press_enter:
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(1500)

        return f"Successfully typed '{text}' into '{selector}'." + (" (Pressed Enter)" if press_enter else "")
    except Exception as e:
        logger.error(f"[BrowserControl] browser_type failed: {e}")
        return f"Error typing into '{selector}': {e}"


@tool(name="browser_press_key", description="Press a keyboard key (e.g. Enter, Tab, Escape, ArrowDown, ArrowUp, Space, Backspace) on the active page.")
async def browser_press_key(key: str) -> str:
    """Send keypress to active browser window."""
    try:
        page = await controller.get_current_page()
        if not page:
            return "Error: No active browser window is open."

        logger.info(f"[BrowserControl] Pressing key '{key}'")
        await page.keyboard.press(key)
        await page.wait_for_timeout(500)
        return f"Pressed key '{key}' in browser."
    except Exception as e:
        return f"Error pressing key '{key}': {e}"


@tool(name="browser_scroll", description="Scroll the active browser page 'up' or 'down' by a specified pixel amount, or 'top' / 'bottom'.")
async def browser_scroll(direction: str = "down", amount: int = 500) -> str:
    """Scroll webpage up/down or to bounds."""
    try:
        page = await controller.get_current_page()
        if not page:
            return "Error: No active browser window is open."

        dir_clean = direction.strip().lower()
        if dir_clean == "bottom":
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            return "Scrolled to the bottom of the page."
        elif dir_clean == "top":
            await page.evaluate("window.scrollTo(0, 0)")
            return "Scrolled to the top of the page."
        elif dir_clean == "up":
            await page.evaluate(f"window.scrollBy(0, -{amount})")
            return f"Scrolled up by {amount}px."
        else:
            await page.evaluate(f"window.scrollBy(0, {amount})")
            return f"Scrolled down by {amount}px."
    except Exception as e:
        return f"Error scrolling page: {e}"


@tool(name="browser_get_page_content", description="Extract and read the visible text content from the current active web page.")
async def browser_get_page_content(max_chars: int = 4000) -> str:
    """Get clean body text from active webpage."""
    try:
        page = await controller.get_current_page()
        if not page:
            return "Error: No active browser window is open."

        title = await page.title()
        url = page.url
        # Extract readable inner text
        text = await page.evaluate("""() => {
            const clone = document.body.cloneNode(true);
            const removeTags = ['script', 'style', 'noscript', 'svg'];
            removeTags.forEach(tag => {
                const elements = clone.querySelectorAll(tag);
                elements.forEach(el => el.remove());
            });
            return clone.innerText || "";
        }""")

        cleaned = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
        truncated = cleaned[:max_chars]
        if len(cleaned) > max_chars:
            truncated += f"\n... [Truncated: showing first {max_chars} characters of {len(cleaned)} total]"

        return f"Current Page: {title}\nURL: {url}\n\nContent:\n{truncated}"
    except Exception as e:
        return f"Error extracting page text: {e}"


@tool(name="browser_get_interactive_elements", description="Scan the active page and list clickable buttons, inputs, links, and forms with their CSS selectors and labels.")
async def browser_get_interactive_elements() -> str:
    """Inspect and return interactive elements from the current page."""
    try:
        page = await controller.get_current_page()
        if not page:
            return "Error: No active browser window is open."

        elements_data = await page.evaluate("""() => {
            const results = [];
            const interactive = document.querySelectorAll('button, a, input, textarea, select, [role="button"], [role="link"], [role="textbox"]');
            let idx = 1;
            for (const el of interactive) {
                if (idx > 40) break; // limit to top 40 interactive elements
                const rect = el.getBoundingClientRect();
                const isVisible = rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden';
                if (!isVisible) continue;

                const tag = el.tagName.toLowerCase();
                const text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || el.getAttribute('title') || '').trim();
                const type = el.getAttribute('type') || '';
                const id = el.id ? `#${el.id}` : '';
                const name = el.getAttribute('name') ? `[name="${el.getAttribute('name')}"]` : '';
                
                let selector = '';
                if (el.id) {
                    selector = `#${el.id}`;
                } else if (tag === 'button' && text) {
                    selector = `button:has-text("${text.slice(0, 25)}")`;
                } else if (tag === 'a' && text) {
                    selector = `a:has-text("${text.slice(0, 25)}")`;
                } else if (name) {
                    selector = `${tag}${name}`;
                } else if (el.placeholder) {
                    selector = `${tag}[placeholder="${el.placeholder}"]`;
                } else {
                    selector = tag;
                }

                results.push({
                    index: idx++,
                    tag: tag,
                    type: type,
                    text: text.slice(0, 40),
                    selector: selector
                });
            }
            return results;
        }""")

        if not elements_data:
            return "No interactive elements found on the current page."

        output_lines = [f"Interactive Elements on '{page.url}':\n"]
        for el in elements_data:
            line = f"[{el['index']}] <{el['tag']}> {('Text: ' + el['text']) if el['text'] else ''} | Selector: `{el['selector']}`"
            output_lines.append(line)

        return "\n".join(output_lines)
    except Exception as e:
        return f"Error scanning interactive elements: {e}"


@tool(name="browser_take_screenshot", description="Capture a screenshot of the visible browser window or webpage and save it locally.")
async def browser_take_screenshot(filename: Optional[str] = None) -> str:
    """Capture page screenshot and save to disk."""
    try:
        page = await controller.get_current_page()
        if not page:
            return "Error: No active browser window is open."

        screenshot_dir = DATA_DIR / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        if not filename:
            import time
            fname = f"browser_screenshot_{int(time.time())}.png"
        else:
            fname = filename if filename.endswith(".png") or filename.endswith(".jpg") else f"{filename}.png"

        save_path = screenshot_dir / fname
        await page.screenshot(path=str(save_path), full_page=False)
        logger.info(f"[BrowserControl] Screenshot saved to: '{save_path}'")
        return f"Screenshot successfully saved to: '{save_path}'."
    except Exception as e:
        return f"Error taking screenshot: {e}"


@tool(name="browser_back", description="Go back to the previous page in browser history.")
async def browser_back() -> str:
    """Navigate backwards in history."""
    try:
        page = await controller.get_current_page()
        if not page:
            return "Error: No active browser window is open."
        await page.go_back()
        return f"Navigated back. Current URL: {page.url}"
    except Exception as e:
        return f"Error navigating back: {e}"


@tool(name="browser_forward", description="Go forward in browser history.")
async def browser_forward() -> str:
    """Navigate forward in history."""
    try:
        page = await controller.get_current_page()
        if not page:
            return "Error: No active browser window is open."
        await page.go_forward()
        return f"Navigated forward. Current URL: {page.url}"
    except Exception as e:
        return f"Error navigating forward: {e}"


@tool(name="browser_close", description="Close the visible web browser window and release resources.")
async def browser_close() -> str:
    """Close active browser session."""
    try:
        return await controller.close()
    except Exception as e:
        return f"Error closing browser: {e}"


@tool(name="browser_fill_form_and_login", description="Automatically detect username/email and password fields on a webpage, fill in credentials, and click the Login/Sign-In button.")
async def browser_fill_form_and_login(
    username_or_email: str,
    password: str,
    url: Optional[str] = None,
    submit_button_text: Optional[str] = None
) -> str:
    """Automatically fills login credentials and submits the login form on the page."""
    try:
        page = await controller.ensure_page(headless=False)
        if url:
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url
            logger.info(f"[BrowserControl] Navigating to login URL: '{url}'...")
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(1000)

        # 1. Locate Username / Email input field
        user_selectors = [
            'input[autocomplete="username"]',
            'input[autocomplete="email"]',
            'input[type="email"]',
            'input[name*="user" i]',
            'input[name*="email" i]',
            'input[name*="login" i]',
            'input[id*="user" i]',
            'input[id*="email" i]',
            'input[id*="login" i]',
            'input[placeholder*="user" i]',
            'input[placeholder*="email" i]',
            'input[placeholder*="phone" i]',
            'input[type="text"]'
        ]

        user_input = None
        for sel in user_selectors:
            loc = page.locator(sel).first
            if await loc.count() > 0 and await loc.is_visible():
                user_input = loc
                logger.info(f"[BrowserControl] Found username input with selector: '{sel}'")
                break

        if not user_input:
            return "Error: Could not locate a username or email input field on the page. Try inspecting the page with 'browser_get_interactive_elements'."

        await user_input.fill("")
        await user_input.fill(username_or_email)
        await page.wait_for_timeout(300)

        # 2. Locate Password field
        pass_selectors = [
            'input[type="password"]',
            'input[autocomplete="current-password"]',
            'input[name*="pass" i]',
            'input[id*="pass" i]',
            'input[placeholder*="pass" i]'
        ]

        pass_input = None
        for sel in pass_selectors:
            loc = page.locator(sel).first
            if await loc.count() > 0 and await loc.is_visible():
                pass_input = loc
                logger.info(f"[BrowserControl] Found password input with selector: '{sel}'")
                break

        if pass_input:
            await pass_input.fill("")
            await pass_input.fill(password)
            await page.wait_for_timeout(300)

        # 3. Locate & Click Login / Submit Button
        submit_btn = None
        if submit_button_text:
            btn_loc = page.locator(f'button:has-text("{submit_button_text}"), input[value*="{submit_button_text}" i], a:has-text("{submit_button_text}")').first
            if await btn_loc.count() > 0 and await btn_loc.is_visible():
                submit_btn = btn_loc

        if not submit_btn:
            button_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Sign in")',
                'button:has-text("Sign In")',
                'button:has-text("Log in")',
                'button:has-text("Log In")',
                'button:has-text("Login")',
                'button:has-text("Submit")',
                'button:has-text("Next")',
                'button:has-text("Continue")',
                'button[name*="login" i]',
                'button[id*="login" i]'
            ]
            for btn_sel in button_selectors:
                loc = page.locator(btn_sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    submit_btn = loc
                    logger.info(f"[BrowserControl] Found submit button with selector: '{btn_sel}'")
                    break

        if submit_btn:
            await submit_btn.click()
        elif pass_input:
            # Fallback: Press Enter in the password field
            await pass_input.press("Enter")
        else:
            await user_input.press("Enter")

        # Wait for page transition / network settle
        await page.wait_for_timeout(3000)
        new_title = await page.title()
        return f"Login credentials submitted for '{username_or_email}'.\nNew Page Title: '{new_title}'\nActive URL: {page.url}"
    except Exception as e:
        logger.error(f"[BrowserControl] browser_fill_form_and_login failed: {e}")
        return f"Error during automated login: {e}"
