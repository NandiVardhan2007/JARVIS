"""Terminal / Shell Tool for JARVIS — hardened sandbox.

Security model
--------------
1. Commands are parsed with `shlex.split()` and executed via
   `subprocess.run(argv, shell=False, ...)`. There is no shell in the loop,
   so shell metacharacters (; | & > < $() and backticks etc.) are never interpreted —
   they're just inert argument text to the child process, which eliminates
   command-chaining/injection as an attack vector entirely.
2. Only an explicit allowlist of read-only / informational / dev-tooling
   base commands may run. General-purpose interpreters and package managers
   (`python`, `pip`, `node`, `npm`, ...) are intentionally EXCLUDED: letting
   an "allowlisted" command run arbitrary code (`python3 -c "..."`) defeats
   the whole point of an allowlist, so those tools are not exposed here.
   Use the dedicated `run_file_in_vscode` / `auto_write_and_debug_code`
   tools for code execution instead — they run in their own accounted-for
   flow rather than a bare shell.
3. A per-argument denylist blocks dangerous flags on otherwise-safe
   commands (e.g. find's -exec/-delete, curl/wget upload & data flags
   that could be used to exfiltrate local files to a remote URL).
4. A hard 30s timeout and capped output size prevent runaway/hanging
   commands from blocking the agent indefinitely.
"""

import logging
import os
import shlex
import subprocess

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

# ── Allowlist: base command names that are allowed ───────────────────────────
# Deliberately excludes python/python3/pip/npm/node/bash/sh — anything that is
# itself a general-purpose code interpreter or can install/execute arbitrary
# code defeats sandboxing.
ALLOWED_COMMANDS = {
    "git", "echo", "ls", "pwd", "whoami", "ifconfig", "ip", "ping",
    "cat", "grep", "mkdir", "find", "top", "ps", "df", "free", "uptime",
    "curl", "wget", "systemctl", "journalctl", "which", "head", "tail",
}

# Flags that turn an otherwise-safe command into a dangerous one.
_DENY_FLAGS_BY_CMD = {
    "find": {"-exec", "-execdir", "-delete", "-fprintf"},
    "curl": {"-d", "--data", "--data-raw", "--data-binary", "--data-urlencode",
             "-F", "--form", "-T", "--upload-file", "-o", "--output"},
    "wget": {"--post-data", "--post-file", "-O", "--output-document"},
    "systemctl": {"stop", "disable", "mask", "kill", "poweroff", "reboot", "halt"},
}

MAX_OUTPUT_CHARS = 8000


def _is_command_safe(argv: list[str]) -> tuple[bool, str]:
    """
    Multi-layer safety check on the parsed argument vector.
    Returns (is_safe, reason) — reason is non-empty only when blocked.
    """
    if not argv:
        return False, "Empty command."

    first_word = os.path.splitext(os.path.basename(argv[0]))[0].lower()

    if first_word not in ALLOWED_COMMANDS:
        return False, f"Command '{first_word}' is not in the allowlist for safety."

    deny_flags = _DENY_FLAGS_BY_CMD.get(first_word)
    if deny_flags:
        for arg in argv[1:]:
            flag = arg.split("=", 1)[0]
            if flag in deny_flags:
                return False, f"Flag '{flag}' is blocked for '{first_word}' for safety."

    return True, ""


@function_tool
async def run_terminal_command(command: str, working_dir: str | None = None) -> str:
    """
    Executes a shell-style command (e.g. git, ls, curl, find) in a hardened,
    non-shell sandbox. Chaining, redirection, and general-purpose code
    interpreters (python, pip, node, npm, bash) are not available here.

    Args:
        command: The command to execute, e.g. "git status" or "ls -la".
        working_dir: Optional absolute path to run the command in. Defaults
            to the current working directory if omitted.
    """
    try:
        try:
            argv = shlex.split(command)
        except ValueError as e:
            return f"Command could not be parsed: {e}"

        is_safe, reason = _is_command_safe(argv)
        if not is_safe:
            logger.warning(f"Blocked command: {command!r} — {reason}")
            return f"Command blocked: {reason}"

        cwd = None
        if working_dir:
            candidate = os.path.abspath(working_dir)
            if not os.path.isdir(candidate):
                return f"working_dir '{working_dir}' does not exist or is not a directory."
            cwd = candidate

        logger.info(f"Running terminal command: {argv}")

        result = subprocess.run(
            argv,
            shell=False,
            capture_output=True,
            text=True,
            timeout=30,  # Hard timeout
            cwd=cwd,
        )

        stdout = result.stdout.strip()[:MAX_OUTPUT_CHARS]
        stderr = result.stderr.strip()[:MAX_OUTPUT_CHARS]

        if result.returncode == 0:
            out = "Command succeeded.\n"
            if stdout: out += f"[STDOUT]:\n{stdout}"
            if stderr: out += f"\n[STDERR]:\n{stderr}"
            return out.strip()
        else:
            out = f"Command failed with exit code {result.returncode}.\n"
            if stdout: out += f"[STDOUT]:\n{stdout}\n"
            if stderr: out += f"[STDERR]:\n{stderr}"
            return out.strip()

    except FileNotFoundError:
        return f"Command not found: {command.split()[0] if command.split() else command}"
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds."
    except Exception as e:
        logger.error(f"Terminal execution error: {e}")
        return f"Execution error: {e}"
