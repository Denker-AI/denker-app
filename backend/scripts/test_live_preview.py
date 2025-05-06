#!/usr/bin/env python3
"""
Simple test for live preview functionality
"""

import sys
import os
import asyncio
import logging
from pathlib import Path

from mcp_agent.agents.agent import Agent
from mcp_agent.app import MCPApp

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("live-preview-test")

async def test_live_preview():
    """Test the live preview functionality"""
    try:
        # Create a simple markdown file for testing
        test_md_path = "/tmp/live_preview_test.md"
        with open(test_md_path, "w") as f:
            f.write("""# Live Preview Test

## This is a test document

This document was created to test the live preview functionality.

- Item 1
- Item 2
- Item 3

| Header 1 | Header 2 | Header 3 |
|----------|----------|----------|
| Cell 1   | Cell 2   | Cell 3   |
| Cell 4   | Cell 5   | Cell 6   |
""")
        
        logger.info(f"Created test markdown file at {test_md_path}")
        
        # Initialize MCP app
        logger.info("Initializing MCP app...")
        mcp_app = MCPApp(name="preview_test")
        
        async with mcp_app.run() as app_context:
            # Create test agent
            logger.info("Creating test agent...")
            test_agent = Agent(
                name="preview_test_agent",
                instruction="Test the live preview functionality",
                server_names=["markdown-editor"]
            )
            
            await test_agent.initialize()
            
            # List tools
            logger.info("Listing available tools...")
            tools = await test_agent.list_tools()
            tool_names = [t.name for t in tools.tools] if hasattr(tools, 'tools') else []
            logger.info(f"Available tools: {tool_names}")
            
            # Create simple preview
            logger.info("Testing simple preview...")
            preview_result = await test_agent.call_tool("markdown-editor-preview", {
                "file_path": test_md_path,
                "format": "html"
            })
            
            logger.info(f"Preview result: {'success' if not preview_result.isError else 'error'}")
            
            # Start live preview
            logger.info("Starting live preview...")
            live_preview_result = await test_agent.call_tool("markdown-editor-live_preview", {
                "file_path": test_md_path,
                "port": 8088  # Using a different port
            })
            
            logger.info(f"Live preview result: {live_preview_result}")
            
            if not live_preview_result.isError:
                content = live_preview_result.content[0].text if hasattr(live_preview_result, 'content') and live_preview_result.content else ""
                # Extract and log the server URL from the result
                import json
                try:
                    result_json = json.loads(content)
                    if 'server_url' in result_json:
                        url = result_json['server_url']
                        logger.info(f"Live preview URL: {url}")
                        logger.info(f"To access the preview, make sure port 8088 is mapped from the container")
                        logger.info(f"Try: http://localhost:8088 in your web browser")
                except:
                    logger.error(f"Could not parse server response: {content}")
            
            # Keep the server running for a while
            logger.info("Server is running. Press Ctrl+C to stop...")
            try:
                await asyncio.sleep(600)  # Run for 10 minutes
            except asyncio.CancelledError:
                logger.info("Test cancelled")
            
            return True
    except Exception as e:
        logger.error(f"Error testing live preview: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("Starting live preview test")
    result = asyncio.run(test_live_preview())
    logger.info(f"Test completed with result: {'Success' if result else 'Failed'}") 