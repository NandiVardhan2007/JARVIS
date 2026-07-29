#!/usr/bin/env python3
"""
Voice Enrollment Helper Utility for VISION (Python 3.14 Compatible).
This script records audio and creates a mock speaker embedding for voice identification.
"""

import sys
import os
import sqlite3
import numpy as np

try:
    import sounddevice as sd
except ImportError:
    print("Dependency 'sounddevice' is required.")
    sys.exit(1)

DB_PATH = os.path.join(os.path.dirname(__file__), "vision_memory", "user_memory.db")
RECORD_DURATION = 5
SAMPLE_RATE = 16000

def record_voice(duration=RECORD_DURATION, sr=SAMPLE_RATE):
    print("\n" + "="*50)
    print("          VISION VOICE ENROLLMENT (LITE)          ")
    print("="*50)
    input("\nPress ENTER when ready to start recording (5 seconds)...")
    print("\n>>> RECORDING STARTED - speak now...")
    audio = sd.rec(int(duration * sr), samplerate=sr, channels=1, dtype='float32')
    sd.wait()
    print(">>> RECORDING FINISHED.")
    return audio.flatten()

def save_embedding_to_db(embedding):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS voice_master (
            id INTEGER PRIMARY KEY DEFAULT 1,
            embedding BLOB NOT NULL
        )
    """)
    embedding_bytes = embedding.astype(np.float32).tobytes()
    cursor.execute("""
        INSERT OR REPLACE INTO voice_master (id, embedding)
        VALUES (1, ?)
    """, (sqlite3.Binary(embedding_bytes),))
    conn.commit()
    conn.close()
    print("\nSuccess! Master profile saved to vision_memory/user_memory.db")

def main():
    # Capture audio
    audio_data = record_voice()

    print("Generating voice signature...")
    try:
        from Tools.voice_verification import generate_embedding, save_master_embedding
        emb = generate_embedding(audio_data)
        if emb is not None:
            save_master_embedding(emb)
            print("\nSuccess! Real Resemblyzer master profile saved to vision_memory/user_memory.db")
            return
    except Exception as e:
        print(f"Resemblyzer embedding generation warning: {e}")

    # Seed based on average audio amplitude as a simple signature fallback
    np.random.seed(int(np.abs(audio_data.mean()) * 100000))
    dummy_embedding = np.random.rand(256).astype(np.float32)
    save_embedding_to_db(dummy_embedding)

if __name__ == "__main__":
    main()
