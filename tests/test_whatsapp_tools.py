"""
Test suite for WhatsApp automation tools.
"""

from vision.tools.whatsapp_tools import send_whatsapp_message, save_whatsapp_contact_alias, _resolve_contact_from_memory
from vision.tools.registry import tool_registry


def test_whatsapp_tool_registered():
    assert "send_whatsapp_message" in tool_registry._tools
    assert "save_whatsapp_contact_alias" in tool_registry._tools


def test_whatsapp_tool_validation():
    res = send_whatsapp_message("", "")
    assert "Error" in res


def test_whatsapp_alias_tool():
    res = save_whatsapp_contact_alias("Bro", "Brother (College)")
    assert "Saved WhatsApp contact in memory" in res


def test_whatsapp_self_resolution():
    assert _resolve_contact_from_memory("myself") == "7337419275"
    assert _resolve_contact_from_memory("me") == "7337419275"
    assert _resolve_contact_from_memory("my number") == "7337419275"
