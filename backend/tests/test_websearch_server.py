#!/usr/bin/env python3
"""
Test script for WebSearch MCP Server
"""

import asyncio
import json
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_websearch_server():
    """Test the WebSearch server directly using stdin/stdout communication"""
    try:
        # Import the necessary classes
        from mcp_local.servers.websearch.server import WebSearchServer
        from mcp_local.base.protocol import Request
        
        # Create the server instance
        server = WebSearchServer()
        logger.info("Created WebSearchServer instance")
        
        # Construct an initialization request as a Request object
        init_request = Request(
            type="initialize",
            id="1",
            name="initialize",
            arguments={}
        )
        
        logger.info(f"Sending initialize request")
        
        # Send the request directly
        response = await server._dispatch_request(init_request)
        
        # Print the response
        logger.info(f"Received initialize response: {response.type}")
        logger.info(f"Response details: {response.__dict__}")
        
        # Test list_tools
        tools_request = Request(
            type="list_tools",
            id="2",
            name="list_tools",
            arguments={}
        )
        
        logger.info(f"Sending list_tools request")
        tools_response = await server._dispatch_request(tools_request)
        
        # Print the response
        logger.info(f"Received tools response type: {tools_response.type}")
        if hasattr(tools_response, 'tools'):
            logger.info(f"Found {len(tools_response.tools)} tools:")
            for tool in tools_response.tools:
                logger.info(f"  - {tool.name}: {tool.description}")
        else:
            logger.info(f"No tools found in response: {tools_response.__dict__}")
        
        # Test a search query if tools were successfully listed
        if hasattr(tools_response, 'tools') and any(tool.name == "search" for tool in tools_response.tools):
            logger.info("Testing search tool")
            search_request = Request(
                type="call_tool",
                id="3",
                name="search",
                arguments={"query": "test query", "num_results": 3}
            )
            
            logger.info(f"Sending search request")
            search_response = await server._dispatch_request(search_request)
            
            logger.info(f"Received search response type: {search_response.type}")
            if hasattr(search_response, 'tool_result'):
                logger.info(f"Search results: {len(search_response.tool_result)} items")
                logger.info(f"First result: {search_response.tool_result[0] if search_response.tool_result else 'None'}")
            else:
                logger.info(f"No search results in response: {search_response.__dict__}")
        
        return True
    except Exception as e:
        logger.error(f"Error testing WebSearch server: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = asyncio.run(test_websearch_server())
    if success:
        logger.info("✅ WebSearch server test passed")
        sys.exit(0)
    else:
        logger.error("❌ WebSearch server test failed")
        sys.exit(1) 