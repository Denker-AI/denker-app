#!/usr/bin/env python3
"""
Test script for Markdown Editor MCP Server

This script tests various tools provided by the Markdown Editor server.
"""

import asyncio
import logging
import os
from mcp_agent.agents.agent import Agent
from mcp_agent.app import MCPApp

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("markdown-editor-test")

async def test_markdown_editor():
    """Test the main functionality of the Markdown Editor server"""
    try:
        # Initialize MCP App
        logger.info("Initializing MCP app...")
        mcp_app = MCPApp(name="markdown_test")
        
        async with mcp_app.run() as app_context:
            # Create an agent to test Markdown Editor server connection
            logger.info("Creating test agent for Markdown Editor server...")
            test_agent = Agent(
                name="markdown_test_agent",
                instruction="Test connection to Markdown Editor server",
                server_names=["markdown-editor"]
            )
            
            await test_agent.initialize()
            
            # List tools to verify connection
            tools = await test_agent.list_tools()
            tool_names = [tool.name for tool in tools.tools] if hasattr(tools, 'tools') else []
            logger.info(f"Available Markdown Editor tools: {tool_names}")
            
            # Create a test markdown document
            tmp_file = "/tmp/test_markdown.md"
            logger.info(f"Creating a test markdown document at {tmp_file}")
            
            create_result = await test_agent.call_tool("markdown-editor-create_document", {
                "content": "# Test Markdown Document\n\n## Section 1\n\nThis is a test markdown document created by the MCP Markdown Editor.\n\n## Section 2\n\n- Item 1\n- Item 2\n- Item 3\n\n## Section 3\n\n| Column 1 | Column 2 | Column 3 |\n|----------|----------|----------|\n| Value 1  | Value 2  | Value 3  |\n| Value 4  | Value 5  | Value 6  |",
                "file_path": tmp_file
            })
            
            logger.info(f"Create document result: {create_result}")
            
            # Generate a preview of the document
            logger.info("Generating a preview of the document...")
            preview_result = await test_agent.call_tool("markdown-editor-preview", {
                "file_path": tmp_file,
                "format": "html"
            })
            
            preview_length = len(str(preview_result.content[0].text)) if hasattr(preview_result, 'content') and preview_result.content else 0
            logger.info(f"Preview generated with {preview_length} characters of HTML")
            
            # Append content to the document
            logger.info("Appending content to the document...")
            append_result = await test_agent.call_tool("markdown-editor-append_content", {
                "file_path": tmp_file,
                "content": "\n\n## Section 4\n\nThis is additional content appended to the document.",
                "section": "## Section 3"
            })
            
            logger.info(f"Append content result: {append_result}")
            
            # Extract a table from the document
            logger.info("Extracting a table from the document...")
            table_result = await test_agent.call_tool("markdown-editor-extract_table", {
                "markdown_file": tmp_file,
                "table_index": 0
            })
            
            logger.info(f"Table extraction result: {table_result}")
            
            # OPTIONAL: Start a live preview server (uncomment to test)
            # This will start a web server on the specified port
            # NOTE: This won't automatically open a browser, but you can access it
            # at http://localhost:8080 if port forwarding is set up
            
            logger.info("Starting a live preview server...")
            live_preview_result = await test_agent.call_tool("markdown-editor-live_preview", {
                "file_path": tmp_file,
                "port": 8080
            })
            
            logger.info(f"Live preview server result: {live_preview_result}")
            # Keep the server running for a while to allow manual testing
            logger.info("Live preview server running. Press Ctrl+C to stop...")
            await asyncio.sleep(300)  # Run for 5 minutes to allow testing
            
            logger.info("Test completed successfully!")
            return True
    except Exception as e:
        logger.error(f"Error testing Markdown Editor server: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("Starting Markdown Editor server test")
    success = asyncio.run(test_markdown_editor())
    
    if success:
        logger.info("✅ Markdown Editor server test PASSED")
    else:
        logger.error("❌ Markdown Editor server test FAILED") 