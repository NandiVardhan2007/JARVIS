"""
Semantic Intent Classifier and Dynamic Tool Selection Router.
Selects only the top relevant tools for the user query, drastically reducing token usage
from ~5,000 tokens down to ~300 tokens and eliminating API rate limits.
"""

import re
from typing import List, Dict, Any, Set
from vision.logger import logger


DOMAIN_KEYWORD_MAP = {
    "hardware": {
        "keywords": ["volume", "sound", "audio", "mute", "unmute", "loud", "quiet", "brightness", "dim", "screen brightness", "lock", "lock screen", "lock pc", "lock workstation", "battery", "charge", "charging", "battery percentage", "power state", "hardware", "cpu usage", "ram usage", "system health", "hardware health", "disk usage", "free space"],
        "tools": ["set_volume", "increase_volume", "decrease_volume", "mute_volume", "unmute_volume", "get_volume_status", "set_brightness", "increase_brightness", "decrease_brightness", "get_brightness_status", "lock_screen", "lock_workstation", "get_battery_status", "get_hardware_health", "get_system_stats"]
    },
    "network": {
        "keywords": ["speedtest", "speed test", "internet speed", "download speed", "upload speed", "wifi", "wi-fi", "network", "signal", "ssid", "ping", "latency", "dns", "gateway", "ip address", "public ip", "connection speed"],
        "tools": ["test_internet_speed", "get_network_diagnostics", "ping_host"]
    },
    "window": {
        "keywords": ["window", "desktop", "minimize", "maximize", "restore", "snap", "close", "kill", "terminate", "switch to", "running apps", "show desktop"],
        "tools": ["show_desktop", "minimize_all_windows", "restore_windows", "close_application", "switch_to_window", "maximize_window", "snap_window", "list_running_applications"]
    },
    "input": {
        "keywords": ["write", "type", "note", "notepad", "draft", "shortcut", "press", "key", "save", "save note", "save document", "save it"],
        "tools": ["type_text_into_application", "press_keyboard_shortcut", "save_active_document", "create_or_write_file", "open_application"]
    },
    "whatsapp": {
        "keywords": ["whatsapp", "message", "msg", "chat", "send to", "text to", "contact"],
        "tools": ["send_whatsapp_message", "save_whatsapp_contact_alias"]
    },
    "printer": {
        "keywords": ["print", "printer", "paper", "a4", "margin", "border", "copy", "copies", "pdf"],
        "tools": ["create_bordered_a4_document", "print_document", "create_and_print_bordered_document"]
    },
    "file": {
        "keywords": ["file", "folder", "directory", "downloads", "documents", "desktop", "desktop folder", "delete file", "move file", "rename", "organize", "organize downloads", "clean downloads", "organize desktop", "clean desktop", "tidy", "sort files", "save", "save file", "save in downloads", "save to"],
        "tools": ["organize_downloads", "organize_desktop", "organize_directory", "clean_empty_directories", "create_or_write_file", "list_files", "find_files", "open_file", "read_file_content", "rename_file", "move_file", "copy_file", "delete_file", "create_folder", "save_active_document"]
    },
    "web": {
        "keywords": ["weather", "temperature", "forecast", "search web", "browse", "internet", "google", "news", "online", "fetch"],
        "tools": ["search_web", "fetch_webpage_content", "get_weather_forecast"]
    },
    "system": {
        "keywords": ["open", "launch", "start", "time", "date", "clock", "cpu", "ram", "battery", "stats", "screen", "screenshot"],
        "tools": ["open_application", "get_current_time_and_date", "get_system_stats", "read_screen", "get_battery_status", "get_hardware_health"]
    },
    "memory": {
        "keywords": ["remember", "memory", "memories", "recall", "forget", "know about me", "details", "my details", "about me", "age", "born", "birthday", "who am i", "my name", "college", "address", "my address", "mother", "father", "friends", "cache", "stats", "list memories", "clear cache"],
        "tools": ["remember_fact", "recall_memory", "forget_memory", "list_all_memories", "get_cache_stats", "clear_system_cache"]
    },
    "media": {
        "keywords": ["play", "song", "music", "youtube", "video"],
        "tools": ["play_media", "open_application"]
    },
    "email": {
        "keywords": ["email", "mail", "send mail", "compose"],
        "tools": ["send_email"]
    },
    "mobile": {
        "keywords": ["phone", "mobile", "android", "adb", "unlock phone"],
        "tools": ["connect_phone", "unlock_phone", "launch_mobile_app", "tap_phone_screen"]
    },
    "terminal": {
        "keywords": ["terminal", "command prompt", "cmd", "powershell", "execute command", "run command", "run terminal", "run script", "git status", "pip install", "npm install", "ssh to", "ssh server", "connect to server", "connect to ssh", "remote server"],
        "tools": ["connect_to_ssh_server", "execute_terminal_command", "run_python_code", "git_status_and_summary"]
    },
    "clipboard_translation": {
        "keywords": ["clipboard", "copied", "paste", "copy to clipboard", "translate", "telugu", "hindi", "tamil", "spanish", "translation", "in telugu", "in hindi", "in english"],
        "tools": ["read_clipboard", "write_to_clipboard", "translate_text"]
    },
    "browser": {
        "keywords": ["browser", "website", "open site", "github", "leetcode", "youtube", "gmail", "chatgpt", "google search", "search youtube", "download", "download file", "web page"],
        "tools": ["open_website", "search_youtube_videos", "search_google_web", "download_file_from_url"]
    },
    "power_process": {
        "keywords": ["kill", "terminate", "force close", "kill process", "sleep", "sleep pc", "lock", "lock pc", "lock workstation", "lock screen", "workstation", "shutdown", "restart", "cancel shutdown", "recycle", "recycle bin", "empty bin", "bin", "trash", "clean trash"],
        "tools": ["kill_process_by_name", "lock_workstation", "lock_screen", "sleep_pc", "empty_recycle_bin", "shutdown_pc", "restart_pc", "cancel_shutdown"]
    },
    "archive": {
        "keywords": ["zip", "unzip", "compress", "extract", "tar", "archive", "compress folder", "extract zip"],
        "tools": ["compress_to_zip", "extract_zip_archive"]
    },
    "reminder": {
        "keywords": ["remind", "reminder", "remind me", "timer", "alarm", "countdown", "set timer", "set reminder", "cancel reminder", "cancel timer", "my reminders", "active reminders"],
        "tools": ["set_voice_reminder", "set_timer", "list_active_reminders", "cancel_reminder", "get_current_time_and_date"]
    },
    "interview": {
        "keywords": ["interview", "mock interview", "interview prep", "prepare for interview", "interview question", "interview practice", "evaluate answer", "end interview", "technical interview", "hr interview", "mock interview session"],
        "tools": ["start_mock_interview", "evaluate_interview_answer", "end_mock_interview"]
    }
}

