"""
Cartesia Sonic Neural Voice Audition & Preview Utility for VISION.
Run this script to listen to Cartesia voice samples and test dynamic neural synthesis:
    python scripts/test_voices.py
"""

import asyncio
import io
import soundfile as sf
import sounddevice as sd
from vision.config import config
from vision.synthesis.cartesia_tts import CartesiaTTS

CARTESIA_VOICE_SAMPLES = [
    {"id": "1259b7e3-cb8a-43df-9446-30971a46b8b0", "label": "VISION Default Jarvis / Smooth Conversational Male"},
    {"id": "694f9389-aac1-45b6-b726-9d9369183238", "label": "Sarah (Natural Conversational Female)"},
    {"id": "a0e99841-438c-4a64-b679-ae501e7d6091", "label": "Barbershop Man (Deep American Male)"},
    {"id": "79a125e8-cd45-4c13-8a67-188112f4dd22", "label": "British Man (Refined Jarvis / Butler)"},
    {"id": "248be419-c632-4f23-adf1-5324ed7dbf1d", "label": "California Girl (Dynamic Modern Female)"},
]


async def preview_all():
    print("=" * 60)
    print("VISION Cartesia Sonic-2 Voice Audition")
    print("=" * 60)

    if not config.CARTESIA_API_KEY and not config.CARTESIA_API_KEYS:
        print("[!] ERROR: No Cartesia API keys found in .env (CARTESIA_API_KEY).")
        return

    tts = CartesiaTTS()

    for item in CARTESIA_VOICE_SAMPLES:
        voice_id = item["id"]
        label = item["label"]
        phrase = f"Hello Nandu! This is {label}. VISION is operating purely on Cartesia Sonic neural voice."

        print(f"\n▶ Playing Cartesia Voice: {label} ({voice_id[:8]}...)")
        try:
            audio_bytes = await tts.synthesize(phrase, voice_id=voice_id)
            if audio_bytes:
                with io.BytesIO(audio_bytes) as f:
                    data, fs = sf.read(f, dtype='float32')
                    sd.play(data, fs)
                    sd.wait()
            else:
                print("  [!] Failed to synthesize with this Cartesia voice.")
        except Exception as e:
            print(f"  [!] Synthesis error: {e}")

    print("\n" + "=" * 60)
    print("To set your favorite Cartesia voice, update .env with:")
    print(f"  CARTESIA_VOICE_ID={config.CARTESIA_VOICE_ID}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(preview_all())
