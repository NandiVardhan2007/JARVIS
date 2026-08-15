"""
Hardware Control Tools for VISION AI OS.
Provides native control for Windows audio volume, mute, display brightness, and screen lock.
"""

import ctypes
from typing import Optional
from vision.tools.registry import tool
from vision.logger import logger

try:
    from pycaw.pycaw import AudioUtilities
except ImportError:
    AudioUtilities = None

try:
    import screen_brightness_control as sbc
except ImportError:
    sbc = None


def _get_audio_endpoint():
    """Helper to retrieve active default audio endpoint volume interface."""
    if not AudioUtilities:
        return None
    try:
        return AudioUtilities.GetSpeakers().EndpointVolume
    except Exception as e:
        logger.error(f"[HardwareTools] Failed to get audio endpoint: {e}")
        return None


# ---------------- Volume Controls ----------------

@tool(name="set_volume", description="Set the PC master audio volume level (0 to 100).")
def set_volume(level: int) -> str:
    """Set system audio volume percentage (0-100)."""
    endpoint = _get_audio_endpoint()
    if not endpoint:
        return "Error: Audio device interface not available."

    clamped_level = max(0, min(100, int(level)))
    scalar = clamped_level / 100.0
    endpoint.SetMasterVolumeLevelScalar(scalar, None)
    # Automatically unmute if setting positive volume
    if clamped_level > 0 and endpoint.GetMute():
        endpoint.SetMute(0, None)

    logger.info(f"[HardwareTools] System volume set to {clamped_level}%")
    return f"System volume set to {clamped_level}%."


@tool(name="increase_volume", description="Increase system audio volume by a percentage step (e.g. step=10).")
def increase_volume(step: int = 10) -> str:
    """Increase system volume by step percent."""
    endpoint = _get_audio_endpoint()
    if not endpoint:
        return "Error: Audio device interface not available."

    curr_scalar = endpoint.GetMasterVolumeLevelScalar()
    curr_pct = round(curr_scalar * 100)
    new_pct = min(100, curr_pct + int(step))
    endpoint.SetMasterVolumeLevelScalar(new_pct / 100.0, None)
    if endpoint.GetMute():
        endpoint.SetMute(0, None)

    logger.info(f"[HardwareTools] Volume increased from {curr_pct}% to {new_pct}%")
    return f"Volume increased to {new_pct}%."


@tool(name="decrease_volume", description="Decrease system audio volume by a percentage step (e.g. step=10).")
def decrease_volume(step: int = 10) -> str:
    """Decrease system volume by step percent."""
    endpoint = _get_audio_endpoint()
    if not endpoint:
        return "Error: Audio device interface not available."

    curr_scalar = endpoint.GetMasterVolumeLevelScalar()
    curr_pct = round(curr_scalar * 100)
    new_pct = max(0, curr_pct - int(step))
    endpoint.SetMasterVolumeLevelScalar(new_pct / 100.0, None)

    logger.info(f"[HardwareTools] Volume decreased from {curr_pct}% to {new_pct}%")
    return f"Volume decreased to {new_pct}%."


@tool(name="mute_volume", description="Mute the system master audio output.")
def mute_volume() -> str:
    """Mute system master audio."""
    endpoint = _get_audio_endpoint()
    if not endpoint:
        return "Error: Audio device interface not available."

    endpoint.SetMute(1, None)
    logger.info("[HardwareTools] Audio output muted.")
    return "System audio muted."


@tool(name="unmute_volume", description="Unmute the system master audio output.")
def unmute_volume() -> str:
    """Unmute system master audio."""
    endpoint = _get_audio_endpoint()
    if not endpoint:
        return "Error: Audio device interface not available."

    endpoint.SetMute(0, None)
    logger.info("[HardwareTools] Audio output unmuted.")
    return "System audio unmuted."


@tool(name="get_volume_status", description="Get current audio volume percentage and mute status.")
def get_volume_status() -> str:
    """Check current volume level and mute status."""
    endpoint = _get_audio_endpoint()
    if not endpoint:
        return "Error: Audio device interface not available."

    curr_pct = round(endpoint.GetMasterVolumeLevelScalar() * 100)
    is_muted = bool(endpoint.GetMute())
    return f"Master Volume: {curr_pct}%, Muted: {'Yes' if is_muted else 'No'}"


# ---------------- Brightness Controls ----------------

@tool(name="set_brightness", description="Set the display screen brightness percentage (0 to 100).")
def set_brightness(level: int) -> str:
    """Set screen brightness percentage (0-100)."""
    if not sbc:
        return "Error: Screen brightness control not available."

    clamped_level = max(0, min(100, int(level)))
    try:
        sbc.set_brightness(clamped_level)
        logger.info(f"[HardwareTools] Screen brightness set to {clamped_level}%")
        return f"Screen brightness set to {clamped_level}%."
    except Exception as e:
        logger.error(f"[HardwareTools] Failed to set brightness: {e}")
        return f"Error setting brightness: {e}"


@tool(name="increase_brightness", description="Increase display screen brightness by a percentage step (e.g. step=10).")
def increase_brightness(step: int = 10) -> str:
    """Increase screen brightness by step percent."""
    if not sbc:
        return "Error: Screen brightness control not available."

    try:
        current = sbc.get_brightness()
        curr_val = current[0] if isinstance(current, list) else int(current)
        new_val = min(100, curr_val + int(step))
        sbc.set_brightness(new_val)
        logger.info(f"[HardwareTools] Brightness increased from {curr_val}% to {new_val}%")
        return f"Screen brightness increased to {new_val}%."
    except Exception as e:
        return f"Error adjusting brightness: {e}"


@tool(name="decrease_brightness", description="Decrease display screen brightness by a percentage step (e.g. step=10).")
def decrease_brightness(step: int = 10) -> str:
    """Decrease screen brightness by step percent."""
    if not sbc:
        return "Error: Screen brightness control not available."

    try:
        current = sbc.get_brightness()
        curr_val = current[0] if isinstance(current, list) else int(current)
        new_val = max(0, curr_val - int(step))
        sbc.set_brightness(new_val)
        logger.info(f"[HardwareTools] Brightness decreased from {curr_val}% to {new_val}%")
        return f"Screen brightness decreased to {new_val}%."
    except Exception as e:
        return f"Error adjusting brightness: {e}"


@tool(name="get_brightness_status", description="Get the current display screen brightness level.")
def get_brightness_status() -> str:
    """Check current brightness percentage."""
    if not sbc:
        return "Error: Screen brightness control not available."

    try:
        current = sbc.get_brightness()
        curr_val = current[0] if isinstance(current, list) else int(current)
        return f"Display Brightness: {curr_val}%"
    except Exception as e:
        return f"Error reading brightness: {e}"


# ---------------- System Security Controls ----------------

@tool(name="lock_screen", description="Immediately lock the Windows PC workstation.")
def lock_screen() -> str:
    """Lock the Windows workstation."""
    try:
        ctypes.windll.user32.LockWorkStation()
        logger.info("[HardwareTools] Workstation locked.")
        return "Windows workstation locked."
    except Exception as e:
        return f"Failed to lock workstation: {e}"
