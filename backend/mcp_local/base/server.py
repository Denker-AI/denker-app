"""
MCP Server base class for custom MCP servers.
Basic implementation to satisfy imports in the local websearch server.
"""

import abc
import asyncio
import json
import logging
import os
import sys
from typing import Dict, Any, List, Optional, Callable, Awaitable

from .protocol import Request, Response, Tool

logger = logging.getLogger(__name__)


class MCPServer(abc.ABC):
    """Base class for MCP servers."""
    
    def __init__(self):
        """Initialize the MCP server."""
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abc.abstractmethod
    async def list_tools(self, request: Request) -> Response:
        """List available tools in this server."""
        pass
    
    @abc.abstractmethod
    async def call_tool(self, request: Request) -> Response:
        """Handle tool calls to this server."""
        pass
    
    async def run(self):
        """Run the MCP server."""
        self.logger.info("Starting MCP server")
        
        async def read_request():
            """Read a request from stdin."""
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                return None
            return json.loads(line)
        
        async def write_response(response: Dict[str, Any]):
            """Write a response to stdout."""
            json_str = json.dumps(response)
            print(json_str, flush=True)
        
        while True:
            try:
                # Read request
                request_data = await read_request()
                if request_data is None:
                    # EOF, exit
                    break
                
                # Parse request
                request_type = request_data.get("type", "")
                
                if request_type == "list_tools":
                    # Handle list_tools
                    request = Request(name="list_tools", arguments={})
                    response = await self.list_tools(request)
                    
                    await write_response({"type": response.type, "tools": [
                        {"name": tool.name, "description": tool.description, "parameters": tool.parameters}
                        for tool in response.tools
                    ]})
                    
                elif request_type == "tool_call":
                    # Handle tool_call
                    name = request_data.get("name", "")
                    arguments = request_data.get("arguments", {})
                    
                    request = Request(name=name, arguments=arguments)
                    response = await self.call_tool(request)
                    
                    if response.type == "tool_result":
                        await write_response({"type": "tool_result", "result": response.tool_result})
                    else:
                        await write_response({"type": "error", "error": response.error})
                
                else:
                    # Unknown request type
                    await write_response({"type": "error", "error": f"Unknown request type: {request_type}"})
            
            except Exception as e:
                # Handle errors
                self.logger.exception("Error handling request")
                await write_response({"type": "error", "error": str(e)})
