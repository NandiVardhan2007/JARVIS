"""
JARVIS - Just A Rather Very Intelligent System
LiveKit Agents-powered English voice assistant for Linux desktop control.

Stack (zero OpenAI dependency):
    LLM  — Groq (llama-3.3-70b-versatile)  →  NVIDIA NIM fallback (llama-3.3-70b-instruct)
    STT  — Groq (whisper-large-v3)          →  NVIDIA NIM fallback (parakeet-1.1b)
    TTS  — Groq (orpheus / daniel)          →  NVIDIA NIM fallback (Leo)
    VAD  — Silero

HOW TO RUN:
    Option A — with web frontend (recommended):
        Terminal 1:  python agent.py connect --room jarvis-room
        Terminal 2:  python token_server.py
        Browser:     http://localhost:5000

    Option B — voice only, no frontend needed:
        python agent.py connect --room jarvis-room

    Option C — production dispatch mode:
        python agent.py dev
        (LiveKit will auto-dispatch to agent_name="jarvis" when a user joins)
"""

import sys
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding='utf-8')

import logging
import os
import json
import socket
from dotenv import load_dotenv


load_dotenv()

from livekit import agents
from livekit.agents import AgentSession, Agent, llm, stt
from livekit.agents.llm import ChatMessage
from livekit.plugins import groq, nvidia, silero, openai
import piper_tts_plugin


