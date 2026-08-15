"""
System and OS automation tools for Windows/Desktop control.
"""

import subprocess
import os
from vision.tools.registry import tool
from vision.perception.vision.screen import screen_capture
from vision.perception.vision.gemini_vision import gemini_vision
from vision.logger import logger

try:
    import psutil
except ImportError:
    psutil = None


@tool(name="open_application", description="Launch an installed desktop application or open a URL.")
def open_application(app_name: str) -> str:
    """Launch an application on the local OS."""
    try:
        subprocess.Popen(f"start {app_name}", shell=True)
        return f"Successfully launched {app_name}."
    except Exception as e:
        return f"Failed to launch {app_name}: {e}"


@tool(name="get_system_stats", description="Get CPU, memory, and battery status of the host computer.")
def get_system_stats() -> str:
    """Retrieve host performance statistics."""
    if not psutil:
        return "psutil package is not installed; system metrics unavailable."
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    battery = psutil.sensors_battery()
    bat_str = f"{battery.percent}% ({'Plugged in' if battery.power_plugged else 'On Battery'})" if battery else "No battery detected"
    return f"CPU Usage: {cpu}%\nRAM Usage: {mem.percent}% ({mem.used // (1024*1024)}MB / {mem.total // (1024*1024)}MB)\nBattery: {bat_str}"


@tool(name="read_screen", description="Take a screenshot and use vision AI to describe the current desktop contents.")
async def read_screen(query: str = "Describe what is currently visible on the screen") -> str:
    """Inspect and analyze the screen visually."""
    img_bytes = screen_capture.capture_screen()
    if not img_bytes:
        return "Failed to capture desktop screenshot."
    try:
        analysis = await gemini_vision.analyze_image(img_bytes, prompt=query)
        return analysis
    except Exception as e:
        return f"Failed to analyze screen with Vision AI: {e}"
