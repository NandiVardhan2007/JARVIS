"""
JARVIS Tools Package
All tool functions registered as livekit.agents function_tools.
"""

from .web_search import search_web
from .weather import get_weather, get_time_info
from .news import get_news
from .system_control import (
    system_power_action, get_system_info, control_screen_brightness,
    control_system_volume, control_media, use_smart_clipboard, scan_system_for_viruses
)
from .window_manager import manage_window, manage_window_state, list_active_windows, open_app_on_screen
from .open_app import open_app
from .media import play_media
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
from .notepad import write_in_notepad
from .file_ops import (
    open_file_command, list_directory, search_files, create_file, 
    create_folder, copy_file_or_folder, move_or_rename_path, 
    delete_path, read_text_file
)
from .ai_image import generate_local_image_comfyui, generate_ai_video, get_generation_presets
from .code_generator import generate_and_type_code, run_file_in_vscode
from .iot_control import control_ac_bulb
from .multi_task import execute_multi_task
from .screen_reader import read_screen, read_selected_region, list_monitors
from .messaging import send_telegram_message, get_telegram_messages, send_discord_message, get_discord_messages
from .process_manager import list_processes, find_process, kill_process, get_top_resource_hogs, restart_process
from .user_memory import memorize_fact, recall_memory, forget_fact
from .task_manager import add_task, complete_task, list_tasks, prioritize_task
from .terminal import run_terminal_command
from .github_tool import list_github_repos, get_github_pull_requests, create_github_issue, get_github_recent_commits
from .knowledge_base import save_note, search_knowledge_base
from .error_telemetry import get_error_summary, get_recent_errors
from .mobile_control import (
    connect_phone, get_phone_status, unlock_phone, lock_phone,
    phone_tap, phone_swipe, phone_type, phone_press_key,
    open_phone_app, close_phone_app, list_installed_apps,
    send_phone_notification, read_phone_screen, phone_ocr_tap,
    push_file_to_phone, pull_file_from_phone, run_phone_command
)

# ── NOVA features ─────────────────────────────────────────────────────────────
from .document_processor import process_document_query
from .scheduler import schedule_task, view_scheduled_tasks, cancel_scheduled_task
from .code_fixer import fix_code_error
from .briefing import morning_briefing

# ── Tool Categories ───────────────────────────────────────────────────────────

# Core tools are always loaded regardless of intent
CORE_TOOLS = [
    search_web, get_weather, get_time_info, get_news,
    get_error_summary, get_recent_errors,
    memorize_fact, recall_memory, forget_fact,
    add_task, complete_task, list_tasks, prioritize_task,
    save_note, search_knowledge_base, execute_multi_task
]

TOOL_CATEGORIES = {
    "email": [
        send_email, validate_email, read_inbox, read_email, 
        search_emails, reply_email, mark_email_read, label_email, summarize_email, delete_emails
    ],
    "scraper": [
        scrape_url, extract_tables, get_page_links, take_web_screenshot, ai_summarize_page
    ],
    "calendar": [
        get_today_schedule, list_upcoming_events, create_event, 
        find_free_slot, delete_event
    ],
    "finance": [
        get_stock_price, get_crypto_price, portfolio_summary, add_to_portfolio
    ],
    "research": [
        deep_research, compare_sources
    ],
    "code": [
        generate_and_type_code, run_file_in_vscode, review_file, 
        review_pr, suggest_refactor, run_terminal_command,
        list_github_repos, get_github_pull_requests, create_github_issue, get_github_recent_commits,
        fix_code_error
    ],
    "system": [
        system_power_action, get_system_info, control_screen_brightness,
        control_system_volume, control_media, use_smart_clipboard, 
        scan_system_for_viruses, list_processes, find_process, 
        kill_process, get_top_resource_hogs, restart_process, control_ac_bulb
    ],
    "desktop": [
        manage_window, manage_window_state, list_active_windows, 
        open_app_on_screen, open_app, play_media, desktop_control, 
        press_key, type_user_message_auto, click_on_text, write_in_notepad,
        open_file_command, read_screen, read_selected_region, list_monitors,
        process_document_query, list_directory, search_files,
        create_file, create_folder, copy_file_or_folder, 
        move_or_rename_path, delete_path, read_text_file
    ],
    "communication": [
        send_telegram_message, get_telegram_messages, 
        send_discord_message, get_discord_messages,
        send_whatsapp_message, send_whatsapp_media, search_google_contact
    ],
    "creative": [
        generate_local_image_comfyui, generate_ai_video, get_generation_presets
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

def get_all_tools() -> list:
    """
    Return all JARVIS tool functions for the agent.
    This is used by the voice agent where context window size is less critical,
    and by the execute_multi_task tool.
    """
    all_tools = list(CORE_TOOLS)
    for cat_tools in TOOL_CATEGORIES.values():
        all_tools.extend(cat_tools)
    # Deduplicate just in case
    return list({t.__name__: t for t in all_tools}.values())

def get_tools_for_category(category) -> list:
    """
    Return tools for a specific category (or list of categories) plus core tools.
    Used by the Telegram bot for intent-based routing to keep context small.
    """
    tools = list(CORE_TOOLS)
    categories = category if isinstance(category, list) else [category]
    for cat in categories:
        if cat in TOOL_CATEGORIES:
            tools.extend(TOOL_CATEGORIES[cat])
    return list({t.__name__: t for t in tools}.values())


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
                      "cpu", "ram", "storage", "disk"],
    "communication": ["telegram", "discord", "whatsapp", "message"],
    "scheduler":     ["schedule", "timer", "remind me at", "remind me after", "briefing",
                      "morning briefing"],
    "desktop":       ["window", "open app", "open folder", "open file", "type", "click",
                      "screen", "notepad", "file", "folder", "directory", "copy", "move",
                      "delete", "pdf", "document", "docx", "analyze my", "play", "music",
                      "song", "media", "youtube", "monitor"],
    "creative":      ["image", "video", "generate", "draw", "art", "picture", "photo"],
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

__all__ = ["get_all_tools", "get_tools_for_category", "classify_intent"]