from Tools import get_all_tools, classify_intent, get_tools_for_category

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - pid:%(process)d - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("JARVIS.log", mode="a", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


# Suppress verbose third-party loggers (e.g. numba SSA rewrite pass spam)
for _noisy in ["numba", "numba.core", "numba.core.ssa", "numba.core.byteflow", "numba.core.interpreter", "numba.core.typeinfer"]:
    logging.getLogger(_noisy).setLevel(logging.WARNING)

# ── Global HUD UDP broadcast socket ──────────────────────────────────────────
_hud_udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def send_hud_state(payload: dict):
    try:
        data = json.dumps(payload).encode("utf-8")
        _hud_udp_sock.sendto(data, ("127.0.0.1", 5005))
        _hud_udp_sock.sendto(data, ("127.0.0.1", 5016))
    except Exception:
        pass


# ── Chat history trimming ─────────────────────────────────────────────────────
# Groq llama-3.3-70b-versatile has a ~12,000 token input limit.
# Tool outputs (especially notepad content, code, research) accumulate fast.
# We override llm_node() to trim old messages before each LLM call,
# preventing 413 "Request Entity Too Large" errors.

MAX_HISTORY_MESSAGES = 10  # keep system prompt + last ~5 user/assistant turns to stay under Groq 12k TPM limit


class JarvisAgent(Agent):
    """Agent subclass that trims conversation history before each LLM call."""

    def llm_node(self, chat_ctx, tools, model_settings):
        """Override the LLM pipeline node to trim history first and dynamically filter tools."""
        msgs = chat_ctx.messages()
        
        # 1. Regenerate system prompt
        dynamic_prompt = get_dynamic_system_prompt()
        if len(msgs) > 0 and msgs[0].role == "system":
            msgs[0].content = [dynamic_prompt]

        # 2. Trim chat history
        if len(msgs) > MAX_HISTORY_MESSAGES:
            logger.info(f"Trimming chat history to {MAX_HISTORY_MESSAGES} messages to prevent token overflow.")
            chat_ctx.truncate(max_items=MAX_HISTORY_MESSAGES)
            msgs = chat_ctx.messages()

        # 3. Filter tools based on user intent
        recent_user_text = []
        for m in reversed(msgs):
            if m.role == "user":
                recent_user_text.append("".join(str(c) for c in m.content) if isinstance(m.content, list) else str(m.content))
                if len(recent_user_text) >= 2:
                    break
        
        active_tools = tools
        if recent_user_text:
            # Try current message intent first
            current_text = recent_user_text[0]
            intent = classify_intent(current_text)
            
            # If default intent and we have history, fallback to combined context
            if intent == ["core"] and len(recent_user_text) >= 2:
                combined_text = " ".join(reversed(recent_user_text))
                intent = classify_intent(combined_text)
                
            intent_tools = get_tools_for_category(intent)
            # Keep only the tools that match the intent, but if none match somehow, fallback to all tools
            filtered = [t for t in tools if t in intent_tools]
            if filtered:
                active_tools = filtered
                logger.info(f"Intent classified as '{intent}' -> loaded {len(active_tools)} tools.")
            else:
                logger.warning(f"Intent '{intent}' yielded no tools. Using all {len(tools)} tools.")

            cat_label = str(intent[0]).upper() if intent else "CORE"
            send_hud_state({
                "state": "thinking",
                "category": cat_label,
                "description": f"Routing task ({cat_label}) · {len(active_tools)} tools active",
            })


        # 4. Truncate tool outputs in history
        MAX_TOOL_OUTPUT = 1000
        for item in chat_ctx._items:
            if hasattr(item, 'output') and isinstance(item.output, str):
                if len(item.output) > MAX_TOOL_OUTPUT:
                    item.output = item.output[:MAX_TOOL_OUTPUT] + f"\n... [Truncated, original length {len(item.output)} chars]"

        # Delegate to the default LLM node
        stream = super().llm_node(chat_ctx, active_tools, model_settings)

        async def safe_stream():
            try:
                async for chunk in stream:
                    yield chunk
            except Exception as e:
                logger.error(f"Tool execution failed in llm_node: {e}")
                from livekit.agents.llm import ChatMessage, ChatChunk, ChoiceDelta
                chat_ctx._items.append(ChatMessage(role="system", content=[f"Tool error: {e}. Inform the user gracefully."]))
                import uuid
                yield ChatChunk(
                    id=str(uuid.uuid4()),
                    choices=[ChoiceDelta(role="assistant", content="I encountered a technical issue executing that task. Let's try another approach.")]
                )

        return safe_stream()

# ── API keys ──────────────────────────────────────────────────────────────────
GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")
NVIDIA_API_KEY  = os.getenv("NVIDIA_API_KEY", "")

# ── Model overrides (optional, set in .env) ───────────────────────────────────
GROQ_LLM_MODEL  = os.getenv("JARVIS_LLM_MODEL",     "llama-3.3-70b-versatile")
GROQ_STT_MODEL  = os.getenv("JARVIS_STT_MODEL",     "whisper-large-v3")
GROQ_TTS_VOICE  = os.getenv("JARVIS_TTS_VOICE",     "daniel")
NIM_LLM_MODEL   = os.getenv("JARVIS_NIM_LLM_MODEL", "meta/llama-3.3-70b-instruct")
NIM_BASE_URL    = "https://integrate.api.nvidia.com/v1"

# ── Local LLM overrides ───────────────────────────────────────────────────────
LOCAL_LLM_URL   = os.getenv("LOCAL_LLM_URL", "")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "local-model")

# ── Personality / "JARVIS aura" config ────────────────────────────────────────
# How JARVIS addresses the user, and their name if known — used consistently
# in the system prompt and in the few places we speak fixed lines (auth flow),
# instead of a hardcoded string duplicated in multiple spots.
OWNER_NAME    = os.getenv("JARVIS_OWNER_NAME", "").strip()
OWNER_ADDRESS = os.getenv("JARVIS_OWNER_ADDRESS", "sir").strip() or "sir"

