#!/bin/bash
# install.sh - Set up the deer-to-bsky MCP server

# Exit on any error
set -e

# Define variables
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$DIR/.venv"

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    cd "$DIR"
    uv venv
fi

# Install dependencies
echo "Installing dependencies..."
cd "$DIR"
uv pip install fastmcp

echo "Installation complete!"
echo ""
echo "To add this MCP server to Claude, add the following to your Claude config:"
echo ""
echo '  "deer-to-bsky": {'
echo '    "command": "uv",'
echo '    "args": ['
echo '      "run",'
echo '      "python",'
echo '      "-m",'
echo '      "deer_to_bsky",'
echo '      "--directory",'
echo '      "'"$DIR"'"'
echo '    ]'
echo '  }'
echo ""
echo "You can find a complete configuration example in claude_config_example.json"
