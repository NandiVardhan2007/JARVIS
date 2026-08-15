"""
Audio Stream Capture & Voice Listener from local microphone with Voice Activity Detection.
Supports adaptive device selection, PortAudio fallback, and graceful error handling.
"""

import io
import time
import wave
from typing import Optional
from vision.logger import logger

try:
    import sounddevice as sd
    import numpy as np
except ImportError:
    sd = None
    np = None


class AudioStreamManager:
    def __init__(self, sample_rate: int = 16000, channels: int = 1, chunk_size: int = 1024):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self._mic_error_logged = False

    def is_mic_available(self) -> bool:
        if sd is None or np is None:
            return False
        try:
            dev = sd.query_devices(kind='input')
            return dev is not None
        except Exception:
            return False

    def record_phrase(
        self,
        energy_threshold: float = 0.012,
        silence_timeout: float = 1.2,
        max_duration: float = 25.0
    ) -> Optional[bytes]:
        """
        Listen on the microphone until speech is detected, record the utterance,
        and stop after silence_timeout seconds of silence. Returns WAV bytes.
        """
        if sd is None or np is None:
            return None

        frames = []
        is_speaking = False
        silence_start_time = None
        start_time = time.time()

        try:
            # Query default input device parameters
            dev_info = sd.query_devices(kind='input')
            native_rate = int(dev_info.get('default_samplerate', self.sample_rate))
            native_channels = min(self.channels, dev_info.get('max_input_channels', 1))

            with sd.InputStream(
                samplerate=native_rate,
                channels=native_channels,
                dtype="float32",
                blocksize=self.chunk_size
            ) as stream:
                self._mic_error_logged = False
                while True:
                    if time.time() - start_time > max_duration:
                        break

                    data, _ = stream.read(self.chunk_size)
                    rms = np.sqrt(np.mean(data**2))

                    if rms > energy_threshold:
                        if not is_speaking:
                            is_speaking = True
                        frames.append(data.copy())
                        silence_start_time = None
                    else:
                        if is_speaking:
                            frames.append(data.copy())
                            if silence_start_time is None:
                                silence_start_time = time.time()
                            elif time.time() - silence_start_time >= silence_timeout:
                                break

            if not frames or not is_speaking:
                return None

            audio_array = np.concatenate(frames, axis=0)
            int16_data = (audio_array * 32767).clip(-32768, 32767).astype(np.int16)

            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wf:
                wf.setnchannels(native_channels)
                wf.setsampwidth(2)
                wf.setframerate(native_rate)
                wf.writeframes(int16_data.tobytes())

            return wav_buffer.getvalue()

        except Exception as e:
            if not self._mic_error_logged:
                logger.warning(f"[AudioStream] Microphone capture unavailable ({e}). Please ensure Windows Microphone permissions are enabled.")
                self._mic_error_logged = True
            return None


audio_stream = AudioStreamManager()
