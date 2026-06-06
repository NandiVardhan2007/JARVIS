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
            {"Windows": lambda: os.system("shutdown /s /t 1"),
             "Darwin":  lambda: os.system("sudo shutdown -h now"),
             "Linux":   lambda: os.system("shutdown now")}.get(sys, lambda: None)()
            return "Shutting the system down now, sir."
        elif action == "restart":
            {"Windows": lambda: os.system("shutdown /r /t 1"),
             "Darwin":  lambda: os.system("sudo shutdown -r now"),
             "Linux":   lambda: os.system("reboot")}.get(sys, lambda: None)()
            return "Restarting the system now, sir."
        elif action == "lock":
            if sys == "Windows":
                import ctypes
                ctypes.windll.user32.LockWorkStation()
            elif sys == "Darwin":
                os.system(
                    "/System/Library/CoreServices/Menu Extras/User.menu"
                    "/Contents/Resources/CGSession -suspend"
                )
            else:
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
        if platform.system() == "Windows":
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMasterVolumeLevelScalar(volume_level / 100, None)
        else:
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
            
        import pyautogui
        key_map = {"previous": "prevtrack", "play_pause": "playpause", "next": "nexttrack"}
        key = key_map.get(action)
        if not key:
            return f"Unknown action '{action}'. Use play_pause, next, or previous."
        pyautogui.press(key)
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
    Manages the Windows clipboard history.

    Args:
        prompt: The user's original request.
        action: "open_history" to open the clipboard panel, "paste_item" to paste a specific entry.
        item_index: 1-based index of the clipboard item to paste (required for paste_item).
    """
    try:
        import pyautogui, time
        if action == "open_history":
            pyautogui.hotkey("win", "v")
            return "Clipboard history opened."
        elif action == "paste_item":
            if not item_index or item_index < 1:
                return "Please specify a valid item index (1 or greater)."
            pyautogui.hotkey("win", "v")
            time.sleep(0.5)
            for _ in range(item_index - 1):
                pyautogui.press("tab")
                time.sleep(0.1)
            pyautogui.press("enter")
            return f"Pasted clipboard item #{item_index}."
        return "Unknown clipboard action."
    except Exception as e:
        return f"Clipboard operation failed: {e}"


@function_tool
async def scan_system_for_viruses() -> str:
    """
    Runs a quick virus scan using Windows Defender and returns the summary.
    """
    if platform.system() != "Windows":
        return "Virus scanning via Windows Defender is only available on Windows."
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Start-MpScan -ScanType QuickScan; "
             "Get-MpThreatDetection | Select-Object -First 5 | Format-List"],
            capture_output=True, text=True, timeout=120,
        )
        output = (result.stdout or result.stderr or "").strip()
        if output:
            return f"Scan complete:\n{output[:800]}"
        return "Scan complete. No threats detected."
    except Exception as e:
        return f"Scan failed: {e}"
