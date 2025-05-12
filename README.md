# Deer.social to Bluesky MCP Converter

An MCP (Machine Capabilities Protocol) server that converts deer.social URLs to Bluesky AT URIs, allowing AI assistants to process deer.social links and retrieve content from Bluesky.

## Features

- Converts deer.social profile post URLs to Bluesky AT URIs
- Converts deer.social profile URLs to Bluesky AT URIs
- Implements the MCP specification for integration with AI assistants

## Installation

This project uses `uv` for package management. Make sure you have `uv` installed:

```bash
curl -sSf https://astral.sh/uv/install.sh | sh
```

Then, create a virtual environment and install the dependencies:

```bash
# Create and activate a virtual environment
uv venv
source .venv/bin/activate  # On Unix/macOS
# OR .venv\Scripts\activate  # On Windows

# Install dependencies
uv pip install -e .
```

For development dependencies:

```bash
uv pip install -e ".[dev]"
```

## Running the server

```bash
python main.py
```

The server will start at http://localhost:8000

## MCP Protocol

This server implements the Machine Capabilities Protocol (MCP), which uses WebSockets and JSON-RPC for communication. It supports the following functions:

### convert-deer-to-bsky

Converts a deer.social URL to a Bluesky AT URI.

Parameters:
```json
{
  "url": "https://deer.social/profile/did:plc:h25avmes6g7fgcddc3xj7qmg/post/3loxuoxb5ts2w"
}
```

Response:
```json
{
  "at_uri": "at://did:plc:h25avmes6g7fgcddc3xj7qmg/app.bsky.feed.post/3loxuoxb5ts2w"
}
```

## Examples

### Converting a profile post URL

Input: `https://deer.social/profile/did:plc:h25avmes6g7fgcddc3xj7qmg/post/3loxuoxb5ts2w`
Output: `at://did:plc:h25avmes6g7fgcddc3xj7qmg/app.bsky.feed.post/3loxuoxb5ts2w`

### Converting a profile URL

Input: `https://deer.social/profile/did:plc:h25avmes6g7fgcddc3xj7qmg`
Output: `at://did:plc:h25avmes6g7fgcddc3xj7qmg`

## Integration with Claude's Bluesky MCP

This server can be configured in your Claude desktop app configuration to enable conversion of deer.social links.

Example configuration (add to `.dotfiles/claude/claude_desktop_config.template.json`):

```json
"mcpServers": {
  "deer-to-bsky": {
    "command": "/Users/Joshua/.local/bin/uv",
    "args": [
      "--directory",
      "/Users/Joshua/Documents/_programming/deer-to-bsky-mcp",
      "run",
      "python",
      "main.py"
    ],
    "env": {
      "PYTHONUNBUFFERED": "1"
    }
  }
}
```

The `PYTHONUNBUFFERED=1` environment variable ensures that Python stdout/stderr output is sent immediately to the log file, which is helpful for debugging.
