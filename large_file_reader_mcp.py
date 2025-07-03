#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastmcp",
#     "pydantic"
# ]
# ///

"""
# Large File Reader MCP Server

MCP server for reading large files in parts, addressing limitations of standard file reading tools
that struggle with files over 1MB. Provides line-based, byte-based, and pattern-based reading operations.

## Claude Configuration

Sample configuration:

```json
{
  "mcpServers": {
    "large-file-reader": {
      "command": "/Users/Joshua/.local/bin/uv",
      "args": [
        "run",
        "--script",
        "/Users/Joshua/Documents/_programming/simple-mcp-servers/large_file_reader_mcp.py"
      ]
    }
  }
}
```

## Claude Code Setup

Add to Claude Code with:
```bash
claude mcp add large-file-reader /Users/Joshua/Documents/_programming/simple-mcp-servers/large_file_reader_mcp.py
```

## Features

- **Line-based reading**: Read specific line ranges from large files
- **Head/tail operations**: Get first or last N lines efficiently
- **Byte-based reading**: Read specific byte ranges
- **Pattern search**: Find text patterns with surrounding context
- **File metadata**: Get file statistics without reading content
- **Chunked reading**: Process very large files in manageable chunks

## Use Cases

- Examining large log files
- Reading specific sections of large source code files
- Searching for patterns in large datasets
- Inspecting file headers/footers without loading entire file
- Processing large files incrementally

## Dependencies

- fastmcp: MCP server framework
- pydantic: Type validation and field descriptions
"""

import os
import re
import sys
import math
from typing import Dict, Any, List, Optional, Union
from fastmcp import FastMCP
from pydantic import Field


# Create server
mcp = FastMCP("large-file-reader")


def _detect_encoding(file_path: str) -> str:
    """Detect file encoding, defaulting to utf-8."""
    try:
        with open(file_path, 'rb') as f:
            sample = f.read(1024)
            if b'\x00' in sample:
                return 'binary'
            # Try UTF-8 first
            try:
                sample.decode('utf-8')
                return 'utf-8'
            except UnicodeDecodeError:
                # Try common encodings
                for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
                    try:
                        sample.decode(encoding)
                        return encoding
                    except UnicodeDecodeError:
                        continue
                return 'utf-8'  # Default fallback
    except Exception:
        return 'utf-8'


def _count_lines(file_path: str, encoding: str = 'utf-8') -> int:
    """Count total lines in file efficiently."""
    if encoding == 'binary':
        return 0
    
    try:
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def _safe_read_lines(file_path: str, start_line: int, end_line: int, encoding: str = 'utf-8') -> List[str]:
    """Safely read lines from file with error handling."""
    if encoding == 'binary':
        return []
        
    lines = []
    try:
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            for i, line in enumerate(f, 1):
                if i < start_line:
                    continue
                if i > end_line:
                    break
                lines.append(line.rstrip('\n\r'))
    except Exception as e:
        print(f"[DEBUG] Error reading lines: {e}", file=sys.stderr)
    
    return lines


@mcp.tool()
def get_file_stats(
    path: str = Field(description="Path to the file to analyze")
) -> Dict[str, Any]:
    """
    Get metadata about a file without reading its contents.

    Args:
        path: Path to the file to analyze

    Returns:
        Dictionary containing file statistics including size, line count, and encoding
    """
    print(f"[DEBUG] Getting stats for: {path}", file=sys.stderr)
    
    result = {
        "path": path,
        "exists": False,
        "size_bytes": 0,
        "line_count": 0,
        "encoding": None,
        "is_binary": False,
        "error": None
    }
    
    try:
        if not os.path.exists(path):
            result["error"] = f"File does not exist: {path}"
            return result
            
        if not os.path.isfile(path):
            result["error"] = f"Path is not a file: {path}"
            return result
            
        result["exists"] = True
        result["size_bytes"] = os.path.getsize(path)
        result["encoding"] = _detect_encoding(path)
        result["is_binary"] = result["encoding"] == 'binary'
        
        if not result["is_binary"]:
            result["line_count"] = _count_lines(path, result["encoding"])
            
        print(f"[DEBUG] File stats: {result['size_bytes']} bytes, {result['line_count']} lines, {result['encoding']} encoding", file=sys.stderr)
        
    except Exception as e:
        result["error"] = f"Error analyzing file: {str(e)}"
        print(f"[DEBUG] Error: {result['error']}", file=sys.stderr)
    
    return result


