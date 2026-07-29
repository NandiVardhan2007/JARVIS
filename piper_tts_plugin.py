import asyncio

from livekit.agents import tts
from piper import PiperVoice
from livekit.agents.tts.tts import DEFAULT_API_CONNECT_OPTIONS, shortuuid
import logging

logger = logging.getLogger(__name__)

# Suppress the spammy phoneme debug logs from piper
logging.getLogger("piper.voice").setLevel(logging.INFO)

def pcm_to_wav_bytes(pcm_bytes: bytes, sample_rate: int = 22050, num_channels: int = 1) -> bytes:
    import io, wave
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()

class PiperChunkedStream(tts.ChunkedStream):
    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        try:
            import re
            is_telugu = bool(re.search(r'[\u0c00-\u0c7f]', self.input_text))
            active_voice = self._tts.voice_te if (is_telugu and self._tts.voice_te) else self._tts.voice_en
            sample_rate = getattr(active_voice.config, 'sample_rate', 22050)

            pcm_chunks = []

            def generate_audio():
                for chunk in active_voice.synthesize(self.input_text):
                    pcm_chunks.append(chunk.audio_int16_bytes)

            await asyncio.to_thread(generate_audio)

            if not pcm_chunks:
                logger.warning(f"No audio synthesized for text: {self.input_text}")
                return

            full_pcm = b''.join(pcm_chunks)

            output_emitter.initialize(
                request_id=shortuuid(),
                sample_rate=sample_rate,
                num_channels=self._tts.num_channels,
                mime_type="audio/pcm",
                stream=False,
            )

            output_emitter.push(full_pcm)
            output_emitter.flush()
            output_emitter.end_input()

                
        except Exception as e:
            self._emit_error(e, recoverable=False)
            raise e



class PiperTTS(tts.TTS):
    def __init__(self, english_model: str = "models/en_US-ryan-high.onnx", 
                 telugu_model: str = "models/te_IN-venkatesh-medium.onnx"):
        import os
        base_dir = os.path.dirname(__file__)

        if not os.path.isabs(english_model):
            english_model = os.path.join(base_dir, english_model)
        self.voice_en = PiperVoice.load(english_model)
        
        if not os.path.isabs(telugu_model):
            telugu_model = os.path.join(base_dir, telugu_model)
            
        try:
            self.voice_te = PiperVoice.load(telugu_model)
        except Exception as e:
            logger.warning(f"Failed to load Telugu Piper voice: {e}")
            self.voice_te = None
        
        # Piper provides sample_rate in config, always 1 channel
        sample_rate = getattr(self.voice_en.config, 'sample_rate', 22050)
        num_channels = 1
        
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=sample_rate,
            num_channels=num_channels,
        )
        self._model_path = english_model
        
    @property
    def model(self) -> str:
        return "piper-multilingual"

    @property
    def provider(self) -> str:
        return "piper"
        
    def synthesize(self, text: str, *, conn_options = None) -> tts.ChunkedStream:
        if conn_options is None:
            conn_options = DEFAULT_API_CONNECT_OPTIONS
        return PiperChunkedStream(tts=self, input_text=text, conn_options=conn_options)
