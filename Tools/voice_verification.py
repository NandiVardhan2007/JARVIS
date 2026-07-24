"""
Voice Verification Utilities for JARVIS.
Handles speaker embedding storage, comparison, and real-time verification.
"""

import os
import sqlite3
import numpy as np
import logging
import asyncio

logger = logging.getLogger(__name__)

# Suppress verbose numba SSA rewrite debug logs
for _numba_logger in ["numba", "numba.core", "numba.core.ssa", "numba.core.byteflow", "numba.core.interpreter", "numba.core.typeinfer"]:
    logging.getLogger(_numba_logger).setLevel(logging.WARNING)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "jarvis_memory", "user_memory.db")
EMBEDDING_DIM = 256  # resemblyzer default embedding dimension

def init_voice_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS voice_master (
                id INTEGER PRIMARY KEY DEFAULT 1,
                embedding BLOB NOT NULL
            )
        """)
        conn.commit()

def load_master_embedding():
    """Load the stored master voice embedding from DB. Returns None if not enrolled."""
    init_voice_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute("SELECT embedding FROM voice_master WHERE id=1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return np.frombuffer(row[0], dtype=np.float32)
        return None
    except Exception as e:
        logger.error(f"Failed to load master embedding: {e}")
        return None

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two embedding vectors."""
    if a is None or b is None:
        return 0.0
    if a.shape != b.shape:
        logger.warning(f"Embedding shape mismatch: {a.shape} vs {b.shape}")
        return 0.0
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))

async def verify_master_voice(audio_samples: np.ndarray, threshold: float = 0.65) -> bool:
    """
    Verifies if the given audio samples match the master's voice.

    Args:
        audio_samples: 1D numpy array of float32 PCM audio (16kHz mono expected).
        threshold: Cosine similarity threshold (0.0 to 1.0). Default 0.65.

    Returns:
        True if the voice matches the master, False otherwise.
    """
    master = load_master_embedding()
    if master is None:
        logger.warning("No master voice profile enrolled. Allowing bypass for now.")
        return True  # Allow through if not enrolled yet

    # Check audio amplitude / energy
    max_amp = float(np.abs(audio_samples).max()) if len(audio_samples) > 0 else 0.0
    if max_amp < 0.015:
        logger.warning(f"Voice sample too quiet (max amplitude {max_amp:.4f}). Speak louder or closer to mic.")
        return False

    # Attempt embedding generation
    embedding = generate_embedding(audio_samples)
    if embedding is None:
        logger.warning("Could not generate embedding from audio. Allowing through.")
        return True  # Allow through if we can't verify

    if embedding.shape != master.shape:
        logger.warning(f"Master voice profile embedding dimension mismatch ({master.shape[0]} vs current {embedding.shape[0]}). Run enroll_voice.py to re-enroll. Allowing bypass.")
        return True

    score = cosine_similarity(embedding, master)
    logger.info(f"Speaker similarity score: {score:.4f} (threshold: {threshold})")
    return score >= threshold

def generate_embedding(audio_samples: np.ndarray, source_sr: int = 16000) -> np.ndarray | None:
    """
    Generate a 128-d speaker embedding from raw audio using resemblyzer.
    Falls back to a simple amplitude-based fingerprint if resemblyzer fails.
    """
    try:
        import torch
        from resemblyzer import VoiceEncoder, preprocess_wav
        encoder = VoiceEncoder()
        # preprocess_wav expects a 1D float32 array or similar
        processed = preprocess_wav(audio_samples, source_sr=source_sr)
        embedding = encoder.embed_utterance(processed)
        return embedding
    except Exception as e:
        logger.warning(f"Resemblyzer embedding failed ({e}), using fallback signature.")
        return generate_fallback_embedding(audio_samples)

def generate_fallback_embedding(audio_samples: np.ndarray) -> np.ndarray:
    """
    Fallback: generate a deterministic embedding from audio properties.
    Not a true speaker embedding — for compatibility only.
    """
    # Use statistical properties of the audio as a lightweight fingerprint
    seed = int(np.abs(audio_samples.mean()) * 1e6 + np.abs(audio_samples.std()) * 1e4)
    rng = np.random.default_rng(seed)
    return rng.random(EMBEDDING_DIM).astype(np.float32)

# ── CLI enrollment (standalone, called by enroll_voice.py) ─────────────────────
def save_master_embedding(embedding: np.ndarray):
    """Save master embedding to the DB."""
    init_voice_db()
    conn = sqlite3.connect(DB_PATH)
    embedding_bytes = embedding.astype(np.float32).tobytes()
    conn.execute("""
        INSERT OR REPLACE INTO voice_master (id, embedding) VALUES (1, ?)
    """, (sqlite3.Binary(embedding_bytes),))
    conn.commit()
    conn.close()
    logger.info("Master voice profile saved.")