# Core fallback tools when intent is ambiguous
CORE_DEFAULT_TOOLS = [
    "open_application", "get_current_time_and_date", "get_system_stats",
    "search_web", "show_desktop", "close_application"
]


class IntentRouter:
    def route_tools(self, user_query: str, all_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter down all registered tool schemas to only the most relevant tools."""
        q_lower = user_query.lower().strip()
        matched_tool_names: Set[str] = set()

        for domain, info in DOMAIN_KEYWORD_MAP.items():
            for kw in info["keywords"]:
                if re.search(rf"\b{re.escape(kw)}\b", q_lower) or kw in q_lower:
                    matched_tool_names.update(info["tools"])
                    break

        # If no specific domain matched, use curated core toolset
        if not matched_tool_names:
            matched_tool_names.update(CORE_DEFAULT_TOOLS)

        # Filter schema dicts
        schema_map = {
            t.get("function", {}).get("name"): t
            for t in all_tools if t.get("function", {}).get("name")
        }

        selected_schemas = [
            schema_map[name]
            for name in matched_tool_names
            if name in schema_map
        ]

        logger.debug(f"[Router] Filtered {len(all_tools)} tools -> {len(selected_schemas)} relevant tools for query: '{user_query[:35]}...'")
        return selected_schemas


router = IntentRouter()
