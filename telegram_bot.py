import os
import json
import logging
import asyncio
import requests
from dotenv import load_dotenv

# Ensure dotenv is loaded before anything else
load_dotenv()

from livekit.plugins import groq, openai
from livekit.agents.llm import ChatContext
from livekit.agents.llm.chat_context import FunctionCall, FunctionCallOutput
from Tools import get_all_tools, get_tools_for_category, classify_intent
from Tools.error_telemetry import log_tool_error
import time
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("telegram_bot")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/"

# Optional security: list of allowed Telegram user IDs
ALLOWED_USERS = os.getenv("TELEGRAM_ALLOWED_USERS", "")
ALLOWED_USERS_LIST = [u.strip() for u in ALLOWED_USERS.split(",")] if ALLOWED_USERS else []

# NVIDIA / Custom LLM API Key for Telegram Bot
TELEGRAM_LLM_API = os.getenv("TELEGRAM_LLM_API", "").strip()

# Local LLM overrides
LOCAL_LLM_URL   = os.getenv("LOCAL_LLM_URL", "")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "local-model")

from collections import OrderedDict
class LRUUserContexts:
    def __init__(self, maxsize=100):
        self.cache = OrderedDict()
        self.maxsize = maxsize
    def __contains__(self, key):
        return key in self.cache
    def __getitem__(self, key):
        self.cache.move_to_end(key)
        return self.cache[key]
    def __setitem__(self, key, value):
        self.cache[key] = value
        self.cache.move_to_end(key)
        if len(self.cache) > self.maxsize:
            self.cache.popitem(last=False)
    def __delitem__(self, key):
        if key in self.cache:
            del self.cache[key]

# Global dictionary to store ChatContext per user
USER_CONTEXTS = LRUUserContexts(maxsize=100)

# ── Rate Limiting ────────────────────────────────────────────────────────────
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW = 60
USER_RATE_LIMITS = defaultdict(lambda: {"tokens": RATE_LIMIT_REQUESTS, "last_updated": time.time()})

def _check_rate_limit(chat_id: str) -> bool:
    now = time.time()
    rate_info = USER_RATE_LIMITS[chat_id]
    
    elapsed = now - rate_info["last_updated"]
    tokens_to_add = elapsed * (RATE_LIMIT_REQUESTS / RATE_LIMIT_WINDOW)
    
    rate_info["tokens"] = min(RATE_LIMIT_REQUESTS, rate_info["tokens"] + tokens_to_add)
    rate_info["last_updated"] = now
    
    if rate_info["tokens"] >= 1:
        rate_info["tokens"] -= 1
        return True
    return False

def send_hud_state(state, context="", tool_name="", category="", desc="", transcript="", split_text="", notify=None, image_url=""):
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        payload = {
            "state": state,
            "context": context,
            "tool_name": tool_name,
            "category": category,
            "description": desc,
            "transcript": transcript,
            "split_text": split_text,
            "image_url": image_url,
            "source": "telegram"
        }
        if notify:
            payload["notify"] = notify
        sock.sendto(json.dumps(payload).encode('utf-8'), ("127.0.0.1", 5005))
    except Exception:
        pass

JARVIS_SYSTEM_PROMPT = """
# JARVIS — Telegram Agent

## Identity
You are JARVIS, an intelligent AI assistant communicating over Telegram. You have full access to desktop control tools, web search, email, calendar, code generation, and more.

## Telegram Output Rules
You are texting, not speaking. Format responses for readability:
1. **Use Markdown formatting.** Bold for emphasis, `code blocks` for technical output, bullet points for lists.
2. **Be concise but complete.** Give full answers, but don't pad with filler. Lead with the result.
3. **Use emoji sparingly** for status indicators (✅ ❌ ⏳ 📎) — never decoratively.
4. **Structure long responses** with headers and sections. Don't dump walls of text.

## Tool Usage
- **NEVER use** `type_user_message_auto`, `write_in_notepad`, `click_on_text`, or any desktop UI automation to reply. Just send text directly.
- **DO use** desktop tools when the user explicitly asks to control the PC (e.g., "open Chrome", "take a screenshot").
- **Act first, ask later.** If the intent is clear, execute the tool immediately.
- **On failure:** Explain briefly what went wrong and suggest an alternative approach.

## Behavior
- **Decisive:** Act on the most likely interpretation. Only clarify when genuinely ambiguous.
- **Proactive:** Use context (time of day, active app, user memories) to give smarter answers.
- **Protective:** Confirm before destructive actions (shutdown, delete files). Everything else: just do it.
- **Identity:** You are JARVIS. Calm confidence, occasional dry wit, zero fluff.

## Language
Respond only in English, even if the user writes in another language.
"""

