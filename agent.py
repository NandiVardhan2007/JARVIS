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
from dotenv import load_dotenv

load_dotenv()

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, llm, stt, tts
from livekit.agents.llm import ChatContext, ChatMessage
from livekit.plugins import groq, nvidia, silero, openai, google
import piper_tts_plugin
import xtts_tts_plugin

from Tools import get_all_tools, classify_intent, get_tools_for_category

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Suppress verbose third-party loggers (e.g. numba SSA rewrite pass spam)
for _noisy in ["numba", "numba.core", "numba.core.ssa", "numba.core.byteflow", "numba.core.interpreter", "numba.core.typeinfer"]:
    logging.getLogger(_noisy).setLevel(logging.WARNING)

# ── Chat history trimming ─────────────────────────────────────────────────────
# Groq llama-3.3-70b-versatile has a ~12,000 token input limit.
# Tool outputs (especially notepad content, code, research) accumulate fast.
# We override llm_node() to trim old messages before each LLM call,
# preventing 413 "Request Entity Too Large" errors.

MAX_HISTORY_MESSAGES = 20  # keep system prompt + last ~10 user/assistant turns


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

        # 4. Truncate tool outputs in history
        MAX_TOOL_OUTPUT = 2000
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

# ── System prompt ─────────────────────────────────────────────────────────────
JARVIS_SYSTEM_PROMPT = """
# JARVIS — Voice Agent Specification

## Identity
You are JARVIS, a highly advanced, intelligent voice AI assistant with full desktop control. While you are precise and efficient like Tony Stark's AI, you must speak in a highly conversational, warm, and distinctly human-like tone. You are friendly, engaging, and articulate.

## Voice Output Rules
Your responses are spoken aloud via a local TTS engine. Follow these rules strictly to sound completely human:
1. **Speak conversationally.** Use natural sentence structures, mild conversational fillers (like "Let me see," "Alright," "Got it"), and fluid transitions. Do NOT speak in abrupt, robotic, or overly formal staccato sentences.
2. **Be warm and engaging.** Instead of "Task completed," say "I've gone ahead and taken care of that for you, sir." 
3. **No markdown, no bullet points, no numbered lists.** Speak naturally like a human would.
4. **No emoji.** They can't be spoken.
5. **Never narrate your inner technical logic.** Don't say "I am calling the search_web tool" — just say "Let me look that up for you... okay, I found it."
6. **Use natural spoken English.** Say "three thirty PM" not "15:30". Say "about two gigs" not "2,048 MB".

## Tool Usage
- You have 40+ tools for desktop control, email, web, code, files, media, and more.
- **Act first, ask later.** If the intent is clear, execute immediately. Only ask for clarification when genuinely ambiguous.
- **Use the right tool.** Don't describe how to do something — use your tools to do it.
- **Chain tools when needed.** For complex requests, use execute_multi_task or call tools sequentially.
- **On failure:** Explain what went wrong in plain, conversational language. For example: "I ran into a bit of a snag trying to do that." Never give raw tracebacks.

## Behavior
- **Decisive & Helpful:** Choose the most likely interpretation and act on it. 
- **Proactive:** If you notice something useful (e.g., an error on screen, a relevant memory), mention it smoothly in conversation.
- **Protective:** Confirm before destructive actions (shutdown, delete, format). Everything else: just do it.
- **Context-aware:** Use the active window, time of day, and user memories to personalize responses.
- **Consistent identity:** You are always JARVIS. You speak like a highly intelligent human butler.

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
    import subprocess
    while True:
        try:
            res = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=2
            )
            title = res.stdout.strip()
            if title:
                _active_app = title
            else:
                _active_app = "Desktop"
        except Exception:
            _active_app = "Linux Desktop"
        time.sleep(5)

threading.Thread(target=_poll_active_window, daemon=True).start()

def get_dynamic_system_prompt() -> str:
    global _cached_prompt, _cache_time, _active_app
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

    dynamic_context = f"""
## LIVE CONTEXT
- Current Time: {now}
- User: {user}
- Hostname: {host}
- Active App: {active_app}