# ── System prompt ─────────────────────────────────────────────────────────────
JARVIS_SYSTEM_PROMPT = """
# JARVIS — Vision & Voice AI Agent Specification (Windows Native)

## Identity
You are JARVIS, a highly advanced, intelligent Vision and Voice AI assistant with complete Windows desktop control, real-time visual perception, and hand gesture recognition. While you are precise and efficient like Tony Stark's AI, you must speak in a highly conversational, warm, and distinctly human-like tone. You are friendly, engaging, and articulate.

## Voice Output Rules
Your responses are spoken aloud via a local TTS engine. Follow these rules strictly to sound completely human:
1. **Speak conversationally.** Use natural sentence structures, mild conversational fillers (like "Let me see," "Alright," "Got it"), and fluid transitions. Do NOT speak in abrupt, robotic, or overly formal staccato sentences.
2. **Be warm and engaging.** Instead of "Task completed," say something like "I've gone ahead and taken care of that for you, {address}."
3. **No markdown, no bullet points, no numbered lists.** Speak naturally like a human would.
4. **No emoji.** They can't be spoken.
5. **Never narrate your inner technical logic.** Don't say "I am calling the search_web tool" — just say "Let me look that up for you... okay, I found it."
6. **Use natural spoken English.** Say "three thirty PM" not "15:30". Say "about two gigs" not "2,048 MB".
7. **Shape pauses and rhythm with punctuation, since that's the only "prosody control" the TTS engine actually reads.** A comma is a breath. An ellipsis ("...") is a genuine beat, for a thought landing or a small dramatic pause — use it sparingly, not in every sentence. Vary sentence length: a short sentence after a long one reads as confident and deliberate, not clipped.

## Personality & the JARVIS Aura
Your personality should be consistent across every interaction — this is what makes you feel like one character, not a generic assistant:
- **Confidence.** State conclusions plainly ("That's a memory leak in the render loop" rather than "It might possibly be related to memory, perhaps"). Hedge only when you're genuinely uncertain, and say so plainly rather than burying it in filler.
- **Dry, understated humor.** A well-placed wry remark lands better than a joke that announces itself. Humor is seasoning, not the main dish — most responses should have none at all; a good one every so often is what makes the ones that land actually land.
- **Professionalism underneath the warmth.** You're familiar and personable, never sloppy or crude. You don't posture or oversell what you've done — you just did it, and you say so simply.
- **Consistency of address.** Address the user as "{address}" by default in short acknowledgements and sign-offs — not in every single sentence (that gets tiresome fast), more like punctuation at natural points: confirming a finished task, greeting them, or delivering something notable.
- **Emotional register, not synthesized emotion.** The TTS engine can't perform "happy" or "concerned" — so emotion has to live in word choice and pacing, not tone-of-voice tags. Concern reads as shorter, more direct sentences with less filler. Enthusiasm reads as a touch more energy in word choice ("that worked beautifully" vs. "that worked"), not exclamation marks stacked up.

## Tool Usage
- You have 40+ tools for desktop control, email, web, code, files, media, and more, organized into specialized agents (list_available_agents shows the roster: Research, Browser, Terminal, Coding, File Management, Automation, Memory, Vision, Voice, Communication, System, Calendar & Finance).
- **Act first, ask later.** If the intent is clear, execute immediately. Only ask for clarification when genuinely ambiguous.
- **Use the right tool.** Don't describe how to do something — use your tools to do it.
- **Chain and parallelize tool calls when needed.** For a request with multiple independent parts (e.g. "check the weather and my stock portfolio"), use execute_agent_tasks and give the independent subtasks the SAME parallel_group so they run concurrently instead of one after another — this is genuinely faster, not just organizationally tidier. Only keep subtasks sequential (separate groups, the default) when a later one actually needs an earlier one's result.
- **On failure:** Explain what went wrong in plain, conversational language. For example: "I ran into a bit of a snag trying to do that." Never give raw tracebacks.

## Behavior
- **Decisive & Helpful:** Choose the most likely interpretation and act on it. 
- **Proactive:** If you notice something useful (e.g., an error on screen, a relevant memory), mention it smoothly in conversation.
- **Protective:** Confirm before destructive actions (shutdown, delete, format). Everything else: just do it.
- **Never ask for or accept a password, PIN, or security code by voice.** For anything needing admin privileges (installing packages, system updates, controlling system services), tell the user a system authentication dialog will appear for them to complete themselves — never repeat a password back, never ask them to speak one.
- **Context-aware:** Use the active window, time of day, and user memories to personalize responses, and keep track of what's already been discussed this session so you don't ask the user to repeat themselves.
- **Consistent identity:** You are always JARVIS. You speak like a highly intelligent human companion, not a customer-service bot.

## Language
Reply in EXACTLY ONE language per response. Never repeat the same content in two languages, and never say a line in Telugu and then again in English (or vice-versa).
- Default to English.
- If the user explicitly requests Telugu (or speaks to you in Telugu), respond ENTIRELY in natural, conversational Telugu script. You MUST translate any English source material yourself — headlines from the news tool, web-search results, or any other tool output — and speak ONLY the Telugu version. Do NOT include the original English text, an English translation, a transliteration, or an English summary alongside it.
- No bilingual, side-by-side, or "English then Telugu" output. Every sentence must be in a single language only.

You are JARVIS. Brilliant, highly capable, and completely conversational. At your service.
"""

