#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastmcp",
#     "pydantic",
#     "GitPython"
# ]
# ///

"""
# GitHub Repository Cloning MCP Server

A single-file Python MCP server that clones GitHub repositories locally and provides filesystem-like
navigation through an API. This server eliminates GitHub API rate limits and provides faster access
by working with local clones while managing storage automatically.

## Core Philosophy
- **Filesystem-like Experience**: Use familiar Read/Grep/Glob-style tools on cloned repositories
- **Automatic Management**: Clone repositories on-demand and clean up automatically
- **Performance First**: Local file access eliminates API rate limits and latency
- **Transparent Operation**: Claude doesn't need to know about local storage details

## Claude Configuration

Sample configuration:

```json
{
  "mcpServers": {
    "github-clone": {
      "command": "/Users/Joshua/.local/bin/uv",
      "args": [
        "run",
        "--script",
        "/Users/Joshua/Documents/_programming/simple-mcp-servers/github_clone_mcp.py"
      ]
    }
  }
}
```

## Claude Code Setup

Add to Claude Code with:
```bash
claude mcp add github-clone /Users/Joshua/Documents/_programming/simple-mcp-servers/github_clone_mcp.py
```

## Tools Provided

- `clone_repo`: Clone or verify a repository is available locally
- `repo_read`: Read file contents (equivalent to Read tool)
- `repo_grep`: Search for patterns in repository files (equivalent to Grep tool)
- `repo_glob`: Find files matching patterns (equivalent to Glob tool)
- `repo_status`: Check repository clone status and metadata

## Usage Examples

```python
# Clone a repository
status = clone_repo("https://github.com/microsoft/vscode")

# Read a file
content = repo_read("https://github.com/microsoft/vscode", "package.json")

# Search for patterns
matches = repo_grep("https://github.com/microsoft/vscode", "electron", include="*.json")

# Find files
files = repo_glob("https://github.com/microsoft/vscode", "*.md")

# Check status
info = repo_status("https://github.com/microsoft/vscode")
```

## Features

- **Automatic Cloning**: Repositories are cloned on first access
- **Shallow Clones**: Uses `--depth=1` for faster cloning
- **Smart Storage**: Stores repositories in `~/Library/Application Support/ClaudeMCP/github-repos/`
- **Automatic Cleanup**: Removes repositories after 48 hours of inactivity
- **Async Status**: Large repositories show "still cloning" status
- **Error Recovery**: Handles network failures and invalid repositories

## Storage Management

- **Location**: `~/Library/Application Support/ClaudeMCP/github-repos/`
- **Naming**: `{owner}_{repo}_{hash}/` (collision-safe)
- **Metadata**: `.mcp_metadata.json` tracks last access time
- **Cleanup**: Automatic removal of unused repositories

## Implementation Roadmap

- [x] Research and design phase
- [x] Core cloning infrastructure
- [x] Basic file reading (repo_read)
- [x] Search capabilities (repo_grep, repo_glob)
- [x] Automatic cleanup and management
- [ ] Background cloning for large repos
- [ ] Performance optimization

## Dependencies

- fastmcp: MCP server framework
- pydantic: Type validation and field descriptions
- GitPython: Git operations and repository management
"""

import os
import re
import sys
import json
import time
import hashlib
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from urllib.parse import urlparse
from fastmcp import FastMCP
from pydantic import Field
import git
from git import Repo, GitCommandError


# Create server
mcp = FastMCP("github-clone")


