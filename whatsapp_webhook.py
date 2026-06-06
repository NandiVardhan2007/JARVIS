import os
import json
import logging
import asyncio
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("whatsapp_webhook")

WAHA_URL = os.getenv("WAHA_URL", "http://localhost:3000")
WHATSAPP_API_KEY = os.getenv("WHATSAPP_API_KEY", "")

# We expect a comma-separated list of numbers like "1234567890,0987654321"
_allowed_env = os.getenv("WHATSAPP_ALLOWED_CONTACTS", "")
ALLOWED_CONTACTS = [c.strip() for c in _allowed_env.split(",")] if _allowed_env else []

_owner_env = os.getenv("WHATSAPP_OWNER_CONTACTS", "917337419275")
OWNER_CONTACTS = [c.strip() for c in _owner_env.split(",")]

PORT = int(os.getenv("WHATSAPP_WEBHOOK_PORT", "5006"))

from livekit.agents.llm import ChatContext, ChatMessage
from livekit.plugins import groq, openai
from Tools import get_all_tools, get_tools_for_category, classify_intent

USER_CONTEXTS = {}

def _build_llm():
    if os.getenv("TELEGRAM_LLM_API", "").strip():
        return openai.LLM(
            model="meta/llama-3.3-70b-instruct",
            api_key=os.getenv("TELEGRAM_LLM_API", "").strip(),
            base_url="https://integrate.api.nvidia.com/v1",
        )
    return groq.LLM(model="llama-3.3-70b-versatile")

