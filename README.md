# Deer to Bluesky

Simple MCP server for converting share links from deer.social to those compatible with the Bluesky MCP server structure.

## Claude Configuration

Sample configuration below:

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
        "/Users/Joshua/Documents/_programming/deer-to-bsky-mcp/deer_to_bsky.py"
      ]
    },
    "other servers here": {}
  }
}
```

