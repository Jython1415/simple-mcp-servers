"""
Deer.social to Bluesky MCP - Main application module.

This module provides an MCP server that converts deer.social URLs to Bluesky AT URIs.
"""

import json
import re
import sys
from typing import Dict, Any, List, Optional, Tuple

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="Deer.social to Bluesky Converter MCP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MCP Protocol version
MCP_VERSION = "2024-11-05"

# Store for active connections
connections = []


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


@app.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for MCP communication."""
    await websocket.accept()
    
    print("MCP connection established", file=sys.stderr)
    connections.append(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            request = json.loads(data)
            
            print(f"Received message: {data}", file=sys.stderr)
            
            method = request.get("method")
            request_id = request.get("id")
            
            if method == "initialize":
                # Handle initialization message
                await handle_initialize(websocket, request)
            elif method == "mcp/listFunctions":
                # Return functions list
                await handle_list_functions(websocket, request)
            elif method == "mcp/invokeFunction":
                # Handle function invocation
                await handle_invoke_function(websocket, request)
            else:
                # Unknown method
                await send_error_response(
                    websocket, 
                    request_id, 
                    -32601, 
                    f"Method not found: {method}"
                )
    
    except WebSocketDisconnect:
        print("Client disconnected", file=sys.stderr)
        if websocket in connections:
            connections.remove(websocket)
    except Exception as e:
        error_msg = f"Error processing request: {str(e)}"
        print(error_msg, file=sys.stderr)
        if websocket in connections:
            await send_error_response(websocket, request_id, -32603, error_msg)


async def handle_initialize(websocket: WebSocket, request: Dict[str, Any]):
    """Handle MCP initialize message."""
    request_id = request.get("id")
    params = request.get("params", {})
    
    # Check protocol version
    protocol_version = params.get("protocolVersion")
    if protocol_version != MCP_VERSION:
        print(f"WARNING: Protocol version mismatch: {protocol_version} != {MCP_VERSION}", file=sys.stderr)
    
    # Log client info
    client_info = params.get("clientInfo", {})
    client_name = client_info.get("name", "unknown")
    client_version = client_info.get("version", "unknown")
    print(f"Client connected: {client_name} v{client_version}", file=sys.stderr)
    
    # Send initialization response
    response = {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "protocolVersion": MCP_VERSION,
            "capabilities": {},
            "serverInfo": {
                "name": "deer-to-bsky-mcp",
                "version": "0.1.0"
            }
        }
    }
    
    await websocket.send_text(json.dumps(response))


async def handle_list_functions(websocket: WebSocket, request: Dict[str, Any]):
    """Handle MCP listFunctions message."""
    request_id = request.get("id")
    
    # Define available functions
    functions = [
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
    
    # Send functions list response
    response = {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "functions": functions
        }
    }
    
    await websocket.send_text(json.dumps(response))


async def handle_invoke_function(websocket: WebSocket, request: Dict[str, Any]):
    """Handle MCP invokeFunction message."""
    request_id = request.get("id")
    params = request.get("params", {})
    
    function_name = params.get("name")
    arguments = params.get("arguments", {})
    
    if function_name == "convert-deer-to-bsky":
        await handle_convert_deer_to_bsky(websocket, request_id, arguments)
    else:
        await send_error_response(
            websocket, 
            request_id, 
            -32601, 
            f"Function not found: {function_name}"
        )


async def handle_convert_deer_to_bsky(websocket: WebSocket, request_id: int, arguments: Dict[str, Any]):
    """Handle convert-deer-to-bsky function invocation."""
    url = arguments.get("url")
    
    if not url:
        await send_error_response(
            websocket, 
            request_id, 
            -32602, 
            "Missing required parameter: url"
        )
        return
    
    result = convert_deer_to_bluesky(url)
    
    if not result:
        await send_error_response(
            websocket, 
            request_id, 
            -32000, 
            "Invalid deer.social URL or unsupported format"
        )
        return
    
    response = {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "at_uri": result
        }
    }
    
    await websocket.send_text(json.dumps(response))


async def send_error_response(websocket: WebSocket, request_id: int, code: int, message: str):
    """Send error response."""
    response = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message
        }
    }
    
    await websocket.send_text(json.dumps(response))


def start():
    """Entry point for starting the server."""
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    start()
