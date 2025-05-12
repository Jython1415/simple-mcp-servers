#!/bin/bash
# test.sh - Test the deer-to-bsky MCP server

# Exit on any error
set -e

# Define variables
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$DIR/.venv"

# Install dependencies if needed
if [ ! -d "$VENV_DIR" ]; then
    echo "Installing dependencies..."
    cd "$DIR"
    uv venv
    uv pip install fastmcp
fi

echo "Testing deer-to-bsky MCP server..."
echo "This will start the server in the foreground."
echo ""
echo "IMPORTANT: MCP servers use JSON-RPC over stdio."
echo "The server should respond automatically to initialization messages."
echo "When you paste a JSON request, the response goes to stdout,"
echo "which may not be visible in your terminal, but the MCP server is working."
echo "Debug logs will be printed to stderr so you can see activity."
echo ""
echo "Example test input (paste this in after the server starts):"
echo '{"jsonrpc":"2.0","id":"1","method":"tool/convert_deer_to_bsky","params":{"url":"https://deer.social/profile/did:plc:h25avmes6g7fgcddc3xj7qmg/post/3loxuoxb5ts2w"}}'
echo ""
echo "The server should stay running until terminated."
echo "Starting server in 3 seconds..."
sleep 3

# Run directly with uv
cd "$DIR"
uv run python -m deer_to_bsky
