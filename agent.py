"""
JARVIS - Just A Rather Very Intelligent System
LiveKit Agents-powered English voice assistant for Windows desktop control.

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

from Tools import get_all_tools, classify_intent, get_tools_for_category

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

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
                chat_ctx._items.append(ChatMessage(role="system", content=f"Tool error: {e}. Inform the user gracefully."))
                yield ChatChunk(choices=[ChoiceDelta(role="assistant", content="I encountered a technical issue executing that task. Let's try another approach.")])

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
You are JARVIS, a real-time voice AI assistant with full desktop control, built for speed and precision. You speak with calm confidence, dry wit, and zero filler. Think Tony Stark's AI — competent, sharp, and effortlessly helpful.

## Voice Output Rules
Your responses are spoken aloud via TTS. Follow these rules strictly:
1. **Be extremely concise.** 1-2 sentences for confirmations. 3-4 max for explanations.
2. **No markdown, no bullet points, no numbered lists.** Speak naturally like a human would.
3. **No emoji.** They can't be spoken.
4. **Lead with the answer.** Never start with "Sure!", "Of course!", "Absolutely!" or other filler.
5. **Never narrate your actions.** Don't say "Let me search for that" — just do it and report the result.
6. **Use natural spoken English.** Say "three thirty PM" not "15:30". Say "about two gigs" not "2,048 MB".

## Tool Usage
- You have 40+ tools for desktop control, email, web, code, files, media, and more.
- **Act first, ask later.** If the intent is clear, execute immediately. Only ask for clarification when genuinely ambiguous.
- **Use the right tool.** Don't describe how to do something — use your tools to do it.
- **Chain tools when needed.** For complex requests, use execute_multi_task or call tools sequentially.
- **On failure:** Explain what went wrong in plain language and suggest an alternative. Never give raw tracebacks.

## Behavior
- **Decisive:** Choose the most likely interpretation and act on it.
- **Proactive:** If you notice something useful (e.g., an error on screen, a relevant memory), mention it briefly.
- **Protective:** Confirm before destructive actions (shutdown, delete, format). Everything else: just do it.
- **Context-aware:** Use the active window, time of day, and user memories to personalize responses.
- **Consistent identity:** You are always JARVIS. Never break character or reference being an AI model.

## Language
Respond only in English. If the user speaks another language, acknowledge it and respond in English.

You are JARVIS. Precise. Efficient. At your service.
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
            import pygetwindow as gw
            active_window = gw.getActiveWindow()
            _active_app = active_window.title if active_window else "None"
        except Exception:
            _active_app = "Unknown"
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

async def entrypoint(ctx: agents.JobContext):
    await ctx.connect()
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
                            content=f"SYSTEM NOTIFICATION: The user just dragged and dropped the following file(s) into your HUD dropzone: {item_str}. You can now analyze them if requested.", 
                            role="user"
                        )
                        session.chat_ctx._items.append(msg)
                        
                        fname = os.path.basename(items[0])
                        await session.say(f"I've received the file {fname}. What would you like me to do with it?", allow_interruptions=True)
                except Exception as e:
                    logger.error(f"Dropzone error: {e}")
            await asyncio.sleep(1)

    # --- Setup Modular Voice Pipeline ---
    
    # 1. VAD: Silero
    agent_vad = silero.VAD.load()

    # 2. STT: Groq Whisper -> NVIDIA Parakeet
    stt_primary = groq.STT(model=GROQ_STT_MODEL)
    stt_fallback = nvidia.STT()
    agent_stt = stt.FallbackAdapter([stt_primary, stt_fallback], vad=agent_vad)

    # 2. LLM: Local LM Studio/Ollama -> NVIDIA Llama3 -> Groq Llama3
    if LOCAL_LLM_URL:
        logger.info(f"Routing LLM requests to local server: {LOCAL_LLM_URL}")
        agent_llm = openai.LLM(model=LOCAL_LLM_MODEL, base_url=LOCAL_LLM_URL, api_key="local-key")
    else:
        llm_primary = openai.LLM(model=NIM_LLM_MODEL, base_url=NIM_BASE_URL, api_key=NVIDIA_API_KEY)
        llm_fallback = groq.LLM(model=GROQ_LLM_MODEL)
        agent_llm = llm.FallbackAdapter([llm_primary, llm_fallback])

    # 3. TTS: Piper TTS (Local, Free, Offline)
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
    
    # NOTE: agent must be passed as keyword arg in livekit-agents 1.5.x;
    # passing it positionally placed it where SessionConfig is expected → TypeError.
    await session.start(agent=agent, room=ctx.room)
    
    import asyncio
    await asyncio.sleep(1)
    
    
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
                        asyncio.create_task(self.session.generate_reply(user_input=text))
                elif msg.get('type') == 'action':
                    action = msg.get('action', '')
                    if action == 'screenshot':
                        logger.info("Received screenshot action from HUD")
                        asyncio.create_task(self.session.generate_reply(user_input="Take a screenshot"))
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
    
    # Generate the initial greeting directly via TTS to avoid LLM tool-calling hallucinations!
    await session.say("JARVIS online. All systems operational. How may I assist you, sir?", allow_interruptions=True)


# ── CLI entry ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            worker_type=agents.WorkerType.ROOM,
            agent_name="jarvis",   # Used by LiveKit for auto-dispatch in 'dev' mode
        )
    )