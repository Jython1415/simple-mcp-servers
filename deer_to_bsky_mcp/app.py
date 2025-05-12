"""
Deer.social to Bluesky MCP - Main application module.

This module provides an MCP server that converts deer.social URLs to Bluesky AT URIs.
"""

import re
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Deer.social to Bluesky Converter MCP")


class ConvertRequest(BaseModel):
    """Request model for URL conversion."""
    url: str  # Deer.social URL to convert


class ConvertResponse(BaseModel):
    """Response model for URL conversion."""
    at_uri: str  # Converted AT URI for Bluesky


class MCPSpecResponse(BaseModel):
    """Response model for MCP specification."""
    name: str
    functions: List[Dict[str, Any]]


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


@app.get("/")
async def root():
    """Root endpoint with basic info."""
    return {
        "name": "Deer.social to Bluesky MCP Converter",
        "description": "Converts deer.social URLs to Bluesky AT URIs"
    }


@app.get("/mcp-spec", response_model=MCPSpecResponse)
async def get_mcp_spec():
    """Return the MCP specification for this server."""
    return {
        "name": "deer-to-bsky",
        "functions": [
            {
                "name": "convert-deer-to-bsky",
                "description": "Convert a deer.social URL to Bluesky AT URI format.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The deer.social URL to convert"
                        }
                    },
                    "required": ["url"]
                }
            }
        ]
    }


@app.post("/convert-deer-to-bsky", response_model=ConvertResponse)
async def convert_url(request: ConvertRequest):
    """Convert a deer.social URL to a Bluesky AT URI."""
    result = convert_deer_to_bluesky(request.url)
    
    if not result:
        raise HTTPException(
            status_code=400, 
            detail="Invalid deer.social URL or unsupported format"
        )
    
    return {"at_uri": result}


def start():
    """Entry point for starting the server."""
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    start()
