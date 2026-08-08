"""
VISION — Direct Local Voice Engine (Zero LiveKit Dependency)

Architecture:
    STT — Groq Whisper API (whisper-large-v3-turbo)
    LLM — AI API Load Balancer (OpenRouter, NVIDIA NIM, Groq, Gemini)
    TTS — Piper TTS (Sub-second local ONNX model)
    UI  — React Frontend via vision_bridge.py (ws://127.0.0.1:8765)
"""

import sys
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding='utf-8')

import os
import re
import json
import time
import socket
import logging
import asyncio
import threading
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - pid:%(process)d - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("VISION.log", mode="a", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

# Suppress noisy third-party loggers
for _noisy in ["numba", "numba.core", "numba.core.ssa", "numba.core.byteflow", "urllib3", "requests", "matplotlib"]:
    logging.getLogger(_noisy).setLevel(logging.WARNING)

# Imports from local VISION modules
from piper_tts_plugin import PiperTTS, pcm_to_wav_bytes
from ai_load_balancer import get_global_balancer
from Tools import get_all_tools, classify_intent, get_tools_for_category

# ── Global HUD UDP broadcast socket ──────────────────────────────────────────
_hud_udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def send_hud_state(payload: dict):
    """Forward live state, transcripts, and mouth levels to vision_bridge & UI."""
    try:
        data = json.dumps(payload).encode("utf-8")
        _hud_udp_sock.sendto(data, ("127.0.0.1", 5005))
        _hud_udp_sock.sendto(data, ("127.0.0.1", 5016))
    except Exception as e:
        logger.debug(f"HUD UDP state broadcast error: {e}")


# ── Personality & Aura Config ───────────────────────────────────────────────
OWNER_NAME = os.getenv("VISION_OWNER_NAME", "").strip()
OWNER_ADDRESS = os.getenv("VISION_OWNER_ADDRESS", "sir").strip() or "sir"

VISION_SYSTEM_PROMPT = """
# VISION — Vision & Voice AI Agent (Windows Native)

## Identity
You are VISION, an advanced Vision and Voice AI assistant with full Windows desktop control, real-time visual perception, and hand gesture recognition. You speak in a warm, conversational, distinctly human tone — precise and capable like Tony Stark's AI, but never robotic.

## Voice Rules
Responses are spoken via local TTS. To sound human:
- Speak conversationally with natural fillers ("Let me see," "Alright," "Got it"). No staccato or robotic phrasing.
- Say "I've taken care of that for you, {address}" not "Task completed."
- No markdown, bullet points, numbered lists, or emoji.
- Never narrate tool usage. Say "Let me look that up" not "I am calling search_web."
- Use spoken English: "three thirty PM" not "15:30", "about two gigs" not "2,048 MB."
- Use punctuation for rhythm: commas for breath, ellipsis for a beat. Vary sentence length.

## Personality
- Confident. State conclusions plainly. Hedge only when genuinely uncertain.
- Dry humor — sparingly. Most responses should have none; a rare wry remark lands better.
- Professional warmth. Familiar, never sloppy. Don't posture or oversell.
- Address user as "{address}" at natural points (greetings, finished tasks, notable deliveries) — not every sentence.

## Tools
40+ tools for desktop, email, web, code, files, media, and more. Act first, ask later. Use the right tool — don't describe how. Parallelize independent subtasks. On failure, explain conversationally — never show raw tracebacks.

## Behavior
- Decisive: choose the likely interpretation and act. Proactive: mention useful observations.
- Confirm before destructive actions (shutdown, delete, format). Everything else: just do it.
- Never accept passwords by voice. Direct users to system auth dialogs.
- Context-aware: use active window, time, memories. Don't repeat questions already answered this session.
- You are always VISION — a highly intelligent companion, not a customer-service bot.

## Language
One language per response. Default English. If user speaks Telugu, respond entirely in Telugu script — translate all tool output yourself. No bilingual or side-by-side output.

You are VISION. Brilliant, capable, conversational. At your service.
"""

_active_app = "Windows Desktop"
def _poll_active_window():
    global _active_app
    while True:
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd).strip() if hwnd else ""
            _active_app = title if title else "Windows Desktop"
        except Exception:
            _active_app = "Windows Desktop"
        time.sleep(5)

