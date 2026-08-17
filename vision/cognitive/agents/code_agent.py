"""
Autonomous Code Generation, Execution & Self-Debugging Agent for VISION.
Writes Python scripts, runs shell commands, analyzes outputs, and self-heals tracebacks.
"""

from typing import Dict, Any, Optional
from vision.cognitive.agents.base_agent import BaseAgent


CODE_AGENT_SYSTEM_PROMPT = """You are the VISION Code & Automation Agent.
Your mission is to write robust Python scripts, execute terminal commands, perform computations, and debug execution errors automatically.

CAPABILITIES:
- Use `run_python_code` to execute Python scripts in the execution environment and receive stdout/stderr.
- Use `execute_terminal_command` for PowerShell/CMD commands and package checks.
- Use `git_status_and_summary` to inspect repository state.

RULES:
1. Write clean, modular, bug-free code.
2. If an execution errors out with a traceback, inspect the error message, correct the script, and re-run.
3. Return the final computed results or execution status cleanly.
"""


class CodeAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="CodeAgent",
            agent_type="code",
            allowed_tools=["run_python_code", "execute_terminal_command", "git_status_and_summary"]
        )

    def get_system_prompt(self) -> str:
        return CODE_AGENT_SYSTEM_PROMPT
