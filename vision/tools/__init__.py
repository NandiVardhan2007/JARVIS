"""
VISION Tools and Automation Package.
"""

from vision.tools.registry import tool, tool_registry, ToolRegistry
import vision.tools.system_tools
import vision.tools.file_tools
import vision.tools.mobile_tools
import vision.tools.email_tools
import vision.tools.media_tools
import vision.memory.rag_engine
import vision.tools.printer_tools
import vision.tools.web_tools
import vision.tools.memory_tools
import vision.tools.cache_tools
import vision.tools.hardware_tools
import vision.tools.whatsapp_tools
import vision.tools.window_tools
import vision.tools.input_tools
import vision.tools.terminal_tools
import vision.tools.clipboard_translation_tools
import vision.tools.browser_navigation_tools
import vision.tools.browser_control_tools
import vision.tools.power_process_tools
import vision.tools.archive_tools
import vision.tools.network_tools
import vision.tools.reminder_tools
import vision.tools.interview_tools
import vision.tools.agent_execution_tools
import vision.tools.remote_server_tools
import vision.tools.academic_tools
import vision.tools.briefing_tools
import vision.tools.code_execution_tools
import vision.tools.task_tracker_tools
import vision.tools.outlook_tools

__all__ = ["tool", "tool_registry", "ToolRegistry"]
