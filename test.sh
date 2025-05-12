#!/bin/bash
# test.sh - Test the deer-to-bsky MCP server

# Exit on any error
set -e

# Define variables
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$DIR/.venv"

# Make sure virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found. Running install script first..."
    bash "$DIR/install.sh"
fi

echo "Testing deer-to-bsky MCP server..."
echo "This will start the server in the foreground."
echo "Try sending it JSON-RPC messages to test it."
echo "Press Ctrl+C to stop the server."
echo ""
echo "Example test input (paste this in after the server starts):"
echo '{"jsonrpc":"2.0","id":"1","method":"tool/convert_deer_to_bsky","params":{"url":"https://deer.social/profile/did:plc:h25avmes6g7fgcddc3xj7qmg/post/3loxuoxb5ts2w"}}'
echo ""
echo "Starting server in 3 seconds..."
sleep 3

# Run the server
cd "$DIR"
/Users/Joshua/.local/bin/uv run python deer_to_bsky.py
