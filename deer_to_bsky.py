# /// script
# dependencies = ["fastmcp"]
# ///

"""
A simple MCP server for converting deer.social links to Bluesky-compatible formats.
"""

import re
import sys
import time
import json
import signal
import threading
from typing import Dict, Any
from fastmcp import FastMCP
from pydantic import Field

# Create the FastMCP server
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
    # Log the request to stderr
    print(f"[DEBUG] Processing URL: {url}", file=sys.stderr)
    
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
        print(f"[DEBUG] Converted to AT URI: {result['at_uri']}", file=sys.stderr)
        return result
    
    # Match profile URL
    profile_match = re.match(DEER_PROFILE_REGEX, url)
    if profile_match:
        result["type"] = "profile"
        result["did"] = profile_match.group(1)
        # Note: We'd need to convert DID to handle for proper use with get-profile
        result["bluesky_tool"] = "get-profile"
        result["error"] = "Profile URLs require a handle, not just a DID. You may need to search for this user."
        print(f"[DEBUG] Processed profile: {result['did']}", file=sys.stderr)
        return result
    
    # If no match, return an error
    result["error"] = f"Unable to parse deer.social URL: {url}"
    print(f"[DEBUG] Error: {result['error']}", file=sys.stderr)
    return result

@mcp.tool()
async def test_conversion() -> Dict[str, Any]:
    """Run a test conversion on the example URL"""
    test_url = "https://deer.social/profile/did:plc:h25avmes6g7fgcddc3xj7qmg/post/3loxuoxb5ts2w"
    print(f"[DEBUG] Testing with URL: {test_url}", file=sys.stderr)
    result = await convert_deer_to_bsky(test_url)
    print(f"[DEBUG] Test result: {json.dumps(result)}", file=sys.stderr)
    return result

# Set up a signal handler for graceful shutdown
def signal_handler(sig, frame):
    print("\nReceived signal to shutdown.", file=sys.stderr)
    sys.exit(0)

# Keep the server alive with a dedicated thread
def keep_alive():
    while True:
        try:
            time.sleep(10)
            print("[DEBUG] Server still running...", file=sys.stderr)
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    print("Starting deer-to-bsky MCP server...", file=sys.stderr)
    print("This server provides tools for converting deer.social links to Bluesky formats", file=sys.stderr)
    print("Server is running and communicating through stdio with JSON-RPC", file=sys.stderr)
    print("Debug logs will appear on stderr", file=sys.stderr)
    
    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start a keep-alive thread
    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
    keep_alive_thread.start()
    
    # Wait for the keep-alive thread to finish (it won't unless the process is terminated)
    # This keeps the main thread alive
    keep_alive_thread.join()
