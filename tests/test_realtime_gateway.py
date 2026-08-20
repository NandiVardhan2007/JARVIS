"""
Unit tests for the OpenAI Realtime Protocol (/v1/realtime) Gateway in VISION.
"""

import asyncio
import base64
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from vision.gateways.web.server import app
from vision.gateways.web.realtime import pcm16_to_wav, RealtimeSession


def test_pcm16_to_wav_conversion():
    """Verify raw PCM16 byte array is properly wrapped with standard RIFF WAV header."""
    raw_pcm = bytes([0] * 3200)  # 100ms of 16kHz 16-bit mono silence
    wav_bytes = pcm16_to_wav(raw_pcm, sample_rate=16000, channels=1)
    
    assert wav_bytes.startswith(b"RIFF")
    assert b"WAVE" in wav_bytes
    assert len(wav_bytes) > len(raw_pcm)


@pytest.mark.asyncio
async def test_realtime_session_lifecycle():
    """Test RealtimeSession initialization, event handling, and event emitting."""
    mock_ws = AsyncMock()
    session = RealtimeSession(mock_ws)

    # 1. Initialize session
    await session.initialize()
    assert mock_ws.send_text.called
    sent_payload = json.loads(mock_ws.send_text.call_args[0][0])
    assert sent_payload["type"] == "session.created"
    assert sent_payload["session"]["id"] == session.session_id

    # 2. Session update
    await session.handle_event({
        "type": "session.update",
        "session": {
            "instructions": "You are JARVIS",
            "voice": "sonic-2"
        }
    })
    assert session.instructions == "You are JARVIS"

    # 3. Audio buffer append & clear
    fake_audio_chunk = base64.b64encode(b"\x00\x00" * 800).decode("utf-8")
    await session.handle_event({
        "type": "input_audio_buffer.append",
        "audio": fake_audio_chunk
    })
    assert len(session.audio_buffer) == 1600

    await session.handle_event({
        "type": "input_audio_buffer.clear"
    })
    assert len(session.audio_buffer) == 0

    # 4. Cleanup
    await session.close()


@pytest.mark.asyncio
async def test_realtime_response_and_bargein():
    """Test realtime response dispatching and barge-in cancellation."""
    mock_ws = AsyncMock()
    session = RealtimeSession(mock_ws)

    with patch("vision.gateways.web.realtime.vision_engine.process_user_input", new_callable=AsyncMock) as mock_engine:
        mock_engine.return_value = {
            "status": "success",
            "response": "Hello Nandu, system is ready!"
        }
        with patch.object(session, "send_event", new_callable=AsyncMock):
            with patch("vision.gateways.web.realtime.cartesia_tts.synthesize", new_callable=AsyncMock) as mock_tts:
                mock_tts.return_value = b"RIFFfakeaudio"

                # Trigger text query
                await session.handle_event({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "Hello Vision"}]
                    }
                })

                # Give asyncio loop a moment to run the background task
                await asyncio.sleep(0.05)

                # Test barge-in cancellation
                await session.cancel_active_response()
                assert not session._is_responding

    await session.close()