def send_whatsapp_reply(chat_id: str, text: str):
    # Prefix text with robot emoji to prevent infinite loops when messaging yourself
    if not (text.startswith("⏳") or text.startswith("✅") or text.startswith("❌") or text.startswith("🤖")):
        text = f"🤖 {text}"
        
    url = f"{WAHA_URL.rstrip('/')}/api/sendText"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if WHATSAPP_API_KEY:
        headers["X-Api-Key"] = WHATSAPP_API_KEY
    data = {"chatId": chat_id, "text": text, "session": "default"}
    try:
        resp = requests.post(url, json=data, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to send reply to WAHA: {e}")

async def _generate_tts_waha(text: str) -> str | None:
    api_key = os.getenv("WHATSAPP_CARTESIA_API_KEY")
    voice_id = os.getenv("WHATSAPP_CARTESIA_VOICE_ID")
    if not api_key or not voice_id:
        return None
        
    try:
        url = "https://api.cartesia.ai/tts/bytes"
        headers = {
            "Cartesia-Version": "2024-06-10",
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }
        # Strip robot emojis before speaking
        clean_text = text.replace("🤖", "").replace("⏳", "").replace("✅", "").replace("❌", "").strip()
        data = {
            "model_id": "sonic-3.5",
            "transcript": clean_text,
            "voice": {"mode": "id", "id": voice_id},
            "output_format": {"container": "wav", "encoding": "pcm_s16le", "sample_rate": 44100}
        }
        logger.info("Generating TTS via Cartesia...")
        resp = requests.post(url, json=data, headers=headers, timeout=30)
        if resp.status_code != 200:
            logger.error(f"Cartesia API Error {resp.status_code}: {resp.text}")
        resp.raise_for_status()
        import base64
        return base64.b64encode(resp.content).decode('utf-8')
    except Exception as e:
        logger.error(f"TTS Generation failed: {e}")
        return None

def send_whatsapp_voice(chat_id: str, audio_b64: str) -> bool:
    url = f"{WAHA_URL.rstrip('/')}/api/sendVoice"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if WHATSAPP_API_KEY:
        headers["X-Api-Key"] = WHATSAPP_API_KEY
    data = {
        "chatId": chat_id,
        "session": "default",
        "file": {
            "mimetype": "audio/wav",
            "filename": "voice.wav",
            "data": f"data:audio/wav;base64,{audio_b64}"
        }
    }
    try:
        response = requests.post(url, json=data, headers=headers, timeout=15)
        response.raise_for_status()
        logger.info(f"Successfully sent voice reply to {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send voice to WAHA: {e}")
        return False

def send_whatsapp_image(chat_id: str, file_path: str, caption: str = "") -> bool:
    url = f"{WAHA_URL.rstrip('/')}/api/sendFile"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if WHATSAPP_API_KEY:
        headers["X-Api-Key"] = WHATSAPP_API_KEY
    
    import base64
    import mimetypes
    try:
        mime = mimetypes.guess_type(file_path)[0] or "image/jpeg"
        with open(file_path, "rb") as f:
            file_data = f.read()
        b64_data = base64.b64encode(file_data).decode('utf-8')
        
        data = {
            "chatId": chat_id,
            "session": "default",
            "caption": caption,
            "file": {
                "mimetype": mime,
                "filename": os.path.basename(file_path),
                "data": f"data:{mime};base64,{b64_data}"
            }
        }
        response = requests.post(url, json=data, headers=headers, timeout=60)
        response.raise_for_status()
        logger.info(f"Successfully sent image reply to {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send image to WAHA: {e}")
        return False

async def _transcribe_waha_voice(msg_id: str, media_url: str = "") -> str | None:
    try:
        import urllib.parse
        encoded_msg_id = urllib.parse.quote(msg_id, safe='')
        
        if media_url:
            if "localhost" in media_url or "127.0.0.1" in media_url:
                parsed_url = urllib.parse.urlparse(media_url)
                url = f"{WAHA_URL.rstrip('/')}{parsed_url.path}"
            else:
                url = media_url
        else:
            url = f"{WAHA_URL.rstrip('/')}/api/default/messages/{encoded_msg_id}/download"
            
        logger.info(f"Downloading voice note from: {url}")
        headers = {"Accept": "application/json"}
        if WHATSAPP_API_KEY:
            headers["X-Api-Key"] = WHATSAPP_API_KEY
            
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        
        content_type = resp.headers.get("Content-Type", "")
        if "application/json" in content_type:
            data = resp.json()
            
            import base64
            mimetype = data.get("mimetype", "")
            if not (mimetype.startswith("audio/") or mimetype.startswith("video/")):
                logger.info(f"Message {msg_id} is not audio (mimetype: {mimetype}). Skipping STT.")
                return None
                
            audio_bytes = base64.b64decode(data.get("data", ""))
        else:
            if not (content_type.startswith("audio/") or content_type.startswith("video/") or content_type == "application/octet-stream"):
                logger.info(f"Message {msg_id} is not audio (content-type: {content_type}). Skipping STT.")
                return None
            audio_bytes = resp.content
        
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            logger.error("GROQ_API_KEY missing for STT")
            return None
            
        files = {
            "file": ("audio.ogg", audio_bytes, "audio/ogg"),
        }
        form_data = {
            "model": os.getenv("JARVIS_STT_MODEL", "whisper-large-v3"),
        }
        auth_headers = {
            "Authorization": f"Bearer {groq_key}"
        }
        
        logger.info("Transcribing voice note via Groq STT...")
        stt_resp = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers=auth_headers,
            files=files,
            data=form_data,
            timeout=30,
        )
        stt_resp.raise_for_status()
        
        return stt_resp.json().get("text", "").strip()
    except Exception as e:
        logger.error(f"Error in WAHA voice transcription: {e}")
        return None


