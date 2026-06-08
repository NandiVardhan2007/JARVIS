"""
Mobile Control Tool — ADB over TCP/IP for Android automation.
No root required for most features.
"""

import asyncio
import logging
import os
import subprocess
import time
from typing import Literal, Optional

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

PHONE_IP   = os.getenv("JARVIS_PHONE_IP", "")       # e.g. 192.168.1.5
PHONE_PORT = os.getenv("JARVIS_PHONE_PORT", "5555")
PHONE_PATTERN = os.getenv("JARVIS_PHONE_PATTERN", "")
ADB_PATH   = os.getenv("ADB_PATH", "adb")           # full path if not in PATH


def _adb(*args, timeout: int = 10) -> tuple[str, str, int]:
    """Run an ADB command against the configured phone. Returns (stdout, stderr, returncode)."""
    if not PHONE_IP:
        return "", "JARVIS_PHONE_IP not set in .env", 1

    target = f"{PHONE_IP}:{PHONE_PORT}"
    cmd = [ADB_PATH, "-s", target] + list(args)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", f"ADB command timed out after {timeout}s", 1
    except FileNotFoundError:
        return "", "ADB not found. Install Android Platform Tools and set ADB_PATH.", 1
    except Exception as e:
        return "", str(e), 1


async def _adb_async(*args, timeout: int = 10) -> tuple[str, str, int]:
    return await asyncio.to_thread(_adb, *args, timeout=timeout)


# ── Connection ────────────────────────────────────────────────────────────────

@function_tool
async def connect_phone() -> str:
    """
    Connect JARVIS to your Android phone over Wi-Fi via ADB.
    Your phone IP must be set as JARVIS_PHONE_IP in .env.
    The phone must have Wireless Debugging enabled in Developer Options.
    """
    if not PHONE_IP:
        return (
            "JARVIS_PHONE_IP not set. Add it to your .env file.\n"
            "Find your phone IP: Settings → Wi-Fi → tap your network → IP address."
        )

    stdout, stderr, code = await _adb_async("connect", f"{PHONE_IP}:{PHONE_PORT}", timeout=15)
    if code == 0 or "connected" in (stdout + stderr).lower():
        return f"Connected to phone at {PHONE_IP}:{PHONE_PORT}."
    return f"Failed to connect: {stderr or stdout}"


@function_tool
async def get_phone_status() -> str:
    """
    Returns the current status and basic info of the connected Android phone.
    Battery level, screen state, current app, Wi-Fi status.
    """
    checks = {
        "Battery":     ("shell", "dumpsys", "battery", "|", "grep", "level"),
        "Screen":      ("shell", "dumpsys", "power", "|", "grep", "mWakefulness"),
        "Current App": ("shell", "dumpsys", "window", "windows", "|", "grep", "mCurrentFocus"),
        "Wi-Fi":       ("shell", "dumpsys", "wifi", "|", "grep", "mWifiInfo"),
    }

    results = []
    for label, args in checks.items():
        stdout, _, _ = await _adb_async(*args, timeout=5)
        first_line = stdout.split("\n")[0].strip() if stdout else "N/A"
        results.append(f"**{label}:** {first_line}")

    return "\n".join(results) if results else "Could not retrieve phone status."


# ── Screen Control ────────────────────────────────────────────────────────────

