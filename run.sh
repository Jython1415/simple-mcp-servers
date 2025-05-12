#!/bin/bash

# Setup and run the deer-to-bsky MCP server

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    uv venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
uv pip install fastmcp

# Run the server
echo "Starting MCP server..."
python deer_to_bsky.py