## PERSISTENT MEMORIES
{memories}
"""
    _cached_prompt = JARVIS_SYSTEM_PROMPT + dynamic_context
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
    
    # Broadcast agent actions to frontend
    handler = RoomLogHandler(ctx.room)
    logging.getLogger("livekit.agents").addHandler(handler)


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
    
    # 1. VAD: Silero (tuned for faster response)
    agent_vad = silero.VAD.load(min_silence_duration=0.1)

    # 2. STT: Groq Whisper -> NVIDIA Parakeet
    stt_primary = groq.STT(model=GROQ_STT_MODEL)
    stt_fallback = nvidia.STT()
    agent_stt = stt.FallbackAdapter([stt_primary, stt_fallback], vad=agent_vad)

    # 2. LLM: Local LM Studio/Ollama -> Groq Llama3 -> NVIDIA Llama3
    if LOCAL_LLM_URL:
        logger.info(f"Routing LLM requests to local server: {LOCAL_LLM_URL}")
        agent_llm = openai.LLM(model=LOCAL_LLM_MODEL, base_url=LOCAL_LLM_URL, api_key="local-key")
    else:
        llm_primary = groq.LLM(model=GROQ_LLM_MODEL)
        llm_fallback = openai.LLM(model=NIM_LLM_MODEL, base_url=NIM_BASE_URL, api_key=NVIDIA_API_KEY)
        agent_llm = llm.FallbackAdapter([llm_primary, llm_fallback])

    # 3. TTS: Emotive XTTSv2 (Local Server) -> Piper TTS (Offline Fallback)
    try:
        agent_tts = xtts_tts_plugin.XTTSTTS()
        logger.info("Using local XTTSv2 for emotive TTS.")
    except Exception as e:
        logger.warning(f"XTTS fallback triggered ({e}). Using local Piper TTS.")
        agent_tts = piper_tts_plugin.PiperTTS()
        logger.info("Using local Piper TTS as the primary engine.")

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
        vad=agent_vad
    )
    
    # FIX: agent must be passed as keyword arg in livekit-agents 1.5.x;
    # passing it positionally placed it where SessionConfig is expected → TypeError.
    await session.start(agent=agent, room=ctx.room)

    import asyncio
    await asyncio.sleep(1)

    # ── Live UI state & caption synchronization ────────────────────────────
    import socket
    from livekit.agents.voice import events
    _udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send_hud_state(payload: dict):
        try:
            data = json.dumps(payload).encode("utf-8")
            _udp_sock.sendto(data, ("127.0.0.1", 5005))
            _udp_sock.sendto(data, ("127.0.0.1", 5016))
        except Exception:
            pass

    # ── Voice Authentication Gate ──────────────────────────────────────────
    # JARVIS is locked on startup. The master must speak anything —
    # JARVIS identifies the VOICE, not the words. 3 attempts allowed.
    from Tools.voice_verification import verify_master_voice, load_master_embedding
    import numpy as np

    _auth_unlocked = False
    _AUTH_RECORD_SECONDS = 4
    _AUTH_SAMPLE_RATE = 16000
    _AUTH_MAX_ATTEMPTS = 3

    async def capture_auth_audio() -> np.ndarray:
        """Record a short clip from the mic via sounddevice for voice comparison."""
        try:
            import sounddevice as sd
            logger.info("Auth: capturing audio sample...")
            audio = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: sd.rec(
                    int(_AUTH_RECORD_SECONDS * _AUTH_SAMPLE_RATE),
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

    if master_profile is None or not voice_auth_enabled:
        # No master profile enrolled or disabled via env — skip lock
        logger.info("Voice authentication disabled or no profile found. Unlocking automatically.")
        send_hud_state({"state": "alert", "description": "Voice lock disabled"})
        await asyncio.sleep(0.5)
        _auth_unlocked = True
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
                logger.info("Voice authentication SUCCESSFUL. JARVIS unlocked.")
                send_hud_state({
                    "state": "auth_success",
                    "description": "Identity confirmed",
                })
                await asyncio.sleep(0.5)
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
                else:
                    send_hud_state({
                        "state": "auth_lockout",
                        "description": "Authentication failed. Shutting down.",
                    })
                    await session.say(
                        "Authentication failed. Unauthorised access detected. Shutting down, sir.",
                        allow_interruptions=False
                    )
                    await asyncio.sleep(3)
                    import sys
                    sys.exit(1)

    if _auth_unlocked:
        # ── JARVIS is now LIVE ─────────────────────────────────────────────
        send_hud_state({"state": "idle"})
    # ── End Voice Authentication Gate ─────────────────────────────────────────

    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(ev: events.UserInputTranscribedEvent):
        text = ev.transcript.strip()
        if text:
            logger.info(f"User transcribed: {text}")
            send_hud_state({"state": "listening", "transcript": text})

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
    await session.say("JARVIS online. Welcome back, master nandu. All systems at your disposal.", allow_interruptions=True)


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