@function_tool
async def unlock_phone(pin: str = "", pattern: str = "") -> str:
    """
    Wakes up and unlocks the Android phone.
    DO NOT ask the user for a PIN or pattern! Just call this function with empty arguments to use their saved default.

    Args:
        pin: The phone unlock PIN (leave empty to use the saved default).
        pattern: The phone unlock pattern (leave empty to use the saved default).
    """
    # Wake screen
    await _adb_async("shell", "input", "keyevent", "KEYCODE_WAKEUP")
    await asyncio.sleep(0.8)

    # Swipe up to dismiss lock screen
    await _adb_async("shell", "input", "swipe", "540", "1600", "540", "800", "300")
    await asyncio.sleep(0.5)

    if pin:
        # Type PIN
        stdout, stderr, code = await _adb_async("shell", "input", "text", pin)
        await asyncio.sleep(0.3)
        await _adb_async("shell", "input", "keyevent", "KEYCODE_ENTER")
        if code == 0:
            return "Phone unlocked with PIN."
        return f"PIN entry failed: {stderr}"

    pattern_to_use = pattern or PHONE_PATTERN
    if pattern_to_use:
        import tempfile
        import xml.etree.ElementTree as ET
        import re

        # Dump UI
        await _adb_async("shell", "uiautomator", "dump", "/sdcard/window_dump.xml")
        await asyncio.sleep(0.5)

        with tempfile.TemporaryDirectory() as tmp:
            local_path = os.path.join(tmp, "window_dump.xml")
            await _adb_async("pull", "/sdcard/window_dump.xml", local_path)

            if not os.path.exists(local_path):
                return "Failed to get UI dump for pattern unlock."

            tree = ET.parse(local_path)
            root = tree.getroot()
            
            # Find LockPatternView
            pattern_view = None
            for node in root.iter('node'):
                res_id = node.get('resource-id', '')
                if 'lockPatternView' in res_id:
                    pattern_view = node
                    break
            
            if pattern_view is None:
                return "Could not find LockPatternView on screen."

            # bounds="[x1,y1][x2,y2]"
            bounds_str = pattern_view.get('bounds')
            m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
            if not m:
                return f"Invalid bounds format: {bounds_str}"

            x1, y1, x2, y2 = map(int, m.groups())
            width = x2 - x1
            height = y2 - y1

            # Calculate 3x3 grid dot centers
            cell_w = width / 3.0
            cell_h = height / 3.0
            
            dots = {}
            dot_idx = 1
            for row in range(3):
                for col in range(3):
                    cx = x1 + (col * cell_w) + (cell_w / 2)
                    cy = y1 + (row * cell_h) + (cell_h / 2)
                    dots[str(dot_idx)] = (int(cx), int(cy))
                    dot_idx += 1

            # Generate Monkey Script
            script_lines = [
                "type= raw events",
                "count= 1",
                "speed= 1.0",
                "start data >>"
            ]

            pattern_to_use = pattern_to_use.replace(" ", "")
            prev_x, prev_y = None, None
            
            for i, p in enumerate(pattern_to_use):
                if p not in dots:
                    continue
                x, y = dots[p]
                
                if i == 0:
                    script_lines.append(f"DispatchPointer(0, 0, 0, {x}, {y}, 1, 1, 0, 0, 0, 0, 0)")
                    script_lines.append("UserWait(50)")
                else:
                    # Interpolate points for a smooth, human-like swipe
                    steps = 8
                    for step in range(1, steps + 1):
                        inter_x = prev_x + (x - prev_x) * (step / steps)
                        inter_y = prev_y + (y - prev_y) * (step / steps)
                        script_lines.append(f"DispatchPointer(0, 0, 2, {int(inter_x)}, {int(inter_y)}, 1, 1, 0, 0, 0, 0, 0)")
                        script_lines.append("UserWait(15)")

                if i == len(pattern_to_use) - 1:
                    script_lines.append(f"DispatchPointer(0, 0, 1, {x}, {y}, 1, 1, 0, 0, 0, 0, 0)")
                    
                prev_x, prev_y = x, y

            script_content = "\n".join(script_lines) + "\n"
            script_path = os.path.join(tmp, "pattern.txt")
            with open(script_path, "w") as f:
                f.write(script_content)

            await _adb_async("push", script_path, "/sdcard/pattern.txt")
            stdout, stderr, code = await _adb_async("shell", "monkey", "-f", "/sdcard/pattern.txt", "1")
            await _adb_async("shell", "rm", "/sdcard/pattern.txt")

            if code == 0:
                return f"Pattern {pattern} entered via monkey script."
            return f"Pattern unlock failed: {stderr}"

    return "Phone woken and lock screen dismissed."