class RepositoryManager:
    """Manages local repository storage and cloning operations."""
    
    def __init__(self):
        self.base_path = Path.home() / "Library" / "Application Support" / "ClaudeMCP" / "github-repos"
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.cloning_repos = set()  # Track repositories currently being cloned
        self.clone_lock = threading.Lock()
    
    def parse_repo_url(self, repo_url: str) -> Optional[Dict[str, str]]:
        """Parse GitHub repository URL to extract owner and repo name."""
        # Handle shorthand format (owner/repo)
        if "/" in repo_url and "://" not in repo_url:
            parts = repo_url.split("/", 1)
            if len(parts) == 2:
                return {"owner": parts[0], "repo": parts[1]}
        
        # Parse full URLs
        try:
            parsed = urlparse(repo_url)
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
                
            return {"owner": owner, "repo": repo}
            
        except Exception:
            return None
    
    def get_repo_path(self, repo_url: str) -> Optional[Path]:
        """Get the local path for a repository."""
        parsed = self.parse_repo_url(repo_url)
        if not parsed:
            return None
        
        # Create collision-safe directory name
        repo_id = f"{parsed['owner']}_{parsed['repo']}"
        url_hash = hashlib.md5(repo_url.encode()).hexdigest()[:8]
        repo_dir = f"{repo_id}_{url_hash}"
        
        return self.base_path / repo_dir
    
    def get_metadata_path(self, repo_path: Path) -> Path:
        """Get metadata file path for a repository."""
        return repo_path / ".mcp_metadata.json"
    
    def update_last_access(self, repo_path: Path):
        """Update the last access time for a repository."""
        metadata_path = self.get_metadata_path(repo_path)
        metadata = {
            "last_access": time.time(),
            "created": time.time()
        }
        
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r') as f:
                    existing = json.load(f)
                    metadata["created"] = existing.get("created", time.time())
            except Exception:
                pass
        
        try:
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f)
        except Exception:
            pass
    
    def is_repo_cloned(self, repo_path: Path) -> bool:
        """Check if a repository is already cloned and valid."""
        if not repo_path.exists():
            return False
        
        git_dir = repo_path / ".git"
        if not git_dir.exists():
            return False
        
        try:
            # Verify it's a valid git repository
            repo = Repo(str(repo_path))
            return True
        except Exception:
            return False
    
    def clone_repository(self, repo_url: str, repo_path: Path) -> Dict[str, Any]:
        """Clone a repository to the local path."""
        result = {
            "success": False,
            "error": None,
            "status": "failed"
        }
        
        try:
            # Mark as cloning
            with self.clone_lock:
                self.cloning_repos.add(str(repo_path))
            
            # Ensure parent directory exists
            repo_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert shorthand to full URL if needed
            clone_url = repo_url
            if not repo_url.startswith(('http://', 'https://')):
                clone_url = f"https://github.com/{repo_url}"
            
            # Clone with shallow depth for speed
            repo = Repo.clone_from(
                clone_url,
                str(repo_path),
                depth=1,
                single_branch=True
            )
            
            # Update metadata
            self.update_last_access(repo_path)
            
            result["success"] = True
            result["status"] = "completed"
            
        except GitCommandError as e:
            result["error"] = f"Git error: {str(e)}"
            result["status"] = "failed"
            
            # Clean up partial clone
            if repo_path.exists():
                import shutil
                shutil.rmtree(str(repo_path), ignore_errors=True)
                
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            result["status"] = "failed"
            
            # Clean up partial clone
            if repo_path.exists():
                import shutil
                shutil.rmtree(str(repo_path), ignore_errors=True)
        
        finally:
            # Remove from cloning set
            with self.clone_lock:
                self.cloning_repos.discard(str(repo_path))
        
        return result
    
    def is_cloning(self, repo_path: Path) -> bool:
        """Check if a repository is currently being cloned."""
        with self.clone_lock:
            return str(repo_path) in self.cloning_repos
    
    def cleanup_old_repositories(self, max_age_hours: int = 48):
        """Remove repositories that haven't been accessed recently."""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        for repo_dir in self.base_path.iterdir():
            if not repo_dir.is_dir():
                continue
            
            metadata_path = self.get_metadata_path(repo_dir)
            if not metadata_path.exists():
                continue
            
            try:
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                last_access = metadata.get("last_access", 0)
                if current_time - last_access > max_age_seconds:
                    import shutil
                    shutil.rmtree(str(repo_dir), ignore_errors=True)
                    
            except Exception:
                continue


# Global repository manager
repo_manager = RepositoryManager()


@mcp.tool()
def clone_repo(
    repo_url: str = Field(description="GitHub repository URL (e.g., 'https://github.com/owner/repo' or 'owner/repo')")
) -> Dict[str, Any]:
    """Clone or verify a repository is available locally."""
    
    result = {
        "repo_url": repo_url,
        "status": "unknown",
        "local_path": None,
        "error": None
    }
    
    try:
        # Parse repository URL
        parsed = repo_manager.parse_repo_url(repo_url)
        if not parsed:
            result["error"] = "Invalid repository URL. Use format 'owner/repo' or 'https://github.com/owner/repo'"
            result["status"] = "error"
            return result
        
        # Get local path
        repo_path = repo_manager.get_repo_path(repo_url)
        if not repo_path:
            result["error"] = "Failed to determine local path for repository"
            result["status"] = "error"
            return result
        
        result["local_path"] = str(repo_path)
        
        # Check if already cloned
        if repo_manager.is_repo_cloned(repo_path):
            repo_manager.update_last_access(repo_path)
            result["status"] = "available"
            return result
        
        # Check if currently cloning
        if repo_manager.is_cloning(repo_path):
            result["status"] = "cloning"
            return result
        
        # Start cloning
        result["status"] = "cloning"
        
        # Clone in background for now (simplified approach)
        clone_result = repo_manager.clone_repository(repo_url, repo_path)
        
        if clone_result["success"]:
            result["status"] = "available"
        else:
            result["error"] = clone_result["error"]
            result["status"] = "failed"
        
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
        result["status"] = "error"
    
    return result


