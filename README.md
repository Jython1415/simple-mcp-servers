# Simple MCP Servers

Repository for holding one-file MCP servers written in Python

## Overview

This repository contains self-contained, single-file MCP (Model Context Protocol) servers that can be easily integrated into Claude Desktop or other MCP-compatible applications. Each server is designed to be standalone with dependencies declared using PEP 723 inline script metadata.

## Features

- **Self-contained scripts** - Each MCP server is a single Python file with embedded dependencies
- **PEP 723 compliant** - Uses inline script metadata for dependency management
- **Direct execution** - Scripts can be run directly with `uv` or executed as standalone programs
- **No setup required** - Dependencies are automatically handled by `uv` at runtime

## Available MCP Servers

### 1. `deer_to_bsky.py`
Converts deer.social URLs to Bluesky-compatible AT URI formats for seamless integration with Bluesky tools.

### 2. `large_file_reader_mcp.py`
Provides efficient methods for reading large files in chunks, including line-based reading, head/tail operations, byte-based access, and pattern searching with context.

### 3. `time_god_mcp.py`
A Scrabble word validation server containing the complete SOWPODS word list for word game applications.

## Installation & Usage

### Prerequisites
- Python >= 3.11
- [uv](https://github.com/astral-sh/uv) package manager

### Running a Server

Each server can be run in multiple ways:

#### Method 1: Direct execution (if executable)
```bash
./deer_to_bsky.py
```

#### Method 2: Using uv
```bash
uv run --script deer_to_bsky.py
```

### Claude Desktop Configuration

Add any server to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "deer-to-bsky": {
      "command": "/path/to/uv",
      "args": [
        "run",
        "--script",
        "/path/to/deer_to_bsky.py"
      ]
    }
  }
}
```

## Development

### Creating a New MCP Server

1. Start with the PEP 723 header:
```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastmcp",
#     "pydantic"
# ]
# ///
```

2. Follow the existing pattern for structure and documentation
3. Make the file executable: `chmod +x your_server_mcp.py`

### Dependencies

All servers use:
- `fastmcp` - MCP framework
- `pydantic` - Data validation

Dependencies are declared inline using PEP 723 format, eliminating the need for `requirements.txt` or other external dependency files.

## Claude Instructions

See `CLAUDE.md` for detailed collaboration notes and development guidelines.

## License

MIT License - See LICENSE file for details

## Author

Joshua Shew (2025)
