import asyncio
import io
import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Optional
from vision.synthesis.base import BaseTTS
from vision.config import config
from vision.logger import logger


try:
    import edge_tts
except ImportError:
    edge_tts = None

try:
    from kokoro_onnx import Kokoro
    import soundfile as sf
except ImportError:
    Kokoro = None
    sf = None


class LocalTTS(BaseTTS):
    """
    High-performance local & offline TTS engine:
    1. Edge-TTS (Microsoft Azure Studio Neural Voices — e.g. en-US-BrianNeural, en-US-GuyNeural, en-GB-RyanNeural)
    2. Kokoro-82M ONNX (100% offline local neural model — e.g. bm_george, am_adam, am_fenrir, af_bella)
    3. Windows SAPI5 / System.Speech (Zero-dependency native fallback)
    """
    def __init__(self, voice_name: Optional[str] = None):
        super().__init__(name="Local-HybridTTS")
        self._kokoro = None
        self._sapi_available = False
        self._check_capabilities()

    @property
    def preferred_engine(self) -> str:
        return getattr(config, "VISION_LOCAL_TTS_ENGINE", "edge_tts").lower().strip()

    @property
    def current_voice(self) -> str:
        return getattr(config, "VISION_LOCAL_TTS_VOICE", "en-US-BrianNeural").strip()

    def _check_capabilities(self):
        # 1. Check Kokoro model files in data/models/kokoro
        onnx_path = Path("data/models/kokoro/kokoro-v1.0.int8.onnx")
        voices_path = Path("data/models/kokoro/voices-v1.0.bin")
        if Kokoro is not None and onnx_path.exists() and voices_path.exists():
            try:
                self._kokoro = Kokoro(str(onnx_path), str(voices_path))
                logger.info("[LocalTTS] Kokoro-82M ONNX offline neural engine loaded successfully.")
            except Exception as e:
                logger.warning(f"[LocalTTS] Kokoro init error: {e}")

        # 2. Check SAPI5
        try:
            import win32com.client
            self._sapi_available = True
        except Exception:
            self._sapi_available = False

    async def _synthesize_kokoro(self, text: str, voice: Optional[str] = None) -> Optional[bytes]:
        """Synthesize using local Kokoro-ONNX neural model."""
        if self._kokoro is None or sf is None:
            return None
        k_voice = voice or (self.current_voice if self.current_voice.startswith(("af_", "am_", "bf_", "bm_")) else "bm_george")
        try:
            def _create_audio():
                samples, sample_rate = self._kokoro.create(
                    text,
                    voice=k_voice,
                    speed=1.0,
                    lang="en-us"
                )
                buf = io.BytesIO()
                sf.write(buf, samples, sample_rate, format="WAV")
                return buf.getvalue()

            return await asyncio.to_thread(_create_audio)
        except Exception as e:
            logger.debug(f"[LocalTTS] Kokoro synthesis error ({k_voice}): {e}")
            return None

    async def _synthesize_edge_tts(self, text: str, voice: Optional[str] = None) -> Optional[bytes]:
        """Synthesize using Edge-TTS neural stream."""
        if edge_tts is None:
            return None
        e_voice = voice or (self.current_voice if "Neural" in self.current_voice else "en-US-BrianNeural")
        try:
            communicate = edge_tts.Communicate(text, e_voice)
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio":
                    audio_data += chunk.get("data", b"")
            if audio_data:
                return audio_data
        except Exception as e:
            logger.debug(f"[LocalTTS] Edge-TTS error ({e_voice}): {e}")
        return None

    def _synthesize_sapi_sync(self, text: str) -> bytes:
        """Render speech to WAV bytes synchronously using SAPI5 voice stream."""
        try:
            import win32com.client
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            stream = win32com.client.Dispatch("SAPI.SpFileStream")
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            stream.Format.Type = 22  # SAFT22kHz16BitMono
            stream.Open(tmp_path, 3) # SSFMCreateForWrite
            speaker.AudioOutputStream = stream
            speaker.Speak(text)
            stream.Close()

            with open(tmp_path, "rb") as f:
                wav_bytes = f.read()

            try:
                os.remove(tmp_path)
            except Exception:
                pass

            return wav_bytes
        except Exception as e:
            logger.error(f"[LocalTTS] SAPI synthesis error: {e}")
            return b""

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to audio bytes with multi-engine ranking based on config."""
        if not text or not text.strip():
            return b""

        clean_text = text.strip()
        engine_pref = self.preferred_engine

        # If user prefers Kokoro
        if engine_pref == "kokoro":
            if self._kokoro is not None:
                audio = await self._synthesize_kokoro(clean_text)
                if audio:
                    return audio
            if edge_tts is not None:
                audio = await self._synthesize_edge_tts(clean_text)
                if audio:
                    return audio
        else:
            # Default: Edge-TTS (ultra-natural studio Azure voices)
            if edge_tts is not None:
                audio = await self._synthesize_edge_tts(clean_text)
                if audio:
                    return audio
            if self._kokoro is not None:
                audio = await self._synthesize_kokoro(clean_text)
                if audio:
                    return audio

        # Fallback to Windows SAPI5
        if self._sapi_available:
            audio = await asyncio.to_thread(self._synthesize_sapi_sync, clean_text)
            if audio:
                return audio

        # Fallback to PowerShell
        try:
            return await asyncio.to_thread(self._synthesize_powershell_sync, clean_text)
        except Exception as e:
            logger.error(f"[LocalTTS] PowerShell fallback TTS error: {e}")
            return b""


        # 3. Try Windows SAPI5
        if self._sapi_available:
            audio = await asyncio.to_thread(self._synthesize_sapi_sync, clean_text)
            if audio:
                return audio

        # 4. Fallback to PowerShell speech synthesizer
        try:
            return await asyncio.to_thread(self._synthesize_powershell_sync, clean_text)
        except Exception as e:
            logger.error(f"[LocalTTS] PowerShell fallback TTS error: {e}")
            return b""

    def _synthesize_powershell_sync(self, text: str) -> bytes:
        """Fallback synthesis via Windows PowerShell speech synthesizer."""
        import subprocess
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        escaped = text.replace('"', '`"').replace("'", "''")
        ps_cmd = (
            f"Add-Type -AssemblyName System.Speech; "
            f"$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$synth.SetOutputToWaveFile('{tmp_path}'); "
            f"$synth.Speak('{escaped}'); "
            f"$synth.Dispose()"
        )
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, timeout=5)
            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 44:
                with open(tmp_path, "rb") as f:
                    data = f.read()
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                return data
        except Exception as e:
            logger.debug(f"[LocalTTS] PowerShell TTS subproc error: {e}")
        return b""

    async def stream_synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        audio_bytes = await self.synthesize(text)
        if audio_bytes:
            yield audio_bytes


local_tts = LocalTTS()

