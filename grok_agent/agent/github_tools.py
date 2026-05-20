"""
GitHub Tools Module for Neximus
Provides read-only access to public GitHub repositories via REST API.
No authentication required for public repos.
"""

import requests
import base64
import logging

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
REPO_OWNER = "thedredgegroup"
REPO_NAME = "neximus"
DEFAULT_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}


def get_repo_info():
    """
    GET /repos/{owner}/{repo}
    Returns repo metadata: description, stars, forks, language, updated_at.
    Returns dict with 'success' bool and 'data' or 'error'.
    """
    url = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}"
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
        resp.raise_for_status()
        raw = resp.json()
        return {
            "success": True,
            "data": {
                "name": raw.get("name"),
                "description": raw.get("description"),
                "stars": raw.get("stargazers_count", 0),
                "forks": raw.get("forks_count", 0),
                "open_issues": raw.get("open_issues_count", 0),
                "language": raw.get("language"),
                "default_branch": raw.get("default_branch"),
                "updated_at": raw.get("updated_at"),
                "html_url": raw.get("html_url"),
                "topics": raw.get("topics", [])
            }
        }
    except requests.HTTPError as e:
        logger.error(f"GitHub repo info HTTP error: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"GitHub repo info error: {e}")
        return {"success": False, "error": str(e)}


def list_contents(path=""):
    """
    GET /repos/{owner}/{repo}/contents/{path}
    Lists files and folders at the given path (default: repo root).
    Returns dict with 'success' bool and 'data' (list of items) or 'error'.
    Each item: name, type ('file'|'dir'), path, size.
    """
    path = path.strip("/")
    url = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
        resp.raise_for_status()
        raw = resp.json()

        # GitHub returns a list for directories, dict for single files
        if isinstance(raw, dict):
            # Single file returned (shouldn't happen for listing, but handle it)
            items = [raw]
        else:
            items = raw

        data = []
        for item in items:
            data.append({
                "name": item.get("name"),
                "type": item.get("type"),   # 'file' or 'dir'
                "path": item.get("path"),
                "size": item.get("size", 0)
            })

        # Sort: dirs first, then files, both alphabetically
        data.sort(key=lambda x: (0 if x["type"] == "dir" else 1, x["name"].lower()))

        return {"success": True, "data": data, "path": path or "/"}
    except requests.HTTPError as e:
        logger.error(f"GitHub list contents HTTP error: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"GitHub list contents error: {e}")
        return {"success": False, "error": str(e)}


def read_file(path):
    """
    GET /repos/{owner}/{repo}/contents/{path}
    Fetches a single file and returns its decoded text content.
    Returns dict with 'success' bool and 'content' (str) or 'error'.
    Also returns 'name' and 'path' for reference.
    """
    path = path.strip("/")
    url = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        resp.raise_for_status()
        raw = resp.json()

        if isinstance(raw, list):
            return {"success": False, "error": f"Path '{path}' is a directory, not a file."}

        encoding = raw.get("encoding")
        if encoding == "base64":
            content_bytes = base64.b64decode(raw.get("content", ""))
            content = content_bytes.decode("utf-8", errors="replace")
        else:
            content = raw.get("content", "")

        return {
            "success": True,
            "name": raw.get("name"),
            "path": raw.get("path"),
            "size": raw.get("size", 0),
            "content": content
        }
    except requests.HTTPError as e:
        logger.error(f"GitHub read file HTTP error: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"GitHub read file error: {e}")
        return {"success": False, "error": str(e)}


def get_commits(per_page=10):
    """
    GET /repos/{owner}/{repo}/commits
    Returns the most recent commits (default 10).
    Each commit: sha (short), message, author, date.
    """
    url = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/commits"
    params = {"per_page": per_page}
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, params=params, timeout=10)
        resp.raise_for_status()
        raw = resp.json()

        data = []
        for item in raw:
            commit = item.get("commit", {})
            author = commit.get("author", {})
            data.append({
                "sha": item.get("sha", "")[:7],
                "message": commit.get("message", "").split("\n")[0],  # First line only
                "author": author.get("name", "unknown"),
                "date": author.get("date", "")
            })

        return {"success": True, "data": data}
    except requests.HTTPError as e:
        logger.error(f"GitHub commits HTTP error: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"GitHub commits error: {e}")
        return {"success": False, "error": str(e)}


def get_issues(state="open", per_page=10):
    """
    GET /repos/{owner}/{repo}/issues
    Returns issues filtered by state ('open', 'closed', 'all').
    Each issue: number, title, state, labels, created_at, user.
    """
    url = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/issues"
    params = {"state": state, "per_page": per_page}
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, params=params, timeout=10)
        resp.raise_for_status()
        raw = resp.json()

        data = []
        for item in raw:
            # GitHub issues endpoint also returns PRs - filter them out
            if "pull_request" in item:
                continue
            data.append({
                "number": item.get("number"),
                "title": item.get("title"),
                "state": item.get("state"),
                "labels": [lbl.get("name") for lbl in item.get("labels", [])],
                "created_at": item.get("created_at", ""),
                "user": item.get("user", {}).get("login", "unknown")
            })

        return {"success": True, "data": data}
    except requests.HTTPError as e:
        logger.error(f"GitHub issues HTTP error: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"GitHub issues error: {e}")
        return {"success": False, "error": str(e)}