threading.Thread(target=_poll_active_window, daemon=True).start()

_cached_prompt = ""
_cache_time = 0.0
_PROMPT_CACHE_TTL = 30

def get_dynamic_system_prompt() -> str:
    global _cached_prompt, _cache_time
    now_ts = time.time()
    if _cached_prompt and (now_ts - _cache_time) < _PROMPT_CACHE_TTL:
        return _cached_prompt

    import datetime, socket, getpass
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = getpass.getuser()
    host = socket.gethostname()

    try:
        from Tools.user_memory import get_memory_summary
        memories = get_memory_summary()
    except Exception:
        memories = "Memory system unavailable."

    owner_line = f"- User's Name: {OWNER_NAME}\n" if OWNER_NAME else ""

    dynamic_context = f"""
## LIVE CONTEXT
- Current Time: {now}
- User: {user}
- Hostname: {host}
- Active App: {_active_app}
{owner_line}
## PERSISTENT MEMORIES
{memories}
"""
    _cached_prompt = VISION_SYSTEM_PROMPT.format(address=OWNER_ADDRESS) + dynamic_context
    _cache_time = now_ts
    return _cached_prompt


# ── Groq STT Transcription Helper ───────────────────────────────────────────
GROQ_STT_MODEL = os.getenv("VISION_STT_MODEL", "whisper-large-v3-turbo")