@function_tool
async def lock_phone() -> str:
    """Locks the Android phone screen immediately."""
    stdout, stderr, code = await _adb_async("shell", "input", "keyevent", "KEYCODE_SLEEP")
    return "Phone locked." if code == 0 else f"Lock failed: {stderr}"


@function_tool
async def phone_tap(x: int, y: int) -> str:
    """
    Taps a specific screen coordinate on the phone.

    Args:
        x: X coordinate in pixels.
        y: Y coordinate in pixels.
    """
    stdout, stderr, code = await _adb_async("shell", "input", "tap", str(x), str(y))
    return f"Tapped ({x}, {y})." if code == 0 else f"Tap failed: {stderr}"


@function_tool
async def phone_swipe(
    x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300
) -> str:
    """
    Swipes on the phone screen from one point to another.

    Args:
        x1, y1: Start coordinates.
        x2, y2: End coordinates.
        duration_ms: Swipe duration in milliseconds (default 300).
    """
    stdout, stderr, code = await _adb_async(
        "shell", "input", "swipe",
        str(x1), str(y1), str(x2), str(y2), str(duration_ms)
    )
    return (
        f"Swiped from ({x1},{y1}) to ({x2},{y2})."
        if code == 0 else f"Swipe failed: {stderr}"
    )


@function_tool
async def phone_type(text: str) -> str:
    """
    Types text into the currently focused field on the phone.

    Args:
        text: Text to type (spaces must be encoded as %s for ADB).
    """
    # ADB input text doesn't handle spaces or special chars well
    # Use clipboard method for reliability
    encoded = text.replace(" ", "%s").replace("'", "")
    stdout, stderr, code = await _adb_async("shell", "input", "text", encoded)
    return f"Typed text on phone." if code == 0 else f"Type failed: {stderr}"


@function_tool
async def phone_press_key(key: str) -> str:
    """
    Presses a hardware or navigation key on the phone.

    Args:
        key: Key name — home, back, recent, volume_up, volume_down,
             power, enter, delete, camera, screenshot.
    """
    key_map = {
        "home":        "KEYCODE_HOME",
        "back":        "KEYCODE_BACK",
        "recent":      "KEYCODE_APP_SWITCH",
        "volume_up":   "KEYCODE_VOLUME_UP",
        "volume_down": "KEYCODE_VOLUME_DOWN",
        "power":       "KEYCODE_POWER",
        "enter":       "KEYCODE_ENTER",
        "delete":      "KEYCODE_DEL",
        "camera":      "KEYCODE_CAMERA",
        "screenshot":  "KEYCODE_SYSRQ",
        "mute":        "KEYCODE_MUTE",
    }
    keycode = key_map.get(key.lower())
    if not keycode:
        return f"Unknown key '{key}'. Available: {', '.join(key_map.keys())}"

    stdout, stderr, code = await _adb_async("shell", "input", "keyevent", keycode)
    return f"Pressed {key}." if code == 0 else f"Key press failed: {stderr}"


# ── App Control ───────────────────────────────────────────────────────────────

@function_tool
async def open_phone_app(app_name_or_package: str) -> str:
    """
    Launches an app on the phone by its name (e.g. 'WhatsApp') or package name (e.g. 'com.whatsapp').

    Args:
        app_name_or_package: The name of the app or its package name.
    """
    package_name = app_name_or_package.lower().strip()
    
    # If it doesn't look like a package name, try to resolve it
    if "." not in package_name:
        stdout, stderr, code = await _adb_async("shell", "pm", "list", "packages")
        if code == 0:
            packages = [
                line.replace("package:", "").strip()
                for line in stdout.split("\n")
                if line.startswith("package:")
            ]
            
            # Find packages that contain the app name
            matches = [p for p in packages if package_name in p.lower()]
            
            if matches:
                # Prefer third-party apps if possible (they usually don't start with com.android or com.google)
                # But if there's a direct match in the last part of the package name, use that.
                best_match = matches[0]
                for match in matches:
                    if match.endswith(f".{package_name}"):
                        best_match = match
                        break
                package_name = best_match

    stdout, stderr, code = await _adb_async(
        "shell", "monkey", "-p", package_name,
        "-c", "android.intent.category.LAUNCHER", "1"
    )
    if code == 0 and "Events injected: 1" in stdout:
        return f"Launched {package_name}."
    return f"Failed to launch {package_name}: {stderr or stdout}"


