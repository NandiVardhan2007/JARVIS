"""Screen reader — screenshot + Gemini vision analysis, spoken summary."""

import base64
import logging
import os
import time
from typing import Literal, Optional

import requests
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
GOOGLE_CLOUD_VISION_API_KEY = os.getenv("GOOGLE_CLOUD_VISION_API_KEY", "")

GEMINI_VISION_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)
GROQ_VISION_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
GOOGLE_VISION_URL = "https://vision.googleapis.com/v1/images:annotate"

LOCAL_LLM_URL   = os.getenv("LOCAL_LLM_URL", "")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "local-model")


def _cleanup_old_screenshots() -> None:
    """Delete screenshots older than 24 hours."""
    save_dir = os.path.join(os.path.expanduser("~/Desktop"), "jarvis_screenshots")
    if not os.path.exists(save_dir):
        return
        
    try:
        now = time.time()
        for filename in os.listdir(save_dir):
            if not filename.endswith(".png"):
                continue
            path = os.path.join(save_dir, filename)
            if os.path.isfile(path):
                # 24 hours = 86400 seconds
                if os.stat(path).st_mtime < now - 86400:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
    except Exception as e:
        logger.warning(f"Failed to cleanup screenshots: {e}")

def _start_cleanup_task():
    import threading
    def run_periodically():
        while True:
            _cleanup_old_screenshots()
            time.sleep(21600)  # 6 hours
    threading.Thread(target=run_periodically, daemon=True).start()

# Run cleanup periodically
_start_cleanup_task()


