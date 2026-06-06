"""Code Review Agent — reviews local files and GitHub PRs via LLM.

Uses the existing _chat_completion() helper from code_generator.py for inference,
and the GitHub integration from github_tool.py for PR fetching.
"""

import logging
import os
from livekit.agents import function_tool

logger = logging.getLogger(__name__)


def _review_with_llm(code: str, prompt: str) -> str:
    """Send code to the LLM for review using the existing dual-provider helper."""
    from Tools.code_generator import _chat_completion

    system = (
        "You are JARVIS, a senior software engineer performing a thorough code review. "
        "Analyze the code for correctness, maintainability, performance, and security.\n\n"
        "Format your review as:\n"
        "## Summary\nBrief overall assessment (quality score 1-10 and one-line verdict).\n\n"
        "## Issues Found\nNumbered list with severity:\n"
        "- 🔴 Critical: bugs, crashes, data loss, security vulnerabilities\n"
        "- 🟡 Warning: performance issues, bad patterns, edge cases\n"
        "- 🔵 Info: style, naming, minor improvements\n\n"
        "## Suggestions\nNumbered list of specific improvement recommendations with rationale.\n\n"
        "## Security\nAny security concerns: injection, auth, data exposure, hardcoded secrets.\n\n"
        "Be direct, specific, and reference line numbers. Focus on issues that matter."
    )
    return _chat_completion(system, f"{prompt}\n\n```\n{code}\n```")


@function_tool
async def review_file(file_path: str) -> str:
    """
    Reads a local code file and returns structured review feedback covering
    code quality, bugs, style, and security.

    Args:
        file_path: Absolute or relative path to the file to review.
    """
    logger.info(f"Reviewing file: {file_path}")

    # Resolve path
    path = os.path.abspath(file_path)
    if not os.path.exists(path):
        return f"File not found: {path}"

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            code = f.read()
    except Exception as e:
        return f"Failed to read file: {e}"

    if not code.strip():
        return f"File is empty: {path}"

    # Truncate very large files
    if len(code) > 15000:
        code = code[:15000] + "\n\n# ... (file truncated at 15,000 chars for review)"

    ext = os.path.splitext(path)[1].lstrip(".")
    lang_map = {
        "py": "Python", "js": "JavaScript", "ts": "TypeScript",
        "java": "Java", "cpp": "C++", "c": "C", "go": "Go",
        "rs": "Rust", "rb": "Ruby", "php": "PHP", "kt": "Kotlin",
        "swift": "Swift", "cs": "C#", "sh": "Shell", "ps1": "PowerShell",
    }
    language = lang_map.get(ext, ext or "unknown")

    try:
        prompt = (
            f"Review this {language} file ({os.path.basename(path)}).\n"
            f"File size: {len(code)} characters, {code.count(chr(10))+1} lines."
        )
        review = _review_with_llm(code, prompt)
        return f"Code Review — {os.path.basename(path)}\n{'═' * 40}\n{review}"
    except Exception as e:
        logger.error(f"review_file LLM error: {e}")
        return f"Code review failed: {e}"


@function_tool
async def review_pr(repo_name: str, pr_number: int) -> str:
    """
    Fetches a GitHub Pull Request diff and reviews it for quality, bugs,
    and best practices.

    Args:
        repo_name: Full repo name, e.g. 'owner/repo'.
        pr_number: The pull request number.
    """
    logger.info(f"Reviewing PR #{pr_number} in {repo_name}")

    try:
        from github import Github, Auth

        token = os.getenv("GITHUB_TOKEN")
        if not token:
            return "GitHub integration not configured. Set GITHUB_TOKEN in .env."

        g = Github(auth=Auth.Token(token))
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        # Get PR metadata
        title = pr.title
        body = pr.body or "(no description)"
        author = pr.user.login
        changed_files = pr.changed_files
        additions = pr.additions
        deletions = pr.deletions

        # Fetch the diff (file patches)
        files = pr.get_files()
        diff_parts = []
        total_chars = 0
        for f in files:
            patch = f.patch or "(binary or empty)"
            header = f"### {f.filename} (+{f.additions}/-{f.deletions})"
            part = f"{header}\n```diff\n{patch}\n```"
            if total_chars + len(part) > 12000:
                diff_parts.append("... (remaining files omitted for size)")
                break
            diff_parts.append(part)
            total_chars += len(part)

        diff_text = "\n\n".join(diff_parts)

        prompt = (
            f"Review this GitHub Pull Request.\n\n"
            f"**PR #{pr_number}: {title}**\n"
            f"Author: {author}\n"
            f"Changed files: {changed_files}, +{additions}/-{deletions}\n"
            f"Description: {body[:500]}\n\n"
            f"## Diff:\n{diff_text}"
        )

        review = _review_with_llm(diff_text, prompt)
        return (
            f"PR Review — {repo_name}#{pr_number}: {title}\n"
            f"{'═' * 50}\n"
            f"Author: {author} | {changed_files} files | +{additions}/-{deletions}\n\n"
            f"{review}"
        )
    except Exception as e:
        logger.error(f"review_pr error: {e}")
        return f"Failed to review PR: {e}"


@function_tool
async def suggest_refactor(file_path: str) -> str:
    """
    Analyzes a code file and suggests specific refactoring improvements
    (structure, naming, patterns, performance).

    Args:
        file_path: Path to the file to analyze.
    """
    logger.info(f"Suggesting refactors for: {file_path}")

    path = os.path.abspath(file_path)
    if not os.path.exists(path):
        return f"File not found: {path}"

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            code = f.read()
    except Exception as e:
        return f"Failed to read file: {e}"

    if not code.strip():
        return f"File is empty: {path}"

    if len(code) > 15000:
        code = code[:15000] + "\n\n# ... (truncated)"

    ext = os.path.splitext(path)[1].lstrip(".")

    try:
        from Tools.code_generator import _chat_completion

        system = (
            "You are JARVIS, a senior software architect specializing in code refactoring. "
            "Analyze the code and provide specific, high-impact refactoring suggestions.\n\n"
            "Format:\n"
            "## Current Assessment\n"
            "Quality score (1-10) and brief assessment of current code health.\n\n"
            "## Refactoring Suggestions\nNumbered list, each with:\n"
            "- **What:** The specific change to make\n"
            "- **Why:** The concrete benefit (performance gain, reduced complexity, better testability)\n"
            "- **How:** Brief code example showing before -> after\n\n"
            "## Design Pattern Opportunities\n"
            "Patterns that could improve the code (Strategy, Observer, Factory, etc.) — only "
            "suggest patterns that genuinely simplify, not patterns for their own sake.\n\n"
            "Focus on practical, high-impact improvements. Don't nitpick formatting or naming "
            "unless it significantly hurts readability."
        )
        prompt = f"Analyze and suggest refactoring for this {ext} file ({os.path.basename(path)}):"
        result = _chat_completion(system, f"{prompt}\n\n```\n{code}\n```")
        return f"Refactoring Suggestions — {os.path.basename(path)}\n{'═' * 40}\n{result}"
    except Exception as e:
        logger.error(f"suggest_refactor error: {e}")
        return f"Refactoring analysis failed: {e}"


__all__ = ["review_file", "review_pr", "suggest_refactor"]
