# CLAUDE.md - Collaboration Notes

This file contains notes for Claude to understand the project structure and facilitate future collaboration on MCP server development.

## Project Overview

**Repository**: `simple-mcp-servers`  
**Purpose**: Collection of one-file MCP (Model Context Protocol) servers written in Python  
**License**: MIT License (Copyright 2025 Joshua Shew)  
**Primary Language**: Python

## Project Structure

```
simple-mcp-servers/
├── .git/                    # Git repository
├── .gitignore              # Python-specific gitignore
├── LICENSE                 # MIT License
├── README.md               # Basic project description
├── __pycache__/            # Python cache (gitignored)
├── deer_to_bsky.py         # MCP server for deer.social → Bluesky URL conversion
├── time_god_mcp.py         # Large MCP server (3.6MB) - purpose TBD
└── CLAUDE.md               # This file - collaboration notes
```

## Existing MCP Servers

### 1. deer_to_bsky.py
- **Purpose**: Converts deer.social URLs to Bluesky-compatible formats
- **Framework**: FastMCP
- **Dependencies**: `fastmcp`, `pydantic`
- **Key Features**:
  - Regex-based URL parsing for deer.social profiles and posts
  - Converts to AT URI format
  - Returns structured data for Bluesky tool compatibility
  - Includes error handling and debug logging
- **Tools Provided**: `convert_deer_to_bsky`

**Configuration Example**:
```json
{
  "mcpServers": {
    "deer-to-bsky": {
      "command": "/Users/Joshua/.local/bin/uv",
      "args": [
        "run",
        "--with",
        "fastmcp",
        "--with",
        "pydantic",
        "/path/to/deer_to_bsky.py"
      ]
    }
  }
}
```

### 2. time_god_mcp.py
- **Purpose**: Scrabble-related MCP server
- **Size**: 3.6MB (contains entire Scrabble word list embedded in code)
- **Created**: May 22, 2025
- **Architecture**: Simple logic with large embedded dataset
- **Note**: Large file size is due to word list data, not complex code

## Development Patterns

### Standard Structure (Based on deer_to_bsky.py)
1. **Header Docstring**: Comprehensive documentation with Claude configuration example
2. **Imports**: Standard Python imports + MCP framework imports
3. **Server Creation**: `mcp = FastMCP("server-name")`
4. **Tool Definitions**: Functions decorated with `@mcp.tool()`
5. **Server Execution**: `mcp.run()`

### Dependencies Management
- Uses `uv` package manager
- Dependencies specified via `--with` flags in configuration
- No requirements.txt file (dependencies managed at runtime)

### Code Style Observations
- Type hints using Pydantic `Field` for parameter descriptions
- Comprehensive docstrings with usage examples
- Error handling with structured return objects
- Debug logging to stderr
- Single-file servers (no module splitting)

## Development Environment

### Tools Used
- **Package Manager**: uv
- **MCP Framework**: FastMCP
- **Type System**: Pydantic for parameter validation
- **Runtime**: Python 3.13 (based on pycache files)

### .gitignore Coverage
- Python cache files (`__pycache__/`, `*.pyc`, etc.)
- Virtual environments (`.env`, `.venv`, etc.)
- UV cache (`.uv/`)
- IDE files (`.idea/`, `.vscode/`, etc.)
- Distribution files (`dist/`, `build/`, etc.)
- Local config (`config.json`)

## Future Development Guidelines

### Adding New MCP Servers

1. **File Naming**: Use descriptive names with `_mcp.py` suffix
2. **Documentation**: Include comprehensive docstring with:
   - Purpose description
   - Claude configuration example
   - Dependencies list
   - Usage instructions
3. **Structure**: Follow deer_to_bsky.py pattern:
   - Header documentation
   - Imports
   - Server creation
   - Tool definitions with type hints
   - Error handling
   - Server execution
4. **Testing**: Consider adding test files following existing pattern

### Configuration Management
- Each server should include its own Claude configuration example
- Use uv with `--with` flags for dependency management
- Maintain single-file architecture for simplicity

### Best Practices
- Include comprehensive type hints and docstrings
- Implement structured error handling
- Add debug logging for troubleshooting
- Follow existing naming conventions
- Keep servers focused and single-purpose

## Known Issues/Todo

1. **Documentation**: Expand README.md with individual server descriptions
2. **Testing**: Consider adding unit tests for server functionality
3. **Dependencies**: Evaluate if requirements.txt would be beneficial
4. **Tool Limitations**: Current file reading tools don't handle very large files well

## Collaboration Notes

- **User Preferences**: Uses macOS, Obsidian-flavor markdown
- **Workflow**: Expects proactive tool usage and examination of existing content
- **Style**: Maintain consistency with existing patterns and documentation
- **Approach**: Use multiple tools/approaches when single method insufficient

## Tool Limitations Discovered

- **Large File Reading**: File reading tools struggle with files >1MB (like time_god_mcp.py)
- **Sandboxed Python**: `run_python_code` tool is sandboxed and cannot access external files
- **Partial File Access**: No current tool for reading just the beginning/end of large files
- **Future Enhancement**: User may provide read-only command-line access for better file inspection

---

*Last Updated: May 29, 2025*  
*Created by: Claude (Sonnet 4) for collaboration with Joshua*