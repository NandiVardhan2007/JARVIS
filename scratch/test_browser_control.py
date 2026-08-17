import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from vision.tools.browser_control_tools import (
    browser_open,
    browser_navigate,
    browser_type,
    browser_get_interactive_elements,
    browser_get_page_content,
    browser_take_screenshot,
    browser_close
)
from vision.logger import logger


async def run_test():
    print("=== Testing VISION Browser Control ===")
    
    # 1. Open browser to DuckDuckGo
    print("\n[Step 1] Opening visible browser...")
    res = await browser_open("https://duckduckgo.com")
    print("Open Result:", res)
    await asyncio.sleep(2)

    # 2. Get interactive elements
    print("\n[Step 2] Scanning interactive elements...")
    elements = await browser_get_interactive_elements()
    print("Interactive Elements Sample:\n", elements[:400], "...\n")

    # 3. Type into search input and press Enter
    print("\n[Step 3] Typing search query and pressing Enter...")
    type_res = await browser_type("input[name='q']", "Google DeepMind Antigravity AI", press_enter=True)
    print("Type Result:", type_res)
    await asyncio.sleep(3)

    # 4. Extract content
    print("\n[Step 4] Extracting page content...")
    content = await browser_get_page_content(max_chars=300)
    print("Content Sample:\n", content)

    # 5. Take screenshot
    print("\n[Step 5] Taking screenshot...")
    screenshot_res = await browser_take_screenshot("test_browser_verification.png")
    print("Screenshot Result:", screenshot_res)
    await asyncio.sleep(1)

    # 6. Close browser
    print("\n[Step 6] Closing browser...")
    close_res = await browser_close()
    print("Close Result:", close_res)
    print("\n=== Verification Completed Successfully! ===")


if __name__ == "__main__":
    asyncio.run(run_test())
