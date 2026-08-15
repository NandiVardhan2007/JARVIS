"""
Android Mobile Control automation tools via wireless ADB.
"""

import subprocess
from vision.tools.registry import tool
from vision.config import config
from vision.logger import logger


def _run_adb_cmd(cmd: str) -> str:
    full_cmd = f"{config.ADB_PATH} -s {config.VISION_PHONE_IP}:{config.VISION_PHONE_PORT} {cmd}"
    try:
        res = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, timeout=10)
        return res.stdout.strip() or "Success"
    except Exception as e:
        return f"ADB Error: {e}"


@tool(name="connect_phone", description="Connect to the wireless Android phone via ADB.")
def connect_phone() -> str:
    """Connect to phone ADB over Wi-Fi."""
    cmd = f"{config.ADB_PATH} connect {config.VISION_PHONE_IP}:{config.VISION_PHONE_PORT}"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return res.stdout.strip()


@tool(name="unlock_phone", description="Wake up and unlock the connected Android phone.")
def unlock_phone() -> str:
    """Wake screen and enter unlock pattern/swipe."""
    _run_adb_cmd("shell input keyevent 26")
    _run_adb_cmd("shell input swipe 500 1500 500 500 300")
    return "Sent unlock sequence to mobile device."


@tool(name="launch_mobile_app", description="Launch an app package on the Android phone.")
def launch_mobile_app(package_name: str) -> str:
    """Launch app on phone."""
    return _run_adb_cmd(f"shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1")


@tool(name="tap_phone_screen", description="Tap specific (x, y) coordinates on the Android phone screen.")
def tap_phone_screen(x: int, y: int) -> str:
    """Tap coordinates on mobile screen."""
    return _run_adb_cmd(f"shell input tap {x} {y}")