@mcp.tool()
def read_file_lines(
    path: str = Field(description="Path to the file to read"),
    start_line: int = Field(description="Starting line number (1-indexed)", ge=1),
    end_line: int = Field(description="Ending line number (1-indexed)", ge=1)
) -> Dict[str, Any]:
    """
    Read specific line range from a file.

    Args:
        path: Path to the file to read
        start_line: Starting line number (1-indexed)
        end_line: Ending line number (1-indexed)

    Returns:
        Dictionary containing the requested lines and metadata
    """
    print(f"[DEBUG] Reading lines {start_line}-{end_line} from: {path}", file=sys.stderr)
    
    result = {
        "path": path,
        "start_line": start_line,
        "end_line": end_line,
        "lines": [],
        "total_lines": 0,
        "encoding": None,
        "truncated": False,
        "error": None
    }
    
    try:
        # Get file stats first
        stats = get_file_stats(path)
        if stats["error"]:
            result["error"] = stats["error"]
            return result
            
        if stats["is_binary"]:
            result["error"] = "Cannot read lines from binary file"
            return result
            
        result["total_lines"] = stats["line_count"]
        result["encoding"] = stats["encoding"]
        
        # Validate line range
        if start_line > end_line:
            result["error"] = "start_line must be <= end_line"
            return result
            
        if start_line > result["total_lines"]:
            result["error"] = f"start_line ({start_line}) exceeds total lines ({result['total_lines']})"
            return result
            
        # Adjust end_line if it exceeds file length
        actual_end_line = min(end_line, result["total_lines"])
        if actual_end_line < end_line:
            result["truncated"] = True
            result["end_line"] = actual_end_line
        
        # Read the lines
        result["lines"] = _safe_read_lines(path, start_line, actual_end_line, result["encoding"])
        
        print(f"[DEBUG] Read {len(result['lines'])} lines", file=sys.stderr)
        
    except Exception as e:
        result["error"] = f"Error reading file: {str(e)}"
        print(f"[DEBUG] Error: {result['error']}", file=sys.stderr)
    
    return result


@mcp.tool()
def read_file_head(
    path: str = Field(description="Path to the file to read"),
    lines: int = Field(description="Number of lines to read from the beginning", ge=1, default=50)
) -> Dict[str, Any]:
    """
    Read first N lines from a file.

    Args:
        path: Path to the file to read
        lines: Number of lines to read from the beginning (default: 50)

    Returns:
        Dictionary containing the first N lines and metadata
    """
    print(f"[DEBUG] Reading first {lines} lines from: {path}", file=sys.stderr)
    return read_file_lines(path, 1, lines)


@mcp.tool()
def read_file_tail(
    path: str = Field(description="Path to the file to read"),
    lines: int = Field(description="Number of lines to read from the end", ge=1, default=50)
) -> Dict[str, Any]:
    """
    Read last N lines from a file.

    Args:
        path: Path to the file to read
        lines: Number of lines to read from the end (default: 50)

    Returns:
        Dictionary containing the last N lines and metadata
    """
    print(f"[DEBUG] Reading last {lines} lines from: {path}", file=sys.stderr)
    
    # Get total line count first
    stats = get_file_stats(path)
    if stats["error"] or stats["is_binary"]:
        return {
            "path": path,
            "lines": [],
            "total_lines": stats.get("line_count", 0),
            "encoding": stats.get("encoding"),
            "error": stats.get("error") or "Cannot read lines from binary file"
        }
    
    total_lines = stats["line_count"]
    start_line = max(1, total_lines - lines + 1)
    
    return read_file_lines(path, start_line, total_lines)


@mcp.tool()
def read_file_bytes(
    path: str = Field(description="Path to the file to read"),
    start_byte: int = Field(description="Starting byte position (0-indexed)", ge=0),
    length: int = Field(description="Number of bytes to read", ge=1)
) -> Dict[str, Any]:
    """
    Read specific byte range from a file.

    Args:
        path: Path to the file to read
        start_byte: Starting byte position (0-indexed)
        length: Number of bytes to read

    Returns:
        Dictionary containing the requested bytes as text and metadata
    """
    print(f"[DEBUG] Reading {length} bytes from position {start_byte} in: {path}", file=sys.stderr)
    
    result = {
        "path": path,
        "start_byte": start_byte,
        "length": length,
        "content": "",
        "actual_length": 0,
        "total_bytes": 0,
        "encoding": None,
        "error": None
    }
    
    try:
        if not os.path.exists(path):
            result["error"] = f"File does not exist: {path}"
            return result
            
        result["total_bytes"] = os.path.getsize(path)
        
        if start_byte >= result["total_bytes"]:
            result["error"] = f"start_byte ({start_byte}) exceeds file size ({result['total_bytes']})"
            return result
        
        # Read the bytes
        with open(path, 'rb') as f:
            f.seek(start_byte)
            data = f.read(length)
            result["actual_length"] = len(data)
            
            # Try to decode as text
            encoding = _detect_encoding(path)
            result["encoding"] = encoding
            
            if encoding == 'binary':
                # For binary files, show hex representation
                result["content"] = data.hex()
            else:
                try:
                    result["content"] = data.decode(encoding, errors='replace')
                except Exception:
                    result["content"] = data.decode('utf-8', errors='replace')
        
        print(f"[DEBUG] Read {result['actual_length']} bytes", file=sys.stderr)
        
    except Exception as e:
        result["error"] = f"Error reading file: {str(e)}"
        print(f"[DEBUG] Error: {result['error']}", file=sys.stderr)
    
    return result


