#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastmcp",
#     "pydantic",
#     "requests",
#     "tiktoken"
# ]
# ///

"""
# GitHub Repository MCP Server

A single-file Python MCP server that provides filesystem-like navigation of public GitHub repositories 
with intelligent token-based safety limits. This server follows the established patterns from the 
`simple-mcp-servers` project.

## Core Philosophy
- **Filesystem-like Experience**: Navigation should feel similar to using local filesystem tools
- **Token Efficiency**: Intelligent token limits using tiktoken to prevent context window overflow
- **Self-Documenting**: Error messages include suggestions for alternative approaches
- **Simple & Focused**: Essential navigation tools only, following single-file MCP server pattern

## Claude Configuration

Sample configuration below:

```json
{
  "mcpServers": {
    "github-repo": {
      "command": "/Users/Joshua/.local/bin/uv",
      "args": [
        "run",
        "--script",
        "/Users/Joshua/Documents/_programming/simple-mcp-servers/github_repo_mcp.py"
      ]
    },
    "other servers here": {}
  }
}
```

## Tools Provided

- `repo_list_directory`: List contents of a directory in a GitHub repository
- `repo_tree_view`: Provides recursive directory tree view with configurable depth  
- `repo_file_info`: Get metadata about a file without reading its contents
- `repo_read_file`: Read file contents with intelligent token-based safety limits

## Example Usage

```python
# List repository root
result = repo_list_directory("microsoft", "vscode")

# Explore src directory  
result = repo_list_directory("microsoft", "vscode", "src")

# Get tree view
result = repo_tree_view("microsoft", "vscode", max_depth=2)

# Check file info first
info = repo_file_info("microsoft", "vscode", "package.json")

# Read with default limits
content = repo_read_file("microsoft", "vscode", "package.json")

# Continue reading if truncated
if content.get("continuation_start_line"):
    next_content = repo_read_file(
        "microsoft", "vscode", "package.json", 
        start_line=content["continuation_start_line"]
    )
```

## Environment Variables

- `GITHUB_TOKEN`: Optional GitHub personal access token for higher rate limits

## Features

- **Token Aware**: Prevents context window overflow with intelligent limits
- **Self-Documenting**: Error messages guide users to appropriate alternatives  
- **Familiar Interface**: Matches local filesystem tool patterns
- **Simple Architecture**: Single-file implementation following project standards
- **Optional Performance**: GitHub token support for higher rate limits
- **Safety First**: Binary detection and sensible defaults
"""

import os
import re
import sys
import base64
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse, unquote
from fastmcp import FastMCP
from pydantic import Field
import requests
import tiktoken


# Create server
mcp = FastMCP("github-repo")


def get_github_headers() -> Dict[str, str]:
    """Get headers for GitHub API requests with optional authentication."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "GitHub-Repo-MCP/1.0"
    }
    
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    
    return headers


def parse_github_url(url: str) -> Optional[Dict[str, str]]:
    """
    Parse GitHub URLs to extract owner/repo/path information.
    
    Supports:
    - https://github.com/owner/repo
    - https://github.com/owner/repo.git
    - https://github.com/owner/repo/tree/main/path
    - https://github.com/owner/repo/blob/main/file.py
    - owner/repo (shorthand)
    """
    # Handle shorthand format (owner/repo)
    if "/" in url and "://" not in url:
        parts = url.split("/", 1)
        if len(parts) == 2:
            return {"owner": parts[0], "repo": parts[1], "path": ""}
    
    # Parse full URLs
    try:
        parsed = urlparse(url)
        if parsed.hostname != "github.com":
            return None
            
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) < 2:
            return None
            
        owner = path_parts[0]
        repo = path_parts[1]
        
        # Remove .git suffix if present
        if repo.endswith(".git"):
            repo = repo[:-4]
            
        # Extract file/directory path for tree/blob URLs
        extracted_path = ""
        if len(path_parts) > 4 and path_parts[2] in ["tree", "blob"]:
            extracted_path = "/".join(path_parts[4:])
            
        return {"owner": owner, "repo": repo, "path": extracted_path}
        
    except Exception:
        return None


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken."""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        # Fallback to rough estimation if tiktoken fails
        return len(text) // 4


