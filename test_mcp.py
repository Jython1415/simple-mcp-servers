"""
Test script for the deer-to-bsky MCP server.

This script tests the WebSocket-based MCP protocol implementation.
"""

import asyncio
import json
import websockets


async def test_mcp_server():
    """Connect to the MCP server and test its functionality."""
    print("Connecting to MCP server...")
    
    async with websockets.connect("ws://localhost:8000") as websocket:
        print("Connected!")
        
        # Send initialize request
        initialize_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "mcp-test-client",
                    "version": "0.1.0"
                }
            }
        }
        
        print("Sending initialize request...")
        await websocket.send(json.dumps(initialize_request))
        response = await websocket.recv()
        print(f"Response: {response}")
        
        # Send listFunctions request
        list_functions_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "mcp/listFunctions"
        }
        
        print("\nSending listFunctions request...")
        await websocket.send(json.dumps(list_functions_request))
        response = await websocket.recv()
        print(f"Response: {response}")
        
        # Send invokeFunction request
        invoke_function_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "mcp/invokeFunction",
            "params": {
                "name": "convert-deer-to-bsky",
                "arguments": {
                    "url": "https://deer.social/profile/did:plc:h25avmes6g7fgcddc3xj7qmg/post/3loxuoxb5ts2w"
                }
            }
        }
        
        print("\nSending invokeFunction request...")
        await websocket.send(json.dumps(invoke_function_request))
        response = await websocket.recv()
        print(f"Response: {response}")
        
        # Test with an invalid URL
        invalid_request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "mcp/invokeFunction",
            "params": {
                "name": "convert-deer-to-bsky",
                "arguments": {
                    "url": "https://deer.social/invalid/url"
                }
            }
        }
        
        print("\nSending request with invalid URL...")
        await websocket.send(json.dumps(invalid_request))
        response = await websocket.recv()
        print(f"Response: {response}")
        
        print("\nAll tests completed!")


if __name__ == "__main__":
    asyncio.run(test_mcp_server())
