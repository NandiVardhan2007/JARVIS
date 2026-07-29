"""
Voice Verification Utilities for VISION.
Handles speaker embedding storage, comparison, and real-time verification.
"""

import os
import sqlite3
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Suppress verbose numba SSA rewrite debug logs
for _numba_logger in ["numba", "numba.core", "numba.core.ssa", "numba.core.byteflow", "numba.core.interpreter", "numba.core.typeinfer"]:
    logging.getLogger(_numba_logger).setLevel(logging.WARNING)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vision_memory", "user_memory.db")
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

async def verify_master_voice(audio_samples: np.ndarray, threshold: float = 0.75) -> bool:

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


# ── Live re-authentication gate for sensitive actions ───────────────────────
# The startup voice lock in agent.py only verifies identity once per session.
# Anything destructive (shutdown, deleting files, financial actions, etc.)
# re-checks the live voice right before executing, so an unlocked session left
# running can't be used by someone else to do something irreversible.
async def require_live_master_voice(threshold: float = 0.7, record_seconds: float = 3.0) -> tuple[bool, str]:
    """
    Records a short clip from the live mic right now and checks it against the
    enrolled master voiceprint.

    Returns (ok, message). If no master voice is enrolled, this is a no-op
    that returns (True, "...") — voice auth is opt-in, gated on enrollment.
    """
    master = load_master_embedding()
    if master is None:
        return True, "No master voice enrolled — action allowed without re-verification."

    try:
        import sounddevice as sd
        import asyncio
        loop = asyncio.get_event_loop()
        audio = await loop.run_in_executor(
            None,
            lambda: sd.rec(
                int(record_seconds * 16000), samplerate=16000, channels=1,
                dtype="float32", blocking=True,
            ),
        )
        audio = audio.flatten()
    except Exception as e:
        logger.error(f"Live re-auth audio capture failed: {e}")
        return False, "Could not capture audio for voice re-verification. Action blocked for safety."

    matched = await verify_master_voice(audio, threshold=threshold)
    if matched:
        return True, "Voice re-verified."
    return False, "Voice re-verification failed — this doesn't sound like the registered master voice. Action blocked."


def requires_live_master_voice(threshold: float = 0.7):
    """
    Decorator for function_tools that perform a destructive/high-risk action.
    Re-checks the LIVE voice against the enrolled master right before running
    the wrapped function, so an unlocked session can't be used by someone
    else in the room to do something irreversible. No-ops safely if no
    master voice is enrolled (voice auth is opt-in).

    Usage:
        @function_tool
        @requires_live_master_voice()
        async def dangerous_thing(...) -> str:
            ...
    """
    def decorator(fn):
        import functools

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            ok, msg = await require_live_master_voice(threshold=threshold)
            if not ok:
                logger.warning(f"Blocked '{fn.__name__}': {msg}")
                return msg
            return await fn(*args, **kwargs)
        return wrapper
    return decorator


# ── Session-level authentication flag ───────────────────────────────────────
# agent.py sets this once the startup voice lock (or an explicit auth-disabled
# bypass) completes, so that tools — which don't have access to agent.py's
# local session variables — can still enforce "only after authentication"
# in code, not just via a hopeful system-prompt instruction.
_session_authenticated = False


def mark_session_authenticated(value: bool = True) -> None:
    global _session_authenticated
    _session_authenticated = value


def is_session_authenticated() -> bool:
    return _session_authenticated


async def reenroll_master_voice(sample_paragraph_audio: np.ndarray) -> str:
    """
    Securely re-enrolls the master voice. Requires the CURRENT session to
    already be authenticated (checked by the caller before invoking this —
    see agent.py's _auth_unlocked gate) and a fresh live sample of the
    provided paragraph audio, which becomes the new master embedding.
    """
    embedding = generate_embedding(sample_paragraph_audio)
    if embedding is None:
        return "Could not generate a voiceprint from that recording. Please try again in a quieter environment."
    save_master_embedding(embedding)
    logger.info("Master voice profile re-enrolled.")
    return "Master voice profile has been re-enrolled successfully."


ENROLLMENT_PARAGRAPH = (
    "I am VISION, and this is my voice. I am speaking clearly and naturally "
    "so my assistant can learn to recognise me anywhere in the room."
)


from livekit.agents import function_tool  # noqa: E402  (kept near the tool it defines)


@function_tool
async def start_voice_reenrollment() -> str:
    """
    Starts secure re-enrollment of the master voice. Only works on an
    already-authenticated session — this is enforced in code (not just by
    prompting), and additionally re-verifies the CURRENT master voice live
    before accepting a new one, so re-enrollment can't be used to silently
    swap in someone else's voice during an unlocked session.

    Before calling this tool, say the following sentence aloud to the user
    and ask them to read it back, then call this tool while they speak:
    "I am VISION, and this is my voice. I am speaking clearly and naturally
    so my assistant can learn to recognise me anywhere in the room."

    Records a fresh sample while they read it and replaces the stored
    master voiceprint.
    """
    if not is_session_authenticated():
        return "Re-enrollment requires an authenticated session. Please verify your identity first."

    # Extra safety: if a master voice is already enrolled, require a fresh
    # live match against it before allowing it to be overwritten.
    if load_master_embedding() is not None:
        ok, msg = await require_live_master_voice()
        if not ok:
            return f"Re-enrollment blocked: {msg}"

    try:
        import sounddevice as sd
        import asyncio
        logger.info("Re-enrollment: capturing new master voice sample...")
        loop = asyncio.get_event_loop()
        audio = await loop.run_in_executor(
            None,
            lambda: sd.rec(int(6 * 16000), samplerate=16000, channels=1, dtype="float32", blocking=True),
        )
        audio = audio.flatten()
    except Exception as e:
        return f"Could not capture audio for re-enrollment: {e}"

    return await reenroll_master_voice(audio)