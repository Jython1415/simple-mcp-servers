#!/bin/bash

# Setup and run the deer-to-bsky MCP server

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    /Users/Joshua/.local/bin/uv venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
/Users/Joshua/.local/bin/uv pip install fastmcp

# Run the server
echo "Starting MCP server..."
python deer_to_bsky.py