@mcp.tool()
def repo_read(
    repo_url: str = Field(description="GitHub repository URL"),
    file_path: str = Field(description="Path to file within repository"),
    start_line: int = Field(default=1, description="Starting line number (1-indexed)"),
    num_lines: Optional[int] = Field(default=None, description="Number of lines to read (None for all)")
) -> Dict[str, Any]:
    """Read file contents from a cloned repository (equivalent to Read tool)."""
    
    result = {
        "repo_url": repo_url,
        "file_path": file_path,
        "content": "",
        "start_line": start_line,
        "end_line": 0,
        "total_lines": 0,
        "error": None
    }
    
    try:
        # Get repository path
        repo_path = repo_manager.get_repo_path(repo_url)
        if not repo_path:
            result["error"] = "Invalid repository URL"
            return result
        
        # Check if repository is available
        if not repo_manager.is_repo_cloned(repo_path):
            if repo_manager.is_cloning(repo_path):
                result["error"] = "Repository is still cloning. Please try again in a moment."
                return result
            else:
                result["error"] = "Repository not cloned. Use clone_repo() first."
                return result
        
        # Update last access
        repo_manager.update_last_access(repo_path)
        
        # Read file
        full_file_path = repo_path / file_path
        if not full_file_path.exists():
            result["error"] = f"File '{file_path}' not found in repository"
            return result
        
        if not full_file_path.is_file():
            result["error"] = f"Path '{file_path}' is not a file"
            return result
        
        # Read file content
        try:
            with open(full_file_path, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
        except UnicodeDecodeError:
            try:
                with open(full_file_path, 'r', encoding='latin-1') as f:
                    all_lines = f.readlines()
            except Exception:
                result["error"] = "Could not decode file content"
                return result
        
        result["total_lines"] = len(all_lines)
        
        # Validate start_line
        if start_line < 1:
            start_line = 1
        if start_line > result["total_lines"]:
            result["error"] = f"Start line {start_line} exceeds file length ({result['total_lines']} lines)"
            return result
        
        # Calculate end line
        if num_lines is None:
            end_line = result["total_lines"]
        else:
            end_line = min(start_line + num_lines - 1, result["total_lines"])
        
        # Extract requested lines
        selected_lines = all_lines[start_line - 1:end_line]
        result["content"] = "".join(selected_lines)
        result["start_line"] = start_line
        result["end_line"] = end_line
        
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
    
    return result


@mcp.tool()
def repo_grep(
    repo_url: str = Field(description="GitHub repository URL"),
    pattern: str = Field(description="Regular expression pattern to search for"),
    include: Optional[str] = Field(default=None, description="File pattern to include (e.g., '*.py', '*.{js,ts}')"),
    path: Optional[str] = Field(default=None, description="Directory path within repo to search (default: root)")
) -> Dict[str, Any]:
    """Search for patterns in repository files (equivalent to Grep tool)."""
    
    result = {
        "repo_url": repo_url,
        "pattern": pattern,
        "matches": [],
        "total_matches": 0,
        "files_searched": 0,
        "error": None
    }
    
    try:
        # Get repository path
        repo_path = repo_manager.get_repo_path(repo_url)
        if not repo_path:
            result["error"] = "Invalid repository URL"
            return result
        
        # Check if repository is available
        if not repo_manager.is_repo_cloned(repo_path):
            if repo_manager.is_cloning(repo_path):
                result["error"] = "Repository is still cloning. Please try again in a moment."
                return result
            else:
                result["error"] = "Repository not cloned. Use clone_repo() first."
                return result
        
        # Update last access
        repo_manager.update_last_access(repo_path)
        
        # Determine search path
        search_path = repo_path
        if path:
            search_path = repo_path / path
            if not search_path.exists():
                result["error"] = f"Path '{path}' not found in repository"
                return result
        
        # Compile regex pattern
        try:
            regex = re.compile(pattern)
        except re.error as e:
            result["error"] = f"Invalid regex pattern: {str(e)}"
            return result
        
        # Search files
        for file_path in search_path.rglob("*"):
            if not file_path.is_file():
                continue
            
            # Skip hidden files and directories
            if any(part.startswith('.') for part in file_path.parts):
                continue
            
            # Apply include filter
            if include:
                import fnmatch
                relative_path = file_path.relative_to(repo_path)
                if not fnmatch.fnmatch(str(relative_path), include):
                    continue
            
            # Skip binary files
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except (UnicodeDecodeError, PermissionError):
                continue
            
            result["files_searched"] += 1
            
            # Search for pattern
            lines = content.splitlines()
            for line_num, line in enumerate(lines, 1):
                if regex.search(line):
                    relative_path = file_path.relative_to(repo_path)
                    result["matches"].append({
                        "file": str(relative_path),
                        "line": line_num,
                        "content": line.strip(),
                        "match": regex.search(line).group(0)
                    })
                    result["total_matches"] += 1
    
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
    
    return result


@mcp.tool()
def repo_glob(
    repo_url: str = Field(description="GitHub repository URL"),
    pattern: str = Field(description="Glob pattern to match files (e.g., '*.py', '**/*.js')"),
    path: Optional[str] = Field(default=None, description="Directory path within repo to search (default: root)")
) -> Dict[str, Any]:
    """Find files matching patterns in repository (equivalent to Glob tool)."""
    
    result = {
        "repo_url": repo_url,
        "pattern": pattern,
        "files": [],
        "total_files": 0,
        "error": None
    }
    
    try:
        # Get repository path
        repo_path = repo_manager.get_repo_path(repo_url)
        if not repo_path:
            result["error"] = "Invalid repository URL"
            return result
        
        # Check if repository is available
        if not repo_manager.is_repo_cloned(repo_path):
            if repo_manager.is_cloning(repo_path):
                result["error"] = "Repository is still cloning. Please try again in a moment."
                return result
            else:
                result["error"] = "Repository not cloned. Use clone_repo() first."
                return result
        
        # Update last access
        repo_manager.update_last_access(repo_path)
        
        # Determine search path
        search_path = repo_path
        if path:
            search_path = repo_path / path
            if not search_path.exists():
                result["error"] = f"Path '{path}' not found in repository"
                return result
        
        # Find matching files
        try:
            if pattern.startswith("**/"):
                # Recursive pattern
                matches = search_path.rglob(pattern[3:])
            else:
                # Non-recursive pattern
                matches = search_path.glob(pattern)
            
            for match in matches:
                if match.is_file():
                    # Skip hidden files
                    if any(part.startswith('.') for part in match.parts):
                        continue
                    
                    relative_path = match.relative_to(repo_path)
                    file_info = {
                        "path": str(relative_path),
                        "size": match.stat().st_size,
                        "modified": match.stat().st_mtime
                    }
                    result["files"].append(file_info)
                    result["total_files"] += 1
            
            # Sort by path
            result["files"].sort(key=lambda x: x["path"])
            
        except Exception as e:
            result["error"] = f"Error matching pattern: {str(e)}"
    
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
    
    return result


@mcp.tool()
def repo_status(
    repo_url: str = Field(description="GitHub repository URL")
) -> Dict[str, Any]:
    """Check repository clone status and metadata."""
    
    result = {
        "repo_url": repo_url,
        "status": "unknown",
        "local_path": None,
        "cloned": False,
        "cloning": False,
        "metadata": {},
        "error": None
    }
    
    try:
        # Parse repository URL
        parsed = repo_manager.parse_repo_url(repo_url)
        if not parsed:
            result["error"] = "Invalid repository URL"
            return result
        
        # Get local path
        repo_path = repo_manager.get_repo_path(repo_url)
        if not repo_path:
            result["error"] = "Failed to determine local path for repository"
            return result
        
        result["local_path"] = str(repo_path)
        
        # Check status
        result["cloned"] = repo_manager.is_repo_cloned(repo_path)
        result["cloning"] = repo_manager.is_cloning(repo_path)
        
        if result["cloned"]:
            result["status"] = "available"
            repo_manager.update_last_access(repo_path)
        elif result["cloning"]:
            result["status"] = "cloning"
        else:
            result["status"] = "not_cloned"
        
        # Get metadata if available
        metadata_path = repo_manager.get_metadata_path(repo_path)
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r') as f:
                    result["metadata"] = json.load(f)
            except Exception:
                pass
        
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
    
    return result


if __name__ == "__main__":
    # Clean up old repositories on startup
    repo_manager.cleanup_old_repositories()
    mcp.run()