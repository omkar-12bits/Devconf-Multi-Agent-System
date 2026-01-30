import json
import logging
import os
from typing import Dict, Any, Optional

import httpx
from google.adk.tools import FunctionTool

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    logger.error("GITHUB_TOKEN environment variable is not set")
    raise ValueError("GITHUB_TOKEN environment variable is not set")

headers = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "GitHub-Project-Analyst-Agent",
    "Authorization": f"token {GITHUB_TOKEN}"
}


def _make_github_request(endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """Make a request to GitHub API"""
    try:
        url = f"https://api.github.com/{endpoint.lstrip('/')}"
        response = httpx.get(url, headers=headers, params=params, timeout=10)
        if response.status_code != 200:
            logger.error(f"GitHub API request failed: {response.status_code} {response.text}")
            return {"error": f"GitHub API request failed: {response.status_code} {response.text}"}
        return response.json()
    except httpx.RequestError as e:
        logger.error(f"GitHub API request failed: {str(e)}")
        return {"error": f"GitHub API request failed: {str(e)}"}

def get_repository_info(owner: str, repo: str) -> str:
    """
    Get basic information about a GitHub repository
    
    Args:
        owner: Repository owner (username or organization)
        repo: Repository name
    Returns:
        A JSON object with repository information or an error message if the request fails.
    """
    data = _make_github_request(f"repos/{owner}/{repo}")
    
    if "error" in data:
        logger.error(f"Error getting repository info for {owner}/{repo}: {data['error']}")
        return json.dumps({"error": f"Error getting repository info for {owner}/{repo}: {data['error']}"})
    
    # Extract key information
    repo_info = {
        "name": data.get("name"),
        "full_name": data.get("full_name"),
        "description": data.get("description"),
        "language": data.get("language"),
        "stars": data.get("stargazers_count"),
        "forks": data.get("forks_count"),
        "open_issues": data.get("open_issues_count"),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "size": data.get("size"),
        "default_branch": data.get("default_branch"),
        "topics": data.get("topics", []),
        "license": data.get("license", {}).get("name") if data.get("license") else None,
        "homepage": data.get("homepage"),
        "clone_url": data.get("clone_url"),
        "ssh_url": data.get("ssh_url")
    }
    
    return json.dumps(repo_info, indent=2)

def get_repository_languages(owner: str, repo: str) -> str:
    """
    Get programming languages used in a repository
    
    Args:
        owner: Repository owner (username or organization)
        repo: Repository name
    Returns:
        A JSON object with language statistics or an error message if the request fails.
    """
    data = _make_github_request(f"repos/{owner}/{repo}/languages")
    
    if "error" in data:
        logger.error(f"Error getting languages for {owner}/{repo}: {data['error']}")
        return json.dumps({"error": f"Error getting languages for {owner}/{repo}: {data['error']}"})
    
    # Calculate percentages
    total_bytes = sum(data.values())
    languages_with_percentages = {}
    
    for language, bytes_count in data.items():
        percentage = (bytes_count / total_bytes * 100) if total_bytes > 0 else 0
        languages_with_percentages[language] = {
            "bytes": bytes_count,
            "percentage": round(percentage, 2)
        }
    
    # Sort by bytes count
    sorted_languages = dict(sorted(languages_with_percentages.items(), 
                                 key=lambda x: x[1]["bytes"], reverse=True))
    
    return json.dumps(sorted_languages, indent=2)

def get_repository_contributors(owner: str, repo: str, per_page: int = 20) -> str:
    """
    Get contributors to a repository

    Args:
        owner: Repository owner (username or organization)
        repo: Repository name
        per_page: Number of contributors to fetch (max 20)
    Returns:
        A JSON object with contributor information or an error message if the request fails.
    """
    params = {"per_page": min(per_page, 20)}
    data = _make_github_request(f"repos/{owner}/{repo}/contributors", params)
    
    if "error" in data:
        logger.error(f"Error getting contributors for {owner}/{repo}: {data['error']}")
        return json.dumps({"error": f"Error getting contributors for {owner}/{repo}: {data['error']}"})
    
    contributors = []
    for contributor in data:
        contributors.append({
            "login": contributor.get("login"),
            "contributions": contributor.get("contributions"),
            "type": contributor.get("type"),
            "profile_url": contributor.get("html_url")
        })
    
    return json.dumps(contributors, indent=2)

def get_repository_issues(owner: str, repo: str, state: str = "open", per_page: int = 20) -> str:
    """
    Get issues from a repository
    
    Args:
        owner: Repository owner (username or organization)
        repo: Repository name
        state: Issue state ('open', 'closed', or 'all')
        per_page: Number of issues to fetch (max 20)
    Returns:
        A JSON object with issue information or an error message if the request fails.
    """
    params = {"state": state, "per_page": min(per_page, 20)}
    data = _make_github_request(f"repos/{owner}/{repo}/issues", params)
    
    if "error" in data:
        logger.error(f"Error getting issues for {owner}/{repo}: {data['error']}")
        return json.dumps({"error": f"Error getting issues for {owner}/{repo}: {data['error']}"})
    
    issues = []
    for issue in data:
        # Skip pull requests (they appear in issues endpoint)
        if issue.get("pull_request"):
            continue
            
        issues.append({
            "number": issue.get("number"),
            "title": issue.get("title"),
            "state": issue.get("state"),
            "created_at": issue.get("created_at"),
            "updated_at": issue.get("updated_at"),
            "labels": [label.get("name") for label in issue.get("labels", [])],
            "assignees": [assignee.get("login") for assignee in issue.get("assignees", [])],
            "comments": issue.get("comments"),
            "author": issue.get("user", {}).get("login"),
            "url": issue.get("html_url")
        })
    
    return json.dumps(issues, indent=2)

def get_repository_pulls(owner: str, repo: str, state: str = "open", per_page: int = 20) -> str:
    """
    Get pull requests from a repository
    
    Args:
        owner: Repository owner (username or organization)
    :param repo: Repository name
    :param state: PR state ('open', 'closed', or 'all')
    :param per_page: Number of PRs to fetch (max 100)
    :return: JSON string with pull request information
    """
    params = {"state": state, "per_page": min(per_page, 20)}
    data = _make_github_request(f"repos/{owner}/{repo}/pulls", params)
    
    if "error" in data:
        logger.error(f"Error getting pulls for {owner}/{repo}: {data['error']}")
        return json.dumps({"error": f"Error getting pulls for {owner}/{repo}: {data['error']}"})
    
    pulls = []
    for pr in data:
        pulls.append({
            "number": pr.get("number"),
            "title": pr.get("title"),
            "state": pr.get("state"),
            "created_at": pr.get("created_at"),
            "updated_at": pr.get("updated_at"),
            "merged_at": pr.get("merged_at"),
            "author": pr.get("user", {}).get("login"),
            "base_branch": pr.get("base", {}).get("ref"),
            "head_branch": pr.get("head", {}).get("ref"),
            "additions": pr.get("additions"),
            "deletions": pr.get("deletions"),
            "changed_files": pr.get("changed_files"),
            "comments": pr.get("comments"),
            "review_comments": pr.get("review_comments"),
            "url": pr.get("html_url")
        })
    
    return json.dumps(pulls, indent=2)

def get_repository_releases(owner: str, repo: str, per_page: int = 20) -> str:
    """
    Get releases from a repository
    
    Args:
        owner: Repository owner (username or organization)
        repo: Repository name
        per_page: Number of releases to fetch (max 20)
    Returns:
        A JSON object with release information or an error message if the request fails.
    """
    params = {"per_page": min(per_page, 20)}
    data = _make_github_request(f"repos/{owner}/{repo}/releases", params)
    
    if "error" in data:
        logger.error(f"Error getting releases for {owner}/{repo}: {data['error']}")
        return json.dumps({"error": f"Error getting releases for {owner}/{repo}: {data['error']}"})
    
    releases = []
    for release in data:
        releases.append({
            "name": release.get("name"),
            "tag_name": release.get("tag_name"),
            "published_at": release.get("published_at"),
            "created_at": release.get("created_at"),
            "author": release.get("author", {}).get("login"),
            "prerelease": release.get("prerelease"),
            "draft": release.get("draft"),
            "assets_count": len(release.get("assets", [])),
            "body": release.get("body", "")[:500] + "..." if len(release.get("body", "")) > 500 else release.get("body", ""),
            "url": release.get("html_url")
        })
    
    return json.dumps(releases, indent=2)

def search_repositories(query: str, sort: str = "stars", order: str = "desc", per_page: int = 10) -> str:
    """
    Search for repositories on GitHub
    
    Args:
        query: Search query
        sort: Sort criteria ('stars', 'forks', 'help-wanted-issues', 'updated')
        order: Sort order ('asc' or 'desc')
        per_page: Number of results to fetch (max 10)
    Returns:
        A JSON object with search results or an error message if the request fails.
    """
    params = {
        "q": query,
        "sort": sort,
        "order": order,
        "per_page": min(per_page, 10)
    }
    data = _make_github_request("search/repositories", params)
    
    if "error" in data:
        logger.error(f"Error searching repositories for {query}: {data['error']}")
        return json.dumps({"error": f"Error searching repositories for {query}: {data['error']}"})
    
    results = {
        "total_count": data.get("total_count"),
        "incomplete_results": data.get("incomplete_results"),
        "repositories": []
    }
    
    for repo in data.get("items", []):
        results["repositories"].append({
            "name": repo.get("name"),
            "full_name": repo.get("full_name"),
            "description": repo.get("description"),
            "language": repo.get("language"),
            "stars": repo.get("stargazers_count"),
            "forks": repo.get("forks_count"),
            "open_issues": repo.get("open_issues_count"),
            "created_at": repo.get("created_at"),
            "updated_at": repo.get("updated_at"),
            "topics": repo.get("topics", []),
            "license": repo.get("license", {}).get("name") if repo.get("license") else None,
            "url": repo.get("html_url")
        })
    
    return json.dumps(results, indent=2)


GITHUB_TOOLS = [
    FunctionTool(func=get_repository_info),
    FunctionTool(func=get_repository_languages),
    FunctionTool(func=get_repository_contributors),
    FunctionTool(func=get_repository_issues),
    FunctionTool(func=get_repository_pulls),
    FunctionTool(func=get_repository_releases),
    FunctionTool(func=search_repositories)
]