def _take_screenshot(save_dir: Optional[str] = None, monitor_index: int = 1) -> str:
    """Take a screenshot using mss, save to disk, return file path."""
    import mss
    from PIL import Image

    if not save_dir:
        save_dir = os.path.join(os.path.expanduser("~/Desktop"), "jarvis_screenshots")
    os.makedirs(save_dir, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(save_dir, f"screen_{timestamp}.png")

    with mss.mss() as sct:
        if monitor_index >= len(sct.monitors) or monitor_index < 0:
            monitor_index = 0 # Default to all monitors
            
        sct_img = sct.grab(sct.monitors[monitor_index])
        screenshot = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

    # Resize to max 1920x1080 to keep payload small
    max_w, max_h = 1920, 1080
    w, h = screenshot.size
    if w > max_w or h > max_h:
        ratio = min(max_w / w, max_h / h)
        screenshot = screenshot.resize(
            (int(w * ratio), int(h * ratio)), Image.LANCZOS
        )
    screenshot.save(path, "PNG", optimize=True)
    return path


def _image_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _analyse_with_gemini(b64: str, prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set")
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": b64}},
            ]
        }]
    }
    resp = requests.post(
        GEMINI_VISION_URL,
        params={"key": GEMINI_API_KEY},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def _analyse_with_groq(b64: str, prompt: str) -> str:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set")
    payload = {
        "model": GROQ_VISION_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text",       "text": prompt},
                {"type": "image_url",  "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        }],
        "max_tokens": 1024,
    }
    resp = requests.post(
        GROQ_VISION_URL,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _analyse_with_google_vision_and_llm(b64: str, prompt: str) -> str:
    if not GOOGLE_CLOUD_VISION_API_KEY:
        raise ValueError("GOOGLE_CLOUD_VISION_API_KEY not set")
    
    payload = {
        "requests": [{
            "image": {"content": b64},
            "features": [{"type": "TEXT_DETECTION"}, {"type": "LABEL_DETECTION"}]
        }]
    }
    resp = requests.post(
        GOOGLE_VISION_URL,
        params={"key": GOOGLE_CLOUD_VISION_API_KEY},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    
    responses = data.get("responses", [{}])[0]
    
    text_annotations = responses.get("textAnnotations", [])
    extracted_text = text_annotations[0].get("description", "") if text_annotations else "No text found."
    
    label_annotations = responses.get("labelAnnotations", [])
    labels = [label.get("description", "") for label in label_annotations]
    labels_str = ", ".join(labels) if labels else "No labels found."

    llm_payload = {
        "model": os.getenv("JARVIS_LLM_MODEL", "llama-3.3-70b-versatile"),
        "messages": [{
            "role": "user",
            "content": f"{prompt}\n\n[Google Cloud Vision Data]\nLabels: {labels_str}\n\nOCR Text:\n{extracted_text}"
        }],
        "max_tokens": 1024,
    }
    llm_resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json=llm_payload,
        timeout=30,
    )
    llm_resp.raise_for_status()
    return llm_resp.json()["choices"][0]["message"]["content"].strip()


def _analyse_image(b64: str, prompt: str) -> str:
    """Try Local Vision -> Google Vision → Gemini → Groq fallback."""
    if LOCAL_LLM_URL:
        try:
            url = LOCAL_LLM_URL + "/chat/completions" if not LOCAL_LLM_URL.endswith("chat/completions") else LOCAL_LLM_URL
            payload = {
                "model": LOCAL_LLM_MODEL,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text",       "text": prompt},
                        {"type": "image_url",  "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                }],
                "max_tokens": 1024,
            }
            resp = requests.post(url, headers={"Authorization": "Bearer local-key"}, json=payload, timeout=60)
            resp.raise_for_status()
            logger.info("Screen analysis via local LLM.")
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"Local LLM vision failed ({e}), trying Google Vision...")

    if GOOGLE_CLOUD_VISION_API_KEY and GROQ_API_KEY:
        try:
            result = _analyse_with_google_vision_and_llm(b64, prompt)
            logger.info("Screen analysis via Google Cloud Vision + LLM.")
            return result
        except Exception as e:
            logger.warning(f"Google Cloud Vision failed ({e}), trying Gemini…")
    if GEMINI_API_KEY:
        try:
            result = _analyse_with_gemini(b64, prompt)
            logger.info("Screen analysis via Gemini.")
            return result
        except Exception as e:
            logger.warning(f"Gemini vision failed ({e}), trying Groq…")

    if GROQ_API_KEY:
        try:
            result = _analyse_with_groq(b64, prompt)
            logger.info("Screen analysis via Groq vision.")
            return result
        except Exception as e:
            logger.warning(f"Groq vision failed ({e}).")

    raise RuntimeError(
        "No vision API available. Set GEMINI_API_KEY or ensure GROQ_API_KEY is valid."
    )


# ── Prompt templates ──────────────────────────────────────────────────────────

_PROMPTS = {
    "summary": (
        "You are JARVIS, an AI assistant analyzing a screenshot. Provide a concise spoken-style "
        "summary (3-5 sentences). Identify: the active application or window, what the user is "
        "currently doing (browsing, coding, chatting, etc.), any key content visible (titles, "
        "numbers, messages), and any alerts, errors, or notifications. Be specific — mention "
        "application names, tab titles, and visible data rather than vague descriptions."
    ),
    "document": (
        "You are JARVIS analyzing a document visible on screen. Extract and summarize: the "
        "document title/type, the main topic and thesis, key data points (dates, amounts, "
        "names, figures), and any action items or deadlines mentioned. Give a spoken-style "
        "summary in 4-6 sentences. Ignore headers, footers, and page numbers."
    ),
    "code": (
        "You are JARVIS analyzing code visible on screen. Identify: the programming language, "
        "the file name (if visible in a tab), what the code does (its purpose), any visible "
        "errors, warnings, or red-underlined text in the IDE, and any obvious bugs or issues "
        "you spot. Mention the line numbers if errors are visible. Spoken-style, 3-5 sentences."
    ),
    "ocr": (
        "Extract ALL visible text from this screenshot exactly as it appears on screen. "
        "Preserve the original structure, layout, and hierarchy (headings, labels, values, "
        "table rows, menu items). Use plain text formatting — no added commentary or "
        "summarization. Include button text, status bar content, and any tooltip text visible."
    ),
    "error": (
        "You are JARVIS. Focus exclusively on any error messages, warnings, exception dialogs, "
        "crash reports, or red/yellow alert UI elements visible on screen. For each error: "
        "state what it says, which application shows it, and suggest a likely fix. If no errors "
        "are visible, say 'No errors visible on screen.' Spoken-style, concise."
    ),
}


# ── Public tools ──────────────────────────────────────────────────────────────

@function_tool
async def read_screen(
    mode: Literal["summary", "document", "code", "ocr", "error"] = "summary",
    custom_question: Optional[str] = None,
    monitor_index: int = 1,
) -> str:
    """
    Takes a screenshot of the current screen and analyses it using a vision AI model.
    Returns a spoken-style description of what is on screen.

    Args:
        mode: Analysis mode —
            "summary"  : General overview of what's on screen (default).
            "document" : Summarise a document, PDF, or article visible on screen.
            "code"     : Describe code, highlight errors or what it does.
            "ocr"      : Extract all visible text verbatim (no AI summary).
            "error"    : Focus on error messages or warnings on screen.
        custom_question: Optional specific question about the screen content,
            e.g. "What is the total amount on this invoice?" Overrides mode prompt.
        monitor_index: Which monitor to screenshot (1 for primary, 2 for secondary, 0 for all).
    """
    logger.info(f"Screen read requested — mode: {mode}, question: {custom_question}, monitor: {monitor_index}")
    try:
        path = _take_screenshot(monitor_index=monitor_index)
        b64  = _image_to_base64(path)

        if custom_question:
            prompt = (
                f"You are JARVIS, an AI desktop assistant. Analyze this screenshot carefully "
                f"and answer the following question precisely. Be specific with numbers, names, "
                f"and data visible on screen. Answer in 2-4 natural sentences.\n\n"
                f"Question: {custom_question}"
            )
        else:
            prompt = _PROMPTS.get(mode, _PROMPTS["summary"])

        result = _analyse_image(b64, prompt)

        # Clean up screenshot after use (optional — comment out to keep)
        try:
            os.remove(path)
        except OSError:
            pass

        return result

    except Exception as e:
        logger.error(f"Screen read failed: {e}")
        return f"Screen analysis failed: {e}"


@function_tool
async def read_selected_region(
    x: int,
    y: int,
    width: int,
    height: int,
    question: Optional[str] = None,
) -> str:
    """
    Captures and analyses a specific region of the screen instead of the full display.
    Useful for reading a single window, dialog box, or element.

    Args:
        x: Left edge of the region in pixels.
        y: Top edge of the region in pixels.
        width: Width of the region in pixels.
        height: Height of the region in pixels.
        question: Optional question about the captured region.
    """
    logger.info(f"Region capture: ({x},{y}) {width}x{height}")
    try:
        import pyautogui
        from PIL import Image

        screenshot = pyautogui.screenshot(region=(x, y, width, height))
        save_dir = os.path.join(os.path.expanduser("~/Desktop"), "jarvis_screenshots")
        os.makedirs(save_dir, exist_ok=True)
        path = os.path.join(save_dir, f"region_{time.strftime('%H%M%S')}.png")
        screenshot.save(path)

        b64 = _image_to_base64(path)
        prompt = (
            question
            if question
            else (
                "You are JARVIS. Analyze this screen region precisely. Describe: what UI "
                "element or content is captured, any text visible (read it out), the state "
                "of buttons/toggles/inputs, and any relevant data. Be specific, 2-3 sentences."
            )
        )

        result = _analyse_image(b64, prompt)

        try:
            os.remove(path)
        except OSError:
            pass

        return result

    except Exception as e:
        return f"Region capture failed: {e}"

@function_tool
async def list_monitors() -> str:
    """Lists available monitors/displays and their IDs to be used in read_screen."""
    try:
        import mss
        with mss.mss() as sct:
            monitors = sct.monitors
            if len(monitors) <= 1:
                return "Only 1 monitor detected (or running in headless mode)."
                
            # monitors[0] is a virtual monitor encompassing all physical monitors
            result = f"Found {len(monitors)-1} physical monitor(s):\n"
            for i, monitor in enumerate(monitors[1:], 1):
                result += f"Monitor {i}: {monitor['width']}x{monitor['height']} at ({monitor['left']}, {monitor['top']})\n"
            return result
    except Exception as e:
        return f"Failed to list monitors: {e}"
