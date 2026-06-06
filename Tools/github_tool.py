"""GitHub Integration Tool for JARVIS."""

import os
import logging
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

def _get_github():
    try:
        from github import Github
        from github import Auth
    except ImportError:
        return None
        
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return None
        
    auth = Auth.Token(token)
    return Github(auth=auth)

@function_tool
async def list_github_repos(visibility: str = "all") -> str:
    """
    Lists repositories for the authenticated GitHub user.
    
    Args:
        visibility: Filter by 'all', 'public', or 'private'.
    """
    g = _get_github()
    if not g:
        return "GitHub integration is not configured. Please add GITHUB_TOKEN to .env and install PyGithub."
        
    try:
        user = g.get_user()
        repos = user.get_repos(visibility=visibility)
        
        # Limit to 10 to avoid huge outputs
        repo_list = []
        for i, repo in enumerate(repos):
            if i >= 10:
                repo_list.append("... (showing first 10)")
                break
            repo_list.append(f"- {repo.full_name} ({'private' if repo.private else 'public'}): {repo.html_url}")
            
        if not repo_list:
            return "No repositories found."
        return "\n".join(repo_list)
    except Exception as e:
        logger.error(f"GitHub list_repos error: {e}")
        return f"Failed to list repos: {e}"

@function_tool
async def get_github_pull_requests(repo_name: str, state: str = "open") -> str:
    """
    Gets pull requests for a specific repository.
    
    Args:
        repo_name: Full name of the repo, e.g. 'owner/repo'
        state: 'open', 'closed', or 'all'
    """
    g = _get_github()
    if not g:
        return "GitHub integration is not configured. Please add GITHUB_TOKEN to .env and install PyGithub."
        
    try:
        repo = g.get_repo(repo_name)
        prs = repo.get_pulls(state=state, sort='created', direction='desc')
        
        pr_list = []
        for i, pr in enumerate(prs):
            if i >= 5:
                pr_list.append("... (showing first 5)")
                break
            pr_list.append(f"#{pr.number} {pr.title} by {pr.user.login} ({pr.state})")
            
        if not pr_list:
            return f"No {state} pull requests found in {repo_name}."
        return f"PRs in {repo_name}:\n" + "\n".join(pr_list)
    except Exception as e:
        logger.error(f"GitHub get_prs error: {e}")
        return f"Failed to get PRs: {e}"

@function_tool
async def create_github_issue(repo_name: str, title: str, body: str = "") -> str:
    """
    Creates a new issue in a GitHub repository.
    
    Args:
        repo_name: Full name of the repo, e.g. 'owner/repo'
        title: Issue title
        body: Optional issue body/description
    """
    g = _get_github()
    if not g:
        return "GitHub integration is not configured. Please add GITHUB_TOKEN to .env and install PyGithub."
        
    try:
        repo = g.get_repo(repo_name)
        issue = repo.create_issue(title=title, body=body)
        return f"Issue created successfully: #{issue.number} {issue.html_url}"
    except Exception as e:
        logger.error(f"GitHub create_issue error: {e}")
        return f"Failed to create issue: {e}"

@function_tool
async def get_github_recent_commits(repo_name: str, branch: str = "main", limit: int = 5) -> str:
    """
    Gets the most recent commits for a repository branch.
    
    Args:
        repo_name: Full name of the repo, e.g. 'owner/repo'
        branch: Branch name
        limit: Number of commits to fetch (1-10)
    """
    g = _get_github()
    if not g:
        return "GitHub integration is not configured. Please add GITHUB_TOKEN to .env and install PyGithub."
        
    limit = max(1, min(limit, 10))
    
    try:
        repo = g.get_repo(repo_name)
        commits = repo.get_commits(sha=branch)
        
        commit_list = []
        for i, commit in enumerate(commits):
            if i >= limit:
                break
            msg = commit.commit.message.split('\n')[0]
            author = commit.commit.author.name
            commit_list.append(f"- {commit.sha[:7]} by {author}: {msg}")
            
        if not commit_list:
            return f"No commits found on {branch} in {repo_name}."
        return f"Recent commits on {branch}:\n" + "\n".join(commit_list)
    except Exception as e:
        logger.error(f"GitHub get_commits error: {e}")
        return f"Failed to get commits: {e}"
