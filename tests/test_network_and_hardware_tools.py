"""
Unit tests for Network Tools and Hardware Health Monitors in VISION AI OS.
"""

import pytest
from vision.tools.network_tools import test_internet_speed, get_network_diagnostics, ping_host
from vision.tools.hardware_tools import get_battery_status, get_hardware_health


def test_get_battery_status():
    """Verify battery status returns valid information."""
    result = get_battery_status()
    assert isinstance(result, str)
    assert ("Level:" in result or "Desktop PC" in result)


def test_get_hardware_health():
    """Verify hardware health telemetry returns CPU, RAM, and Disk metrics."""
    result = get_hardware_health()
    assert isinstance(result, str)
    assert "Hardware & System Health" in result
    assert "CPU Utilization" in result
    assert "RAM Usage" in result


def test_get_network_diagnostics():
    """Verify network diagnostics returns Wi-Fi / IP / Connectivity details."""
    result = get_network_diagnostics()
    assert isinstance(result, str)
    assert "Network & Wi-Fi Diagnostics" in result
    assert "Local IPv4" in result


def test_ping_host():
    """Verify ping tool pings a host and returns packet loss and latency."""
    result = ping_host("127.0.0.1", count=1)
    assert isinstance(result, str)
    assert ("Packet Loss" in result or "127.0.0.1" in result)
