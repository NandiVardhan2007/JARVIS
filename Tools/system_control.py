"""System control tools — power, volume, brightness, clipboard, antivirus."""

import logging
import os
import platform
import socket
import subprocess
from typing import Literal, Optional
from livekit.agents import function_tool

logger = logging.getLogger(__name__)


@function_tool
async def system_power_action(action: Literal["shutdown", "restart", "lock"]) -> str:
    """
    Controls the system power state.

    Args:
        action: "shutdown" to power off, "restart" to reboot, "lock" to lock the screen.
    """
    logger.info(f"Power action requested: {action}")
    try:
        sys = platform.system()
        if action == "shutdown":
            os.system("shutdown now")
            return "Shutting the system down now, sir."
        elif action == "restart":
            os.system("reboot")
            return "Restarting the system now, sir."
        elif action == "lock":
            os.system("loginctl lock-session")
            return "Screen locked."
        return f"Unknown action: {action}"
    except Exception as e:
        return f"Power action failed: {e}"


@function_tool
async def get_system_info() -> str:
    """
    Returns a full diagnostic report: battery, CPU, RAM, storage, and network status.
    """
    try:
        import psutil
        hostname = platform.node()

        battery = psutil.sensors_battery()
        bat_str = (
            f"{int(battery.percent)}% ({'Charging' if battery.power_plugged else 'On Battery'})"
            if battery else "N/A"
        )

        disk = psutil.disk_usage("/")
        free_gb = round(disk.free / 1024**3, 1)
        total_gb = round(disk.total / 1024**3, 1)

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            net_str = f"Connected — IP: {ip}"
        except Exception:
            net_str = "Not Connected"

        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        ram_used = round(ram.used / 1024**3, 1)
        ram_total = round(ram.total / 1024**3, 1)

        return (
            f"System Report — {hostname}\n"
            f"Battery: {bat_str}\n"
            f"Storage: {free_gb} GB free of {total_gb} GB\n"
            f"Network: {net_str}\n"
            f"CPU Usage: {cpu}%\n"
            f"RAM Usage: {ram_used} GB of {ram_total} GB"
        )
    except Exception as e:
        return f"Failed to retrieve system info: {e}"


@function_tool
async def control_screen_brightness(prompt: str, brightness_level: int) -> str:
    """
    Sets the screen brightness.

    Args:
        prompt: The user's original request.
        brightness_level: Desired brightness as an integer from 0 to 100.
    """
    if not 0 <= brightness_level <= 100:
        return "Brightness level must be between 0 and 100."
    try:
        import screen_brightness_control as sbc
        sbc.set_brightness(brightness_level)
        return f"Screen brightness set to {brightness_level}%."
    except Exception as e:
        return f"Failed to adjust brightness: {e}"


@function_tool
async def control_system_volume(prompt: str, volume_level: int) -> str:
    """
    Sets the system volume.

    Args:
        prompt: The user's original request.
        volume_level: Desired volume as an integer from 0 to 100.
    """
    if not 0 <= volume_level <= 100:
        return "Volume level must be between 0 and 100."
    try:
        os.system(f"pactl set-sink-volume @DEFAULT_SINK@ {volume_level}%")
        return f"System volume set to {volume_level}%."
    except Exception as e:
        return f"Failed to adjust volume: {e}"


@function_tool
async def control_media(prompt: str, action: Literal["play_pause", "next", "previous"]) -> str:
    """
    Controls media playback (background player or system media keys).

    Args:
        prompt: The user's original request.
        action: "play_pause", "next", or "previous".
    """
    try:
        from Tools.media import _media_player
        if _media_player and _media_player.get_state() != 0:
            if action == "play_pause":
                if _media_player.is_playing():
                    _media_player.pause()
                else:
                    _media_player.play()
                return "Background music playback toggled."
            elif action in ["next", "previous"]:
                _media_player.stop()
                return f"Background music stopped (skip {action} requested)."
            
        cmd_map = {"previous": "previous", "play_pause": "play-pause", "next": "next"}
        if action not in cmd_map:
            return f"Unknown action '{action}'. Use play_pause, next, or previous."
        os.system(f"playerctl {cmd_map[action]}")
        label = {"play_pause": "Play/Pause toggled.", "next": "Skipped to next track.",
                 "previous": "Went back to previous track."}
        return label[action]
    except Exception as e:
        return f"Media control failed: {e}"


@function_tool
async def use_smart_clipboard(
    prompt: str,
    action: Literal["open_history", "paste_item"],
    item_index: Optional[int] = None,
) -> str:
    """
    Manages system clipboard history on Linux.

    Args:
        prompt: The user's original request.
        action: "open_history" to view clipboard history, "paste_item" to paste a specific entry.
        item_index: 1-based index of the clipboard item to paste (required for paste_item).
    """
    try:
        from Tools.clipboard_manager import get_recent_clipboard
        history = await get_recent_clipboard(limit=5)
        return f"Clipboard History:\n{history}"
    except Exception as e:
        return f"Clipboard operation failed: {e}"


@function_tool
async def scan_system_for_viruses() -> str:
    """
    Runs a virus and malware scan on Linux using ClamAV.
    """
    try:
        import shutil
        if not shutil.which("clamscan"):
            return "ClamAV (clamscan) is not installed on this system. You can install it using 'sudo apt install clamav'."
        
        result = subprocess.run(
            ["clamscan", "-r", "--no-summary", os.path.expanduser("~")],
            capture_output=True, text=True, timeout=120,
        )
        output = (result.stdout or result.stderr or "").strip()
        if output:
            return f"Scan complete:\n{output[:800]}"
        return "Scan complete. No threats detected."
    except Exception as e:
        return f"Scan failed: {e}"