@function_tool
async def close_phone_app(package_name: str) -> str:
    """
    Force-closes an app on the phone.

    Args:
        package_name: The package name of the app to close.
    """
    stdout, stderr, code = await _adb_async(
        "shell", "am", "force-stop", package_name
    )
    return f"Closed {package_name}." if code == 0 else f"Failed: {stderr}"


@function_tool
async def list_installed_apps(filter_keyword: str = "") -> str:
    """
    Lists installed apps on the phone, with optional keyword filter.

    Args:
        filter_keyword: Optional keyword to filter package names.
    """
    stdout, stderr, code = await _adb_async("shell", "pm", "list", "packages", "-3")
    if code != 0:
        return f"Failed to list apps: {stderr}"

    packages = [
        line.replace("package:", "").strip()
        for line in stdout.split("\n")
        if line.startswith("package:")
    ]
    if filter_keyword:
        packages = [p for p in packages if filter_keyword.lower() in p.lower()]

    if not packages:
        return f"No apps found matching '{filter_keyword}'."
    return f"Installed apps ({len(packages)}):\n" + "\n".join(packages[:30])


# ── Notifications ─────────────────────────────────────────────────────────────

@function_tool
async def send_phone_notification(title: str, body: str) -> str:
    """
    Pushes a notification to the Android phone via ADB shell.

    Args:
        title: Notification title.
        body: Notification body text.
    """
    # Uses the service call approach — works without Termux
    cmd = (
        f'shell service call notification 1 i32 1 s16 "android" s16 '
        f'"{title}" s16 "{body}"'
    )
    # Simpler and more reliable: use am broadcast with a notification intent
    # The cleanest no-root approach is a companion app or Termux
    # Fallback: use adb to start the settings notification as a workaround
    stdout, stderr, code = await _adb_async(
        "shell", "am", "broadcast",
        "-a", "android.intent.action.MAIN",
        "--es", "title", title,
        "--es", "body", body
    )
    # The reliable cross-device method:
    return await _notify_via_termux(title, body)


async def _notify_via_termux(title: str, body: str) -> str:
    """Send notification via Termux:API (most reliable ADB notification method)."""
    stdout, stderr, code = await _adb_async(
        "shell",
        f"termux-notification --title '{title}' --content '{body}' --id 42"
    )
    if code == 0:
        return f"Notification sent: {title}"
    # Fallback: toast message (shows briefly on screen)
    await _adb_async(
        "shell", "am", "start", "-W",
        "-a", "android.intent.action.VIEW",
        "--es", "message", f"{title}: {body}"
    )
    return f"Notification pushed (toast fallback): {title}"


# ── Screen Reading ────────────────────────────────────────────────────────────

@function_tool
async def read_phone_screen(question: Optional[str] = None) -> str:
    """
    Takes a screenshot of the phone screen and analyses it using the
    same vision AI pipeline as JARVIS's desktop read_screen tool.

    Args:
        question: Optional specific question about what's on screen.
    """
    import tempfile
    import os

    # Capture screenshot on device
    await _adb_async("shell", "screencap", "-p", "/sdcard/jarvis_screen.png")
    await asyncio.sleep(0.5)

    # Pull to PC
    with tempfile.TemporaryDirectory() as tmp:
        local_path = os.path.join(tmp, "phone_screen.png")
        stdout, stderr, code = await _adb_async(
            "pull", "/sdcard/jarvis_screen.png", local_path
        )
        if code != 0:
            return f"Failed to pull screenshot: {stderr}"

        # Reuse existing vision pipeline
        try:
            from Tools.screen_reader import _image_to_base64, _analyse_image, _PROMPTS
            b64 = _image_to_base64(local_path)
            prompt = (
                question
                if question
                else _PROMPTS["summary"].replace(
                    "desktop assistant", "mobile assistant"
                )
            )
            result = _analyse_image(b64, prompt)
            return f"Phone screen: {result}"
        except Exception as e:
            return f"Vision analysis failed: {e}"


