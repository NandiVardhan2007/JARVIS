"""
Voice Audition & Preview Utility for VISION.
Run this script to listen to voice samples and pick your favorite:
    python scripts/test_voices.py
"""

import asyncio
import io
import soundfile as sf
import sounddevice as sd
from vision.synthesis.player import audio_player

VOICE_SAMPLES = [
    # Edge-TTS Studio Neural Voices (Indistinguishable from real humans)
    {"engine": "edge_tts", "voice": "en-US-BrianNeural", "label": "Edge-TTS: Brian (Deep, natural, authoritative - Recommended)"},
    {"engine": "edge_tts", "voice": "en-US-GuyNeural", "label": "Edge-TTS: Guy (Crisp modern American assistant)"},
    {"engine": "edge_tts", "voice": "en-GB-RyanNeural", "label": "Edge-TTS: Ryan (British Jarvis / Butler style)"},
    {"engine": "edge_tts", "voice": "en-US-AndrewNeural", "label": "Edge-TTS: Andrew (Warm conversational male)"},
    {"engine": "edge_tts", "voice": "en-US-AriaNeural", "label": "Edge-TTS: Aria (Natural expressive female)"},
    {"engine": "edge_tts", "voice": "en-IN-PrabhatNeural", "label": "Edge-TTS: Prabhat (Indian English natural male)"},

    # Kokoro-82M ONNX (100% Local Offline Neural)
    {"engine": "kokoro", "voice": "bm_george", "label": "Kokoro-ONNX: George (British classic Jarvis)"},
    {"engine": "kokoro", "voice": "am_adam", "label": "Kokoro-ONNX: Adam (Deep American male)"},
    {"engine": "kokoro", "voice": "am_fenrir", "label": "Kokoro-ONNX: Fenrir (Cinematic deep male)"},
    {"engine": "kokoro", "voice": "af_bella", "label": "Kokoro-ONNX: Bella (Smooth natural female)"},
]


async def preview_all():
    from vision.synthesis.local_tts import local_tts
    print("=" * 60)
    print("VISION Voice Audition: Testing Local & Studio Neural Voices")
    print("=" * 60)

    for item in VOICE_SAMPLES:
        engine = item["engine"]
        voice = item["voice"]
        label = item["label"]
        phrase = f"Hello Nandu! This is {label}. How can I assist you with VISION today?"

        print(f"\n▶ Playing: {label}")
        if engine == "edge_tts":
            audio_bytes = await local_tts._synthesize_edge_tts(phrase, voice=voice)
        else:
            audio_bytes = await local_tts._synthesize_kokoro(phrase, voice=voice)

        if audio_bytes:
            with io.BytesIO(audio_bytes) as f:
                data, fs = sf.read(f, dtype='float32')
                sd.play(data, fs)
                sd.wait()
        else:
            print("  [!] Failed to synthesize with this engine/voice.")

    print("\n" + "=" * 60)
    print("To set your favorite voice, update .env with:")
    print("  VISION_LOCAL_TTS_ENGINE=edge_tts   (or kokoro)")
    print("  VISION_LOCAL_TTS_VOICE=en-US-BrianNeural   (or bm_george, etc.)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(preview_all())
