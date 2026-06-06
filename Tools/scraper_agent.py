"""Web Scraper Agent — httpx + BeautifulSoup for content extraction.

Fixes the shallow-search problem: JARVIS can now fetch and parse any URL,
extract clean text, pull tables, and list links.
"""

import logging
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

# Shared headers to look like a real browser
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _fetch(url: str, timeout: int = 15) -> str:
    """Fetch a URL and return the HTML body. Raises on failure."""
    import httpx

    with httpx.Client(
        headers=_HEADERS,
        follow_redirects=True,
        timeout=timeout,
        verify=True,
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


def _soup(html: str):
    """Parse HTML into a BeautifulSoup object."""
    from bs4 import BeautifulSoup

    return BeautifulSoup(html, "html.parser")


def _clean_text(soup_obj) -> str:
    """Extract readable text from a soup object, stripping boilerplate."""
    # Remove script, style, nav, footer, header tags
    for tag in soup_obj(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()

    text = soup_obj.get_text(separator="\n", strip=True)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@function_tool
async def scrape_url(url: str, mode: str = "text", max_length: int = 4000) -> str:
    """
    Extracts content from a URL. Supports text, HTML, and markdown modes.

    Args:
        url: The URL to scrape.
        mode: Extraction mode — 'text' (clean readable text), 'html' (raw HTML),
              or 'markdown' (simplified markdown-like output). Default: 'text'.
        max_length: Maximum characters to return (default 4000).
    """
    logger.info(f"Scraping URL: {url} (mode={mode})")

    try:
        html = _fetch(url)
        soup = _soup(html)

        if mode == "html":
            result = html[:max_length]
        elif mode == "markdown":
            # Convert to a markdown-like format
            lines = []
            for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote"]):
                name = tag.name
                text = tag.get_text(strip=True)
                if not text:
                    continue
                if name == "h1":
                    lines.append(f"# {text}")
                elif name == "h2":
                    lines.append(f"## {text}")
                elif name == "h3":
                    lines.append(f"### {text}")
                elif name == "h4":
                    lines.append(f"#### {text}")
                elif name == "li":
                    lines.append(f"- {text}")
                elif name == "blockquote":
                    lines.append(f"> {text}")
                else:
                    lines.append(text)
            result = "\n\n".join(lines)
        else:  # text mode
            result = _clean_text(soup)

        # Truncate
        if len(result) > max_length:
            result = result[:max_length] + "\n\n... (truncated)"

        if not result.strip():
            return f"Page loaded but no readable content found at {url}."

        title = soup.title.string.strip() if soup.title and soup.title.string else urlparse(url).netloc
        return f"Content from '{title}':\n{'─' * 40}\n{result}"
    except Exception as e:
        logger.error(f"scrape_url error: {e}")
        return f"Failed to scrape {url}: {e}"


@function_tool
async def extract_tables(url: str) -> str:
    """
    Extracts all HTML tables from a URL as structured text.

    Args:
        url: The URL containing tables.
    """
    logger.info(f"Extracting tables from: {url}")

    try:
        html = _fetch(url)
        soup = _soup(html)
        tables = soup.find_all("table")

        if not tables:
            return f"No tables found at {url}."

        results = []
        for i, table in enumerate(tables[:5], 1):  # Max 5 tables
            rows = table.find_all("tr")
            if not rows:
                continue

            table_data = []
            for row in rows:
                cells = row.find_all(["th", "td"])
                cell_texts = [c.get_text(strip=True) for c in cells]
                table_data.append(" | ".join(cell_texts))

            if table_data:
                # Add header separator after first row
                header = table_data[0]
                separator = " | ".join(["---"] * header.count("|") + ["---"])
                formatted = [header, separator] + table_data[1:]
                results.append(f"Table {i}:\n" + "\n".join(formatted))

        if not results:
            return f"Tables found but they were empty at {url}."

        return "\n\n".join(results)
    except Exception as e:
        logger.error(f"extract_tables error: {e}")
        return f"Failed to extract tables: {e}"


@function_tool
async def get_page_links(url: str, filter: str = "") -> str:
    """
    Lists all links on a page, with optional keyword filtering.

    Args:
        url: The URL to scan for links.
        filter: Optional keyword to filter links by text or URL (case-insensitive).
    """
    logger.info(f"Getting links from: {url} (filter={filter!r})")

    try:
        html = _fetch(url)
        soup = _soup(html)
        anchors = soup.find_all("a", href=True)

        links = []
        seen = set()
        for a in anchors:
            href = a["href"]
            text = a.get_text(strip=True) or "(no text)"

            # Resolve relative URLs
            full_url = urljoin(url, href)

            # Skip anchors, javascript:, mailto:
            if full_url.startswith(("javascript:", "mailto:", "#")):
                continue

            # Deduplicate
            if full_url in seen:
                continue
            seen.add(full_url)

            # Apply filter
            if filter:
                if filter.lower() not in text.lower() and filter.lower() not in full_url.lower():
                    continue

            links.append(f"• {text[:80]}\n  {full_url}")

        if not links:
            return f"No links found" + (f" matching '{filter}'" if filter else "") + f" at {url}."

        # Cap at 30 links
        output = links[:30]
        total_msg = f" (showing 30 of {len(links)})" if len(links) > 30 else ""
        return f"Links on page{total_msg}:\n\n" + "\n\n".join(output)
    except Exception as e:
        logger.error(f"get_page_links error: {e}")
        return f"Failed to get links: {e}"


@function_tool
async def take_web_screenshot(url: str) -> str:
    """
    Captures a screenshot of a web page and saves it to the Desktop.

    Args:
        url: The URL to screenshot.
    """
    logger.info(f"Taking screenshot of: {url}")

    try:
        from html2image import Html2Image
        import os

        output_dir = os.path.expanduser("~/Desktop")
        hti = Html2Image(output_path=output_dir)

        # Generate filename from URL
        domain = urlparse(url).netloc.replace(".", "_")
        filename = f"screenshot_{domain}.png"

        hti.screenshot(url=url, save_as=filename, size=(1280, 900))

        filepath = os.path.join(output_dir, filename)
        if os.path.exists(filepath):
            return f"Screenshot saved to: {filepath}"
        else:
            return "Screenshot was taken but the file could not be verified."
    except ImportError:
        return "html2image is not installed. Install it with: pip install html2image"
    except Exception as e:
        logger.error(f"take_web_screenshot error: {e}")
        return f"Failed to take screenshot: {e}"


__all__ = ["scrape_url", "extract_tables", "get_page_links", "take_web_screenshot", "ai_summarize_page"]

# ── Dedicated LLM for the scraper agent ───────────────────────────────────────

import os as _os

SCRAPER_AGENT_LLM_API = _os.getenv("SCRAPER_AGENT_LLM_API", "")
SCRAPER_AGENT_LLM_API = _os.getenv("SCRAPER_AGENT_LLM_API", "")
_NIM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
_NIM_MODEL = "meta/llama-3.3-70b-instruct"

LOCAL_LLM_URL = _os.getenv("LOCAL_LLM_URL", "")
LOCAL_LLM_MODEL = _os.getenv("LOCAL_LLM_MODEL", "local-model")


def _scraper_llm(system: str, user: str) -> str:
    """Call the LLM using local LM Studio or fallback to NVIDIA NIM."""
    import requests as _requests

    if LOCAL_LLM_URL:
        url = LOCAL_LLM_URL + "/chat/completions" if not LOCAL_LLM_URL.endswith("chat/completions") else LOCAL_LLM_URL
        api_key = "local-key"
        model = LOCAL_LLM_MODEL
    elif SCRAPER_AGENT_LLM_API:
        url = _NIM_URL
        api_key = SCRAPER_AGENT_LLM_API
        model = _NIM_MODEL
    else:
        raise RuntimeError(
            "Neither LOCAL_LLM_URL nor SCRAPER_AGENT_LLM_API is set in .env. "
            "Cannot use LLM features in the scraper agent."
        )

    resp = _requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.3,
            "max_tokens": 1024,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


@function_tool
async def ai_summarize_page(url: str) -> str:
    """
    Scrapes a webpage and uses the LLM to generate a concise summary.

    Args:
        url: The URL to scrape and summarize.
    """
    logger.info(f"AI summarizing URL: {url}")
    
    try:
        # Re-use internal fetch and clean text
        html = _fetch(url)
        soup = _soup(html)
        text = _clean_text(soup)
        
        if not text.strip():
            return f"No readable text found at {url} to summarize."
            
        # Truncate text to avoid token limits
        text = text[:15000]
        
        title = soup.title.string.strip() if soup.title and soup.title.string else urlparse(url).netloc
        
        system = (
            "You are JARVIS, a web research assistant. Analyze the webpage content and provide "
            "a structured, actionable summary.\n\n"
            "Format:\n"
            "## Summary\n"
            "1-2 concise paragraphs capturing the main points and purpose of the page.\n\n"
            "## Key Facts\n"
            "- Bulleted list of 3-7 specific facts, data points, or claims from the content.\n\n"
            "## Key Takeaways\n"
            "- What's most important or actionable from this content?\n\n"
            "Rules: Be factual. Extract specific numbers, dates, and names. "
            "Don't add information that isn't on the page."
        )
        
        user_prompt = f"Title: {title}\nURL: {url}\n\nContent:\n{text}"
        
        summary = _scraper_llm(system, user_prompt)
        return f"AI Summary for '{title}'\n{'═' * 50}\n{summary}"
        
    except Exception as e:
        logger.error(f"ai_summarize_page error: {e}")
        return f"Failed to summarize page: {e}"