@function_tool
async def phone_ocr_tap(target_text: str) -> str:
    """
    Finds text on the phone screen using OCR and taps it.
    Combines read_phone_screen with coordinate detection.

    Args:
        target_text: The text visible on screen to find and tap.
    """
    import tempfile
    import os

    await _adb_async("shell", "screencap", "-p", "/sdcard/jarvis_screen.png")
    await asyncio.sleep(0.3)

    with tempfile.TemporaryDirectory() as tmp:
        local_path = os.path.join(tmp, "phone_screen.png")
        stdout, stderr, code = await _adb_async(
            "pull", "/sdcard/jarvis_screen.png", local_path
        )
        if code != 0:
            return f"Screenshot failed: {stderr}"

        try:
            import pytesseract
            from PIL import Image

            pytesseract.pytesseract.tesseract_cmd = (
                r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            )
            img = Image.open(local_path)
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

            for i, word in enumerate(data["text"]):
                if target_text.lower() in word.lower() and data["conf"][i] > 40:
                    x = data["left"][i] + data["width"][i] // 2
                    y = data["top"][i] + data["height"][i] // 2
                    await phone_tap(x, y)
                    return f"Tapped '{target_text}' at ({x}, {y}) on phone."

            return f"Could not find '{target_text}' on phone screen."
        except Exception as e:
            return f"OCR tap failed: {e}"


# ── File & Media ──────────────────────────────────────────────────────────────

@function_tool
async def push_file_to_phone(local_path: str, remote_path: str = "/sdcard/Download/") -> str:
    """
    Transfers a file from the PC to the phone.

    Args:
        local_path: Path to the file on this PC.
        remote_path: Destination path on the phone (default: Downloads folder).
    """
    if not os.path.exists(local_path):
        return f"File not found: {local_path}"

    stdout, stderr, code = await _adb_async(
        "push", local_path, remote_path, timeout=60
    )
    return (
        f"File pushed to phone: {remote_path}"
        if code == 0 else f"Push failed: {stderr}"
    )


@function_tool
async def pull_file_from_phone(
    remote_path: str, local_path: str = ""
) -> str:
    """
    Downloads a file from the phone to the PC.

    Args:
        remote_path: Path on the phone, e.g. '/sdcard/DCIM/photo.jpg'.
        local_path: Where to save on PC (defaults to Desktop).
    """
    if not local_path:
        filename = remote_path.split("/")[-1]
        local_path = os.path.join(os.path.expanduser("~/Desktop"), filename)

    stdout, stderr, code = await _adb_async(
        "pull", remote_path, local_path, timeout=60
    )
    return (
        f"File saved to: {local_path}"
        if code == 0 else f"Pull failed: {stderr}"
    )


@function_tool
async def run_phone_command(command: str) -> str:
    """
    Runs a raw ADB shell command on the phone.
    Only use for commands not covered by other tools.

    Args:
        command: Shell command to run, e.g. 'getprop ro.product.model'.
    """
    # Basic safety filter
    blocked = ["rm -rf", "format", "wipe", "reboot bootloader"]
    if any(b in command.lower() for b in blocked):
        return f"Command blocked for safety."

    stdout, stderr, code = await _adb_async("shell", command, timeout=15)
    if stdout:
        return stdout[:2000]
    if stderr:
        return f"Error: {stderr[:500]}"
    return "Command executed (no output)."