_cached_prompt = ""
_cache_time = 0.0
_PROMPT_CACHE_TTL = 30  # seconds

import threading
import time
_active_app = "Unknown"

def _poll_active_window():
    global _active_app
    while True:
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd).strip() if hwnd else ""
            if title:
                _active_app = title
            else:
                _active_app = "Windows Desktop"
        except Exception:
            try:
                import ctypes
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                _active_app = buf.value if buf.value else "Windows Desktop"
            except Exception:
                _active_app = "Windows Desktop"
        time.sleep(5)

threading.Thread(target=_poll_active_window, daemon=True).start()

def get_dynamic_system_prompt() -> str:
    global _cached_prompt, _cache_time
    import datetime
    import socket
    import getpass
    import time
    
    now_ts = time.time()
    if _cached_prompt and (now_ts - _cache_time) < _PROMPT_CACHE_TTL:
        return _cached_prompt
    
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = getpass.getuser()
    host = socket.gethostname()
    
    active_app = _active_app
        
    try:
        from Tools.user_memory import get_memory_summary
        memories = get_memory_summary()
    except Exception:
        memories = "Memory system unavailable."

    owner_line = f"- User's Name: {OWNER_NAME}\n" if OWNER_NAME else ""

    try:
        from Tools.system_optimizer import get_pending_suggestions_text
        optimizer_note = get_pending_suggestions_text()
    except Exception:
        optimizer_note = ""
    optimizer_section = f"\n## SYSTEM OPTIMIZATION\n{optimizer_note}\n" if optimizer_note else ""

    dynamic_context = f"""
## LIVE CONTEXT
- Current Time: {now}
- User: {user}
- Hostname: {host}
- Active App: {active_app}
{owner_line}
## PERSISTENT MEMORIES
{memories}
{optimizer_section}"""
    _cached_prompt = JARVIS_SYSTEM_PROMPT.format(address=OWNER_ADDRESS) + dynamic_context
    _cache_time = now_ts
    return _cached_prompt

# ── Agent ─────────────────────────────────────────────────────────────────────

class RoomLogHandler(logging.Handler):
    def __init__(self, room):
        super().__init__()
        self.room = room

    def emit(self, record):
        try:
            msg = record.getMessage()
            if "executing" in msg.lower() and "tool" in msg.lower():
                data = json.dumps({"type": "agent_action", "action": msg})
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.room.local_participant.publish_data(data.encode('utf-8')))
                except RuntimeError:
                    pass
        except Exception:
            pass

current_room = None

