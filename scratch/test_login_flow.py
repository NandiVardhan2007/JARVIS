import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from vision.tools.browser_control_tools import (
    browser_open,
    browser_fill_form_and_login,
    browser_close,
    controller
)


async def run_test():
    print("=== Testing Automated Form Fill & Login ===")
    
    # 1. Open mock login page
    page = await controller.ensure_page(headless=False)
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><title>Portal Login</title></head>
    <body style="font-family: sans-serif; padding: 50px;">
        <h2>Sign in to Student Portal</h2>
        <form id="loginForm" onsubmit="event.preventDefault(); document.getElementById('status').innerText = 'Login Successful for ' + document.getElementById('user').value;">
            <div>
                <label>Username / Student ID:</label><br>
                <input type="text" id="user" placeholder="Enter Roll Number or Email" style="padding: 8px; width: 250px;">
            </div>
            <br>
            <div>
                <label>Password:</label><br>
                <input type="password" id="pass" placeholder="Enter Password" style="padding: 8px; width: 250px;">
            </div>
            <br>
            <button type="submit" style="padding: 10px 20px; background: #2563eb; color: white; border: none; border-radius: 4px; cursor: pointer;">Sign In</button>
        </form>
        <h3 id="status" style="color: green; margin-top: 20px;"></h3>
    </body>
    </html>
    """
    await page.set_content(html_content)
    print("Loaded login page mockup.")
    await asyncio.sleep(2)

    # 2. Run auto login tool
    print("\n[Executing browser_fill_form_and_login]...")
    result = await browser_fill_form_and_login(
        username_or_email="23MH1A05XX",
        password="MySecretPassword123"
    )
    print("Login Tool Result:\n", result)
    await asyncio.sleep(2)

    status_text = await page.inner_text("#status")
    print(f"Page Status Text: '{status_text}'")
    assert "Login Successful" in status_text, "Form submission failed!"

    # 3. Clean up
    await browser_close()
    print("\n=== Auto-Login Verification Passed 100%! ===")


if __name__ == "__main__":
    asyncio.run(run_test())
