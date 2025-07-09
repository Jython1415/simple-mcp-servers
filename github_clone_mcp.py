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

- `repo_read`: Read file contents (equivalent to Read tool)
- `repo_grep`: Search for patterns in repository files (equivalent to Grep tool)
- `repo_glob`: Find files matching patterns (equivalent to Glob tool)
- `repo_status`: Check repository clone status and metadata

## Usage Examples

```python
# Read a file (automatically clones if needed)
content = repo_read("https://github.com/microsoft/vscode", "package.json")

# Search for patterns (automatically clones if needed)
matches = repo_grep("https://github.com/microsoft/vscode", "electron", include="*.json")

# Find files (automatically clones if needed)
files = repo_glob("https://github.com/microsoft/vscode", "*.md")

# Check status and metadata
info = repo_status("https://github.com/microsoft/vscode")
```

## Features

- **Seamless Access**: Repositories are automatically cloned on first access to any file operation
- **Smart Updates**: Automatically updates outdated repositories using `git pull` or full re-clone
- **Storage Management**: Environment-based storage limits with automatic cleanup of oldest repositories
- **Shallow Clones**: Uses `--depth=1` for faster cloning
- **Smart Storage**: Stores repositories in `~/Library/Application Support/ClaudeMCP/github-repos/`
- **Automatic Cleanup**: Removes repositories after 48 hours of inactivity or when storage limit reached
- **Async Status**: Large repositories show "still cloning" status
- **Error Recovery**: Handles network failures and invalid repositories

## Storage Management

- **Location**: `~/Library/Application Support/ClaudeMCP/github-repos/`
- **Naming**: `{owner}_{repo}_{hash}/` (collision-safe)
- **Metadata**: `.mcp_metadata.json` tracks last access time
- **Cleanup**: Automatic removal of unused repositories

## Implementation Roadmap

### Completed Features
- [x] Research and design phase
- [x] Core cloning infrastructure
- [x] Basic file reading (repo_read)
- [x] Search capabilities (repo_grep, repo_glob)
- [x] Automatic cleanup and management
- [x] API revamp: abstract away the need to "clone" a repository, and simplify treat it as if it were performing local file operations on a remote repository
- [x] If a cloned repository is outdated, automatically update the clone
- [x] Add a configuration option for the amount of storage dedicated to the server

### Phase 2: Timeout Handling (Future Enhancement)
- [ ] **Add clone progress tracking and status reporting**: Main priority for handling when clone operations take longer than MCP timeout period
- [ ] **Prevent duplicate work**: Ensure 2 simultaneous clone operations don't repeat work  
- [ ] **Return partial results**: Show "X% done in Y seconds" when possible during long operations
- [ ] **Flexible implementation**: Focus on progress tracking over specific timeout mechanisms

