"""Terminal / Shell Tool for JARVIS — hardened sandbox."""

import subprocess
import logging
import re
import os
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

# ── Allowlist: base command names that are allowed ───────────────────────────
ALLOWED_COMMANDS = {
    "git", "echo", "dir", "ls", "pwd",
    "whoami", "ipconfig", "ping", "cd", "type", "cat", "grep",
    "mkdir", "find", "python", "pip", "npm", "node"
}


def _is_command_safe(command: str) -> tuple[bool, str]:
    """
    Multi-layer safety check on the command string.
    Returns (is_safe, reason) — reason is non-empty only when blocked.
    """
    cmd_stripped = command.strip()
    if not cmd_stripped:
        return False, "Empty command."

    # First-word allowlist
    first_word = cmd_stripped.split()[0].lower()
    first_word = os.path.splitext(os.path.basename(first_word))[0].lower()
    
    if first_word not in ALLOWED_COMMANDS:
        return False, f"Command '{first_word}' is not in the allowlist for safety."

    # Prevent chaining to escape sandbox
    if any(char in cmd_stripped for char in ["|", "&", ";", ">", "<", "`", "$", "\n", "\r"]):
        return False, "Command chaining and redirection are blocked for safety."

    return True, ""


@function_tool
async def run_terminal_command(command: str) -> str:
    """
    Executes a shell command (e.g. Python scripts, git, npm) in the terminal.

    Args:
        command: The shell command to execute.
    """
    try:
        is_safe, reason = _is_command_safe(command)
        if not is_safe:
            logger.warning(f"Blocked command: {command!r} — {reason}")
            return f"Command blocked: {reason}"

        # Run command
        logger.info(f"Running terminal command: {command}")

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30  # Hard timeout
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode == 0:
            out = f"Command succeeded.\n"
            if stdout: out += f"[STDOUT]:\n{stdout}"
            if stderr: out += f"\n[STDERR]:\n{stderr}"
            return out.strip()
        else:
            out = f"Command failed with exit code {result.returncode}.\n"
            if stdout: out += f"[STDOUT]:\n{stdout}\n"
            if stderr: out += f"[STDERR]:\n{stderr}"
            return out.strip()

    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds."
    except Exception as e:
        logger.error(f"Terminal execution error: {e}")
        return f"Execution error: {e}"
