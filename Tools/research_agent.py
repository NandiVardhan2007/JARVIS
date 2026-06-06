"""Research Agent — multi-step research combining scraping and knowledge base."""

import logging
from typing import List
from livekit.agents import function_tool

logger = logging.getLogger(__name__)


@function_tool
async def deep_research(topic: str, num_sources: int = 3) -> str:
    """
    Conducts deep research on a topic by searching the web, scraping top results,
    and generating a comprehensive summary.
    
    Args:
        topic: The topic to research.
        num_sources: Number of sources to scrape (default 3, max 5).
    """
    logger.info(f"Conducting deep research on: {topic}")
    
    num_sources = max(1, min(num_sources, 5))
    
    try:
        # We would ideally use execute_multi_task here internally or orchestrate directly
        # For simplicity, we'll use duckduckgo search directly to get URLs
        from langchain_community.tools import DuckDuckGoSearchResults
        import re
        
        search_res = DuckDuckGoSearchResults().run(topic)
        # Extract URLs from the string result (it formats as [snippet] (link))
        urls = re.findall(r'\]\((https?://[^\)]+)\)', search_res)
        
        if not urls:
            return f"Could not find valid sources for '{topic}'."
            
        urls_to_scrape = urls[:num_sources]
        
        from Tools.scraper_agent import _fetch, _soup, _clean_text
        from Tools.scraper_agent import _scraper_llm, SCRAPER_AGENT_LLM_API
        
        if not SCRAPER_AGENT_LLM_API:
             return "SCRAPER_AGENT_LLM_API not set. Deep research requires LLM capabilities."
        
        scraped_texts = []
        for url in urls_to_scrape:
            try:
                html = _fetch(url, timeout=10)
                soup = _soup(html)
                text = _clean_text(soup)
                # Take snippet to avoid huge prompts
                scraped_texts.append(f"Source: {url}\n{text[:4000]}")
            except Exception as e:
                logger.warning(f"Failed to scrape {url} for research: {e}")
                
        if not scraped_texts:
            return "Failed to extract content from the found sources."
            
        combined_text = "\n\n---\n\n".join(scraped_texts)
        
        system = (
            "You are JARVIS, an expert research analyst. Synthesize information from multiple "
            "sources into a comprehensive, well-structured research report.\n\n"
            "Format:\n"
            "# Research Report: [Topic]\n\n"
            "## Executive Summary\n"
            "2-3 paragraph overview of key findings.\n\n"
            "## Key Findings\n"
            "Numbered list of the most important discoveries, with source attribution.\n\n"
            "## Detailed Analysis\n"
            "In-depth discussion organized by theme, not by source. Cross-reference sources.\n\n"
            "## Source Credibility\n"
            "Brief assessment of each source's reliability and potential bias.\n\n"
            "## Sources\n"
            "Numbered list of URLs used.\n\n"
            "Rules: Be objective. Distinguish between facts and opinions. Flag contradictions "
            "between sources. Cite specific sources when making claims."
        )
        
        user_prompt = f"Topic: {topic}\n\nInformation:\n{combined_text}"
        
        report = _scraper_llm(system, user_prompt)
        
        # Optionally save to Knowledge Base
        try:
            from Tools.knowledge_base import save_note
            save_note._func(title=f"Research: {topic}", content=report)
            saved_msg = "\n\n(This report has been saved to your Knowledge Base)"
        except Exception:
            saved_msg = ""
            
        return f"Research complete.\n{'═' * 50}\n{report}{saved_msg}"
        
    except Exception as e:
        logger.error(f"deep_research error: {e}")
        return f"Research failed: {e}"


@function_tool
async def compare_sources(urls: List[str]) -> str:
    """
    Scrapes multiple URLs and produces a comparison analysis.
    
    Args:
        urls: List of URLs to compare (max 4).
    """
    logger.info(f"Comparing {len(urls)} sources")
    
    if not urls:
        return "No URLs provided for comparison."
        
    urls = urls[:4]
    
    try:
        from Tools.scraper_agent import _fetch, _soup, _clean_text
        from Tools.scraper_agent import _scraper_llm, SCRAPER_AGENT_LLM_API
        
        if not SCRAPER_AGENT_LLM_API:
             return "SCRAPER_AGENT_LLM_API not set. Comparison requires LLM capabilities."
             
        scraped_texts = []
        valid_urls = []
        for url in urls:
            try:
                html = _fetch(url, timeout=10)
                soup = _soup(html)
                text = _clean_text(soup)
                scraped_texts.append(f"Source {len(valid_urls)+1}: {url}\n{text[:4000]}")
                valid_urls.append(url)
            except Exception as e:
                logger.warning(f"Failed to scrape {url} for comparison: {e}")
                
        if len(valid_urls) < 2:
            return "Need at least 2 successfully scraped sources to make a comparison."
            
        combined_text = "\n\n---\n\n".join(scraped_texts)
        
        system = (
            "You are JARVIS, an expert analyst performing a source comparison.\n\n"
            "Format:\n"
            "## Overview\n"
            "What these sources cover and their respective perspectives.\n\n"
            "## Points of Agreement\n"
            "Facts and claims that multiple sources confirm (cite which ones).\n\n"
            "## Points of Contention\n"
            "Where sources disagree, with each side's argument summarized fairly.\n\n"
            "## Unique Information per Source\n"
            "Key facts that only appear in one source.\n\n"
            "## Recommendation\n"
            "Which source(s) appear most reliable and why.\n\n"
            "Rules: Be objective and balanced. Don't favor any source without evidence."
        )
        
        user_prompt = f"Please compare these sources:\n\n{combined_text}"
        
        comparison = _scraper_llm(system, user_prompt)
        
        return f"Source Comparison\n{'═' * 50}\n{comparison}"
        
    except Exception as e:
        logger.error(f"compare_sources error: {e}")
        return f"Comparison failed: {e}"


__all__ = ["deep_research", "compare_sources"]
