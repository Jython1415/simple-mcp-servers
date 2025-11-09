#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastmcp",
#     "pydantic",
# ]
# ///

"""
Obsidian Toy MCP Server

A minimal MCP server for testing logging infrastructure before implementing
in the production Obsidian vault server. Provides basic file access functionality
for proof-of-concept development.

Configuration for Claude Desktop:
```json
{
  "mcpServers": {
    "obsidian-toy": {
      "command": "/Users/Joshua/.local/bin/uv",
      "args": [
        "run",
        "--script",
        "/path/to/obsidian_toy_mcp.py"
      ],
      "env": {
        "OBSIDIAN_VAULT_PATH": "/path/to/your/obsidian/vault"
      }
    }
  }
}
```

## Claude Code Setup

Add to Claude Code with:
```bash
claude mcp add obsidian-toy /Users/Joshua/Documents/_programming/simple-mcp-servers/obsidian_toy_mcp.py --env OBSIDIAN_VAULT_PATH=/path/to/your/obsidian/vault
```

Direct execution:
```bash
chmod +x obsidian_toy_mcp.py
OBSIDIAN_VAULT_PATH="/path/to/vault" ./obsidian_toy_mcp.py
```

Environment Variables:
- OBSIDIAN_VAULT_PATH: Path to your Obsidian vault directory (required)

## Roadmap

- [x] Create basic toy MCP server with simple file access tool
- [x] Research log destination options (stderr, file, stdout, system logging)
- [x] Research MCP server testing approaches and automation capabilities
- [x] Implement and test logging infrastructure on toy server
- [x] Validate logging approach and refine implementation plan

"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone
from functools import wraps

from fastmcp import FastMCP
from pydantic import Field

# Initialize the MCP server
mcp = FastMCP("obsidian-toy")

# Global configuration
VAULT_PATH = None
LOGGING_ENABLED = False
LOG_FILE = None

def get_vault_path() -> Path:
    """Get the vault path from environment variable."""
    global VAULT_PATH
    if VAULT_PATH is None:
        vault_path_str = os.environ.get("OBSIDIAN_VAULT_PATH")
        if not vault_path_str:
            raise ValueError("OBSIDIAN_VAULT_PATH environment variable is required")
        VAULT_PATH = Path(vault_path_str).expanduser().resolve()
        if not VAULT_PATH.exists():
            raise ValueError(f"Vault path does not exist: {VAULT_PATH}")
        if not VAULT_PATH.is_dir():
            raise ValueError(f"Vault path is not a directory: {VAULT_PATH}")
    return VAULT_PATH

def init_logging():
    """Initialize logging configuration from environment variables."""
    global LOGGING_ENABLED, LOG_FILE
    
    # Check if logging is enabled
    LOGGING_ENABLED = os.environ.get("OBSIDIAN_TOOL_LOGGING", "").lower() in ("true", "1", "yes")
    
    # Get log file path if specified
    log_file_path = os.environ.get("OBSIDIAN_LOG_FILE")
    if log_file_path:
        try:
            LOG_FILE = Path(log_file_path).expanduser().resolve()
            # Ensure parent directory exists
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            # Test write permissions
            with open(LOG_FILE, 'a') as f:
                pass
        except Exception as e:
            print(f"Warning: Could not initialize log file {log_file_path}: {e}", file=sys.stderr)
            LOG_FILE = None

def log_tool_call(tool_name: str, parameters: Dict[str, Any], accessed_files: List[str], 
                  execution_time_ms: float, success: bool, error_message: Optional[str] = None):
    """Log a tool call with structured JSON format."""
    if not LOGGING_ENABLED:
        return
    
    try:
        # Create log entry
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_name": tool_name,
            "parameters": parameters,
            "accessed_files": accessed_files,
            "execution_time_ms": round(execution_time_ms, 2),
            "success": success,
            "error_message": error_message
        }
        
        # Convert to JSON
        log_line = json.dumps(log_entry)
        
        # Write to log destination
        if LOG_FILE:
            try:
                with open(LOG_FILE, 'a') as f:
                    f.write(log_line + '\n')
            except Exception as e:
                # Fallback to stderr if file logging fails
                print(f"Log write failed: {e}", file=sys.stderr)
                print(log_line, file=sys.stderr)
        else:
            # Log to stderr by default
            print(log_line, file=sys.stderr)
            
    except Exception as e:
        # Don't let logging failures break the tool
        print(f"Logging error: {e}", file=sys.stderr)

class FileAccessTracker:
    """Context manager to track file access during tool execution."""
    
    def __init__(self):
        self.accessed_files = []
        self.original_open = None
    
    def __enter__(self):
        # Track file access by monkey-patching open
        self.original_open = __builtins__['open']
        
        def tracked_open(file, *args, **kwargs):
            # Only track files within the vault
            try:
                file_path = Path(file).resolve()
                vault_path = get_vault_path()
                if file_path.is_relative_to(vault_path):
                    relative_path = str(file_path.relative_to(vault_path))
                    if relative_path not in self.accessed_files:
                        self.accessed_files.append(relative_path)
            except Exception:
                # If we can't determine the path relationship, skip tracking
                pass
            
            return self.original_open(file, *args, **kwargs)
        
        __builtins__['open'] = tracked_open
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original open
        __builtins__['open'] = self.original_open

def log_tool_call_decorator(func: Callable) -> Callable:
    """Decorator to log tool calls with execution time and file access tracking."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not LOGGING_ENABLED:
            return func(*args, **kwargs)
        
        # Record start time
        start_time = time.time()
        
        # Track file access
        with FileAccessTracker() as tracker:
            try:
                # Execute the tool
                result = func(*args, **kwargs)
                
                # Calculate execution time
                execution_time_ms = (time.time() - start_time) * 1000
                
                # Determine success based on result
                success = True
                error_message = None
                if isinstance(result, dict) and 'success' in result:
                    success = result['success']
                    if not success and 'error' in result:
                        error_message = result['error']
                
                # Log the call
                log_tool_call(
                    tool_name=func.__name__,
                    parameters=dict(zip(func.__code__.co_varnames, args)) if args else kwargs,
                    accessed_files=tracker.accessed_files,
                    execution_time_ms=execution_time_ms,
                    success=success,
                    error_message=error_message
                )
                
                return result
                
            except Exception as e:
                # Calculate execution time for failed calls
                execution_time_ms = (time.time() - start_time) * 1000
                
                # Log the failed call
                log_tool_call(
                    tool_name=func.__name__,
                    parameters=dict(zip(func.__code__.co_varnames, args)) if args else kwargs,
                    accessed_files=tracker.accessed_files,
                    execution_time_ms=execution_time_ms,
                    success=False,
                    error_message=str(e)
                )
                
                # Re-raise the exception
                raise
    
    return wrapper

