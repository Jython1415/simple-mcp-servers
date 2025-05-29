#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastmcp",
#     "pydantic",
#     "httpx"
# ]
# ///

"""
# Deer to Bluesky

Simple MCP server for converting share links from deer.social to those compatible with the Bluesky MCP server structure.

## Claude Configuration

Sample configuration below:

```json
{
  "mcpServers": {
    "deer-to-bsky": {
      "command": "/Users/Joshua/.local/bin/uv",
      "args": [
        "run",
        "--script",
        "/Users/Joshua/Documents/_programming/simple-mcp-servers/deer_to_bsky.py"
      ]
    },
    "other servers here": {}
  }
}
```

## History

If you check the commit history, you can see that I initially vibe coded this with Claude and it was a mess. Afterwards, I fixed up the boilerplate/structure and it works fine.

TBH the failure was my own. I forgot how to set up a MCP server nicely and this was the first time I used FastMCP.
"""

import re
import sys
import time
import json
import signal
import threading
from typing import Dict, Any, Optional
from fastmcp import FastMCP
from pydantic import Field
import httpx


# Create server
mcp = FastMCP("deer-to-bsky")

# Regular expressions for parsing deer.social URLs
DEER_PROFILE_REGEX = r"https://deer\.social/profile/([^/]+)/?$"
DEER_POST_REGEX = r"https://deer\.social/profile/([^/]+)/post/([^/]+)/?$"

# Bluesky API endpoint
BSKY_API_BASE = "https://bsky.social/xrpc"


def resolve_did_to_handle(did: str) -> Optional[str]:
    """
    Resolve a DID to a handle using the AT Protocol.

    Args:
        did: The DID to resolve (e.g., "did:plc:xyz...")

    Returns:
        The handle if found, None otherwise
    """
    try:
        print(f"[DEBUG] Resolving DID to handle: {did}", file=sys.stderr)

        with httpx.Client(timeout=10.0) as client:
            # First try: Use the PLC directory to get the DID document
            plc_response = client.get(f"https://plc.directory/{did}")

            if plc_response.status_code == 200:
                plc_data = plc_response.json()
                # Look for handle in alsoKnownAs field
                also_known_as = plc_data.get("alsoKnownAs", [])
                for aka in also_known_as:
                    if aka.startswith("at://"):
                        handle = aka.replace("at://", "")
                        print(
                            f"[DEBUG] Resolved {did} to handle via PLC: {handle}",
                            file=sys.stderr,
                        )
                        return handle

            # Second try: Use Bluesky API repo describe
            repo_response = client.get(
                f"{BSKY_API_BASE}/com.atproto.repo.describeRepo", params={"repo": did}
            )

            if repo_response.status_code == 200:
                repo_data = repo_response.json()
                handle = repo_data.get("handle")
                if handle:
                    print(
                        f"[DEBUG] Resolved {did} to handle via Bluesky API: {handle}",
                        file=sys.stderr,
                    )
                    return handle

    except Exception as e:
        print(f"[DEBUG] Error resolving DID {did}: {e}", file=sys.stderr)

    return None


@mcp.tool()
def convert_deer_to_bsky(
    url: str = Field(description="A deer.social URL to convert"),
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
        "error": None,
    }

    # Match post URL
    post_match = re.match(DEER_POST_REGEX, url)
    if post_match:
        result["type"] = "post"
        result["did"] = post_match.group(1)
        result["post_id"] = post_match.group(2)
        result["at_uri"] = (
            f"at://{result['did']}/app.bsky.feed.post/{result['post_id']}"
        )
        result["bluesky_tool"] = "get-post-thread"
        result["bluesky_params"] = {"uri": result["at_uri"]}
        print(f"[DEBUG] Converted to AT URI: {result['at_uri']}", file=sys.stderr)
        return result

    # Match profile URL
    profile_match = re.match(DEER_PROFILE_REGEX, url)
    if profile_match:
        result["type"] = "profile"
        result["did"] = profile_match.group(1)
        result["bluesky_tool"] = "get-profile"

        # Try to resolve DID to handle
        handle = resolve_did_to_handle(result["did"])
        if handle:
            result["bluesky_params"] = {"handle": handle}
            print(
                f"[DEBUG] Successfully resolved profile: {result['did']} -> {handle}",
                file=sys.stderr,
            )
        else:
            # If we can't resolve the DID, suggest using search instead
            result["bluesky_tool"] = "search-people"
            result["bluesky_params"] = {"query": result["did"]}
            result["error"] = (
                f"Could not resolve DID {result['did']} to handle. Trying search instead."
            )
            print(
                f"[DEBUG] Could not resolve DID, suggesting search: {result['did']}",
                file=sys.stderr,
            )

        return result

    # If no match, return an error
    result["error"] = f"Unable to parse deer.social URL: {url}"
    print(f"[DEBUG] Error: {result['error']}", file=sys.stderr)
    return result


mcp.run()