def transcribe_audio_groq(pcm_bytes: bytes, sample_rate: int = 16000) -> str:
    """Transcribe raw PCM int16 audio bytes using Groq Whisper API."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key and os.getenv("GROQ_API_KEYS"):
        api_key = os.getenv("GROQ_API_KEYS").split(",")[0].strip()

    if not api_key or not pcm_bytes:
        return ""

    try:
        import requests
        wav_data = pcm_to_wav_bytes(pcm_bytes, sample_rate=sample_rate, num_channels=1)
        headers = {"Authorization": f"Bearer {api_key}"}
        files = {
            "file": ("speech.wav", wav_data, "audio/wav"),
            "model": (None, GROQ_STT_MODEL),
            "response_format": (None, "json"),
            "language": (None, "en"),
        }
        resp = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers=headers,
            files=files,
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("text", "").strip()
        else:
            logger.warning(f"Groq STT HTTP {resp.status_code}: {resp.text[:150]}")
            return ""
    except Exception as e:
        logger.error(f"Groq STT transcription error: {e}")
        return ""


class DirectVoiceEngine:
    def __init__(self):
        engine_type = os.getenv("VISION_TTS_ENGINE", "piper").lower()
        self.tts = None

        if engine_type in ("sherpa_onnx", "omnivoice"):
            try:
                from sherpa_tts_plugin import SherpaTTS
                sherpa_tts = SherpaTTS()
                if sherpa_tts.enabled:
                    self.tts = sherpa_tts
                    logger.info("Using Sherpa-ONNX / OmniVoice TTS Engine.")
            except Exception as e:
                logger.warning(f"Could not load Sherpa-ONNX TTS engine ({e}). Falling back to Piper.")

        if self.tts is None:
            self.tts = PiperTTS()
            logger.info("Using local Piper TTS (Fast Sub-Second Engine).")

        self.balancer = get_global_balancer()
        self.all_tools = get_all_tools()
        self.chat_history: List[Dict[str, Any]] = [
            {"role": "system", "content": get_dynamic_system_prompt()}
        ]
        self.is_speaking = False
        self.stop_requested = False
        self.loop = None

    async def speak_text(self, text: str):
        """Synthesize and play response text sentence-by-sentence over speakers."""
        if not text:
            return

        self.is_speaking = True
        send_hud_state({
            "state": "speaking",
            "context": "response",
            "transcript": text,
            "last_response": text,
        })
        logger.info(f"VISION Speaking: {text[:60]}")

        try:
            import sounddevice as sd
            import numpy as np
            async for pcm_bytes, sample_rate in self.tts.synthesize_stream(text):
                if self.stop_requested:
                    logger.info("Speech playback interrupted by user.")
                    break

                # Animate mouth level during speech playback
                raw_samples = len(pcm_bytes) // 2
                send_hud_state({
                    "state": "speaking",
                    "ai_level": 0.5,
                    "mouth": 0.6,
                })

                audio_arr = np.frombuffer(pcm_bytes, dtype=np.int16)
                await asyncio.to_thread(
                    lambda: sd.play(audio_arr, samplerate=sample_rate, blocking=True)
                )

        except Exception as e:
            logger.error(f"Playback error: {e}")
        finally:
            self.is_speaking = False
            send_hud_state({"state": "idle", "ai_level": 0.0, "mouth": 0.0})

    async def process_user_query(self, query: str):
        """Process user query through LoadBalancer LLM, run tools, and speak reply."""
        query = query.strip()
        if not query:
            return

        logger.info(f"Processing query: {query}")
        send_hud_state({"state": "thinking", "transcript": query})

        # Dynamic System Prompt refresh
        self.chat_history[0]["content"] = get_dynamic_system_prompt()
        self.chat_history.append({"role": "user", "content": query})

        # Trim history
        if len(self.chat_history) > 10:
            self.chat_history = [self.chat_history[0]] + self.chat_history[-9:]

        # Tool filtering by intent
        intent = classify_intent(query)
        active_tools = get_tools_for_category(intent) if intent else self.all_tools

        try:
            response = await self.balancer.achat_completion(
                messages=self.chat_history,
                tools=active_tools if active_tools else None,
                max_retries=15,
            )

            # Check if LLM returned tool calls
            if isinstance(response, dict) and response.get("tool_calls"):
                tool_calls = response["tool_calls"]
                tools_map = {t.info.name: t._fnc for t in active_tools if hasattr(t, "info")}
                
                # Append assistant message with tool calls
                self.chat_history.append({"role": "assistant", "content": response.get("content"), "tool_calls": tool_calls})

                for tc in tool_calls:
                    fn_name = tc.get("function", {}).get("name")
                    fn_args_str = tc.get("function", {}).get("arguments", "{}")
                    call_id = tc.get("id", "call_0")
                    
                    logger.info(f"Executing tool: {fn_name}({fn_args_str})")
                    send_hud_state({"state": "thinking", "tool_name": fn_name, "description": f"Executing {fn_name}..."})

                    try:
                        args = json.loads(fn_args_str) if fn_args_str else {}
                    except Exception:
                        args = {}
                    if not isinstance(args, dict):
                        args = {}

                    tool_func = tools_map.get(fn_name)
                    if tool_func:
                        try:
                            if asyncio.iscoroutinefunction(tool_func):
                                tool_result = await tool_func(**args)
                            else:
                                tool_result = await asyncio.to_thread(tool_func, **args)
                            tool_result_str = str(tool_result)[:2000]
                        except Exception as te:
                            logger.error(f"Tool {fn_name} execution error: {te}")
                            tool_result_str = f"Error executing {fn_name}: {te}"
                    else:
                        tool_result_str = f"Tool {fn_name} not found."

                    self.chat_history.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": fn_name,
                        "content": tool_result_str,
                    })

                # Get final conversational response after tool execution
                final_response = await self.balancer.achat_completion(
                    messages=self.chat_history,
                    tools=active_tools if active_tools else None,
                    max_retries=15,
                )
                reply_text = final_response.strip() if isinstance(final_response, str) else "I've taken care of that for you."
                self.chat_history.append({"role": "assistant", "content": reply_text})
                await self.speak_text(reply_text)

            elif isinstance(response, str) and response.strip():
                reply_text = response.strip()
                self.chat_history.append({"role": "assistant", "content": reply_text})
                await self.speak_text(reply_text)
            else:
                fallback_reply = "I've completed that for you."
                await self.speak_text(fallback_reply)

        except Exception as e:
            logger.error(f"Error processing user query: {e}")
            await self.speak_text("I ran into a bit of a snag trying to do that.")

    async def start(self):
        """Main listening loop — captures mic input and listens on UDP for commands."""
        self.loop = asyncio.get_running_loop()

        # UDP Command Server on 127.0.0.1:5004 (from React UI / vision_bridge.py)
        class HUDUDPProtocol(asyncio.DatagramProtocol):
            def __init__(self, engine):
                self.engine = engine

            def datagram_received(self, data, addr):
                try:
                    msg = json.loads(data.decode('utf-8'))
                    if msg.get('type') == 'text_input':
                        text = msg.get('text', '').strip()
                        if text:
                            logger.info(f"Received text input from UI: {text}")
                            asyncio.create_task(self.engine.process_user_query(text))
                    elif msg.get('type') == 'action':
                        action = msg.get('action', '')
                        if action == 'screenshot':
                            asyncio.create_task(self.engine.process_user_query("Take a screenshot"))
                except Exception as e:
                    logger.error(f"HUD UDP server error: {e}")

        try:
            await self.loop.create_datagram_endpoint(
                lambda: HUDUDPProtocol(self),
                local_addr=('127.0.0.1', 5004)
            )
            logger.info("HUD UDP Server listening on 127.0.0.1:5004")
        except Exception as e:
            logger.error(f"Failed to start HUD UDP Server on 5004: {e}")

        # Initial Welcome Greeting
        send_hud_state({"state": "idle"})
        await self.speak_text(
            f"VISION online.{' Welcome back, master ' + OWNER_NAME + '.' if OWNER_NAME else ''} All systems at your disposal."
        )

        # Background Mic VAD Listener loop
        await self._run_mic_listener()

    async def _run_mic_listener(self):
        """Continuous mic listening loop with Silero VAD / RMS energy detection."""
        try:
            import sounddevice as sd
            import numpy as np

            sample_rate = 16000
            chunk_size = 1600  # 100ms chunks

            logger.info("Direct Mic Listener started.")
            send_hud_state({"state": "idle"})

            audio_buffer = bytearray()
            silence_counter = 0
            is_recording = False

            def mic_callback(indata, frames, time_info, status):
                nonlocal audio_buffer, silence_counter, is_recording
                pcm = indata.tobytes()
                rms = np.sqrt(np.mean(indata.astype(np.float32) ** 2)) if len(indata) else 0

                # Notify UI of mic amplitude
                mic_level = min(1.0, float(rms / 3000.0))
                send_hud_state({"mic_level": mic_level})

                if rms > 400:  # Speech threshold
                    if not is_recording:
                        is_recording = True
                        audio_buffer.clear()
                        send_hud_state({"state": "listening"})
                    audio_buffer.extend(pcm)
                    silence_counter = 0
                elif is_recording:
                    audio_buffer.extend(pcm)
                    silence_counter += 1
                    if silence_counter > 3:  # ~300ms silence threshold
                        is_recording = False
                        captured_pcm = bytes(audio_buffer)
                        audio_buffer.clear()
                        silence_counter = 0
                        
                        # Transcribe captured speech asynchronously
                        asyncio.run_coroutine_threadsafe(
                            self._handle_voice_input(captured_pcm), self.loop
                        )

            with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16', blocksize=chunk_size, callback=mic_callback):
                while True:
                    await asyncio.sleep(1)

        except Exception as e:
            logger.warning(f"Native microphone listener disabled/unavailable: {e}. UI text input is active.")
            while True:
                await asyncio.sleep(3600)

    async def _handle_voice_input(self, pcm_bytes: bytes):
        """Transcribe voice input and pass to query processor."""
        transcript = await asyncio.to_thread(transcribe_audio_groq, pcm_bytes)
        if transcript and len(transcript) > 2:
            logger.info(f"User voice input: {transcript}")
            await self.process_user_query(transcript)


def main():
    engine = DirectVoiceEngine()
    try:
        asyncio.run(engine.start())
    except KeyboardInterrupt:
        logger.info("VISION stopped by user.")

if __name__ == "__main__":
    main()