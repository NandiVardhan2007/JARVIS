"""IoT control — ESP32-connected AC bulb via HTTP."""

import logging
import os
import requests
from typing import Literal
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DEFAULT_ESP32_IP = os.getenv("JARVIS_ESP32_IP", "10.216.226.11")


@function_tool
async def control_ac_bulb(
    action: Literal["on", "off", "status"],
    ip_address: str = DEFAULT_ESP32_IP,
    timeout: int = 5,
) -> str:
    """
    Controls an ESP32-connected AC bulb over the local network.

    WARNING: This controls 220V AC equipment. Ensure proper installation.

    Args:
        action: "on" to switch on, "off" to switch off, "status" to query state.
        ip_address: ESP32 device IP address (default: 10.216.226.11).
        timeout: HTTP request timeout in seconds (default: 5).
    """
    base = f"http://{ip_address}"

    if action == "status":
        try:
            resp = requests.get(f"{base}/status", timeout=timeout)
            if resp.status_code == 200:
                ct = resp.headers.get("content-type", "")
                state = resp.json().get("state", "unknown") if "json" in ct else resp.text.strip()
                return f"Bulb status: {state} (response time: {resp.elapsed.total_seconds():.2f}s)"
            return f"ESP32 returned HTTP {resp.status_code}."
        except requests.Timeout:
            return f"Request timed out. Verify ESP32 at {ip_address} is online."
        except Exception as e:
            return f"Status check failed: {e}"

    endpoint = "/on" if action == "on" else "/off"
    try:
        resp = requests.get(f"{base}{endpoint}", timeout=timeout)
        if resp.status_code == 200:
            return f"Bulb turned {action} successfully."
        return f"Control failed — HTTP {resp.status_code}. Check device power and WiFi."
    except requests.Timeout:
        return f"ESP32 not responding. Check device at {ip_address}."
    except Exception as e:
        return (
            f"Critical failure: {e}\n"
            "Emergency: disconnect ESP32 power immediately if in an unsafe state."
        )