async def handle_whatsapp_message(chat_id: str, text: str, is_owner: bool = False, msg_id: str = "", has_media: bool = False, msg_type: str = "", media_url: str = ""):
    if has_media and (msg_type in ("ptt", "audio", "voice") or not text):
        transcribed = await _transcribe_waha_voice(msg_id, media_url)
        if transcribed:
            text = transcribed
            send_whatsapp_reply(chat_id, f"📝 *Transcription:* {text}")
        elif msg_type in ("ptt", "audio", "voice"):
            send_whatsapp_reply(chat_id, "❌ *Failed to transcribe voice note.*")
            return
            
    if not text:
        logger.info("Message has no text and couldn't be transcribed. Ignoring.")
        return

    if chat_id not in USER_CONTEXTS:
        USER_CONTEXTS[chat_id] = ChatContext()
    
    ctx = USER_CONTEXTS[chat_id]
    
    if is_owner:
        # Owner messaging themselves — Full PC Control
        try:
            from telegram_bot import get_dynamic_system_prompt
            dynamic_prompt = get_dynamic_system_prompt().replace("Telegram", "WhatsApp")
            dynamic_prompt += """

## WhatsApp-Specific Rules
- **Format for WhatsApp:** Use *bold* and _italic_ (WhatsApp style). No markdown headers or code blocks — they don't render.
- **Keep replies short.** WhatsApp is a mobile chat — walls of text are unreadable. Max 3-4 short paragraphs.
- **Language:** Reply in the same language the user uses. If they write in Telugu, respond in Telugu script. If Hindi, respond in Devanagari. Default to English.
- **Voice notes:** When the user sends a voice note, keep your reply natural and conversational as if speaking back.
"""
        except ImportError:
            dynamic_prompt = (
                "You are JARVIS, a smart AI assistant on WhatsApp with full PC control. "
                "Be concise, use *bold* for emphasis (WhatsApp style). "
                "Reply in the same language the user uses."
            )
            
        intent = classify_intent(text)
        active_tools = [t for t in get_tools_for_category(intent) if t.info.name != "execute_multi_task"]
    else:
        # Someone else messaging — Auto-reply on behalf of owner, NO tools for security
        dynamic_prompt = (
            "You are JARVIS, an AI assistant replying on behalf of your owner on WhatsApp. "
            "Be warm, polite, and conversational — you represent your owner, so be helpful and friendly. "
            "You do NOT have access to PC control or personal data tools for this conversation (security restriction). "
            "You CAN generate images if they explicitly ask for one. "
            "Keep replies short and natural for WhatsApp. Use *bold* for emphasis. "
            "Reply in the same language the user uses — if they message in Telugu, reply in Telugu script."
        )
        intent = classify_intent(text)
        if intent == "creative":
            try:
                from Tools.ai_image import generate_local_image_comfyui
                active_tools = [generate_local_image_comfyui]
            except Exception:
                active_tools = []
        else:
            active_tools = []
        
    msgs = ctx.messages()
    if len(msgs) > 0 and msgs[0].role == "system":
        msgs[0].content = [dynamic_prompt]
    else:
        ctx._items.insert(0, ChatMessage(role="system", content=[dynamic_prompt]))
        
    ctx.add_message(role="user", content=text)
    logger.info(f"Processing message from {chat_id} (is_owner={is_owner}): {text[:50]}")
    
    llm = _build_llm()
    
    MAX_LOOPS = 5
    from livekit.agents.llm.chat_context import FunctionCall, FunctionCallOutput
    tools_dict = {t.info.name: t._func for t in active_tools}

    for loop_num in range(MAX_LOOPS):
        try:
            res = await llm.chat(chat_ctx=ctx, tools=active_tools).collect()
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            break
            
        response_text = res.text if res.text else ""
            
        if not res.tool_calls:
            if response_text:
                if has_media and msg_type in ("ptt", "audio", "voice"):
                    audio_b64 = await _generate_tts_waha(response_text)
                    if audio_b64:
                        send_whatsapp_voice(chat_id, audio_b64)
                    else:
                        send_whatsapp_reply(chat_id, response_text)
                else:
                    send_whatsapp_reply(chat_id, response_text)
                ctx.add_message(role="assistant", content=response_text)
            break
            
        # Execute tools
        for tc in res.tool_calls:
            ctx.insert(FunctionCall(call_id=tc.call_id, name=tc.name, arguments=tc.arguments))
            
        if response_text:
            ctx.add_message(role="assistant", content=response_text)
            if has_media and msg_type in ("ptt", "audio", "voice"):
                audio_b64 = await _generate_tts_waha(response_text)
                if audio_b64:
                    send_whatsapp_voice(chat_id, audio_b64)
                else:
                    send_whatsapp_reply(chat_id, response_text)
            else:
                send_whatsapp_reply(chat_id, response_text)
            
        # Inform user a tool is running
        
        for tc in res.tool_calls:
            tool_name = tc.name
            args_str = tc.arguments
            
            try:
                args = json.loads(args_str) if args_str.strip() else {}
            except Exception:
                args = {}
                
            try:
                func = tools_dict.get(tool_name)
                if func is None:
                    result = f"Error: Tool {tool_name} not found."
                    is_error = True
                elif asyncio.iscoroutinefunction(func):
                    result = str(await func(**args))
                    is_error = False
                else:
                    result = str(func(**args))
                    is_error = False
            except Exception as e:
                result = str(e)
                is_error = True
                # Log to error telemetry for pattern detection
                try:
                    from Tools.error_telemetry import log_tool_error
                    log_tool_error(tool_name, e, args)
                except Exception:
                    pass
                
            ctx.insert(FunctionCallOutput(call_id=tc.call_id, name=tool_name, output=result, is_error=is_error))
            
            if is_error:
                send_whatsapp_reply(chat_id, f"❌ *Failed:* `{tool_name}`")
            else:
                send_whatsapp_reply(chat_id, f"✅ *Finished:* `{tool_name}`")
                
            # Intercept image tools
            if not is_error and "Saved to: " in result:
                try:
                    import re
                    match = re.search(r"Saved to:\s*(.+)", result)
                    if match:
                        file_path = match.group(1).strip()
                        if os.path.exists(file_path):
                            send_whatsapp_image(chat_id, file_path, caption=f"Generated by {tool_name}")
                except Exception as e:
                    logger.error(f"Failed to extract and send image: {e}")


