"""
Groq Cloud STT Adapter using Whisper Large v3 Turbo (sub-300ms transcription).
"""

from io import BytesIO
from vision.perception.stt.base import BaseSTT
from vision.config import config
from vision.logger import logger

try:
    from groq import AsyncGroq
except ImportError:
    AsyncGroq = None


DEFAULT_PROMPT = (
    "VISION AI assistant, JARVIS, Python, YouTube, WhatsApp, weather, browser, "
    "terminal, system, music, open, search, remember, schedule, mute, unmute, "
    "volume, battery, memory, notes, status, run, execute."
)


class GroqSTT(BaseSTT):
    def __init__(self, api_key: str = None, model: str = None, prompt: str = None):
        super().__init__(name="Groq-Whisper")
        self.api_key = api_key or config.GROQ_API_KEY
        self.model = model or config.VISION_STT_MODEL or "whisper-large-v3-turbo"
        self.prompt = prompt or DEFAULT_PROMPT
        self.client = AsyncGroq(api_key=self.api_key) if AsyncGroq and self.api_key else None

    async def transcribe(self, audio_data: bytes, language: str = "en", filename: str = None, prompt: str = None) -> str:
        if not self.client:
            raise RuntimeError("groq library is not installed or API key missing.")
        try:
            ext_filename = "input.webm"
            if filename and "." in filename:
                ext_part = filename.rsplit(".", 1)[-1].lower()
                ext_filename = f"input.{ext_part}"
            elif audio_data.startswith(b"RIFF"):
                ext_filename = "input.wav"
            elif audio_data.startswith(b"OggS"):
                ext_filename = "input.ogg"
            elif audio_data.startswith(b"\x1a\x45\xdf\xa3") or b"webm" in audio_data[:64] or b"matroska" in audio_data[:64]:
                ext_filename = "input.webm"

            audio_file = BytesIO(audio_data)
            audio_file.name = ext_filename

            prompt_text = prompt or self.prompt
            transcription = await self.client.audio.transcriptions.create(
                file=audio_file,
                model=self.model,
                language=language if language and language != "auto" else None,
                prompt=prompt_text,
                temperature=0.0,
                response_format="text"
            )
            text = str(transcription).strip()
            logger.debug(f"[GroqSTT] Transcribed ({len(audio_data)} bytes) -> '{text}'")
            return text
        except Exception as e:
            logger.error(f"[GroqSTT] Transcription failed: {e}")
            raise e
