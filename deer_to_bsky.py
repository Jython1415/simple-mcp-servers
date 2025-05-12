# /// script
# dependencies = ["fastmcp"]
# ///

"""
A simple MCP server for converting deer.social links to Bluesky-compatible formats.

Usage with uv:
1. Install uv: pip install uv
2. Create venv and install dependencies: uv venv && source .venv/bin/activate && uv pip install fastmcp
3. Run the script: uv run python -m deer_to_bsky
"""

from fastmcp import FastMCP
from pydantic import Field
import re
from typing import Dict, Any

# Initialize the FastMCP server
mcp = FastMCP(
    "deer-to-bsky",
    dependencies=["fastmcp"],
)

# Regular expressions for parsing deer.social URLs
DEER_PROFILE_REGEX = r"https://deer\.social/profile/([^/]+)/?$"
DEER_POST_REGEX = r"https://deer\.social/profile/([^/]+)/post/([^/]+)/?$"

@mcp.tool()
async def convert_deer_to_bsky(
    url: str = Field(description="A deer.social URL to convert")
) -> Dict[str, Any]:
    """
    Convert a deer.social URL to formats compatible with Bluesky tools.
    
    Args:
        url: A deer.social URL (e.g., https://deer.social/profile/did:plc:xyz/post/123)
        
    Returns:
        A dictionary containing converted formats for use with Bluesky tools
    """
    result = {
        "original_url": url,
        "type": None,
        "did": None,
        "post_id": None,
        "at_uri": None,
        "bluesky_tool": None,
        "bluesky_params": {},
        "error": None
    }
    
    # Match post URL
    post_match = re.match(DEER_POST_REGEX, url)
    if post_match:
        result["type"] = "post"
        result["did"] = post_match.group(1)
        result["post_id"] = post_match.group(2)
        result["at_uri"] = f"at://{result['did']}/app.bsky.feed.post/{result['post_id']}"
        result["bluesky_tool"] = "get-post-thread"
        result["bluesky_params"] = {"uri": result["at_uri"]}
        return result
    
    # Match profile URL
    profile_match = re.match(DEER_PROFILE_REGEX, url)
    if profile_match:
        result["type"] = "profile"
        result["did"] = profile_match.group(1)
        # Note: We'd need to convert DID to handle for proper use with get-profile
        result["bluesky_tool"] = "get-profile"
        result["error"] = "Profile URLs require a handle, not just a DID. You may need to search for this user."
        return result
    
    # If no match, return an error
    result["error"] = f"Unable to parse deer.social URL: {url}"
    return result

@mcp.tool()
async def test_conversion() -> Dict[str, Any]:
    """Run a test conversion on the example URL"""
    test_url = "https://deer.social/profile/did:plc:h25avmes6g7fgcddc3xj7qmg/post/3loxuoxb5ts2w"
    result = await convert_deer_to_bsky(test_url)
    return result

def main():
    print("Starting deer-to-bsky MCP server...")
    print("This server provides tools for converting deer.social links to Bluesky formats")
    print("Server is running and communicating through stdio with JSON-RPC")
    # FastMCP handles the server startup automatically

if __name__ == "__main__":
    main()