### Technical Notes
- **Environment Configuration**: `GITHUB_CLONE_MAX_STORAGE_GB` controls storage limits
- **Smart Updates**: Attempts `git pull` first, falls back to re-clone if needed
- **Automatic Cleanup**: Removes oldest (last accessed) repositories when storage limit reached
- **Seamless Experience**: All tools automatically clone repositories without explicit `clone_repo` calls

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
            "created": time.time(),
            "last_updated": time.time()
        }
        
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r') as f:
                    existing = json.load(f)
                    metadata["created"] = existing.get("created", time.time())
                    metadata["last_updated"] = existing.get("last_updated", time.time())
            except Exception:
                pass
        
        try:
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f)
        except Exception:
            pass
    
    def update_last_updated(self, repo_path: Path):
        """Update the last updated time for a repository."""
        metadata_path = self.get_metadata_path(repo_path)
        metadata = {
            "last_access": time.time(),
            "created": time.time(),
            "last_updated": time.time()
        }
        
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r') as f:
                    existing = json.load(f)
                    metadata["created"] = existing.get("created", time.time())
                    metadata["last_access"] = existing.get("last_access", time.time())
            except Exception:
                pass
        
        try:
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f)
        except Exception:
            pass
    
    def is_repo_outdated(self, repo_path: Path, max_age_hours: int = 24) -> bool:
        """Check if a repository is outdated based on last update time."""
        metadata_path = self.get_metadata_path(repo_path)
        if not metadata_path.exists():
            return True
        
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            last_updated = metadata.get("last_updated", 0)
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            return current_time - last_updated > max_age_seconds
        except Exception:
            return True
    
    def update_repository(self, repo_url: str, repo_path: Path) -> Dict[str, Any]:
        """Update an existing repository, trying git pull first, then fallback to re-clone."""
        result = {
            "success": False,
            "error": None,
            "status": "failed",
            "method": None
        }
        
        try:
            # Try git pull first
            repo = Repo(str(repo_path))
            origin = repo.remotes.origin
            origin.pull()
            
            # Update metadata
            self.update_last_updated(repo_path)
            
            result["success"] = True
            result["status"] = "updated"
            result["method"] = "git_pull"
            
        except Exception as e:
            # Git pull failed, try full re-clone
            try:
                # Remove existing repository
                import shutil
                shutil.rmtree(str(repo_path), ignore_errors=True)
                
                # Re-clone
                clone_result = self.clone_repository(repo_url, repo_path)
                
                result["success"] = clone_result["success"]
                result["error"] = clone_result["error"]
                result["status"] = clone_result["status"]
                result["method"] = "re_clone"
                
            except Exception as e2:
                result["error"] = f"Both git pull and re-clone failed: {str(e)}, {str(e2)}"
                result["status"] = "failed"
                result["method"] = "both_failed"
        
        return result
    
    def get_storage_usage_gb(self) -> float:
        """Calculate current storage usage in GB."""
        total_size = 0
        for repo_dir in self.base_path.iterdir():
            if repo_dir.is_dir():
                for file_path in repo_dir.rglob("*"):
                    if file_path.is_file():
                        try:
                            total_size += file_path.stat().st_size
                        except (OSError, FileNotFoundError):
                            continue
        return total_size / (1024 ** 3)  # Convert to GB
    
    def get_storage_limit_gb(self) -> Optional[float]:
        """Get storage limit from environment variable."""
        limit_str = os.environ.get("GITHUB_CLONE_MAX_STORAGE_GB")
        if limit_str:
            try:
                return float(limit_str)
            except ValueError:
                return None
        return None
    
    def get_repo_sizes(self) -> List[Dict[str, Any]]:
        """Get list of repositories with their sizes and metadata."""
        repos = []
        for repo_dir in self.base_path.iterdir():
            if not repo_dir.is_dir():
                continue
            
            repo_size = 0
            for file_path in repo_dir.rglob("*"):
                if file_path.is_file():
                    try:
                        repo_size += file_path.stat().st_size
                    except (OSError, FileNotFoundError):
                        continue
            
            # Get metadata
            metadata_path = self.get_metadata_path(repo_dir)
            last_access = 0
            if metadata_path.exists():
                try:
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                        last_access = metadata.get("last_access", 0)
                except Exception:
                    pass
            
            repos.append({
                "path": repo_dir,
                "name": repo_dir.name,
                "size_bytes": repo_size,
                "size_gb": repo_size / (1024 ** 3),
                "last_access": last_access
            })
        
        return repos
    
    def cleanup_for_space(self, required_space_gb: float) -> bool:
        """Remove oldest repositories to free up space."""
        limit_gb = self.get_storage_limit_gb()
        if not limit_gb:
            return True  # No storage limit set
        
        current_usage = self.get_storage_usage_gb()
        if current_usage + required_space_gb <= limit_gb:
            return True  # Enough space available
        
        # Get repositories sorted by last access time (oldest first)
        repos = self.get_repo_sizes()
        repos.sort(key=lambda x: x["last_access"])
        
        space_to_free = (current_usage + required_space_gb) - limit_gb
        space_freed = 0
        
        for repo in repos:
            if space_freed >= space_to_free:
                break
            
            try:
                import shutil
                shutil.rmtree(str(repo["path"]), ignore_errors=True)
                space_freed += repo["size_gb"]
            except Exception:
                continue
        
        return space_freed >= space_to_free
    
    def check_storage_before_clone(self, estimated_size_gb: float = 0.1) -> Dict[str, Any]:
        """Check if there's enough storage space before cloning."""
        result = {
            "has_space": True,
            "current_usage_gb": 0,
            "storage_limit_gb": None,
            "estimated_size_gb": estimated_size_gb,
            "cleanup_performed": False,
            "error": None
        }
        
        limit_gb = self.get_storage_limit_gb()
        if not limit_gb:
            result["storage_limit_gb"] = None
            return result  # No storage limit set
        
        current_usage = self.get_storage_usage_gb()
        result["current_usage_gb"] = current_usage
        result["storage_limit_gb"] = limit_gb
        
        if current_usage + estimated_size_gb <= limit_gb:
            result["has_space"] = True
            return result
        
        # Try to free up space
        cleanup_success = self.cleanup_for_space(estimated_size_gb)
        result["cleanup_performed"] = True
        
        if cleanup_success:
            result["has_space"] = True
        else:
            result["has_space"] = False
            result["error"] = f"Insufficient storage space. Need {estimated_size_gb:.2f}GB, limit is {limit_gb:.2f}GB"
        
        return result
    
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
            self.update_last_updated(repo_path)
            
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
    
    def _ensure_repo_available(self, repo_url: str, force_update: bool = False) -> Dict[str, Any]:
        """Ensure repository is available locally, cloning if necessary."""
        result = {
            "success": False,
            "status": "unknown",
            "error": None,
            "action": None
        }
        
        try:
            # Parse repository URL
            parsed = self.parse_repo_url(repo_url)
            if not parsed:
                result["error"] = "Invalid repository URL. Use format 'owner/repo' or 'https://github.com/owner/repo'"
                return result
            
            # Get local path
            repo_path = self.get_repo_path(repo_url)
            if not repo_path:
                result["error"] = "Failed to determine local path for repository"
                return result
            
            # Check if repository is already cloned and valid
            if self.is_repo_cloned(repo_path):
                # Check if repository is outdated (unless force_update is True)
                if not force_update and not self.is_repo_outdated(repo_path):
                    self.update_last_access(repo_path)
                    result["success"] = True
                    result["status"] = "available"
                    result["action"] = "accessed"
                    return result
                elif not force_update:
                    # Repository is outdated, trigger update
                    force_update = True
                    result["action"] = "auto_updating"
            
            # Check if currently cloning
            if self.is_cloning(repo_path):
                result["error"] = "Repository is still cloning. Please try again in a moment."
                result["status"] = "cloning"
                return result
            
            # Clone or update repository
            if force_update and self.is_repo_cloned(repo_path):
                # Repository exists and needs updating
                update_result = self.update_repository(repo_url, repo_path)
                
                if update_result["success"]:
                    result["success"] = True
                    result["status"] = "available"
                    result["action"] = f"updated_via_{update_result['method']}"
                else:
                    result["error"] = update_result["error"]
                    result["status"] = "failed"
            else:
                # Repository doesn't exist, clone it
                result["action"] = "cloning"
                
                # Check storage before cloning
                storage_check = self.check_storage_before_clone()
                if not storage_check["has_space"]:
                    result["error"] = storage_check["error"]
                    result["status"] = "failed"
                    return result
                
                clone_result = self.clone_repository(repo_url, repo_path)
                
                if clone_result["success"]:
                    result["success"] = True
                    result["status"] = "available"
                else:
                    result["error"] = clone_result["error"]
                    result["status"] = "failed"
                
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            result["status"] = "error"
        
        return result
    
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
def repo_read(
    repo_url: str = Field(description="GitHub repository URL"),
    file_path: str = Field(description="Path to file within repository"),
    start_line: str = Field(default="1", description="Starting line number (1-indexed)"),
    num_lines: Optional[str] = Field(default=None, description="Number of lines to read (None for all)"),
    force_update: bool = Field(default=False, description="Force update repository before reading")
) -> Dict[str, Any]:
    """Read file contents from a repository (automatically clones if needed)."""
    
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
        # Type coercion for parameters that might come as strings
        if isinstance(start_line, str):
            try:
                start_line = int(start_line)
            except ValueError:
                result["error"] = f"Invalid start_line value: '{start_line}' must be a number"
                return result
        
        if isinstance(num_lines, str):
            try:
                num_lines = int(num_lines) if num_lines.strip() else None
            except ValueError:
                result["error"] = f"Invalid num_lines value: '{num_lines}' must be a number"
                return result
        
        # Update result with coerced values
        result["start_line"] = start_line
        
        # Ensure repository is available
        ensure_result = repo_manager._ensure_repo_available(repo_url, force_update)
        if not ensure_result["success"]:
            result["error"] = ensure_result["error"]
            return result
        
        # Get repository path
        repo_path = repo_manager.get_repo_path(repo_url)
        if not repo_path:
            result["error"] = "Invalid repository URL"
            return result
        
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
    path: Optional[str] = Field(default=None, description="Directory path within repo to search (default: root)"),
    force_update: bool = Field(default=False, description="Force update repository before searching")
) -> Dict[str, Any]:
    """Search for patterns in repository files (automatically clones if needed)."""
    
    result = {
        "repo_url": repo_url,
        "pattern": pattern,
        "matches": [],
        "total_matches": 0,
        "files_searched": 0,
        "error": None
    }
    
    try:
        # Ensure repository is available
        ensure_result = repo_manager._ensure_repo_available(repo_url, force_update)
        if not ensure_result["success"]:
            result["error"] = ensure_result["error"]
            return result
        
        # Get repository path
        repo_path = repo_manager.get_repo_path(repo_url)
        if not repo_path:
            result["error"] = "Invalid repository URL"
            return result
        
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
    path: Optional[str] = Field(default=None, description="Directory path within repo to search (default: root)"),
    force_update: bool = Field(default=False, description="Force update repository before searching")
) -> Dict[str, Any]:
    """Find files matching patterns in repository (automatically clones if needed)."""
    
    result = {
        "repo_url": repo_url,
        "pattern": pattern,
        "files": [],
        "total_files": 0,
        "error": None
    }
    
    try:
        # Ensure repository is available
        ensure_result = repo_manager._ensure_repo_available(repo_url, force_update)
        if not ensure_result["success"]:
            result["error"] = ensure_result["error"]
            return result
        
        # Get repository path
        repo_path = repo_manager.get_repo_path(repo_url)
        if not repo_path:
            result["error"] = "Invalid repository URL"
            return result
        
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
        "storage_info": {
            "current_usage_gb": 0,
            "storage_limit_gb": None,
            "total_repositories": 0
        },
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
        
        # Get storage information
        try:
            result["storage_info"]["current_usage_gb"] = repo_manager.get_storage_usage_gb()
            result["storage_info"]["storage_limit_gb"] = repo_manager.get_storage_limit_gb()
            result["storage_info"]["total_repositories"] = len(repo_manager.get_repo_sizes())
        except Exception:
            pass
        
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
    
    return result


if __name__ == "__main__":
    # Clean up old repositories on startup
    repo_manager.cleanup_old_repositories()
    mcp.run()