def get_dynamic_system_prompt() -> str:
    import datetime
    import socket
    import getpass
    
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = getpass.getuser()
    host = socket.gethostname()
    
    try:
        import pygetwindow as gw
        active_window = gw.getActiveWindow()
        active_app = active_window.title if active_window else "None"
    except Exception:
        active_app = "Unknown"
        
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
    return JARVIS_SYSTEM_PROMPT + dynamic_context


def send_message(chat_id: str, text: str) -> str | None:
    """Send a text message and return the message_id. Uses Markdown with a plaintext fallback."""
    if not text.strip():
        return None
    try:
        # Try sending with Markdown parsing first
        resp = requests.post(
            TELEGRAM_API + "sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        data = resp.json()
        
        # If Telegram rejects it due to unclosed markdown entities, fallback to plain text
        if not data.get("ok") and data.get("error_code") == 400:
            logger.warning(f"Markdown parse failed, falling back to plain text: {data.get('description')}")
            resp = requests.post(
                TELEGRAM_API + "sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=10,
            )
            data = resp.json()
            
        if data.get("ok"):
            return str(data["result"]["message_id"])
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
    return None

def _edit_message(chat_id: str, message_id: str, text: str) -> None:
    """Edit an existing Telegram message with Markdown and plaintext fallback."""
    if not text.strip():
        return
    try:
        resp = requests.post(
            TELEGRAM_API + "editMessageText",
            json={"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        data = resp.json()
        if not data.get("ok") and data.get("error_code") == 400:
            requests.post(
                TELEGRAM_API + "editMessageText",
                json={"chat_id": chat_id, "message_id": message_id, "text": text},
                timeout=10,
            )
    except Exception as e:
        # Ignore rate limit errors for edits
        pass


def _send_typing(chat_id: str) -> None:
    try:
        requests.post(
            TELEGRAM_API + "sendChatAction",
            json={"chat_id": chat_id, "action": "typing"},
            timeout=5,
        )
    except Exception:
        pass


async def _transcribe_voice(file_id: str) -> str | None:
    """Download a voice note from Telegram and transcribe it using Groq."""
    try:
        # 1. Get file path from Telegram
        file_info_resp = requests.get(
            TELEGRAM_API + "getFile",
            params={"file_id": file_id},
            timeout=10,
        )
        file_info = file_info_resp.json()
        if not file_info.get("ok"):
            logger.error(f"Failed to get file info: {file_info}")
            return None
            
        file_path = file_info["result"]["file_path"]
        
        # 2. Download the file
        download_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        audio_resp = requests.get(download_url, timeout=20)
        audio_resp.raise_for_status()
        audio_bytes = audio_resp.content
        
        # 3. Transcribe using Groq
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            logger.error("GROQ_API_KEY missing, cannot transcribe voice note.")
            return None
            
        files = {
            "file": ("audio.ogg", audio_bytes, "audio/ogg"),
        }
        data = {
            "model": os.getenv("JARVIS_STT_MODEL", "whisper-large-v3"),
        }
        
        headers = {
            "Authorization": f"Bearer {groq_key}"
        }
        
        transcribe_resp = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers=headers,
            files=files,
            data=data,
            timeout=30,
        )
        transcribe_resp.raise_for_status()
        
        transcription = transcribe_resp.json().get("text", "")
        return transcription.strip()
    except Exception as e:
        logger.error(f"Error transcribing voice note: {e}")
        return None


def _build_llm():
    """Return the configured LLM instance."""
    if TELEGRAM_LLM_API:
        return openai.LLM(
            model="meta/llama-3.3-70b-instruct",
            api_key=TELEGRAM_LLM_API,
            base_url="https://integrate.api.nvidia.com/v1",
        )
    if LOCAL_LLM_URL:
        return openai.LLM(
            model=LOCAL_LLM_MODEL,
            api_key="local-key",
            base_url=LOCAL_LLM_URL,
        )
    return groq.LLM(model="llama-3.3-70b-versatile")


async def handle_message(chat_id: str, text: str) -> None:
    """Process an incoming Telegram message end-to-end."""
    from livekit.agents.llm import ChatMessage
    
    if chat_id not in USER_CONTEXTS:
        USER_CONTEXTS[chat_id] = ChatContext()

    ctx = USER_CONTEXTS[chat_id]
    
    # Update system prompt dynamically
    dynamic_prompt = get_dynamic_system_prompt()
    msgs = ctx.messages()
    if len(msgs) > 0 and msgs[0].role == "system":
        msgs[0].content = [dynamic_prompt]
    else:
        ctx._items.insert(0, ChatMessage(role="system", content=[dynamic_prompt]))

    # Prevent message injection by quoting external content
    safe_text = f"<user_message>{text}</user_message>"
    ctx.add_message(role="user", content=safe_text)
    _send_typing(chat_id)
    
    send_hud_state("thinking", context="tool", tool_name="Telegram Message", category="MESSAGING", desc=f"Received: {text[:40]}...", notify={"title": "Telegram", "body": text[:40] + "...", "category": "MESSAGING"})

    llm = _build_llm()

    # Determine intent and load specific tools for this turn
    intent = classify_intent(text)
    active_tools = [t for t in get_tools_for_category(intent) if t.info.name != "execute_multi_task"]
    logger.info(f"Intent classified as '{intent}' -> loaded {len(active_tools)} tools.")

    try:
        await _run_llm_loop(chat_id, ctx, llm, active_tools)
    except Exception as e:
        logger.error(f"LLM loop error: {e}", exc_info=True)
        send_message(chat_id, f"Sorry, something went wrong: {e}")


async def _run_llm_loop(chat_id: str, ctx: ChatContext, llm, active_tools: list) -> None:
    import time
    from livekit.agents.llm import ChatMessage
    
    tools_dict = {t.info.name: t._func for t in active_tools}
    MAX_LOOPS = 5

    for loop_num in range(MAX_LOOPS):
        _send_typing(chat_id)

        # ── Context Compression ───────────────────────────────────────────────
        msgs = ctx.messages()
        if len(msgs) > 20 and loop_num == 0:
            logger.info(f"Context length {len(msgs)} > 20. Compressing...")
            try:
                # Extract oldest 10 messages (skipping system prompt at index 0)
                old_msgs = msgs[1:11]
                summary_prompt = "Summarize the following conversation briefly:\n"
                for m in old_msgs:
                    # m.content is a list of strings/images, so we extract text
                    content_str = "".join(str(c) for c in m.content) if isinstance(m.content, list) else str(m.content)
                    summary_prompt += f"{m.role}: {content_str}\n"
                
                summary_ctx = ChatContext()
                summary_ctx.add_message(role="user", content=summary_prompt)
                summary_resp = await llm.chat(chat_ctx=summary_ctx).collect()
                
                # Delete old messages from _items
                for m in old_msgs:
                    if m in ctx._items:
                        ctx._items.remove(m)
                
                # Insert summary after system prompt
                sys_idx = 0
                for i, item in enumerate(ctx._items):
                    if getattr(item, "role", None) == "system":
                        sys_idx = i
                        break
                        
                ctx._items.insert(sys_idx + 1, ChatMessage(role="assistant", content=[f"[Compressed history]: {summary_resp.text}"]))
            except Exception as e:
                logger.error(f"Context compression failed: {e}")

        # ── Collect stream (text + tool calls) ────────────────────────────────
        stream = llm.chat(chat_ctx=ctx, tools=active_tools)
        
        response_text = ""
        tool_calls = []
        msg_id = None
        last_edit_time = 0.0
        
        async with stream:
            async for chunk in stream:
                if chunk.delta:
                    if chunk.delta.content:
                        response_text += chunk.delta.content
                        
                        now_time = time.time()
                        # Update Telegram every ~1 second to respect rate limits
                        if now_time - last_edit_time > 1.0 and len(response_text.strip()) > 0:
                            if not msg_id:
                                msg_id = send_message(chat_id, response_text)
                            else:
                                _edit_message(chat_id, msg_id, response_text)
                            
                            send_hud_state("idle", context="response", transcript=response_text)
                            last_edit_time = now_time
                            
                    if chunk.delta.tool_calls:
                        tool_calls.extend(chunk.delta.tool_calls)

        response_text = response_text.strip()
        if msg_id:
            # Final edit to ensure the last chunk is included
            _edit_message(chat_id, msg_id, response_text)
        elif not tool_calls and response_text:
            msg_id = send_message(chat_id, response_text)

        logger.debug(
            f"Loop {loop_num+1}: text={repr(response_text[:80])}, "
            f"tool_calls={[tc.name for tc in tool_calls]}"
        )

        # ── No tool calls → final text reply, done ────────────────────────────
        if not tool_calls:
            if response_text:
                ctx.add_message(role="assistant", content=response_text)
            else:
                logger.warning("LLM returned empty response with no tool calls.")
            return

        # ── Has tool calls → inject assistant turn, execute, inject results ───
        for tc in tool_calls:
            ctx.insert(
                FunctionCall(
                    call_id=tc.call_id,
                    name=tc.name,
                    arguments=tc.arguments,
                )
            )

        if response_text:
            ctx.add_message(role="assistant", content=response_text)

        # Pre-execution: Send "Running..." messages
        tool_status_msgs = {}
        for tc in tool_calls:
            tool_name = tc.name
            args_str = tc.arguments
            
            logger.info(f"Executing tool '{tool_name}' args={args_str!r}")
            
            # Show on HUD
            send_hud_state("thinking", context="tool", tool_name=tool_name, category="TOOL", desc="Executing via Telegram...")
            
            # Send live progress to Telegram
            t_msg_id = send_message(chat_id, f"⏳ *Running:* `{tool_name}`...")
            if t_msg_id:
                tool_status_msgs[tc.call_id] = t_msg_id

            try:
                args = json.loads(args_str) if args_str.strip() else {}
            except json.JSONDecodeError as e:
                logger.error(f"Bad JSON args for {tool_name}: {e}")
                args = {}

            try:
                func = tools_dict.get(tool_name)
                if func is None:
                    result = f"Error: tool '{tool_name}' not found."
                    is_error = True
                elif asyncio.iscoroutinefunction(func):
                    result = str(await func(**args))
                    is_error = False
                else:
                    result = str(func(**args))
                    is_error = False
            except Exception as e:
                result = f"I encountered a technical issue while using the '{tool_name}' tool. Let's try another approach."
                is_error = True
                logger.error(f"Tool {tool_name} exception: {e}", exc_info=True)
                # Log to error telemetry for pattern detection
                try:
                    from Tools.error_telemetry import log_tool_error
                    log_tool_error(tool_name, e, args)
                except Exception:
                    pass

            MAX_TOOL_OUTPUT = 2000
            if len(result) > MAX_TOOL_OUTPUT:
                result = result[:MAX_TOOL_OUTPUT] + f"\n... [Truncated, original length {len(result)} chars]"

            logger.info(f"Tool '{tool_name}' result: {result!r}")

            # Inject tool output using FunctionCallOutput (proper API)
            # The call_id MUST match the FunctionCall inserted above.
            ctx.insert(
                FunctionCallOutput(
                    call_id=tc.call_id,
                    name=tool_name,
                    output=result,
                    is_error=is_error,
                )
            )
            
            # Post-execution: Edit tool status message
            if tc.call_id in tool_status_msgs:
                t_msg_id = tool_status_msgs[tc.call_id]
                if is_error:
                    _edit_message(chat_id, t_msg_id, f"❌ *Failed:* `{tool_name}`")
                else:
                    _edit_message(chat_id, t_msg_id, f"✅ *Done:* `{tool_name}`")

        # Continue loop → LLM will now see the tool results and generate a reply

    # Fallback if we hit MAX_LOOPS without a clean text-only response
    logger.warning("Reached max LLM loops without a final text response.")
    send_message(chat_id, "I ran into a processing loop. Please try again.")


OFFSET_FILE = "telegram_offset.txt"

def load_offset():
    if os.path.exists(OFFSET_FILE):
        try:
            with open(OFFSET_FILE, "r") as f:
                return int(f.read().strip())
        except Exception:
            pass
    return None

def save_offset(offset):
    try:
        with open(OFFSET_FILE, "w") as f:
            f.write(str(offset))
    except Exception:
        pass

async def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is missing in .env. Exiting.")
        return

    logger.info("Starting JARVIS Telegram Bot polling...")
    offset: int | None = load_offset()
    
    import random
    import time
    start_time = time.time()
    
    retry_count = 0
    max_backoff = 60

    while True:
        try:
            resp = requests.get(
                TELEGRAM_API + "getUpdates",
                params={
                    "timeout": 30,
                    "allowed_updates": ["message"],
                    **({"offset": offset} if offset is not None else {}),
                },
                timeout=40,
            )

            if resp.status_code != 200:
                logger.error(f"Telegram API error: {resp.text}")
                retry_count += 1
                backoff_time = min(max_backoff, (2 ** retry_count) + random.uniform(0, 2))
                await asyncio.sleep(backoff_time)
                continue
            
            # Reset backoff on success
            retry_count = 0

            for update in resp.json().get("result", []):
                offset = update["update_id"] + 1
                save_offset(offset)

                msg = update.get("message", {})
                
                # Ignore messages older than 60 seconds before bot startup
                if msg.get("date", 0) < start_time - 60:
                    logger.info(f"Ignoring stale message from {msg.get('date')}")
                    continue
                    
                chat_id = str(msg.get("chat", {}).get("id", ""))
                text = msg.get("text", "")
                voice = msg.get("voice", {})

                if not chat_id:
                    continue
                    
                if not text and voice:
                    # Handle Voice Note
                    file_id = voice.get("file_id")
                    if file_id:
                        _send_typing(chat_id)
                        send_hud_state("thinking", context="tool", tool_name="Transcribing Voice", category="MESSAGING", desc="Processing voice note...")
                        text = await _transcribe_voice(file_id)
                        if not text:
                            send_message(chat_id, "Sorry, I couldn't transcribe that voice note.")
                            continue
                        logger.info(f"Transcribed voice note: {text}")

                if not text:
                    continue

                user = msg.get("from", {})
                username = user.get("username", "Unknown")

                # Security check
                if not ALLOWED_USERS_LIST:
                    send_message(chat_id, "Bot is not configured for any users. Set TELEGRAM_ALLOWED_USERS in .env.")
                    continue
                if (
                    chat_id not in ALLOWED_USERS_LIST
                    and username not in ALLOWED_USERS_LIST
                ):
                    logger.warning(f"Unauthorized: {chat_id} (@{username})")
                    send_message(chat_id, "You are not authorized to use this JARVIS instance.")
                    continue

                if text.startswith("/start"):
                    send_message(chat_id, "🔷 *JARVIS Online*\nAll systems operational.\n\nUse /help to see what I can do, or simply speak/type to me.")
                    continue
                elif text.startswith("/mute"):
                    import socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.sendto(json.dumps({"state": "idle", "mic_muted": True, "notify": {"title": "JARVIS", "body": "Muted via Telegram", "category": "SYSTEM"}}).encode('utf-8'), ("127.0.0.1", 5005))
                    send_message(chat_id, "🔇 *Desktop Microphone Muted*")
                    continue
                elif text.startswith("/unmute"):
                    import socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.sendto(json.dumps({"state": "idle", "mic_muted": False, "notify": {"title": "JARVIS", "body": "Unmuted via Telegram", "category": "SYSTEM"}}).encode('utf-8'), ("127.0.0.1", 5005))
                    send_message(chat_id, "🎙️ *Desktop Microphone Unmuted*")
                    continue
                elif text.startswith("/status"):
                    import psutil
                    cpu = psutil.cpu_percent(interval=0.1)
                    ram = psutil.virtual_memory().percent
                    status_msg = f"📊 *JARVIS System Status*\n\n💻 *CPU:* `{cpu}%`\n🧠 *RAM:* `{ram}%`\n⚡ *Connection:* `Online`\n🔗 *LLM:* `NVIDIA / Groq`"
                    send_message(chat_id, status_msg)
                    continue
                elif text.startswith("/voice"):
                    try:
                        from livekit import api
                        import uuid
                        token = api.AccessToken(
                            os.getenv("LIVEKIT_API_KEY"),
                            os.getenv("LIVEKIT_API_SECRET")
                        )
                        room_name = os.getenv("LIVEKIT_ROOM", "jarvis-room")
                        token.with_identity(f"telegram_user_{chat_id}_{str(uuid.uuid4())[:8]}")
                        token.with_name(username)
                        import datetime
                        token.with_ttl(datetime.timedelta(minutes=30))
                        token.with_grants(api.VideoGrants(
                            room_join=True,
                            room=room_name,
                        ))
                        jwt_token = token.to_jwt()
                        
                        livekit_url = os.getenv("LIVEKIT_URL", "wss://your-project.livekit.cloud")
                        meet_url = f"https://meet.livekit.io/custom?liveKitUrl={livekit_url}&token={jwt_token}"
                        
                        send_message(chat_id, f"🎤 *Voice Bridge Ready*\n\nJoin the JARVIS voice room here:\n[Connect to Voice]({meet_url})")
                    except Exception as e:
                        logger.error(f"Failed to generate LiveKit token: {e}", exc_info=True)
                        send_message(chat_id, f"Failed to generate voice bridge token: {e}")
                    continue
                elif text.startswith("/help"):
                    help_msg = (
                        "🔷 *JARVIS Commands*\n\n"
                        "*/voice* - Join the LiveKit voice bridge\n"
                        "*/mute* - Mute the desktop microphone remotely\n"
                        "*/unmute* - Unmute the desktop microphone\n"
                        "*/status* - Check PC hardware status\n"
                        "*/clear* - Reset conversation memory\n\n"
                        "*Capabilities:*\n"
                        "📧 *Email*: Read, search, summarize, and reply.\n"
                        "🌐 *Web*: Search Google, summarize URLs, scrape websites.\n"
                        "📅 *Calendar*: Check schedule, find free slots, create events.\n"
                        "📈 *Finance*: Track stocks, crypto, and portfolio.\n"
                        "💻 *System*: Process management, volume, brightness, viruses.\n"
                        "⌨️ *Desktop*: Automate apps, typing, clicking, WhatsApp.\n"
                        "🖼️ *Creative*: Generate images and videos.\n"
                    )
                    send_message(chat_id, help_msg)
                    continue
                elif text.startswith("/clear"):
                    if chat_id in USER_CONTEXTS:
                        del USER_CONTEXTS[chat_id]
                    send_message(chat_id, "Conversation memory cleared. Ready for a new task.")
                    continue

                logger.info(f"Received from {chat_id} (@{username}): {text}")

                if not _check_rate_limit(chat_id):
                    logger.warning(f"Rate limit exceeded for {chat_id} (@{username})")
                    send_message(chat_id, "Rate limit exceeded. Please wait a moment before sending more messages.")
                    continue

                # await directly — create_task() caused replies to be
                # garbage-collected before they could run.
                await handle_message(chat_id, text)

        except requests.exceptions.RequestException as e:
            logger.warning(f"Network error: {e}")
            retry_count += 1
            backoff_time = min(max_backoff, (2 ** retry_count) + random.uniform(0, 2))
            logger.info(f"Backing off for {backoff_time:.1f}s")
            await asyncio.sleep(backoff_time)
        except Exception as e:
            logger.error(f"Polling loop error: {e}", exc_info=True)
            retry_count += 1
            backoff_time = min(max_backoff, (2 ** retry_count) + random.uniform(0, 2))
            await asyncio.sleep(backoff_time)


if __name__ == "__main__":
    asyncio.run(main())