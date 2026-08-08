"""
VISION Tools Package
All tool functions registered as livekit.agents function_tools.
"""

from .web_search import search_web
from .weather import get_weather, get_time_info
from .news import get_news
from .system_control import (
    system_power_action, get_system_info, control_screen_brightness,
    control_system_volume, control_media, use_smart_clipboard, scan_system_for_viruses
)
from .clipboard_manager import get_recent_clipboard, search_clipboard
from .window_manager import manage_window, manage_window_state, list_active_windows, open_app_on_screen
from .windows_system import (
    search_package, install_package, remove_package, check_for_updates, update_system,
    list_services, get_service_status, control_service,
    read_system_logs, list_docker_containers, docker_container_action,
    get_dev_environment_info, get_file_permissions, set_file_permissions,
    list_startup_apps, set_startup_app_enabled,
)
from .hand_gesture_control import (
    start_hand_gesture_control, stop_hand_gesture_control,
    get_gesture_control_status, set_gesture_sensitivity,
)
from .open_app import open_app
from .media import play_media, stop_media
from .voice_verification import start_voice_reenrollment
from .resource_optimizer import get_vision_resource_usage, release_idle_resources
from .system_optimizer import (
    get_system_health_report, optimize_system_now,
    get_pending_optimization_suggestions, start_system_optimizer, stop_system_optimizer,
)
from .desktop_control import desktop_control, press_key, type_user_message_auto, click_on_text
from .email_sender import send_email, validate_email
from .email_agent import read_inbox, read_email, search_emails, reply_email, mark_email_read, label_email, summarize_email, delete_emails
from .scraper_agent import scrape_url, extract_tables, get_page_links, take_web_screenshot, ai_summarize_page
from .calendar_agent import get_today_schedule, list_upcoming_events, create_event, find_free_slot, delete_event
from .finance_agent import get_stock_price, get_crypto_price, portfolio_summary, add_to_portfolio
from .research_agent import deep_research, compare_sources
from .code_review_agent import review_file, review_pr, suggest_refactor
from .reminder import say_reminder, get_today_reminder_message_from_db
from .whatsapp import send_whatsapp_message, send_whatsapp_media
from .google_contacts import search_google_contact
from .notepad import write_in_notepad, open_notepad, type_and_save_notepad
from .file_ops import (
    open_file_command, list_directory, search_files, create_file, 
    create_folder, copy_file_or_folder, move_or_rename_path, 
    delete_path, read_text_file, edit_file_diff
)
from .file_manager import (
    smart_find_files, organize_folder, suggest_folder_structure,
    find_duplicate_files, delete_duplicate_files, bulk_rename_files,
)
from .report_generator import generate_report
from .workflow_automation import save_workflow, list_workflows, run_workflow, delete_workflow
from .code_generator import generate_and_type_code, run_file_in_vscode
from .iot_control import control_ac_bulb
from .multi_task import execute_agent_tasks
from .screen_reader import read_screen, read_selected_region, list_monitors, take_screenshot
from .messaging import send_discord_message, get_discord_messages
from .process_manager import list_processes, find_process, kill_process, get_top_resource_hogs, restart_process
from .user_memory import memorize_fact, recall_memory, forget_fact
from .task_manager import add_task, complete_task, list_tasks, prioritize_task
from .terminal import run_terminal_command
from .github_tool import list_github_repos, get_github_pull_requests, create_github_issue, get_github_recent_commits
from .knowledge_base import save_note
from .knowledge_rag import add_document_to_knowledge, index_pdf_file, index_folder, search_knowledge_base, list_knowledge_documents
from .conversation_memory import search_past_conversations, index_conversation_history_now
from .error_telemetry import get_error_summary, get_recent_errors
from .mobile_control import (
    connect_phone, get_phone_status, unlock_phone, lock_phone,
    phone_tap, phone_swipe, phone_type, phone_press_key,
    open_phone_app, close_phone_app, list_installed_apps,
    send_phone_notification, read_phone_screen, phone_ocr_tap,
    push_file_to_phone, pull_file_from_phone, run_phone_command,
    android_make_call, android_end_call, android_answer_call
)
from .phone import make_phone_call, end_phone_call, list_active_calls

