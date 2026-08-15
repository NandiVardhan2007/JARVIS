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
        "keywords": ["volume", "sound", "audio", "mute", "unmute", "loud", "quiet", "brightness", "dim", "screen brightness", "lock screen", "lock pc"],
        "tools": ["set_volume", "increase_volume", "decrease_volume", "mute_volume", "unmute_volume", "get_volume_status", "set_brightness", "increase_brightness", "decrease_brightness", "get_brightness_status", "lock_screen"]
    },
    "window": {
        "keywords": ["window", "desktop", "minimize", "maximize", "restore", "snap", "close", "kill", "terminate", "switch to", "running apps", "show desktop"],
        "tools": ["show_desktop", "minimize_all_windows", "restore_windows", "close_application", "switch_to_window", "maximize_window", "snap_window", "list_running_applications"]
    },
    "input": {
        "keywords": ["write", "type", "note", "notepad", "draft", "shortcut", "press", "key"],
        "tools": ["type_text_into_application", "press_keyboard_shortcut", "open_application"]
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
        "keywords": ["file", "folder", "directory", "downloads", "documents", "desktop folder", "delete file", "move file", "rename", "organize"],
        "tools": ["list_files", "find_files", "open_file", "read_file_content", "rename_file", "move_file", "copy_file", "delete_file", "create_folder", "organize_directory"]
    },
    "web": {
        "keywords": ["weather", "temperature", "forecast", "search web", "browse", "internet", "google", "news", "online", "fetch"],
        "tools": ["search_web", "fetch_webpage_content", "get_weather_forecast"]
    },
    "system": {
        "keywords": ["open", "launch", "start", "time", "date", "clock", "cpu", "ram", "battery", "stats", "screen", "screenshot"],
        "tools": ["open_application", "get_current_time_and_date", "get_system_stats", "read_screen"]
    },
    "memory": {
        "keywords": ["remember", "memory", "recall", "forget", "know about me", "details", "age", "born", "who am i", "my name", "college", "cache", "stats"],
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
    }
}

# Core fallback tools when intent is ambiguous
CORE_DEFAULT_TOOLS = [
    "open_application", "get_current_time_and_date", "get_system_stats",
    "recall_memory", "remember_fact", "search_web", "show_desktop", "close_application"
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
