# Deer.social to Bluesky MCP Server

A simple MCP (Multi-Context Provider) server that converts deer.social links to Bluesky-compatible formats for use with Claude's Bluesky MCP tools.

## Features

- Converts deer.social post URLs to Bluesky AT URI format
- Identifies profile URLs (though handle resolution requires additional steps)
- Provides direct parameters for use with existing Bluesky tools

## Installation

1. Create a Python virtual environment using `uv`:

```bash
cd /Users/Joshua/Documents/_programming/deer-to-bsky-mcp
uv venv
source .venv/bin/activate  # On macOS/Linux
# or .venv\Scripts\activate # On Windows
```

2. Install dependencies:

```bash
uv pip install fastmcp
```

## Usage

Run the server:

```bash
python deer_to_bsky.py
```

The server communicates through stdio using JSON-RPC, which makes it compatible with Claude's MCP integration.

## Example

Converting: `https://deer.social/profile/did:plc:h25avmes6g7fgcddc3xj7qmg/post/3loxuoxb5ts2w`

Results in:
- AT URI: `at://did:plc:h25avmes6g7fgcddc3xj7qmg/app.bsky.feed.post/3loxuoxb5ts2w`
- Bluesky tool to use: `get-post-thread`
- Parameters: `{"uri": "at://did:plc:h25avmes6g7fgcddc3xj7qmg/app.bsky.feed.post/3loxuoxb5ts2w"}`

## Connecting to Claude

Add to Claude's config.json to enable this MCP server.