# ── NOVA features ─────────────────────────────────────────────────────────────
from .document_processor import process_document_query
from .scheduler import schedule_task, view_scheduled_tasks, cancel_scheduled_task
from .code_fixer import fix_code_error
from .briefing import morning_briefing
from .coder_agent import auto_write_and_debug_code
from .codebase_rag import index_project_codebase, search_codebase
from .academic_outreach import (
    find_iit_internships_and_professors, draft_cold_email_to_professor,
    list_drafted_cold_emails, send_approved_cold_emails
)

# ── Tool Categories ───────────────────────────────────────────────────────────

from .web_automation import (
    open_webpage, click_web_element, type_into_form, scroll_webpage, close_browser,
    list_browser_tabs, switch_browser_tab, close_browser_tab,
    download_file_from_page, upload_file_to_page, read_page_aloud,
    start_watching_page, list_watched_pages, check_page_changes, stop_watching_page,
)
from .webcam_guard import start_webcam_guard, stop_webcam_guard, analyze_what_master_is_doing, analyze_webcam_frame_vlm, get_webcam_diagnostics
from .whatsapp_web_control import open_whatsapp_web, read_unreads_on_whatsapp, send_whatsapp_reply

# Core tools are always loaded regardless of intent
TOOL_CATEGORIES = {
    "email": [
        send_email, validate_email, read_inbox, read_email, 
        search_emails, reply_email, mark_email_read, label_email, summarize_email, delete_emails
    ],
    "scraper": [
        scrape_url, extract_tables, get_page_links, take_web_screenshot, ai_summarize_page,
        open_webpage, click_web_element, type_into_form, scroll_webpage, close_browser,
        list_browser_tabs, switch_browser_tab, close_browser_tab,
        download_file_from_page, upload_file_to_page, read_page_aloud,
        start_watching_page, list_watched_pages, check_page_changes, stop_watching_page,
    ],
    "calendar": [
        get_today_schedule, list_upcoming_events, create_event, 
        find_free_slot, delete_event
    ],
    "finance": [
        get_stock_price, get_crypto_price, portfolio_summary, add_to_portfolio
    ],
    "research": [
        deep_research, compare_sources,
        find_iit_internships_and_professors, draft_cold_email_to_professor,
        list_drafted_cold_emails, send_approved_cold_emails
    ],
    "code": [
        generate_and_type_code, run_file_in_vscode, review_file, 
        review_pr, suggest_refactor, run_terminal_command,
        list_github_repos, get_github_pull_requests, create_github_issue, get_github_recent_commits,
        fix_code_error, auto_write_and_debug_code, index_project_codebase, search_codebase
    ],
    "system": [
        system_power_action, get_system_info, control_screen_brightness,
        control_system_volume, control_media, use_smart_clipboard,
        get_recent_clipboard, search_clipboard,
        scan_system_for_viruses, list_processes, find_process,
        kill_process, get_top_resource_hogs, restart_process, control_ac_bulb,
        start_webcam_guard, stop_webcam_guard, analyze_what_master_is_doing, analyze_webcam_frame_vlm,
        get_webcam_diagnostics,
        start_hand_gesture_control, stop_hand_gesture_control, get_gesture_control_status, set_gesture_sensitivity,
        search_package, install_package, remove_package, check_for_updates, update_system,
        list_services, get_service_status, control_service,
        read_system_logs, list_docker_containers, docker_container_action,
        get_dev_environment_info, get_file_permissions, set_file_permissions,
        list_startup_apps, set_startup_app_enabled,
    ],
    "desktop": [
        manage_window, manage_window_state, list_active_windows, 
        open_app_on_screen, open_app, play_media, stop_media, desktop_control, 
        press_key, type_user_message_auto, click_on_text, write_in_notepad, open_notepad, type_and_save_notepad,
        start_hand_gesture_control, stop_hand_gesture_control, get_gesture_control_status, set_gesture_sensitivity,
        open_file_command, read_screen, read_selected_region, list_monitors, take_screenshot,
        process_document_query, list_directory, search_files,
        create_file, create_folder, copy_file_or_folder, 
        move_or_rename_path, delete_path, read_text_file, edit_file_diff,
        smart_find_files, organize_folder, suggest_folder_structure,
        find_duplicate_files, delete_duplicate_files, bulk_rename_files,
    ],
    "communication": [
        send_discord_message, get_discord_messages,
        send_whatsapp_message, send_whatsapp_media, search_google_contact,
        android_make_call, android_end_call, android_answer_call,
        make_phone_call, end_phone_call, list_active_calls,
        open_whatsapp_web, read_unreads_on_whatsapp, send_whatsapp_reply,
    ],
    "reminder": [
        say_reminder, get_today_reminder_message_from_db
    ],
    "scheduler": [
        schedule_task, view_scheduled_tasks, cancel_scheduled_task,
        morning_briefing
    ],
    "mobile": [
        connect_phone, get_phone_status, unlock_phone, lock_phone,
        phone_tap, phone_swipe, phone_type, phone_press_key,
        open_phone_app, close_phone_app, list_installed_apps,
        send_phone_notification, read_phone_screen, phone_ocr_tap,
        push_file_to_phone, pull_file_from_phone, run_phone_command
    ]
}

