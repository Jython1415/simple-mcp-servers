#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastmcp",
#     "pydantic",
#     "python-frontmatter",
#     "pyyaml",
# ]
# ///

"""
Obsidian Vault MCP Server

A standalone MCP server for reading and searching Obsidian vaults without requiring
the Obsidian Local REST API plugin. Provides direct filesystem access to vault contents
with comprehensive search capabilities.

This server enables AI tools to:
- Read individual notes with frontmatter parsing
- Search across entire vault with text and regex support
- List vault contents and navigate directories
- Extract metadata from notes (tags, frontmatter, file stats)

Configuration for Claude Desktop:
```json
{
  "mcpServers": {
    "obsidian-vault": {
      "command": "/Users/Joshua/.local/bin/uv",
      "args": [
        "run",
        "--script",
        "/path/to/obsidian_vault_mcp.py"
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
claude mcp add obsidian-vault /Users/Joshua/Documents/_programming/simple-mcp-servers/obsidian_vault_mcp.py --env OBSIDIAN_VAULT_PATH=/path/to/your/obsidian/vault
```

Direct execution:
```bash
chmod +x obsidian_vault_mcp.py
OBSIDIAN_VAULT_PATH="/path/to/vault" ./obsidian_vault_mcp.py
```

Environment Variables:
- OBSIDIAN_VAULT_PATH: Path to your Obsidian vault directory (required)
- OBSIDIAN_USAGE_INSTRUCTIONS: Custom usage instructions for this vault (optional)

## Custom Usage Instructions

The server provides a resource called `usage_instructions` that can contain custom guidance
for working with your specific Obsidian vault. Instructions are loaded in priority order:

1. **Environment Variable**: Set `OBSIDIAN_USAGE_INSTRUCTIONS` when configuring the server
2. **CLAUDE.md File**: Place a `CLAUDE.md` file in your vault root directory
3. **Default Message**: If neither are available, indicates no custom instructions

Example with custom instructions:
```bash
claude mcp add obsidian-vault /path/to/obsidian_vault_mcp.py \
  --env OBSIDIAN_VAULT_PATH=/path/to/vault \
  --env OBSIDIAN_USAGE_INSTRUCTIONS="When searching for Claude instructions, filter by the #claude tag using required_tags=['claude']"
```

Example CLAUDE.md file content:
```markdown
# Claude Usage Instructions for My Vault

- Use required_tags=['claude'] when searching for Claude-specific instructions
- Personal notes are tagged with #personal
- Work notes are tagged with #work
- Meeting notes are in the meetings/ folder
```
"""

import os
import sys
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import frontmatter
import yaml

from fastmcp import FastMCP
from pydantic import Field

# Initialize the MCP server
mcp = FastMCP("obsidian-vault")

# Global configuration
VAULT_PATH = None

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

def is_markdown_file(path: Path) -> bool:
    """Check if a file is a markdown file."""
    return path.suffix.lower() in {'.md', '.markdown'}