def is_binary_file(content_type: str = None, filename: str = None) -> bool:
    """Check if a file is likely binary based on content type or filename."""
    if content_type:
        if content_type.startswith(("image/", "video/", "audio/", "application/")):
            # Allow some text-based application types
            text_apps = ["application/json", "application/xml", "application/javascript"]
            if not any(ct in content_type for ct in text_apps):
                return True
    
    if filename:
        binary_extensions = {
            ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
            ".mp4", ".mp3", ".wav", ".avi", ".mov", ".pdf", ".zip",
            ".tar", ".gz", ".7z", ".rar", ".exe", ".dll", ".so",
            ".dylib", ".bin", ".dat", ".db", ".sqlite", ".woff",
            ".woff2", ".ttf", ".otf", ".eot"
        }
        ext = os.path.splitext(filename)[1].lower()
        return ext in binary_extensions
    
    return False


@mcp.tool()
def repo_list_directory(
    owner: str = Field(description="Repository owner/organization name"),
    repo: str = Field(description="Repository name"),
    path: str = Field(default="", description="Directory path within repo (default: root)")
) -> Dict[str, Any]:
    """List contents of a directory in a GitHub repository."""
    
    result = {
        "owner": owner,
        "repo": repo,
        "path": path,
        "items": [],
        "total_items": 0,
        "error": None
    }
    
    try:
        # Construct API URL
        api_path = f"repos/{owner}/{repo}/contents"
        if path:
            api_path += f"/{path}"
        
        url = f"https://api.github.com/{api_path}"
        headers = get_github_headers()
        
        response = requests.get(url, headers=headers, timeout=30)
        
        # Handle rate limiting
        if response.status_code == 403 and "rate limit" in response.text.lower():
            result["error"] = "GitHub API rate limit exceeded. Consider setting GITHUB_TOKEN environment variable for higher limits."
            return result
        
        # Handle not found
        if response.status_code == 404:
            result["error"] = f"Repository {owner}/{repo} or path '{path}' not found. Use repo_list_directory() with empty path to explore available files."
            return result
        
        response.raise_for_status()
        data = response.json()
        
        # Handle single file response (when path points to a file)
        if isinstance(data, dict) and data.get("type") == "file":
            result["error"] = f"Path '{path}' points to a file, not a directory. Use repo_file_info() or repo_read_file() to access this file."
            return result
        
        # Process directory contents
        for item in data:
            item_info = {
                "name": item["name"],
                "type": "file" if item["type"] == "file" else "dir",
                "path": item["path"]
            }
            
            if item["type"] == "file":
                item_info["size"] = item.get("size", 0)
            else:
                # For directories, we could make another API call to count items
                # but that would be expensive, so we'll skip it
                item_info["item_count"] = None
            
            result["items"].append(item_info)
        
        result["total_items"] = len(result["items"])
        
        # Sort items: directories first, then files, both alphabetically
        result["items"].sort(key=lambda x: (x["type"] == "file", x["name"].lower()))
        
    except requests.exceptions.RequestException as e:
        result["error"] = f"Network error accessing GitHub API: {str(e)}"
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
    
    return result


@mcp.tool()
def repo_tree_view(
    owner: str = Field(description="Repository owner/organization name"),
    repo: str = Field(description="Repository name"),
    path: str = Field(default="", description="Starting directory path (default: root)"),
    max_depth: int = Field(default=3, description="Maximum recursion depth (default: 3)")
) -> Dict[str, Any]:
    """Get recursive directory tree view."""
    
    result = {
        "owner": owner,
        "repo": repo,
        "tree": None,
        "truncated": False,
        "max_depth": max_depth,
        "error": None
    }
    
    def build_tree(current_path: str, current_depth: int) -> Optional[Dict[str, Any]]:
        """Recursively build directory tree."""
        if current_depth > max_depth:
            result["truncated"] = True
            return None
        
        # Get directory listing
        list_result = repo_list_directory(owner, repo, current_path)
        
        if list_result["error"]:
            return None
        
        tree_node = {
            "name": os.path.basename(current_path) or repo,
            "type": "directory",
            "path": current_path,
            "children": []
        }
        
        for item in list_result["items"]:
            if item["type"] == "dir" and current_depth < max_depth:
                child_tree = build_tree(item["path"], current_depth + 1)
                if child_tree:
                    tree_node["children"].append(child_tree)
                elif current_depth + 1 > max_depth:
                    # Add truncated directory indicator
                    tree_node["children"].append({
                        "name": item["name"],
                        "type": "directory",
                        "path": item["path"],
                        "children": ["...truncated..."]
                    })
            else:
                # Add file info
                file_node = {
                    "name": item["name"],
                    "type": "file",
                    "path": item["path"]
                }
                if "size" in item:
                    file_node["size"] = item["size"]
                tree_node["children"].append(file_node)
        
        return tree_node
    
    try:
        result["tree"] = build_tree(path, 1)
        if not result["tree"]:
            result["error"] = f"Could not build tree for {owner}/{repo} starting at path '{path}'"
    
    except Exception as e:
        result["error"] = f"Unexpected error building tree: {str(e)}"
    
    return result