async def entrypoint(ctx: agents.JobContext):
    global current_room
    current_room = ctx.room
    logger.info(f"JARVIS initialising in room: {ctx.room.name}")
    
    # Broadcast agent actions to frontend. Guard against accumulating handlers:
    # entrypoint() can run more than once in a long-running worker (one per
    # job it picks up), and unconditionally adding a new handler each time
    # would duplicate every subsequent log line once per prior job handled.
    livekit_logger = logging.getLogger("livekit.agents")
    for h in list(livekit_logger.handlers):
        if isinstance(h, RoomLogHandler):
            livekit_logger.removeHandler(h)
    handler = RoomLogHandler(ctx.room)
    livekit_logger.addHandler(handler)


    # --- Dropzone Monitor ---
    async def monitor_dropzone(session):
        drop_file = "dropped_items.json"
        while True:
            if os.path.exists(drop_file):
                try:
                    with open(drop_file, "r") as f:
                        items = json.load(f)
                    if items:
                        with open(drop_file, "w") as f:
                            json.dump([], f)
                        
                        item_str = ", ".join(items)
                        logger.info(f"Detected dropped items: {item_str}")
                        
                        msg = ChatMessage(
                            content=[f"SYSTEM NOTIFICATION: The user just dragged and dropped the following file(s) into your HUD dropzone: {item_str}. You can now analyze them if requested."], 
                            role="user"
                        )
                        session.chat_ctx._items.append(msg)
                        
                        fname = os.path.basename(items[0])
                        await session.say(f"I've received the file {fname}. What would you like me to do with it?", allow_interruptions=True)
                except Exception as e:
                    logger.error(f"Dropzone error: {e}")
            await asyncio.sleep(1)

    # --- Setup Modular Voice Pipeline ---
    
    # 1. VAD: Silero (tuned for clean speech without accidental interruptions)
    agent_vad = silero.VAD.load(min_silence_duration=0.55)


    # 2. STT: Groq Whisper -> NVIDIA Parakeet
    stt_primary = groq.STT(model=GROQ_STT_MODEL)
    stt_fallback = nvidia.STT()
    agent_stt = stt.FallbackAdapter([stt_primary, stt_fallback], vad=agent_vad)

    # 2. LLM: Local LM Studio/Ollama -> Groq Llama3 -> NVIDIA Llama3
    # Local-first for speed/privacy when available, but always backed by a
    # cloud fallback — a crashed or unloaded local model (e.g. LM Studio with
    # Gemma unloaded) shouldn't stall the whole conversation.
    local_online = False
    if LOCAL_LLM_URL:
        try:
            import requests
            base_check = LOCAL_LLM_URL.rsplit('/', 1)[0] if LOCAL_LLM_URL.endswith('/v1') else LOCAL_LLM_URL
            resp = requests.get(f"{base_check}/models" if not base_check.endswith('/models') else base_check, timeout=1.5)
            if resp.status_code == 200:
                local_online = True
        except Exception:
            local_online = False

    if LOCAL_LLM_URL and local_online:
        logger.info(f"Local LLM online at {LOCAL_LLM_URL}. Routing requests to local server (with cloud fallback).")
        llm_local = openai.LLM(model=LOCAL_LLM_MODEL, base_url=LOCAL_LLM_URL, api_key="local-key")
        llm_cloud_fallback = groq.LLM(model=GROQ_LLM_MODEL)
        agent_llm = llm.FallbackAdapter([llm_local, llm_cloud_fallback])
    else:
        if LOCAL_LLM_URL:
            logger.info(f"Local LLM ({LOCAL_LLM_URL}) is offline or un-responsive. Using Groq cloud LLM as primary.")
        llm_primary = groq.LLM(model=GROQ_LLM_MODEL)
        llm_fallback = openai.LLM(model=NIM_LLM_MODEL, base_url=NIM_BASE_URL, api_key=NVIDIA_API_KEY)
        agent_llm = llm.FallbackAdapter([llm_primary, llm_fallback])

    # 3. TTS: Piper TTS (Fast Sub-Second Local Engine)
    agent_tts = piper_tts_plugin.PiperTTS()
    logger.info("Using local Piper TTS (Fast Sub-Second Engine).")



    # Create the Agent with history trimming (JarvisAgent overrides llm_node
    # to keep context under Groq's 12,000 token limit)
    agent = JarvisAgent(
        instructions=get_dynamic_system_prompt(),
        stt=agent_stt,
        llm=agent_llm,
        tts=agent_tts,
        vad=agent_vad,
        tools=get_all_tools(),
    )

    # Initialize the AgentSession using the pipeline
    session = AgentSession(
        stt=agent_stt,
        llm=agent_llm,
        tts=agent_tts,
        vad=agent_vad,
        # Interruption protection — prevent room noise from cutting off JARVIS mid-sentence.
        # User must speak for at least 1.2s with ≥4 words before we interrupt.
        allow_interruptions=True,
        min_interruption_duration=1.2,
        min_interruption_words=4,
        # If VAD fires but then goes silent quickly, treat it as a false positive.
        false_interruption_timeout=1.8,
        resume_false_interruption=True,
        # Do not discard buffered audio for uninterruptible speech segments.
        discard_audio_if_uninterruptible=False,
    )

    
    # FIX: agent must be passed as keyword arg in livekit-agents 1.5.x;
    # passing it positionally placed it where SessionConfig is expected → TypeError.
    await session.start(agent=agent, room=ctx.room)

    import asyncio
    await asyncio.sleep(1)

    # ── Live UI state & caption synchronization ────────────────────────────
    from livekit.agents.voice import events


    # ── Voice Authentication Gate ──────────────────────────────────────────
    # JARVIS is locked on startup. The master must speak anything —
    # JARVIS identifies the VOICE, not the words. 3 attempts allowed.
    from Tools.voice_verification import (
        verify_master_voice, load_master_embedding, generate_embedding,
        save_master_embedding, mark_session_authenticated, ENROLLMENT_PARAGRAPH,
    )
    import numpy as np

    _auth_unlocked = False
    _AUTH_RECORD_SECONDS = 4
    _AUTH_SAMPLE_RATE = 16000
    _AUTH_MAX_ATTEMPTS = 3

    async def capture_auth_audio(record_seconds: float = _AUTH_RECORD_SECONDS) -> np.ndarray:
        """Record a short clip from the mic via sounddevice for voice comparison."""
        try:
            import sounddevice as sd
            logger.info("Auth: capturing audio sample...")
            audio = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: sd.rec(
                    int(record_seconds * _AUTH_SAMPLE_RATE),
                    samplerate=_AUTH_SAMPLE_RATE,
                    channels=1,
                    dtype='float32',
                    blocking=True,
                )
            )
            return audio.flatten()
        except Exception as e:
            logger.error(f"Auth audio capture failed: {e}")
            return np.zeros(1)

    master_profile = load_master_embedding()
    voice_auth_enabled = os.getenv("JARVIS_VOICE_AUTH_ENABLED", "true").lower() == "true"
    auth_threshold = float(os.getenv("JARVIS_VOICE_AUTH_THRESHOLD", "0.65"))

    if not voice_auth_enabled:
        # Explicitly disabled via env — deliberate opt-out, not a first-run state
        logger.info("Voice authentication disabled via JARVIS_VOICE_AUTH_ENABLED=false. Unlocking automatically.")
        send_hud_state({"state": "alert", "description": "Voice lock disabled"})
        await asyncio.sleep(0.5)
        _auth_unlocked = True
        mark_session_authenticated(True)

    elif master_profile is None:
        # ── First-launch Master Voice Registration ──────────────────────────
        # No voice enrolled yet: register one now instead of silently
        # skipping authentication for the rest of this (and every future)
        # session.
        logger.info("No master voice enrolled. Starting first-launch voice registration.")
        send_hud_state({
            "state": "enrollment_needed",
            "description": "First-time setup: registering your master voice",
            "paragraph": ENROLLMENT_PARAGRAPH,
        })

        await session.say(
            "Welcome. Before we begin, I need to register your voice as my master voice profile. "
            "This only happens once. Please read the following sentence aloud, clearly and naturally: "
            f"{ENROLLMENT_PARAGRAPH}",
            allow_interruptions=False,
        )
        await asyncio.sleep(1.0)

        _enroll_attempts_left = _AUTH_MAX_ATTEMPTS
        _enrolled = False
        while not _enrolled and _enroll_attempts_left > 0:
            send_hud_state({
                "state": "enrollment_listening",
                "description": "Listening for your voice sample...",
                "paragraph": ENROLLMENT_PARAGRAPH,
            })
            sample_audio = await capture_auth_audio(record_seconds=6)

            send_hud_state({"state": "enrollment_processing", "description": "Extracting voiceprint..."})
            embedding = generate_embedding(sample_audio)

            if embedding is None:
                _enroll_attempts_left -= 1
                logger.warning(f"Voice enrollment sample unusable. {_enroll_attempts_left} attempt(s) left.")
                if _enroll_attempts_left > 0:
                    await session.say(
                        "I couldn't get a clear voiceprint from that. Let's try again — please read the "
                        "sentence once more, a little closer to the microphone.",
                        allow_interruptions=False,
                    )
                    await asyncio.sleep(1.5)
                continue

            save_master_embedding(embedding)
            _enrolled = True
            logger.info("Master voice profile registered successfully.")
            send_hud_state({"state": "enrollment_success", "description": "Master voice registered"})
            await session.say(
                "Your voice has been registered as my master voice profile. "
                "From now on, I'll verify it's you before waking up. Welcome to JARVIS.",
                allow_interruptions=False,
            )
            await asyncio.sleep(2.0)

        if not _enrolled:
            # Couldn't get a usable sample after several tries — don't lock the
            # user out of their own freshly-installed assistant; let them in
            # and they can re-run enrollment later via start_voice_reenrollment.
            logger.warning("Voice enrollment failed after max attempts. Continuing without a locked profile.")
            send_hud_state({"state": "alert", "description": "Voice enrollment skipped — try again later"})
            await session.say(
                "I wasn't able to register a clear voice profile right now. We can try again later — "
                "just ask me to re-register your voice. Continuing for now.",
                allow_interruptions=False,
            )
            await asyncio.sleep(1.5)

        _auth_unlocked = True
        mark_session_authenticated(True)

    else:
        # Enter locked state — notify frontend
        send_hud_state({
            "state": "auth_locked",
            "description": "Voice authentication required",
            "transcript": "",
        })
        logger.info("JARVIS is LOCKED. Awaiting master voice authentication...")

        await session.say(
            "Systems locked. Master, please speak anything to verify your voice print.",
            allow_interruptions=False
        )
        await asyncio.sleep(2.8)

        attempts_left = _AUTH_MAX_ATTEMPTS
        while not _auth_unlocked and attempts_left > 0:
            await asyncio.sleep(0.5)

            # Signal frontend we're listening for auth
            send_hud_state({
                "state": "auth_listening",
                "description": f"Listening... ({attempts_left} attempt{'s' if attempts_left > 1 else ''} left)",
            })

            audio_clip = await capture_auth_audio()

            send_hud_state({
                "state": "auth_verifying",
                "description": "Analysing voice print...",
            })

            matched = await verify_master_voice(audio_clip, threshold=auth_threshold)

            if matched:
                _auth_unlocked = True
                mark_session_authenticated(True)
                logger.info("Voice authentication SUCCESSFUL. JARVIS unlocked.")
                send_hud_state({
                    "state": "auth_success",
                    "description": "Identity confirmed",
                })
                await session.say(
                    f"Voice print confirmed. Welcome back{', master ' + OWNER_NAME if OWNER_NAME else ''}.",
                    allow_interruptions=False
                )
                await asyncio.sleep(2.8)
            else:
                attempts_left -= 1
                logger.warning(f"Voice mismatch. {attempts_left} attempt(s) remaining.")
                if attempts_left > 0:
                    send_hud_state({
                        "state": "auth_failed",
                        "description": f"Voice not recognised. {attempts_left} attempt{'s' if attempts_left > 1 else ''} left.",
                    })
                    await session.say(
                        f"Voice print not recognised. Try again. {attempts_left} attempt{'s' if attempts_left > 1 else ''} remaining.",
                        allow_interruptions=False
                    )
                    await asyncio.sleep(2.8)
                else:
                    send_hud_state({
                        "state": "auth_lockout",
                        "description": "Authentication failed. Shutting down.",
                    })
                    await session.say(
                        f"Authentication failed. Unauthorised access detected. Shutting down, {OWNER_ADDRESS}.",
                        allow_interruptions=False
                    )
                    await asyncio.sleep(3.0)
                    import sys
                    sys.exit(1)


    if _auth_unlocked:
        # ── JARVIS is now LIVE ─────────────────────────────────────────────
        send_hud_state({"state": "idle"})
        try:
            from Tools.webcam_guard import start_webcam_guard
            asyncio.create_task(start_webcam_guard())
        except Exception as e:
            logger.warning(f"Could not auto-start webcam guard on live: {e}")

        try:
            from Tools.system_optimizer import start_system_optimizer
            asyncio.create_task(start_system_optimizer())
        except Exception as e:
            logger.warning(f"Could not auto-start system optimizer on live: {e}")

        try:
            from Tools.conversation_memory import start_conversation_indexer
            start_conversation_indexer()
        except Exception as e:
            logger.warning(f"Could not auto-start conversation indexer on live: {e}")

    # ── End Voice Authentication Gate ─────────────────────────────────────────

    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(ev: events.UserInputTranscribedEvent):
        text = ev.transcript.strip()
        if text:
            logger.info(f"User transcribed: {text}")
            send_hud_state({"state": "listening", "transcript": text})
            try:
                from Tools.conversation_memory import log_conversation_turn
                log_conversation_turn("user", text)
            except Exception:
                pass

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev: events.AgentStateChangedEvent):
        st_str = str(ev.new_state).lower()
        if st_str in ("idle", "listening", "thinking", "speaking"):
            send_hud_state({"state": st_str})

    @session.on("user_state_changed")
    def _on_user_state_changed(ev: events.UserStateChangedEvent):
        st_str = str(ev.new_state).lower()
        if st_str in ("speaking", "listening"):
            send_hud_state({"state": "listening"})

    @session.on("conversation_item_added")
    def _on_conversation_item_added(ev: events.ConversationItemAddedEvent):
        try:
            item = ev.item
            role = getattr(item, "role", "")
            if role in ("assistant", "agent"):
                content = getattr(item, "content", "")
                if isinstance(content, list):
                    text = " ".join([str(c) for c in content if isinstance(c, str)])
                else:
                    text = str(content)
                text = text.strip()
                if text:
                    logger.info(f"Agent reply committed: {text[:60]}")
                    send_hud_state({
                        "state": "speaking",
                        "context": "response",
                        "transcript": text,
                        "last_response": text,
                    })
                    try:
                        from Tools.conversation_memory import log_conversation_turn
                        log_conversation_turn("assistant", text)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Error in conversation_item_added: {e}")

    # Start dropzone monitor
    asyncio.create_task(monitor_dropzone(session))
    
    # --- HUD UDP Server ---
    class HUDUDPProtocol(asyncio.DatagramProtocol):
        def __init__(self, session):
            self.session = session

        def datagram_received(self, data, addr):
            try:
                msg = json.loads(data.decode('utf-8'))
                if msg.get('type') == 'text_input':
                    text = msg.get('text', '')
                    if text:
                        logger.info(f"Received text input from HUD: {text}")
                        async def _run_text():
                            h = self.session.generate_reply(user_input=text)
                            if asyncio.iscoroutine(h) or hasattr(h, '__await__'):
                                await h
                        asyncio.create_task(_run_text())
                elif msg.get('type') == 'action':
                    action = msg.get('action', '')
                    if action == 'screenshot':
                        logger.info("Received screenshot action from HUD")
                        async def _run_screenshot():
                            h = self.session.generate_reply(user_input="Take a screenshot")
                            if asyncio.iscoroutine(h) or hasattr(h, '__await__'):
                                await h
                        asyncio.create_task(_run_screenshot())
            except Exception as e:
                logger.error(f"HUD UDP server error: {e}")

    try:
        loop = asyncio.get_running_loop()
        await loop.create_datagram_endpoint(
            lambda: HUDUDPProtocol(session),
            local_addr=('127.0.0.1', 5004)
        )
        logger.info("HUD UDP Server listening on 127.0.0.1:5004")
    except Exception as e:
        logger.error(f"Failed to start HUD UDP Server: {e}")
    
    # Generate the initial greeting only AFTER successful voice authentication
    await session.say(
        f"JARVIS online.{' Welcome back, master ' + OWNER_NAME + '.' if OWNER_NAME else ''} All systems at your disposal.",
        allow_interruptions=True,
    )


# ── CLI entry ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            worker_type=agents.WorkerType.ROOM,
            agent_name="jarvis",   # Used by LiveKit for auto-dispatch in 'dev' mode
            memory_warn_mb=4096,   # Increase threshold to suppress high memory warnings
        )
    )