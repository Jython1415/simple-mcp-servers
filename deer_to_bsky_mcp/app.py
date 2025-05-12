"""
Deer.social to Bluesky MCP - Main application module.

This module provides an MCP server that converts deer.social URLs to Bluesky AT URIs.
"""

import re
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP


# Create the FastMCP server
mcp = FastMCP("Deer to Bluesky Converter")


def convert_deer_to_bluesky(deer_url: str) -> Optional[str]:
    """
    Convert a deer.social URL to Bluesky AT URI format.
    
    Args:
        deer_url: The deer.social URL to convert
        
    Returns:
        The converted AT URI if successful, None otherwise
        
    Example:
        From: https://deer.social/profile/did:plc:h25avmes6g7fgcddc3xj7qmg/post/3loxuoxb5ts2w
        To: at://did:plc:h25avmes6g7fgcddc3xj7qmg/app.bsky.feed.post/3loxuoxb5ts2w
    """
    # Regular expression to extract DID and post ID from profile post URLs
    profile_post_pattern = r'https?://deer\.social/profile/(did:[^/]+)/post/([^/]+)'
    profile_post_match = re.match(profile_post_pattern, deer_url)
    
    if profile_post_match:
        did = profile_post_match.group(1)
        post_id = profile_post_match.group(2)
        return f"at://{did}/app.bsky.feed.post/{post_id}"
    
    # Regular expression for profile URLs (without post)
    profile_pattern = r'https?://deer\.social/profile/(did:[^/]+)/?$'
    profile_match = re.match(profile_pattern, deer_url)
    
    if profile_match:
        did = profile_match.group(1)
        return f"at://{did}"
    
    return None


@mcp.tool()
def convert_deer_to_bsky(url: str) -> dict:
    """
    Convert a deer.social URL to a Bluesky AT URI.
    
    Args:
        url: The deer.social URL to convert (e.g., https://deer.social/profile/did:plc:abc123/post/xyz789)
        
    Returns:
        A dictionary containing the converted AT URI
        
    Raises:
        ValueError: If the URL is not a valid deer.social URL
    """
    result = convert_deer_to_bluesky(url)
    
    if not result:
        raise ValueError("Invalid deer.social URL or unsupported format")
    
    return {"at_uri": result}


def start():
    """Start the MCP server."""
    print("Starting Deer.social to Bluesky MCP server...", file=sys.stderr)
    mcp.run()


if __name__ == "__main__":
    start()
