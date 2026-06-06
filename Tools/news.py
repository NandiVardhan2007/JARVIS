"""News tool — Google News RSS with DuckDuckGo fallback."""

import logging
from urllib.parse import quote_plus
from livekit.agents import function_tool

logger = logging.getLogger(__name__)


@function_tool
async def get_news(topic: str = "world") -> str:
    """
    Fetches the latest news headlines on a given topic.

    Args:
        topic: Topic to search news for (default: "world")
    """
    logger.info(f"Fetching news for: {topic}")

    # 1. Google News RSS (free, no API key)
    try:
        import feedparser

        url = (
            f"https://news.google.com/rss/search?q={quote_plus(topic)}&hl=en&gl=US&ceid=US:en"
            if topic.lower() != "world"
            else "https://news.google.com/rss?hl=en&gl=US&ceid=US:en"
        )
        feed = feedparser.parse(url)

        if feed.entries:
            headlines = []
            for entry in feed.entries[:5]:
                title = entry.get("title", "No title")
                source = entry.get("source", {}).get("title", "Unknown source")
                published = entry.get("published", "")
                # Clean up the published date to just the date part
                if published:
                    published = published.split("+")[0].strip()
                headlines.append(f"• {title} — {source}" + (f" ({published})" if published else ""))

            return f"Latest news on '{topic}':\n" + "\n".join(headlines)
    except ImportError:
        logger.warning("feedparser not installed, falling back to DuckDuckGo.")
    except Exception as e:
        logger.warning(f"Google News RSS failed: {e}")

    # 2. Fallback: DuckDuckGo news search via langchain
    try:
        from langchain_community.tools import DuckDuckGoSearchRun

        result = DuckDuckGoSearchRun().run(f"latest news {topic} today")
        if result and len(result) > 20:
            return f"Latest news on '{topic}':\n{result[:800]}"
    except Exception as e:
        logger.warning(f"DuckDuckGo news fallback failed: {e}")

    # 3. Fallback: direct RSS from a general feed
    try:
        import feedparser

        # Try Reuters top news as a generic fallback
        feed = feedparser.parse("https://news.google.com/rss?hl=en&gl=US&ceid=US:en")
        if feed.entries:
            headlines = []
            for entry in feed.entries[:5]:
                title = entry.get("title", "No title")
                headlines.append(f"• {title}")
            return f"Top headlines (couldn't find specific '{topic}' news):\n" + "\n".join(headlines)
    except Exception:
        pass

    return "Unable to fetch news at the moment. Please try again shortly."


__all__ = ["get_news"]