# ── Specialized "agent" roster ────────────────────────────────────────────────
# VISION is a single LLM with a large, categorized toolbox rather than
# separate LLM instances per agent — spinning up N independent model
# instances per request would multiply latency and cost for a desktop
# assistant with little benefit. What DOES genuinely help is (1) naming and
# scoping specialized toolsets the way separate agents would be scoped, and
# (2) actually running independent subtasks concurrently instead of one at a
# time — see Tools/multi_task.py's execute_agent_tasks. This roster maps the
# vNext-suggested agent roles onto the tool categories that already exist,
# rather than inventing a parallel taxonomy disconnected from the real code.
AGENT_ROSTER = {
    "Research Agent":         {"categories": ["research", "scraper"], "description": "Web research, source comparison, page summarization/extraction."},
    "Browser Agent":          {"categories": ["scraper"], "description": "Interactive browser control: navigate, click, fill forms, download/upload, watch pages for changes."},
    "Terminal Agent":         {"categories": ["code"], "description": "Sandboxed shell commands, running/debugging code, GitHub operations."},
    "Coding Agent":           {"categories": ["code"], "description": "Code generation, review, refactor suggestions, codebase search."},
    "File Management Agent":  {"categories": ["desktop"], "description": "Smart file search, folder organization, bulk renaming, duplicate detection, file/folder CRUD."},
    "Automation Agent":       {"categories": ["scheduler", "reminder", "mobile"], "description": "Scheduled tasks, reminders, morning briefings, phone automation, and named reusable workflows (save_workflow/run_workflow) for repetitive multi-step or cross-app tasks."},
    "Memory Agent":           {"categories": [], "description": "Long-term facts, RAG knowledge base, and past-conversation recall (memorize_fact, recall_memory, search_knowledge_base, search_past_conversations, etc.), always available as core tools, not category-gated."},
    "Planning Agent":         {"categories": [], "description": "The orchestrator itself — decomposes a request into subtasks and dispatches them via execute_agent_tasks, running independent ones in parallel."},
    "Vision Agent":           {"categories": ["system"], "description": "Webcam gesture control, screen/frame analysis via the local vision model."},
    "Voice Agent":            {"categories": [], "description": "Voice authentication/enrollment and TTS — always-available core/system tools, not category-gated."},
    "Communication Agent":    {"categories": ["email", "communication"], "description": "Email, Discord, WhatsApp, phone calls."},
    "System Agent":           {"categories": ["system"], "description": "Power, volume, brightness, process/service management, package management, system updates, logs, Docker, file permissions, startup apps, and resource/system optimization."},
    "Calendar & Finance Agent": {"categories": ["calendar", "finance"], "description": "Calendar events and stock/crypto/portfolio tracking."},
}


from livekit.agents import function_tool


@function_tool
async def list_available_agents() -> str:
    """
    Lists VISION's specialized agents (Research, Browser, Terminal, Coding,
    File Management, Automation, Memory, Planning, Vision, Voice,
    Communication, System, Calendar & Finance) and what each one covers.
    Use this if the user asks what you're capable of, or to help decide how
    to split a complex request across agents for execute_agent_tasks.
    """
    lines = ["VISION's specialized agents:"]
    for name, info in AGENT_ROSTER.items():
        lines.append(f"• {name}: {info['description']}")
    return "\n".join(lines)


CORE_TOOLS = [
    search_web, get_weather, get_time_info, get_news,
    get_error_summary, get_recent_errors,
    memorize_fact, recall_memory, forget_fact,
    add_task, complete_task, list_tasks, prioritize_task,
    save_note, search_knowledge_base, add_document_to_knowledge,
    index_pdf_file, index_folder, list_knowledge_documents, execute_agent_tasks,
    start_voice_reenrollment, get_vision_resource_usage, release_idle_resources,
    get_system_health_report, optimize_system_now, get_pending_optimization_suggestions,
    start_system_optimizer, stop_system_optimizer, list_available_agents,
    search_past_conversations, index_conversation_history_now,
    generate_report, save_workflow, list_workflows, run_workflow, delete_workflow,
]


