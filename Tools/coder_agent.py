"""Autonomous AI Coder loop for generating and testing code."""

import logging
import os
import subprocess
import requests
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:1234/v1")
LOCAL_CODE_LLM_MODEL = os.getenv("LOCAL_CODE_LLM_MODEL", os.getenv("LOCAL_LLM_MODEL", "local-model"))

def _call_llm(system: str, user: str) -> str:
    url = LOCAL_LLM_URL + "/chat/completions" if not LOCAL_LLM_URL.endswith("chat/completions") else LOCAL_LLM_URL
    resp = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json={
            "model": LOCAL_CODE_LLM_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": 4096,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

def _extract_code(text: str, language: str = "python") -> str:
    """Extract code from markdown fences if present."""
    if f"```{language}" in text:
        return text.split(f"```{language}")[1].split("```")[0].strip()
    elif "```" in text:
        return text.split("```")[1].split("```")[0].strip()
    return text.strip()

@function_tool
async def auto_write_and_debug_code(prompt: str, filename: str) -> str:
    """
    Writes a Python script based on the prompt, executes it, and automatically debugging it up to 3 times if it fails.
    This is an autonomous loop that works in the background.

    Args:
        prompt: Detailed description of what the script should do.
        filename: Name of the file to save as (without .py).
    """
    logger.info(f"Auto-coder starting for: {filename}.py")
    
    system_prompt = (
        "You are an elite Python software engineer. Generate a complete, runnable python script based on the user's prompt. "
        "Output ONLY the raw code inside a markdown block. "
        "The code must include necessary imports and print its final output or status so the user knows it succeeded."
    )
    
    current_prompt = prompt
    max_retries = 3
    
    for attempt in range(1, max_retries + 1):
        try:
            # 1. Generate code
            logger.info(f"Generating code (Attempt {attempt})...")
            raw_response = _call_llm(system_prompt, current_prompt)
            code = _extract_code(raw_response)
            
            # 2. Save file
            save_path = os.path.join(os.path.expanduser("~"), "Documents", "JARVIS", f"{filename}.py")
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(code)
                
            # 3. Execute code
            logger.info(f"Executing {save_path}...")
            result = subprocess.run(
                ["python", save_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # 4. Check for errors
            if result.returncode == 0:
                stdout = result.stdout.strip()
                return f"Successfully wrote and tested '{filename}.py'.\nOutput:\n{stdout[:500]}"
            else:
                stderr = result.stderr.strip()
                logger.warning(f"Execution failed on attempt {attempt}:\n{stderr}")
                
                if attempt == max_retries:
                    return f"Failed to fix the code after {max_retries} attempts. Last error:\n{stderr[-500:]}"
                
                # Update prompt with error for next iteration
                current_prompt = (
                    f"I tried running your previous code but it failed with this error:\n"
                    f"```\n{stderr}\n```\n"
                    f"Please rewrite the entire Python script to fix this bug. Output only the fixed code."
                )
                
        except Exception as e:
            return f"Auto-coder encountered an unexpected error: {str(e)}"
            
    return "Auto-coder loop exhausted."
