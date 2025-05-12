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

## History

If you check the commit history, you can see that I initially vibe coded this with Claude and it was a mess. Afterwards, I fixed up the boilerplate/structure and it works fine.

TBH the failure was my own. I forgot how to set up a MCP server nicely and this was the first time I used FastMCP.