import functools
import traceback
import logging

def _safe_tool_wrapper(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logging.getLogger("VISION.Tools").error(f"Tool {func.__name__} crashed: {e}\n{traceback.format_exc()}")
            return f"SYSTEM EXCEPTION: The tool '{func.__name__}' encountered a runtime error: {e}. Please inform the user."
    return wrapper

def _sandbox_tools(tool_list):
    """Wraps the underlying function of LiveKit FunctionTool objects to prevent crashes."""
    unique_tools = list({t.__name__: t for t in tool_list}.values())
    for t in unique_tools:
        if hasattr(t, "_fnc") and getattr(t, "_sandboxed", False) is False:
            t._fnc = _safe_tool_wrapper(t._fnc)
            t._sandboxed = True
    return unique_tools

def get_all_tools() -> list:
    """
    Return all VISION tool functions for the agent.
    This is used by the voice agent where context window size is less critical,
    and by the execute_agent_tasks orchestrator.
    """
    all_tools = list(CORE_TOOLS)
    for cat_tools in TOOL_CATEGORIES.values():
        all_tools.extend(cat_tools)
    return _sandbox_tools(all_tools)

def get_tools_for_category(category) -> list:
    """
    Return tools for a specific category (or list of categories) plus core tools.
    Used for intent-based routing to keep the tool context small per request.
    """
    tools = list(CORE_TOOLS)
    categories = category if isinstance(category, list) else [category]
    for cat in categories:
        if cat in TOOL_CATEGORIES:
            tools.extend(TOOL_CATEGORIES[cat])
    return _sandbox_tools(tools)


# ── Pre-compiled intent patterns (compiled once at module load) ───────────────
import re as _re

_INTENT_KEYWORDS = {
    "email":         ["email", "inbox", "gmail", "mail"],
    "scraper":       ["scrape", "website", "url", "extract"],
    "calendar":      ["calendar", "event", "meeting", "schedule"],
    "finance":       ["stock", "crypto", "price", "portfolio", "bitcoin", "market"],
    "research":      ["research", "compare"],
    "code":          ["code", "review", "pull request", "github", "terminal", "fix code",
                      "fix error", "debug code", "code error", "compile error", "traceback"],
    "system":        ["process", "brightness", "volume", "system", "virus", "shut down",
                      "shutdown", "restart", "sleep", "pc", "computer", "power", "battery",
                      "cpu", "ram", "storage", "disk", "webcam", "camera", "gesture", "gestures", "hand"],
    "communication": ["discord", "whatsapp", "message", "call", "phone", "ring", "dial", "hang up", "end call"],
    "scheduler":     ["schedule", "timer", "remind me at", "remind me after", "briefing",
                      "morning briefing"],
    "desktop":       ["window", "open", "launch", "open app", "open folder", "open file", "type", "click",
                      "screen", "screenshot", "snapshot", "take screenshot", "notepad", "editor", "text editor", "file", "folder",
                      "directory", "copy", "move", "delete", "pdf", "document", "docx", "analyze my", "play",
                      "music", "song", "media", "youtube", "monitor", "webcam", "camera", "photo", "photos", "picture", "pictures"],
    "reminder":      ["remind"],
    "mobile":        ["phone", "mobile", "android", "unlock", "notification", 
                      "app on phone", "my phone", "send to phone"],
}

_INTENT_PATTERNS = {}
for _cat, _keywords in _INTENT_KEYWORDS.items():
    _pattern = _re.compile(
        r'\b(?:' + '|'.join(_re.escape(k) for k in _keywords) + r')\b',
        _re.IGNORECASE
    )
    _INTENT_PATTERNS[_cat] = _pattern


def classify_intent(text: str) -> list:
    """
    Fast keyword-based intent classifier using pre-compiled regex patterns.
    Returns all category names that match the user's message.
    """
    matches = []
    for cat, pattern in _INTENT_PATTERNS.items():
        if pattern.search(text):
            matches.append(cat)
    return matches if matches else ["core"]

__all__ = ["get_all_tools", "get_tools_for_category", "classify_intent", "list_available_agents", "AGENT_ROSTER"]
