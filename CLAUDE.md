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
...                              # Various smaller MCP server files
├── time_god_mcp.py              # Large MCP server (3.6MB) - Scrabble word list
└── CLAUDE.md                    # This file - collaboration notes
```

## Development Patterns

### Standard Structure
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
4. **Structure**:
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
- **Token Management**: Include max_files/max_results parameters with sensible defaults
- **Response Metadata**: Add files_found, truncated fields for large result sets
- **Backward Compatibility**: New parameters must have defaults, maintain existing response structure

## Testing and Development Lessons

### Testing MCP Functions
- **Problem**: Functions decorated with `@mcp.tool()` cannot be called directly during testing
- **Solution**: Create wrapper functions that replicate the core logic rather than trying to access decorated functions
- **Pattern**: Use mock data with `tempfile.mkdtemp()` and environment variables for testing

### Test Script Structure
```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["fastmcp", "pydantic", "python-frontmatter", "pyyaml"]
# ///
```

### Token Limit Management
- **Default Limits**: max_files=100, max_results=50, max_depth=3
- **Performance Options**: lazy_parsing=True, include_content=False
- **Response Structure**: Always include metadata about truncation:
  ```python
  {
      # ... normal fields ...
      'files_found': total_found,
      'truncated': total_found > returned_count
  }
  ```

### Environment Management in Tests
- Save/restore original environment variables
- Reset global state between tests (`module.GLOBAL_VAR = None`)
- Use try/finally blocks for cleanup

## Known Issues/Todo

- None

## Collaboration Notes

- **User Preferences**: Uses macOS, Obsidian-flavor markdown
- **Workflow**: Expects proactive tool usage and examination of existing content
- **Style**: Maintain consistency with existing patterns and documentation
- **Approach**: Use multiple tools/approaches when single method insufficient

---

*Last Updated: 2025-07-03*
*Created by: Claude (Sonnet 4) for collaboration with Joshua*