@mcp.tool()
@log_tool_call_decorator
def toy_read_file(
    file_path: str = Field(description="Path to file relative to vault root (e.g., 'folder/note.md')")
) -> Dict[str, Any]:
    """
    Read a file from the Obsidian vault by relative path.
    
    Simple file reading tool for testing logging infrastructure.
    Returns file content, size, and modification time.
    """
    try:
        vault_path = get_vault_path()
        
        # Resolve the file path relative to vault
        if Path(file_path).is_absolute():
            try:
                file_path = str(Path(file_path).relative_to(vault_path))
            except ValueError:
                raise ValueError(f"File path is not within vault: {file_path}")
        
        full_path = vault_path / file_path
        
        # Security check - ensure path is within vault
        try:
            full_path.resolve().relative_to(vault_path.resolve())
        except ValueError:
            raise ValueError(f"File path is not within vault: {file_path}")
        
        if not full_path.exists():
            raise ValueError(f"File does not exist: {file_path}")
        
        if not full_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")
        
        # Read file content
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Get file stats
        stat = full_path.stat()
        
        return {
            'relative_path': file_path,
            'content': content,
            'size_bytes': stat.st_size,
            'modified_time': stat.st_mtime,
            'success': True
        }
        
    except Exception as e:
        return {
            'relative_path': file_path,
            'error': str(e),
            'success': False
        }

if __name__ == "__main__":
    # Initialize logging first
    init_logging()
    
    # Validate environment on startup
    try:
        get_vault_path()
        print(f"Obsidian Toy MCP Server starting with vault: {get_vault_path()}", file=sys.stderr)
        if LOGGING_ENABLED:
            if LOG_FILE:
                print(f"Tool logging enabled to file: {LOG_FILE}", file=sys.stderr)
            else:
                print("Tool logging enabled to stderr", file=sys.stderr)
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    
    mcp.run()