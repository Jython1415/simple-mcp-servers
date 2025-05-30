# CLAUDE.md - Collaboration Notes

This file contains notes for Claude to understand the project structure and facilitate future collaboration on MCP server development.

## Project Overview

**Repository**: `simple-mcp-servers`  
**Purpose**: Collection of one-file MCP (Model Context Protocol) servers written in Python  
**License**: MIT License (Copyright 2025 Joshua Shew)  
**Primary Language**: Python
**Dependency Management**: PEP 723 inline script metadata (self-contained scripts)

## Project Structure

```
simple-mcp-servers/
├── .git/                         # Git repository
├── .gitignore                   # Python-specific gitignore
├── LICENSE                      # MIT License
├── README.md                    # Basic project description
├── __pycache__/                 # Python cache (gitignored)
├── deer_to_bsky.py              # MCP server for deer.social → Bluesky URL conversion
├── github_repo_mcp.py           # MCP server for filesystem-like navigation of GitHub repositories
├── large_file_reader_mcp.py     # MCP server for reading large files in parts
├── time_god_mcp.py              # Large MCP server (3.6MB) - Scrabble word list
└── CLAUDE.md                    # This file - collaboration notes
```

## Existing MCP Servers

### 1. deer_to_bsky.py
- **Purpose**: Converts deer.social URLs to Bluesky-compatible formats
- **Framework**: FastMCP
- **Dependencies**: `fastmcp`, `pydantic`, `httpx`
- **Key Features**:
  - Regex-based URL parsing for deer.social profiles and posts
  - DID-to-handle resolution using Bluesky API
  - Converts to AT URI format for posts
  - Returns structured data for Bluesky tool compatibility
  - Fallback to search when DID resolution fails
  - Includes error handling and debug logging
- **Tools Provided**: `convert_deer_to_bsky`
- **Recent Updates**: 
  - **May 29, 2025**: Added DID resolution capability to fix profile retrieval issue
  - Now resolves DIDs like `did:plc:xyz` to handles like `user.bsky.social`
  - Falls back to `search-people` tool when DID resolution fails

**Configuration Example**:
```json
{
  "mcpServers": {
    "deer-to-bsky": {
      "command": "/Users/Joshua/.local/bin/uv",
      "args": [
        "run",
        "--script",
        "/path/to/deer_to_bsky.py"
      ]
    }
  }
}
```

**Direct Execution**: The file is executable and can be run directly:
```bash
./deer_to_bsky.py
```

### 2. large_file_reader_mcp.py
- **Purpose**: Read large files in parts, addressing limitations of standard file reading tools
- **Framework**: FastMCP
- **Dependencies**: `fastmcp`, `pydantic`
- **Key Features**:
  - Line-based reading with specific ranges
  - Head/tail operations for efficient file inspection
  - Byte-based reading for binary file support
  - Pattern search with context lines
  - File metadata without full content loading
  - Chunked reading for incremental processing
  - Encoding detection and error handling
- **Tools Provided**: `get_file_stats`, `read_file_lines`, `read_file_head`, `read_file_tail`, `read_file_bytes`, `search_file_lines`, `read_file_chunk`
- **Use Cases**: Large log files, source code inspection, dataset analysis, file headers/footers

**Configuration Example**:
```json
{
  "mcpServers": {
    "large-file-reader": {
      "command": "/Users/Joshua/.local/bin/uv",
      "args": [
        "run",
        "--script",
        "/path/to/large_file_reader_mcp.py"
      ]
    }
  }
}
```

**Direct Execution**: The file is executable and can be run directly:
```bash
./large_file_reader_mcp.py
```

### 3. github_repo_mcp.py
- **Purpose**: Provides filesystem-like navigation of public GitHub repositories with intelligent token-based safety limits
- **Framework**: FastMCP
- **Dependencies**: `fastmcp`, `pydantic`, `requests`, `tiktoken`
- **Key Features**:
  - Filesystem-like directory listing and navigation
  - Recursive directory tree view with configurable depth
  - File metadata retrieval without reading contents
  - Intelligent file reading with token safety limits (5,000 token default)
  - Binary file detection and handling
  - Rate limiting awareness with helpful error messages
  - Optional GitHub token authentication for higher limits
  - Token counting using tiktoken to prevent context overflow
  - Self-documenting error messages with alternative suggestions
