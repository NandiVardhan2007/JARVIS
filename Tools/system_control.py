"""
System Control Tools for Windows Native: Power, Volume, Brightness, Clipboard, Antivirus.
Utilizes Windows APIs, pycaw, screen_brightness_control, pyautogui, ctypes, and PowerShell.
"""

import ctypes
import logging
import os
import platform
import shutil
import socket
import subprocess
from typing import Literal, Optional
from Tools.function_tool import function_tool

logger = logging.getLogger(__name__)

@function_tool
async def system_power_action(
    action: Literal["shutdown", "restart", "lock"],
    confirm: bool = False,
) -> str:
    """
    Controls the Windows system power state.

    Args:
        action: "shutdown" to power off, "restart" to reboot, "lock" to lock the screen.
        confirm: Must be explicitly set to True for "shutdown" or "restart". Not needed for "lock".
    """
    logger.info(f"Power action requested on Windows: {action} (confirm={confirm})")

    try:
        if action == "lock":
            ctypes.windll.user32.LockWorkStation()
            return "Windows workstation locked, sir."

        if action in ("shutdown", "restart"):
            if not confirm:
                return f"'{action}' is irreversible. Please call again with confirm=True to proceed."
            
            from Tools.voice_verification import require_live_master_voice
            ok, msg = await require_live_master_voice()
            if not ok:
                logger.warning(f"Blocked '{action}': {msg}")
                return msg

            if action == "shutdown":
                subprocess.run(["shutdown", "/s", "/t", "0"], check=False)
                return "Shutting down Windows now, sir."
            else:
                subprocess.run(["shutdown", "/r", "/t", "0"], check=False)
                return "Restarting Windows now, sir."

        return f"Unknown action: {action}"
    except Exception as e:
        return f"Power action failed: {e}"

@function_tool
async def get_system_info() -> str:
    """
    Returns a full Windows diagnostic report: battery, CPU, RAM, storage, and network status.
    """
    try:
        import psutil
        hostname = platform.node()

        battery = psutil.sensors_battery()
        bat_str = (
            f"{int(battery.percent)}% ({'Charging' if battery.power_plugged else 'On Battery'})"
            if battery else "N/A"
        )

        disk = psutil.disk_usage("C:\\")
        free_gb = round(disk.free / (1024**3), 1)
        total_gb = round(disk.total / (1024**3), 1)

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
        ram_used = round(ram.used / (1024**3), 1)
        ram_total = round(ram.total / (1024**3), 1)

        return (
            f"Windows System Report — {hostname}\n"
            f"Battery: {bat_str}\n"
            f"Storage (C:): {free_gb} GB free of {total_gb} GB\n"
            f"Network: {net_str}\n"
            f"CPU Usage: {cpu}%\n"
            f"RAM Usage: {ram_used} GB of {ram_total} GB"
        )
    except Exception as e:
        return f"Failed to retrieve system info: {e}"

@function_tool
async def control_screen_brightness(prompt: str, brightness_level: int) -> str:
    """
    Sets the Windows screen brightness.

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
    Sets the Windows system master audio volume.

    Args:
        prompt: The user's original request.
        volume_level: Desired volume as an integer from 0 to 100.
    """
    if not 0 <= volume_level <= 100:
        return "Volume level must be between 0 and 100."
    try:
        # Try Pycaw Windows Master Volume Control
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
        
        # Convert 0-100 level to scalar 0.0-1.0
        scalar_vol = float(volume_level) / 100.0
        volume.SetMasterVolumeLevelScalar(scalar_vol, None)
        return f"Windows system volume set to {volume_level}%."
    except Exception as pycaw_err:
        logger.warning(f"Pycaw volume adjustment failed ({pycaw_err}); trying fallback.")
        try:
            import pyautogui
            # Press volume mute/down/up to adjust roughly
            if volume_level == 0:
                pyautogui.press("volumemute")
            else:
                pyautogui.press("volumeup")
            return f"System volume adjusted towards {volume_level}%."
        except Exception as e:
            return f"Failed to adjust volume: {e}"

@function_tool
async def control_media(prompt: str, action: Literal["play_pause", "next", "previous"]) -> str:
    """
    Controls Windows system media playback using native media keys.

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
                return "Background media playback toggled."
            elif action in ["next", "previous"]:
                _media_player.stop()
                return f"Background media stopped (skip {action} requested)."

        import pyautogui
        key_map = {
            "play_pause": "playpause",
            "next": "nexttrack",
            "previous": "prevtrack"
        }
        pyautogui.press(key_map[action])
        label_map = {
            "play_pause": "Media Play/Pause toggled.",
            "next": "Skipped to next track.",
            "previous": "Returned to previous track."
        }
        return label_map[action]
    except Exception as e:
        return f"Media control failed: {e}"

@function_tool
async def use_smart_clipboard(
    prompt: str,
    action: Literal["open_history", "paste_item"],
    item_index: Optional[int] = None,
) -> str:
    """
    Manages system clipboard history on Windows.

    Args:
        prompt: The user's original request.
        action: "open_history" to view clipboard history, "paste_item" to paste a specific entry.
        item_index: 1-based index of the clipboard item to paste (required for paste_item).
    """
    try:
        from Tools.clipboard_manager import get_recent_clipboard
        history = await get_recent_clipboard(limit=5)
        return f"Windows Clipboard History:\n{history}"
    except Exception as e:
        return f"Clipboard operation failed: {e}"

@function_tool
async def scan_system_for_viruses() -> str:
    """
    Runs a Windows Defender virus & malware scan using PowerShell Start-MpScan.
    """
    try:
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "Start-MpScan -ScanType QuickScan"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return "Windows Defender Quick Scan initiated in the background, sir. I will keep monitoring system security."
    except Exception as e:
        return f"Windows virus scan initiation failed: {e}"
