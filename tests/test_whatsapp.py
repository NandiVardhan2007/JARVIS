import pytest
from unittest.mock import patch
from Tools.whatsapp import send_whatsapp_media

@pytest.mark.asyncio
async def test_send_whatsapp_media_exception():
    with patch("pyautogui.hotkey", side_effect=Exception("Simulated hotkey error")):
        result = await send_whatsapp_media("Test Contact")
        assert "WhatsApp media send failed: Simulated hotkey error" in result
