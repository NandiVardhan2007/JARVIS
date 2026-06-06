"""Code generation — Groq primary, NVIDIA NIM fallback. Types output into active editor."""

import logging
import os
import subprocess
import requests
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

# ── Groq (primary) ────────────────────────────────────────────────────────────
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GROQ_API_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_LLM_MODEL = "llama-3.3-70b-versatile"

# ── NVIDIA NIM (fallback) ─────────────────────────────────────────────────────
NVIDIA_API_KEY  = os.getenv("NVIDIA_API_KEY", "")
NIM_API_URL     = "https://integrate.api.nvidia.com/v1/chat/completions"
NIM_LLM_MODEL   = "meta/llama-3.3-70b-instruct"

# ── Local LLM (LM Studio) ─────────────────────────────────────────────────────
LOCAL_LLM_URL   = os.getenv("LOCAL_LLM_URL", "")
LOCAL_CODE_LLM_MODEL = os.getenv("LOCAL_CODE_LLM_MODEL", os.getenv("LOCAL_LLM_MODEL", "local-model"))


def _chat_completion(system: str, user: str) -> str:
    """
    Calls Groq first; falls back to NVIDIA NIM if Groq fails or key is missing.
    Returns the raw content string from the model.
    """
    def _call(url: str, key: str, model: str) -> str:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                "temperature": 0.2,
                "max_tokens": 4096,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    # 0. Try Local LLM
    if LOCAL_LLM_URL:
        try:
            result = _call(LOCAL_LLM_URL + "/chat/completions" if not LOCAL_LLM_URL.endswith("chat/completions") else LOCAL_LLM_URL, "local-key", LOCAL_CODE_LLM_MODEL)
            logger.info("Code generated via local LLM.")
            return result
        except Exception as e:
            logger.warning(f"Local LLM code generation failed ({e}), falling back...")

    # 1. Try Groq
    if GROQ_API_KEY:
        try:
            result = _call(GROQ_API_URL, GROQ_API_KEY, GROQ_LLM_MODEL)
            logger.info("Code generated via Groq.")
            return result
        except Exception as e:
            logger.warning(f"Groq code generation failed ({e}), trying NVIDIA NIM...")

    # 2. Fallback to NIM
    if NVIDIA_API_KEY:
        try:
            result = _call(NIM_API_URL, NVIDIA_API_KEY, NIM_LLM_MODEL)
            logger.info("Code generated via NVIDIA NIM fallback.")
            return result
        except Exception as e:
            raise RuntimeError(f"Both Groq and NVIDIA NIM failed. Last error: {e}")

    raise RuntimeError(
        "No API keys configured. Set GROQ_API_KEY or NVIDIA_API_KEY in your .env file."
    )


def _strip_fences(code: str) -> str:
    """Remove markdown code fences if the model added them."""
    if code.startswith("```"):
        lines = code.split("\n")
        end = -1 if lines[-1].strip() == "```" else len(lines)
        return "\n".join(lines[1:end])
    return code


@function_tool
async def generate_and_type_code(
    prompt: str,
    filename: str = "jarvis_code",
    language: str = "python",
    open_notepad: bool = False,
) -> str:
    """
    Generates complete, production-ready code via Groq (with NVIDIA NIM fallback)
    and types it directly into the currently active editor window.

    Args:
        prompt: Description of what the code should do.
        filename: Output filename without extension (used if auto-type fails).
        language: Programming language — python, javascript, java, cpp, go, rust, etc.
        open_notepad: Whether to open Notepad first and save the code into Documents/JARVIS notes.
    """
    logger.info(f"Generating {language} code...")

    system_msg = (
        f"You are JARVIS, an expert {language} developer. Generate complete, production-ready "
        f"code based on the user's description.\n\n"
        "Rules:\n"
        "1. Output ONLY raw code — no markdown fences, no explanations, no preamble.\n"
        "2. Code must be complete, self-contained, and immediately runnable.\n"
        f"3. Follow {language} best practices and style conventions "
        "(PEP 8 for Python, ESLint for JS, etc.).\n"
        "4. Include necessary imports/headers at the top.\n"
        "5. Add concise docstrings/comments for complex logic.\n"
        "6. Use proper error handling — never leave exceptions silently caught.\n"
        "7. Prefer modern language features and idiomatic patterns.\n"
        "8. Use proper indentation and consistent spacing throughout."
    )

    try:
        raw = _chat_completion(system_msg, prompt)
        code = _strip_fences(raw)

        # Type into active editor window
        try:
            import pyautogui
            import time
            pyautogui.FAILSAFE = False
            
            if open_notepad:
                # Open Notepad
                pyautogui.hotkey("win", "r")
                time.sleep(0.5)
                pyautogui.write("notepad", interval=0.05)
                pyautogui.press("enter")
                time.sleep(1.5)
                # clear pre-existing content just in case
                pyautogui.hotkey("ctrl", "a")
                pyautogui.press("delete")
                
            pyautogui.write(code, interval=0.02)
            
            if open_notepad:
                # Save the file
                time.sleep(0.5)
                pyautogui.hotkey("ctrl", "s")
                time.sleep(1.0)
                
                # Documents folder path
                docs_dir = os.path.join(os.path.expanduser("~"), "Documents", "JARVIS")
                os.makedirs(docs_dir, exist_ok=True)
                
                ext_map = {
                    "python": "py", "javascript": "js", "typescript": "ts",
                    "java": "java", "cpp": "cpp", "c": "c", "go": "go",
                    "rust": "rs", "php": "php", "kotlin": "kt", "swift": "swift",
                    "text": "txt", "plain": "txt", "txt": "txt"
                }
                ext = ext_map.get(language.lower(), language.lower())
                save_path = os.path.join(docs_dir, f"{filename}.{ext}")
                
                pyautogui.write(save_path, interval=0.02)
                time.sleep(0.5)
                pyautogui.press("enter")
                time.sleep(0.5)
                return f"{language.capitalize()} code generated, typed in Notepad, and saved to: {save_path}"
                
            return f"{language.capitalize()} code generated and typed ({len(code)} characters)."
        except Exception as type_err:
            # Fallback: save to Desktop
            ext_map = {
                "python": "py", "javascript": "js", "typescript": "ts",
                "java": "java", "cpp": "cpp", "c": "c", "go": "go",
                "rust": "rs", "php": "php", "kotlin": "kt", "swift": "swift",
                "text": "txt", "plain": "txt", "txt": "txt"
            }
            ext = ext_map.get(language.lower(), language.lower())
            save_path = os.path.join(os.path.expanduser("~/Desktop"), f"{filename}.{ext}")
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(code)
            return (
                f"Code generated and saved to: {save_path}\n"
                f"(Auto-type unavailable: {type_err})"
            )
    except Exception as e:
        return f"Code generation failed: {e}"


@function_tool
async def run_file_in_vscode(file_path: str) -> str:
    """
    Opens a file in Visual Studio Code.

    Args:
        file_path: Path to the file to open.
    """
    try:
        subprocess.Popen(["code", file_path])
        return f"Opened '{file_path}' in VS Code."
    except Exception as e:
        return f"Failed to open in VS Code: {e}"
