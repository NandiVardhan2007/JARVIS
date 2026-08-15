"""
Media playback automation tools.
"""

import webbrowser
from vision.tools.registry import tool
from vision.logger import logger


@tool(name="play_media", description="Search and play a video or music track on YouTube/Browser.")
def play_media(query: str) -> str:
    """Open YouTube search / video in default browser."""
    url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
    webbrowser.open(url)
    return f"Opened YouTube search for '{query}'."