@mcp.tool()
def repo_file_info(
    owner: str = Field(description="Repository owner/organization name"),
    repo: str = Field(description="Repository name"),
    path: str = Field(description="File path within repository")
) -> Dict[str, Any]:
    """Get metadata about a file without reading its contents."""
    
    result = {
        "owner": owner,
        "repo": repo,
        "path": path,
        "exists": False,
        "size": 0,
        "encoding": None,
        "is_binary": False,
        "estimated_tokens": 0,
        "line_count_estimate": 0,
        "last_modified": None,
        "download_url": None,
        "error": None
    }
    
    try:
        # Construct API URL
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        headers = get_github_headers()
        
        response = requests.get(url, headers=headers, timeout=30)
        
        # Handle rate limiting
        if response.status_code == 403 and "rate limit" in response.text.lower():
            result["error"] = "GitHub API rate limit exceeded. Consider setting GITHUB_TOKEN environment variable for higher limits."
            return result
        
        # Handle not found
        if response.status_code == 404:
            result["error"] = f"File {path} not found in {owner}/{repo}. Use repo_list_directory() to explore available files."
            return result
        
        response.raise_for_status()
        data = response.json()
        
        # Handle directory response
        if isinstance(data, list):
            result["error"] = f"Path '{path}' is a directory, not a file. Use repo_list_directory() to list its contents."
            return result
        
        if data.get("type") != "file":
            result["error"] = f"Path '{path}' is not a file."
            return result
        
        # Extract file information
        result["exists"] = True
        result["size"] = data.get("size", 0)
        result["download_url"] = data.get("download_url")
        
        # Check if binary
        filename = os.path.basename(path)
        result["is_binary"] = is_binary_file(filename=filename)
        
        if not result["is_binary"]:
            # Estimate encoding
            result["encoding"] = "utf-8"  # GitHub API typically returns UTF-8
            
            # Estimate line count (rough approximation)
            if result["size"] > 0:
                result["line_count_estimate"] = max(1, result["size"] // 50)  # ~50 chars per line average
                
                # Estimate tokens (rough approximation for text files)
                result["estimated_tokens"] = count_tokens("x" * min(result["size"], 1000))  # Sample estimation
                if result["size"] > 1000:
                    result["estimated_tokens"] = int(result["estimated_tokens"] * (result["size"] / 1000))
        
        # Get commit info for last modified (requires additional API call)
        try:
            commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
            commits_params = {"path": path, "per_page": 1}
            commits_response = requests.get(commits_url, headers=headers, params=commits_params, timeout=30)
            
            if commits_response.status_code == 200:
                commits_data = commits_response.json()
                if commits_data:
                    result["last_modified"] = commits_data[0]["commit"]["committer"]["date"]
        except Exception:
            # If we can't get commit info, that's okay
            pass
        
    except requests.exceptions.RequestException as e:
        result["error"] = f"Network error accessing GitHub API: {str(e)}"
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
    
    return result


@mcp.tool()
def repo_read_file(
    owner: str = Field(description="Repository owner/organization name"),
    repo: str = Field(description="Repository name"),
    path: str = Field(description="File path within repository"),
    start_line: int = Field(default=1, description="Starting line number (1-indexed, default: 1)"),
    num_lines: int = Field(default=200, description="Number of lines to read (default: 200)"),
    no_token_limit: bool = Field(default=False, description="Override 5,000 token safety limit (default: False)")
) -> Dict[str, Any]:
    """Read file contents with intelligent token-based safety limits."""
    
    result = {
        "owner": owner,
        "repo": repo,
        "path": path,
        "content": "",
        "start_line": start_line,
        "end_line": 0,
        "lines_read": 0,
        "total_lines": 0,
        "tokens_used": 0,
        "truncated_due_to_tokens": False,
        "continuation_start_line": None,
        "encoding": "utf-8",
        "error": None
    }
    
    try:
        # First get file info to check if it's binary
        file_info = repo_file_info(owner, repo, path)
        
        if file_info["error"]:
            result["error"] = file_info["error"]
            return result
        
        if file_info["is_binary"]:
            result["error"] = "Cannot read binary file. Use repo_file_info() to get metadata about this file."
            return result
        
        # Get the file content from GitHub API
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        headers = get_github_headers()
        
        response = requests.get(url, headers=headers, timeout=30)
        
        # Handle rate limiting
        if response.status_code == 403 and "rate limit" in response.text.lower():
            result["error"] = "GitHub API rate limit exceeded. Consider setting GITHUB_TOKEN environment variable for higher limits."
            return result
        
        response.raise_for_status()
        data = response.json()
        
        # Decode content
        if data.get("encoding") == "base64":
            try:
                content_bytes = base64.b64decode(data["content"])
                full_content = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    full_content = content_bytes.decode("latin-1")
                    result["encoding"] = "latin-1"
                except UnicodeDecodeError:
                    result["error"] = "Could not decode file content. File may be binary or use unsupported encoding."
                    return result
        else:
            result["error"] = f"Unexpected content encoding: {data.get('encoding')}"
            return result
        
        # Split into lines
        all_lines = full_content.splitlines()
        result["total_lines"] = len(all_lines)
        
        # Validate start_line
        if start_line < 1:
            start_line = 1
        if start_line > result["total_lines"]:
            result["error"] = f"Start line {start_line} exceeds file length ({result['total_lines']} lines)"
            return result
        
        # Calculate end line
        end_line = min(start_line + num_lines - 1, result["total_lines"])
        
        # Extract requested lines (convert to 0-indexed for slicing)
        selected_lines = all_lines[start_line - 1:end_line]
        
        # Join lines and check token count
        content = "\n".join(selected_lines)
        result["tokens_used"] = count_tokens(content)
        
        # Apply token safety limit
        if not no_token_limit and result["tokens_used"] > 5000:
            # Binary search to find the maximum lines that fit within token limit
            low, high = 1, len(selected_lines)
            best_lines = []
            
            while low <= high:
                mid = (low + high) // 2
                test_content = "\n".join(selected_lines[:mid])
                test_tokens = count_tokens(test_content)
                
                if test_tokens <= 5000:
                    best_lines = selected_lines[:mid]
                    low = mid + 1
                else:
                    high = mid - 1
            
            if best_lines:
                content = "\n".join(best_lines)
                result["tokens_used"] = count_tokens(content)
                result["truncated_due_to_tokens"] = True
                result["end_line"] = start_line + len(best_lines) - 1
                result["continuation_start_line"] = start_line + len(best_lines)
                result["message"] = f"Output truncated at 5,000 tokens. Use no_token_limit=True to read without limit, or continue from line {result['continuation_start_line']}."
            else:
                result["error"] = "File content would exceed 5,000 tokens. Try reading fewer lines with num_lines parameter, or use no_token_limit=True."
                return result
        else:
            result["end_line"] = end_line
            if end_line < result["total_lines"]:
                result["continuation_start_line"] = end_line + 1
        
        result["content"] = content
        result["start_line"] = start_line
        result["lines_read"] = len(selected_lines) if not result["truncated_due_to_tokens"] else len(best_lines)
        
    except requests.exceptions.RequestException as e:
        result["error"] = f"Network error accessing GitHub API: {str(e)}"
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
    
    return result


if __name__ == "__main__":
    mcp.run()
