"""Web search tool — Wikipedia + DuckDuckGo fallback."""

import logging
import requests
from livekit.agents import function_tool

logger = logging.getLogger(__name__)


@function_tool
async def search_web(query: str) -> str:
    """
    Performs a multi-source web search with automatic fallback logic.

    Args:
        query: The search query or question.

    Workflow:
        1. Tries English Wikipedia summary
        2. Falls back to DuckDuckGo Instant Answer API
        3. Falls back to DuckDuckGo related topics
        4. Falls back to LangChain DuckDuckGo search tool
    """
    logger.info(f"Searching web for: {query}")

    # 1. Wikipedia (English)
    try:
        import wikipedia
        wikipedia.set_lang("en")
        summary = wikipedia.summary(query, sentences=3, auto_suggest=True)
        if summary and len(summary) > 20:
            return f"Wikipedia:\n{summary}"
    except Exception as e:
        logger.debug(f"Wikipedia failed: {e}")

    # 2. DuckDuckGo Instant Answer API
    try:
        from tenacity import retry, stop_after_attempt, wait_exponential
        
        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
        def _fetch_ddg_api():
            return requests.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
                timeout=8,
            )
            
        resp = _fetch_ddg_api()
        data = resp.json()
        if data.get("AbstractText"):
            return f"DuckDuckGo:\n{data['AbstractText']}"
        if data.get("RelatedTopics"):
            topics = [
                f"• {t['Text']}"
                for t in data["RelatedTopics"][:3]
                if isinstance(t, dict) and t.get("Text")
            ]
            if topics:
                return "Related results:\n" + "\n".join(topics)
    except Exception as e:
        logger.debug(f"DuckDuckGo API failed: {e}")

    # 3. LangChain DuckDuckGo search
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        from tenacity import retry, stop_after_attempt, wait_fixed
        
        @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
        def _fetch_ddg_search():
            return DuckDuckGoSearchRun().run(query)
            
        result = _fetch_ddg_search()
        if result and len(result) > 20:
            return f"Search results:\n{result}"
    except Exception as e:
        logger.debug(f"DuckDuckGo search tool failed: {e}")

    return "Sorry sir, I could not find any useful information on that topic right now."