def parse_note_file(file_path: Path) -> Dict[str, Any]:
    """Parse a markdown file and extract frontmatter and content."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            post = frontmatter.load(f)
        
        # Extract file stats
        stat = file_path.stat()
        
        # Extract tags from frontmatter and content
        tags = []
        
        # Tags from frontmatter
        if 'tags' in post.metadata:
            fm_tags = post.metadata['tags']
            if isinstance(fm_tags, str):
                tags.extend([tag.strip() for tag in fm_tags.split(',') if tag.strip()])
            elif isinstance(fm_tags, list):
                tags.extend([str(tag).strip() for tag in fm_tags if str(tag).strip()])
        
        # Tags from content (inline tags like #tag)
        content_tags = re.findall(r'#([a-zA-Z0-9_/-]+)', post.content)
        tags.extend(content_tags)
        
        # Remove duplicates while preserving order
        unique_tags = []
        seen = set()
        for tag in tags:
            if tag not in seen:
                unique_tags.append(tag)
                seen.add(tag)
        
        return {
            'path': str(file_path.relative_to(get_vault_path())),
            'content': post.content,
            'frontmatter': post.metadata,
            'tags': unique_tags,
            'stat': {
                'size': stat.st_size,
                'ctime': stat.st_ctime,
                'mtime': stat.st_mtime,
            }
        }
    except Exception as e:
        raise ValueError(f"Error parsing file {file_path}: {str(e)}")

def resolve_note_path(note_path: str) -> Path:
    """Resolve a note path, handling case-insensitive matching."""
    vault_path = get_vault_path()
    
    # Handle absolute paths by making them relative to vault
    if Path(note_path).is_absolute():
        try:
            note_path = str(Path(note_path).relative_to(vault_path))
        except ValueError:
            # Path is not under vault
            pass
    
    # Direct path check
    full_path = vault_path / note_path
    if full_path.exists():
        return full_path
    
    # Try with .md extension if not present
    if not note_path.endswith(('.md', '.markdown')):
        md_path = vault_path / f"{note_path}.md"
        if md_path.exists():
            return md_path
    
    # Case-insensitive fallback
    try:
        target_parts = Path(note_path).parts
        current_path = vault_path
        
        for part in target_parts:
            found = False
            if current_path.exists() and current_path.is_dir():
                for child in current_path.iterdir():
                    if child.name.lower() == part.lower():
                        current_path = child
                        found = True
                        break
            
            if not found:
                # Try with .md extension for the final part
                if part == target_parts[-1] and not part.endswith(('.md', '.markdown')):
                    md_part = f"{part}.md"
                    for child in current_path.iterdir():
                        if child.name.lower() == md_part.lower():
                            current_path = child
                            found = True
                            break
            
            if not found:
                break
        
        if found and current_path.exists():
            return current_path
    except Exception:
        pass
    
    raise FileNotFoundError(f"Note not found: {note_path}")

@mcp.tool()
def obsidian_read_note(
    note_path: str = Field(description="Path to the note file relative to vault root (e.g., 'folder/note.md' or 'note')")
) -> Dict[str, Any]:
    """
    Read an Obsidian note and return its content, frontmatter, and metadata.
    
    Supports both markdown and plain text content. Automatically parses YAML frontmatter
    and extracts tags from both frontmatter and inline content.
    
    Args:
        note_path: Path to the note relative to vault root. File extension is optional.
                  Case-insensitive matching is supported as fallback.
    
    Returns:
        Dictionary containing:
        - path: Relative path to the note
        - content: Main content of the note (without frontmatter)
        - frontmatter: Parsed YAML frontmatter as dictionary
        - tags: List of all tags found in frontmatter and content
        - stat: File statistics (size, creation time, modification time)
    
    Raises:
        FileNotFoundError: If the note cannot be found
        ValueError: If the file cannot be parsed
    """
    try:
        vault_path = get_vault_path()
        file_path = resolve_note_path(note_path)
        
        # Ensure the resolved path is within the vault
        try:
            file_path.relative_to(vault_path)
        except ValueError:
            raise FileNotFoundError(f"Note path outside vault: {note_path}")
        
        if not is_markdown_file(file_path):
            # For non-markdown files, return basic content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            stat = file_path.stat()
            return {
                'path': str(file_path.relative_to(vault_path)),
                'content': content,
                'frontmatter': {},
                'tags': [],
                'stat': {
                    'size': stat.st_size,
                    'ctime': stat.st_ctime,
                    'mtime': stat.st_mtime,
                }
            }
        
        # Parse markdown file with frontmatter
        return parse_note_file(file_path)
        
    except FileNotFoundError:
        raise FileNotFoundError(f"Note not found: {note_path}")
    except Exception as e:
        raise ValueError(f"Error reading note '{note_path}': {str(e)}")

@mcp.tool()
def obsidian_list_notes(
    directory: str = Field(default="", description="Directory path within vault to list (empty for root)"),
    include_subdirectories: bool = Field(default=True, description="Include subdirectories in results"),
    file_extension_filter: str = Field(default="", description="Filter by file extension (e.g., '.md', '.txt')"),
    name_pattern: str = Field(default="", description="Regex pattern to match file names"),
    max_depth: int = Field(default=3, description="Maximum depth to traverse (0 for no limit)"),
    max_files: int = Field(default=100, description="Maximum number of files to return (prevents token overflow)"),
    lazy_parsing: bool = Field(default=True, description="Skip expensive tag/frontmatter parsing for better performance")
) -> Dict[str, Any]:
    """
    List notes and directories within the Obsidian vault.
    
    Provides a hierarchical view of vault contents with filtering options.
    Can list files in a specific directory or provide a tree view of the entire vault.
    
    Args:
        directory: Directory path within vault to list (empty string for root)
        include_subdirectories: Whether to include subdirectories in results
        file_extension_filter: Filter by file extension (e.g., '.md', '.txt')
        name_pattern: Regex pattern to match file names (case-insensitive)
        max_depth: Maximum depth to traverse (0 for no limit)
        max_files: Maximum number of files to return (prevents token overflow)
        lazy_parsing: Skip expensive tag/frontmatter parsing for better performance
    
    Returns:
        Dictionary containing:
        - directory: The directory that was listed
        - files: List of file information dictionaries
        - subdirectories: List of subdirectory names (if include_subdirectories=True)
        - total_files: Total number of files found
        - total_directories: Total number of directories found
        - files_found: Total files found before max_files limit applied
        - truncated: Whether results were truncated due to max_files limit
    
    Raises:
        FileNotFoundError: If the directory doesn't exist
        ValueError: If there's an error processing the directory
    """
    try:
        vault_path = get_vault_path()
        
        # Resolve target directory
        if directory:
            target_dir = vault_path / directory
        else:
            target_dir = vault_path
        
        if not target_dir.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        if not target_dir.is_dir():
            raise ValueError(f"Path is not a directory: {directory}")
        
        # Ensure directory is within vault
        try:
            target_dir.relative_to(vault_path)
        except ValueError:
            raise ValueError(f"Directory path outside vault: {directory}")
        
        files = []
        subdirectories = []
        files_found = 0
        
        # Compile regex pattern if provided
        pattern = None
        if name_pattern:
            try:
                pattern = re.compile(name_pattern, re.IGNORECASE)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}")
        
        def should_include_file(file_path: Path) -> bool:
            """Check if a file should be included based on filters."""
            # Extension filter
            if file_extension_filter and not file_path.suffix.lower() == file_extension_filter.lower():
                return False
            
            # Name pattern filter
            if pattern and not pattern.search(file_path.name):
                return False
            
            return True
        
        def traverse_directory(dir_path: Path, current_depth: int = 0) -> bool:
            """Recursively traverse directory and collect files. Returns False if max_files reached."""
            nonlocal files_found
            
            if max_depth > 0 and current_depth >= max_depth:
                return True  # Continue processing
            
            if len(files) >= max_files:
                return False  # Stop processing
            
            try:
                for item in sorted(dir_path.iterdir()):
                    if len(files) >= max_files:
                        return False  # Stop processing
                    
                    if item.is_file() and should_include_file(item):
                        files_found += 1
                        
                        # Only add to results if under max_files limit
                        if len(files) < max_files:
                            # Get file info
                            stat = item.stat()
                            relative_path = item.relative_to(vault_path)
                            
                            file_info = {
                                'name': item.name,
                                'path': str(relative_path),
                                'size': stat.st_size,
                                'modified': stat.st_mtime,
                                'is_markdown': is_markdown_file(item)
                            }
                            
                            # Add tag count for markdown files only if not lazy parsing
                            if is_markdown_file(item) and not lazy_parsing:
                                try:
                                    parsed = parse_note_file(item)
                                    file_info['tag_count'] = len(parsed['tags'])
                                    file_info['has_frontmatter'] = bool(parsed['frontmatter'])
                                except Exception:
                                    file_info['tag_count'] = 0
                                    file_info['has_frontmatter'] = False
                            elif is_markdown_file(item) and lazy_parsing:
                                # Skip expensive parsing but indicate it's markdown
                                file_info['tag_count'] = None  # Indicates lazy parsing was used
                                file_info['has_frontmatter'] = None
                            
                            files.append(file_info)
                    
                    elif item.is_dir() and include_subdirectories:
                        relative_path = item.relative_to(vault_path)
                        subdirectories.append(str(relative_path))
                        
                        # Recursively traverse subdirectory
                        if not traverse_directory(item, current_depth + 1):
                            return False  # Stop processing
            
            except PermissionError:
                # Skip directories we can't read
                pass
            
            return True  # Continue processing
        
        # Start traversal
        traverse_directory(target_dir)
        
        return {
            'directory': directory,
            'files': files,
            'subdirectories': subdirectories,
            'total_files': len(files),
            'total_directories': len(subdirectories),
            'files_found': files_found,
            'truncated': files_found > len(files)
        }
        
    except FileNotFoundError:
        raise FileNotFoundError(f"Directory not found: {directory}")
    except Exception as e:
        raise ValueError(f"Error listing directory '{directory}': {str(e)}")

@mcp.tool()
def obsidian_global_search(
    query: str = Field(description="Search query or regex pattern"),
    use_regex: bool = Field(default=False, description="Treat query as regex pattern"),
    case_sensitive: bool = Field(default=False, description="Perform case-sensitive search"),
    search_content: bool = Field(default=True, description="Search in note content"),
    search_frontmatter: bool = Field(default=True, description="Search in frontmatter fields"),
    search_tags: bool = Field(default=True, description="Search in tags"),
    search_filenames: bool = Field(default=True, description="Search in filenames"),
    directory_filter: str = Field(default="", description="Limit search to specific directory"),
    file_extension_filter: str = Field(default=".md", description="Filter by file extension"),
    context_lines: int = Field(default=2, description="Number of context lines around matches"),
    max_results: int = Field(default=50, description="Maximum number of results to return"),
    required_tags: List[str] = Field(default_factory=list, description="Only include results from notes that contain ALL of these tags"),
    any_of_tags: List[str] = Field(default_factory=list, description="Only include results from notes that contain ANY of these tags"),
    exclude_tags: List[str] = Field(default_factory=list, description="Exclude results from notes that contain any of these tags")
) -> Dict[str, Any]:
    """
    Search across the entire Obsidian vault for text, tags, or frontmatter.
    
    Provides comprehensive search capabilities with regex support, context extraction,
    and filtering options. Can search in content, frontmatter, tags, and filenames.
    
    Args:
        query: Search query or regex pattern
        use_regex: Whether to treat query as regex pattern
        case_sensitive: Whether search should be case-sensitive
        search_content: Whether to search in note content
        search_frontmatter: Whether to search in frontmatter fields
        search_tags: Whether to search in tags
        search_filenames: Whether to search in filenames
        directory_filter: Limit search to specific directory within vault
        file_extension_filter: Filter by file extension (default: .md)
        context_lines: Number of context lines to include around matches
        max_results: Maximum number of results to return
        required_tags: Only include results from notes that contain ALL of these tags
        any_of_tags: Only include results from notes that contain ANY of these tags
        exclude_tags: Exclude results from notes that contain any of these tags
    
    Returns:
        Dictionary containing:
        - query: The search query used
        - total_matches: Total number of matches found
        - results: List of match result dictionaries
        - search_stats: Statistics about the search (including tag filtering options)
    
    Raises:
        ValueError: If search parameters are invalid
    
    Examples:
        # Search for "python" in notes that have the "programming" tag
        obsidian_global_search("python", required_tags=["programming"])
        
        # Search for "AI" in notes that have either "machine-learning" or "deep-learning" tags
        obsidian_global_search("AI", any_of_tags=["machine-learning", "deep-learning"])
        
        # Search for "tutorial" but exclude notes with "draft" tag
        obsidian_global_search("tutorial", exclude_tags=["draft"])
        
        # Combined filtering: search for "API" in programming notes but exclude archived ones
        obsidian_global_search("API", required_tags=["programming"], exclude_tags=["archived"])
    """
    try:
        vault_path = get_vault_path()
        
        if not query.strip():
            raise ValueError("Search query cannot be empty")
        
        # Prepare search pattern
        search_flags = 0 if case_sensitive else re.IGNORECASE
        
        if use_regex:
            try:
                pattern = re.compile(query, search_flags)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}")
        else:
            # Escape special regex characters for literal search
            escaped_query = re.escape(query)
            pattern = re.compile(escaped_query, search_flags)
        
        # Determine search directory
        search_dir = vault_path
        if directory_filter and directory_filter.strip():
            search_dir = vault_path / directory_filter
            if not search_dir.exists() or not search_dir.is_dir():
                raise ValueError(f"Directory filter path not found: {directory_filter}")
        
        results = []
        files_searched = 0
        total_matches = 0
        
        def search_in_text(text: str, content_type: str, file_path: str) -> List[Dict[str, Any]]:
            """Search for pattern in text and return matches with context."""
            matches = []
            lines = text.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                if pattern.search(line):
                    # Extract context lines
                    start_line = max(0, line_num - 1 - context_lines)
                    end_line = min(len(lines), line_num + context_lines)
                    
                    context = []
                    for i in range(start_line, end_line):
                        prefix = ">" if i == line_num - 1 else " "
                        context.append(f"{i+1:4d}{prefix} {lines[i]}")
                    
                    matches.append({
                        'file_path': file_path,
                        'line_number': line_num,
                        'content_type': content_type,
                        'matched_line': line.strip(),
                        'context': '\n'.join(context)
                    })
            
            return matches
        
        def search_in_frontmatter(frontmatter: Dict[str, Any], file_path: str) -> List[Dict[str, Any]]:
            """Search in frontmatter fields."""
            matches = []
            
            def search_value(key: str, value: Any, path: str = "") -> None:
                current_path = f"{path}.{key}" if path else key
                
                if isinstance(value, str):
                    if pattern.search(value):
                        matches.append({
                            'file_path': file_path,
                            'content_type': 'frontmatter',
                            'field_path': current_path,
                            'matched_value': value
                        })
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, str) and pattern.search(item):
                            matches.append({
                                'file_path': file_path,
                                'content_type': 'frontmatter',
                                'field_path': f"{current_path}[{i}]",
                                'matched_value': item
                            })
                elif isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        search_value(sub_key, sub_value, current_path)
            
            for key, value in frontmatter.items():
                search_value(key, value)
            
            return matches
        
        def should_include_by_tags(note_tags: List[str]) -> bool:
            """Check if a note should be included based on tag filtering criteria."""
            # Convert to lowercase for case-insensitive matching
            note_tags_lower = [tag.lower() for tag in note_tags]
            
            # Check required_tags (must have ALL)
            if required_tags:
                required_tags_lower = [tag.lower() for tag in required_tags]
                if not all(req_tag in note_tags_lower for req_tag in required_tags_lower):
                    return False
            
            # Check any_of_tags (must have ANY)
            if any_of_tags:
                any_of_tags_lower = [tag.lower() for tag in any_of_tags]
                if not any(any_tag in note_tags_lower for any_tag in any_of_tags_lower):
                    return False
            
            # Check exclude_tags (must NOT have any)
            if exclude_tags:
                exclude_tags_lower = [tag.lower() for tag in exclude_tags]
                if any(excl_tag in note_tags_lower for excl_tag in exclude_tags_lower):
                    return False
            
            return True
        
        # Walk through directory and search files
        for file_path in search_dir.rglob('*'):
            if not file_path.is_file():
                continue
            
            # Apply file extension filter
            if file_extension_filter and file_extension_filter.strip() and not file_path.suffix.lower() == file_extension_filter.lower():
                continue
            
            files_searched += 1
            relative_path = str(file_path.relative_to(vault_path))
            
            # Search in filename (apply tag filtering if it's a markdown file)
            if search_filenames and pattern.search(file_path.name):
                should_include = True
                
                # Apply tag filtering for markdown files
                if is_markdown_file(file_path) and (required_tags or any_of_tags or exclude_tags):
                    try:
                        parsed = parse_note_file(file_path)
                        should_include = should_include_by_tags(parsed['tags'])
                    except Exception:
                        # If we can't parse the file, skip tag filtering for filename matches
                        pass
                
                if should_include:
                    results.append({
                        'file_path': relative_path,
                        'content_type': 'filename',
                        'matched_value': file_path.name
                    })
                    total_matches += 1
            
            # Skip non-markdown files for content search
            if file_extension_filter and file_extension_filter.strip() == '.md' and not is_markdown_file(file_path):
                continue
            
            try:
                # Parse file
                if is_markdown_file(file_path):
                    parsed = parse_note_file(file_path)
                    
                    # Apply tag filtering - skip this file if it doesn't match tag criteria
                    if not should_include_by_tags(parsed['tags']):
                        continue
                    
                    # Search in content
                    if search_content:
                        content_matches = search_in_text(parsed['content'], 'content', relative_path)
                        results.extend(content_matches)
                        total_matches += len(content_matches)
                    
                    # Search in frontmatter
                    if search_frontmatter and parsed['frontmatter']:
                        fm_matches = search_in_frontmatter(parsed['frontmatter'], relative_path)
                        results.extend(fm_matches)
                        total_matches += len(fm_matches)
                    
                    # Search in tags
                    if search_tags and parsed['tags']:
                        for tag in parsed['tags']:
                            if pattern.search(tag):
                                results.append({
                                    'file_path': relative_path,
                                    'content_type': 'tag',
                                    'matched_value': tag
                                })
                                total_matches += 1
                
                else:
                    # Search in plain text files
                    if search_content:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        content_matches = search_in_text(content, 'content', relative_path)
                        results.extend(content_matches)
                        total_matches += len(content_matches)
            
            except Exception as e:
                # Log error but continue searching
                print(f"Error searching file {file_path}: {e}", file=sys.stderr)
                continue
            
            # Limit results
            if len(results) >= max_results:
                break
        
        # Sort results by relevance (filename matches first, then by file path)
        def sort_key(result):
            priority = 0 if result.get('content_type') == 'filename' else 1
            return (priority, result.get('file_path', ''))
        
        results.sort(key=sort_key)
        
        return {
            'query': query,
            'total_matches': total_matches,
            'results': results[:max_results],
            'search_stats': {
                'files_searched': files_searched,
                'results_returned': min(len(results), max_results),
                'search_options': {
                    'use_regex': use_regex,
                    'case_sensitive': case_sensitive,
                    'search_content': search_content,
                    'search_frontmatter': search_frontmatter,
                    'search_tags': search_tags,
                    'search_filenames': search_filenames,
                    'required_tags': required_tags,
                    'any_of_tags': any_of_tags,
                    'exclude_tags': exclude_tags
                }
            }
        }
        
    except Exception as e:
        raise ValueError(f"Error performing search: {str(e)}")

@mcp.tool()
def obsidian_get_vault_info() -> Dict[str, Any]:
    """
    Get information and statistics about the Obsidian vault.
    
    Provides an overview of the vault including file counts, directory structure,
    and basic statistics about the content.
    
    Returns:
        Dictionary containing:
        - vault_path: Absolute path to the vault
        - total_files: Total number of files in vault
        - markdown_files: Number of markdown files
        - total_directories: Number of directories
        - vault_size_bytes: Total size of all files in bytes
        - last_modified: Most recent modification time across all files
        - file_extensions: Count of files by extension
        - largest_files: List of largest files (top 10)
    
    Raises:
        ValueError: If there's an error accessing the vault
    """
    try:
        vault_path = get_vault_path()
        
        total_files = 0
        markdown_files = 0
        total_directories = 0
        total_size = 0
        last_modified = 0
        extension_counts = {}
        file_sizes = []
        
        # Walk through entire vault
        for item in vault_path.rglob('*'):
            if item.is_file():
                total_files += 1
                stat = item.stat()
                file_size = stat.st_size
                total_size += file_size
                
                # Track largest files
                relative_path = str(item.relative_to(vault_path))
                file_sizes.append({
                    'path': relative_path,
                    'size': file_size,
                    'modified': stat.st_mtime
                })
                
                # Track modification times
                if stat.st_mtime > last_modified:
                    last_modified = stat.st_mtime
                
                # Count by extension
                ext = item.suffix.lower()
                if not ext:
                    ext = '(no extension)'
                extension_counts[ext] = extension_counts.get(ext, 0) + 1
                
                # Count markdown files
                if is_markdown_file(item):
                    markdown_files += 1
            
            elif item.is_dir():
                total_directories += 1
        
        # Sort files by size (largest first)
        file_sizes.sort(key=lambda x: x['size'], reverse=True)
        
        return {
            'vault_path': str(vault_path),
            'total_files': total_files,
            'markdown_files': markdown_files,
            'total_directories': total_directories,
            'vault_size_bytes': total_size,
            'vault_size_mb': round(total_size / (1024 * 1024), 2),
            'last_modified': last_modified,
            'last_modified_iso': datetime.fromtimestamp(last_modified).isoformat() if last_modified > 0 else None,
            'file_extensions': extension_counts,
            'largest_files': file_sizes[:10]
        }
        
    except Exception as e:
        raise ValueError(f"Error getting vault info: {str(e)}")

@mcp.resource("obsidian://usage-instructions")
def usage_instructions() -> str:
    """
    Get custom usage instructions for this Obsidian vault.
    
    Checks for instructions in priority order:
    1. OBSIDIAN_USAGE_INSTRUCTIONS environment variable
    2. CLAUDE.md file in vault root
    3. Default message if neither are available
    
    Returns:
        String containing usage instructions or default message
    """
    try:
        # Check environment variable first
        env_instructions = os.environ.get("OBSIDIAN_USAGE_INSTRUCTIONS")
        if env_instructions and env_instructions.strip():
            return env_instructions.strip()
        
        # Check for CLAUDE.md file in vault root
        try:
            vault_path = get_vault_path()
            claude_md_path = vault_path / "CLAUDE.md"
            if claude_md_path.exists() and claude_md_path.is_file():
                with open(claude_md_path, 'r', encoding='utf-8') as f:
                    claude_content = f.read().strip()
                if claude_content:
                    return claude_content
        except Exception:
            # If we can't read CLAUDE.md, continue to default
            pass
        
        # Default fallback
        return "No custom usage instructions specified for this Obsidian vault."
        
    except Exception as e:
        return f"Error retrieving usage instructions: {str(e)}"

if __name__ == "__main__":
    # Validate environment on startup
    try:
        get_vault_path()
        print(f"Obsidian Vault MCP Server starting with vault: {get_vault_path()}", file=sys.stderr)
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    
    mcp.run()