- **Tools Provided**: `repo_list_directory`, `repo_tree_view`, `repo_file_info`, `repo_read_file`
- **Environment Variables**: `GITHUB_TOKEN` (optional for higher rate limits)
- **Use Cases**: Code exploration, repository analysis, documentation reading, file inspection
- **Safety Features**: Binary detection, token limits, intelligent truncation with continuation guidance

**Configuration Example**:
```json
{
  "mcpServers": {
    "github-repo": {
      "command": "/Users/Joshua/.local/bin/uv",
      "args": [
        "run",
        "--script",
        "/path/to/github_repo_mcp.py"
      ]
    }
  }
}
```

**Direct Execution**: The file is executable and can be run directly:
```bash
./github_repo_mcp.py
```

### 4. time_god_mcp.py
- **Purpose**: Scrabble-related MCP server
- **Size**: 3.6MB (contains entire Scrabble word list embedded in code)
- **Created**: May 22, 2025
- **Architecture**: Simple logic with large embedded dataset
- **Note**: Large file size is due to word list data, not complex code

## Development Patterns

### Standard Structure (Based on deer_to_bsky.py)
1. **Shebang Line**: `#!/usr/bin/env -S uv run --script` for direct execution
2. **PEP 723 Metadata Block**: Dependencies and Python version requirements
3. **Header Docstring**: Comprehensive documentation with Claude configuration example
4. **Imports**: Standard Python imports + MCP framework imports
5. **Server Creation**: `mcp = FastMCP("server-name")`
6. **Tool Definitions**: Functions decorated with `@mcp.tool()`
7. **Server Execution**: `mcp.run()`

### Dependencies Management
- Uses `uv` package manager
- Dependencies declared using PEP 723 inline script metadata
- No requirements.txt file needed (dependencies embedded in each script)
- All servers use the same dependencies: `fastmcp` and `pydantic`
- Python version requirement: `>=3.11`

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
2. **PEP 723 Header**: Start every new server with:
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
3. **Documentation**: Include comprehensive docstring with:
   - Purpose description
   - Claude configuration example (using `--script`)
   - Usage instructions
4. **Structure**: Follow deer_to_bsky.py pattern:
   - Shebang line
   - PEP 723 metadata
   - Header documentation
   - Imports
   - Server creation
   - Tool definitions with type hints
   - Error handling
   - Server execution
5. **Make Executable**: Run `chmod +x your_server_mcp.py`
6. **Testing**: Consider adding test files following existing pattern

### Configuration Management
- Each server should include its own Claude configuration example
- Use uv with `--script` flag for running PEP 723 scripts
- Dependencies are declared in the script itself
- Maintain single-file architecture for simplicity
- Scripts can be run directly if made executable

### Best Practices
- Include comprehensive type hints and docstrings
- Implement structured error handling
- Add debug logging for troubleshooting
- Follow existing naming conventions
- Keep servers focused and single-purpose

## Known Issues/Todo

1. **Documentation**: Expand README.md with individual server descriptions and PEP 723 benefits
2. **Testing**: Consider adding unit tests for server functionality
3. ~~**Dependencies**: Evaluate if requirements.txt would be beneficial~~ **SOLVED** - Using PEP 723 inline metadata
4. ~~**Tool Limitations**: Current file reading tools don't handle very large files well~~ **SOLVED** - Implemented large file reader MCP
5. ~~**DID Resolution**: deer_to_bsky.py couldn't resolve DIDs to handles for profile lookups~~ **SOLVED** - Added DID-to-handle resolution via Bluesky API (May 29, 2025)

## Collaboration Notes

- **User Preferences**: Uses macOS, Obsidian-flavor markdown
- **Workflow**: Expects proactive tool usage and examination of existing content
- **Style**: Maintain consistency with existing patterns and documentation
- **Approach**: Use multiple tools/approaches when single method insufficient

## Tool Limitations Discovered

- **Large File Reading**: ~~File reading tools struggle with files >1MB (like time_god_mcp.py)~~ **SOLVED** - Implemented `large_file_reader_mcp.py` for partial file access
- **Sandboxed Python**: `run_python_code` tool is sandboxed and cannot access external files
- **File Permissions**: `run_python_code` tool cannot modify file permissions (e.g., `chmod +x`) due to sandboxed environment
- **Partial File Access**: ~~No current tool for reading just the beginning/end of large files~~ **SOLVED** - Now available via large file reader MCP
- **Future Enhancement**: User may provide read-only command-line access for better file inspection

---

*Last Updated: May 30, 2025*  
*Created by: Claude (Sonnet 4) for collaboration with Joshua*
*Transitioned to PEP 723: May 29, 2025 by Claude (Opus 4)*