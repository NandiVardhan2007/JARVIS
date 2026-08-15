"""
Semantic Intent Classifier and Dynamic Tool Selection Router.
Keeps LLM prompt tokens minimal and latency ultra-low by filtering relevant tools.
"""

from typing import List, Dict, Any
from loguru import logger


class IntentRouter:
    def __init__(self):
        # Keyword & pattern based heuristics
        self.category_keywords = {
            "file": ["file", "files", "folder", "directory", "organize", "list", "open", "read", "rename", "move", "copy", "delete", "create folder", "search file", "find file", "pdf", "image", "document"],
            "mobile": ["phone", "mobile", "android", "adb", "unlock", "swipe", "tap", "call", "sms", "battery"],
            "system": ["volume", "brightness", "app", "launch", "close", "restart", "shutdown", "process", "window", "screenshot"],
            "email": ["email", "mail", "gmail", "inbox", "send email", "draft", "unread"],
            "media": ["play", "music", "song", "video", "youtube", "pause", "resume"],
            "vision": ["see", "look", "screen", "camera", "webcam", "read text", "describe image", "what is on my screen"],
        }

    def route_tools(self, user_query: str, all_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter all registered tools to those relevant to the user query."""
        if not user_query:
            return all_tools

        query_lower = user_query.lower()
        matched_categories = set()

        for category, keywords in self.category_keywords.items():
            if any(kw in query_lower for kw in keywords):
                matched_categories.add(category)

        if not matched_categories:
            return all_tools

        filtered = []
        for tool in all_tools:
            name = tool.get("function", {}).get("name", "").lower()
            desc = tool.get("function", {}).get("description", "").lower()
            
            for cat in matched_categories:
                if cat in name or any(kw in desc for kw in self.category_keywords[cat]):
                    filtered.append(tool)
                    break

        logger.debug(f"[Router] Query matched categories {matched_categories}, filtered to {len(filtered)} tools.")
        return filtered if filtered else all_tools


router = IntentRouter()