@mcp.tool()
def search_file_lines(
    path: str = Field(description="Path to the file to search"),
    pattern: str = Field(description="Regular expression pattern to search for"),
    context_lines: int = Field(description="Number of context lines to include around matches", ge=0, default=5),
    max_matches: int = Field(description="Maximum number of matches to return", ge=1, default=10)
) -> Dict[str, Any]:
    """
    Search for pattern in file and return matches with surrounding context.

    Args:
        path: Path to the file to search
        pattern: Regular expression pattern to search for
        context_lines: Number of context lines to include around matches (default: 5)
        max_matches: Maximum number of matches to return (default: 10)

    Returns:
        Dictionary containing matches with line numbers and context
    """
    print(f"[DEBUG] Searching for pattern '{pattern}' in: {path}", file=sys.stderr)
    
    result = {
        "path": path,
        "pattern": pattern,
        "context_lines": context_lines,
        "matches": [],
        "total_matches": 0,
        "max_matches": max_matches,
        "truncated": False,
        "encoding": None,
        "error": None
    }
    
    try:
        # Get file stats first
        stats = get_file_stats(path)
        if stats["error"]:
            result["error"] = stats["error"]
            return result
            
        if stats["is_binary"]:
            result["error"] = "Cannot search binary file"
            return result
            
        result["encoding"] = stats["encoding"]
        
        # Compile regex pattern
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            result["error"] = f"Invalid regex pattern: {str(e)}"
            return result
        
        # Read file and search
        matches = []
        all_lines = []
        
        with open(path, 'r', encoding=result["encoding"], errors='replace') as f:
            all_lines = [line.rstrip('\n\r') for line in f]
        
        # Find all matches
        for line_num, line in enumerate(all_lines, 1):
            if regex.search(line):
                matches.append({
                    "line_num": line_num,
                    "match_line": line
                })
        
        result["total_matches"] = len(matches)
        
        # Limit matches and add context
        display_matches = matches[:max_matches]
        if len(matches) > max_matches:
            result["truncated"] = True
        
        for match in display_matches:
            line_num = match["line_num"]
            start_line = max(0, line_num - context_lines - 1)
            end_line = min(len(all_lines), line_num + context_lines)
            
            context = []
            for i in range(start_line, end_line):
                context.append({
                    "line_num": i + 1,
                    "content": all_lines[i],
                    "is_match": (i + 1 == line_num)
                })
            
            result["matches"].append({
                "line_num": line_num,
                "match_line": match["match_line"],
                "context": context
            })
        
        print(f"[DEBUG] Found {result['total_matches']} matches, showing {len(result['matches'])}", file=sys.stderr)
        
    except Exception as e:
        result["error"] = f"Error searching file: {str(e)}"
        print(f"[DEBUG] Error: {result['error']}", file=sys.stderr)
    
    return result


@mcp.tool()
def read_file_chunk(
    path: str = Field(description="Path to the file to read"),
    chunk_size: int = Field(description="Number of lines per chunk", ge=1, default=1000),
    chunk_index: int = Field(description="Zero-indexed chunk number to read", ge=0, default=0)
) -> Dict[str, Any]:
    """
    Read file in chunks for processing very large files incrementally.

    Args:
        path: Path to the file to read
        chunk_size: Number of lines per chunk (default: 1000)
        chunk_index: Zero-indexed chunk number to read (default: 0)

    Returns:
        Dictionary containing the requested chunk and navigation info
    """
    print(f"[DEBUG] Reading chunk {chunk_index} (size {chunk_size}) from: {path}", file=sys.stderr)
    
    result = {
        "path": path,
        "chunk_size": chunk_size,
        "chunk_index": chunk_index,
        "lines": [],
        "total_lines": 0,
        "total_chunks": 0,
        "has_more": False,
        "encoding": None,
        "error": None
    }
    
    try:
        # Get file stats first
        stats = get_file_stats(path)
        if stats["error"]:
            result["error"] = stats["error"]
            return result
            
        if stats["is_binary"]:
            result["error"] = "Cannot read chunks from binary file"
            return result
            
        result["total_lines"] = stats["line_count"]
        result["encoding"] = stats["encoding"]
        result["total_chunks"] = math.ceil(result["total_lines"] / chunk_size)
        
        if chunk_index >= result["total_chunks"]:
            result["error"] = f"chunk_index ({chunk_index}) exceeds total chunks ({result['total_chunks']})"
            return result
        
        # Calculate line range for this chunk
        start_line = chunk_index * chunk_size + 1
        end_line = min(start_line + chunk_size - 1, result["total_lines"])
        
        # Read the chunk
        chunk_result = read_file_lines(path, start_line, end_line)
        if chunk_result["error"]:
            result["error"] = chunk_result["error"]
            return result
        
        result["lines"] = chunk_result["lines"]
        result["has_more"] = chunk_index < result["total_chunks"] - 1
        
        print(f"[DEBUG] Read chunk {chunk_index}/{result['total_chunks']-1} with {len(result['lines'])} lines", file=sys.stderr)
        
    except Exception as e:
        result["error"] = f"Error reading chunk: {str(e)}"
        print(f"[DEBUG] Error: {result['error']}", file=sys.stderr)
    
    return result


mcp.run()