import time
from collections import OrderedDict

START_TIME = time.time()

class _LRUDedup:
    """LRU-based message deduplication that evicts oldest entries instead of clearing all."""
    def __init__(self, maxsize=1000):
        self._data = OrderedDict()
        self._maxsize = maxsize
    def add(self, item):
        self._data[item] = None
        self._data.move_to_end(item)
        while len(self._data) > self._maxsize:
            self._data.popitem(last=False)
    def __contains__(self, item):
        return item in self._data

PROCESSED_MESSAGE_IDS = _LRUDedup(maxsize=1000)

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            print(f"DEBUG INCOMING WEBHOOK: {post_data}", flush=True)
            payload = json.loads(post_data)
            event = payload.get("event")
            
            # WAHA Webhook Payload structure for message:
            if event in ("message", "message.any"):
                msg = payload.get("payload", {})
            # Support direct jarvis-waha custom payload
            elif "id" in payload and ("body" in payload or payload.get("hasMedia")):
                msg = payload
            else:
                print("DEBUG: Webhook format not recognized, ignoring.", flush=True)
                self.send_response(200)
                self.end_headers()
                return
                
            msg_id = msg.get("id", "")
            if isinstance(msg_id, dict):
                msg_id = msg_id.get("_serialized", "")
                
            # Removed timestamp check to avoid clock drift issues
            
            if msg_id and msg_id in PROCESSED_MESSAGE_IDS:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Duplicate ignored")
                return
            if msg_id:
                PROCESSED_MESSAGE_IDS.add(msg_id)

            chat_id = msg.get("from", "")
            text = msg.get("body", "")
            is_from_me = msg.get("fromMe", False)
            has_media = msg.get("hasMedia", False)
            msg_type = msg.get("type", msg.get("_data", {}).get("type", ""))
            
            # Ignore messages sent by JARVIS to prevent infinite loops when messaging yourself
            is_bot_msg = text and (text.startswith("🤖") or text.startswith("⏳") or text.startswith("✅") or text.startswith("❌"))
            
            if has_media:
                logger.info(f"WAHA MEDIA PAYLOAD: {json.dumps(msg)}")
            
            if (text or has_media) and chat_id and not is_bot_msg:
                number_only = chat_id.split("@")[0]
                is_owner = is_from_me or (number_only in OWNER_CONTACTS)
                
                # Prevent intercepting outgoing messages to non-owners
                if is_from_me and number_only not in OWNER_CONTACTS:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"Ignored outgoing message")
                    return
                
                if not ALLOWED_CONTACTS:
                    logger.warning("WHATSAPP_ALLOWED_CONTACTS is empty. Rejecting all messages.")
                elif number_only in ALLOWED_CONTACTS:
                    # Offload to async event loop thread
                    media_url = msg.get("media", {}).get("url", "")
                    threading.Thread(target=lambda: asyncio.run(handle_whatsapp_message(chat_id, text, is_owner, msg_id, has_media, msg_type, media_url))).start()
                else:
                    logger.info(f"Ignored message from unauthorized contact: {number_only}")
            
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        except Exception as e:
            logger.error(f"Error parsing webhook: {e}")
            self.send_response(500)
            self.end_headers()

def run_server():
    server = HTTPServer(('0.0.0.0', PORT), WebhookHandler)
    logger.info(f"WAHA Webhook Server listening on 0.0.0.0:{PORT}...")
    server.serve_forever()

if __name__ == "__main__":
    run_server()
