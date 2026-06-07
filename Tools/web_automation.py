"""Web automation and form filling using Playwright."""

import logging
from typing import Dict
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

@function_tool
async def fill_web_form(url: str, form_data: dict) -> str:
    """
    Navigates to a URL and automatically fills a web form using the provided data.
    
    Args:
        url: The URL of the page with the form.
        form_data: A dictionary mapping field names or labels to the values to be filled. Example: {"Username": "john", "Password": "password123"}
    """
    logger.info(f"Filling web form at {url}")
    try:
        from playwright.async_api import async_playwright
        import json
        
        # Parse if form_data is a JSON string due to LiveKit passing strings sometimes
        if isinstance(form_data, str):
            form_data = json.loads(form_data)
            
        async with async_playwright() as p:
            # We use chromium in headless mode to do the work silently, or headful to show the user.
            # Headful is better for desktop automation so the user sees it.
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            await page.goto(url, wait_until="networkidle")
            
            filled_fields = []
            for field, value in form_data.items():
                # Playwright's get_by_label or get_by_placeholder makes this semantic
                try:
                    # Try label first
                    locator = page.get_by_label(field, exact=False).first
                    if await locator.is_visible():
                        await locator.fill(str(value))
                        filled_fields.append(field)
                        continue
                    
                    # Try placeholder
                    locator = page.get_by_placeholder(field, exact=False).first
                    if await locator.is_visible():
                        await locator.fill(str(value))
                        filled_fields.append(field)
                        continue
                        
                    # Try name attribute
                    locator = page.locator(f"[name*='{field}' i]").first
                    if await locator.is_visible():
                        await locator.fill(str(value))
                        filled_fields.append(field)
                        continue
                        
                except Exception as e:
                    logger.warning(f"Failed to fill field {field}: {e}")
            
            # Optionally leave the browser open or close it
            # For demonstration, we'll wait a bit and close. In a real desktop assistant,
            # you might want to leave it open so the user can hit 'Submit'.
            await page.wait_for_timeout(2000)
            await browser.close()
            
            if filled_fields:
                return f"Successfully filled the following fields at {url}: {', '.join(filled_fields)}"
            else:
                return f"Could not find matching fields for the provided data at {url}."
                
    except ImportError:
        return "Playwright is not installed. Please run 'pip install playwright' and 'playwright install'."
    except Exception as e:
        logger.error(f"Form filling failed: {e}")
        return f"Form filling failed: {e}"
