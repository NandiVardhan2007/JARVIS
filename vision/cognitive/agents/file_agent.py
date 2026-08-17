"""
Autonomous File Workspace & Document Agent for VISION.
Handles file generation, markdown/JSON/CSV report writing, directory reorganization, and archiving.
"""

from typing import Dict, Any, Optional
from vision.cognitive.agents.base_agent import BaseAgent


FILE_AGENT_SYSTEM_PROMPT = """You are the VISION File & Workspace Management Agent.
Your mission is to create files, save research reports and summaries, organize folders, search directories, and manage archives.

CAPABILITIES:
- Use `create_or_write_file` to write structured documents (.md, .txt, .json, .py, .csv).
- Use `read_file_content` to inspect local files.
- Use `list_files` and `find_files` to inspect workspace directories.
- Use `organize_directory`, `organize_downloads`, `organize_desktop` to clean files.
- Use `compress_to_zip` and `extract_zip_archive` for compression.

RULES:
1. When generating documents from research or prior task outputs, format them with clean Markdown headings, bullet points, and code blocks.
2. Confirm the destination file path and success status upon completion.
"""


class FileAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="FileAgent",
            agent_type="file",
            allowed_tools=[
                "create_or_write_file", "read_file_content", "list_files", "find_files",
                "organize_directory", "organize_downloads", "organize_desktop",
                "clean_empty_directories", "compress_to_zip", "extract_zip_archive", "move_file", "copy_file"
            ]
        )

    def get_system_prompt(self) -> str:
        return FILE_AGENT_SYSTEM_PROMPT
