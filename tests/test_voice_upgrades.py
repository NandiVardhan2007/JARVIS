"""
Unit and integration tests for VISION Voice & Latency Upgrades:
- Full-Duplex Interruption & Barge-in
- SmartTTSEngine multi-tier failover
- LocalTTS offline synthesis
- Pipelined sentence synthesis & chunking
"""

import pytest
import asyncio
from vision.synthesis.player import AudioPlayer, audio_player
from vision.synthesis.local_tts import LocalTTS
from vision.synthesis.smart_tts import SmartTTSEngine
from vision.core.engine import VisionEngine, clean_text_for_speech


@pytest.mark.asyncio
async def test_audio_player_interrupt():
    """Test that AudioPlayer responds immediately to stop() and sets interrupt event."""
    player = AudioPlayer()
    assert not player.is_interrupted()
    player.stop()
    assert player.is_interrupted()
    player.reset_interrupt()
    assert not player.is_interrupted()


@pytest.mark.asyncio
async def test_local_tts_synthesis():
    """Test that LocalTTS can synthesize text into valid audio bytes."""
    import io
    import soundfile as sf
    local_engine = LocalTTS()
    audio_bytes = await local_engine.synthesize("Testing VISION zero latency local TTS.")
    assert isinstance(audio_bytes, bytes)
    assert len(audio_bytes) > 100
    with io.BytesIO(audio_bytes) as f:
        data, sr = sf.read(f, dtype='float32')
        assert len(data) > 0
        assert sr in (16000, 22050, 24000, 44100, 48000)


@pytest.mark.asyncio
async def test_use_cartesia_voice_toggle(monkeypatch):
    """Test that toggling USE_CARTESIA_VOICE to False routes directly to LocalTTS."""
    import vision.config
    monkeypatch.setattr(vision.config.config, "USE_CARTESIA_VOICE", False)
    smart_engine = SmartTTSEngine()
    audio_bytes = await smart_engine.synthesize("Testing local toggle routing.")
    assert isinstance(audio_bytes, bytes)
    assert len(audio_bytes) > 100




def test_clean_text_for_speech():
    """Test markdown normalization and cleaning for speech output."""
    raw = "Here is the plan:\n\n* First item\n* Second item\n\n```python\nprint('hello')\n```\nDone!"
    cleaned = clean_text_for_speech(raw)
    assert "```" not in cleaned
    assert "First item" in cleaned
    assert "Second item" in cleaned
    assert "Done!" in cleaned


@pytest.mark.asyncio
async def test_speak_pipelined_interruption():
    """Test that speak_pipelined stops when audio_player is interrupted."""
    engine = VisionEngine()
    audio_player.stop()  # Pre-interrupt
    result = await engine.speak_pipelined("Sentence one. Sentence two. Sentence three.")
    assert result is False  # Should abort due to barge-in interrupt
    audio_player.reset_interrupt()
