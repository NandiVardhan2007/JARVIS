"""
Autonomous Web Research & Intelligence Synthesis Agent for VISION.
Performs web queries, extracts webpage information, and produces structured research briefings.
"""

from typing import Dict, Any, Optional
from vision.cognitive.agents.base_agent import BaseAgent
from vision.config import config


RESEARCH_AGENT_SYSTEM_PROMPT = """You are the VISION Autonomous Web Research & Information Gathering Agent.
Your mission is to perform targeted web searches, retrieve webpage contents, synthesize facts, and provide highly structured, accurate research briefings.

CAPABILITIES:
- Use `search_web` to discover URLs, news, and relevant documentation.
- Use `fetch_webpage_content` to read deep webpage content.
- Use `get_weather_forecast` if atmospheric/climate information is requested.

RULES:
1. Synthesize clear, concise, well-structured summaries with key bullet points and facts.
2. Provide direct answers without unnecessary conversational fluff.
3. Include relevant dates, sources, and metrics when available.
"""


class ResearchAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="ResearchAgent",
            agent_type="research",
            dedicated_api_key=getattr(config, "SCRAPER_AGENT_LLM_API", None),
            allowed_tools=["search_web", "fetch_webpage_content", "get_weather_forecast"]
        )

    def get_system_prompt(self) -> str:
        return RESEARCH_AGENT_SYSTEM_PROMPT
