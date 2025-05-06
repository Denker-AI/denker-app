#!/usr/bin/env python3
"""
Direct test of the QuickChart MCP server
This script tests if the QuickChart MCP server can be initialized and used directly.
"""

import sys
import os
import asyncio
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("quickchart-test")

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from mcp_agent.app import MCPApp
    from mcp_agent.agents.agent import Agent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.error("MCP Agent not available, test cannot run")
    sys.exit(1)

async def test_quickchart_server():
    """Test if the QuickChart server can be initialized and used"""
    logger.info("Testing QuickChart MCP server...")
    
    # Try to find the config file
    config_path = None
    possible_paths = [
        "mcp_agent.config.yaml",
        "mcp_local/mcp_agent.config.yaml",
        "/app/mcp_local/mcp_agent.config.yaml"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            config_path = path
            logger.info(f"Found MCP agent config at {path}")
            break
    
    if not config_path:
        logger.error("MCP agent config not found")
        return False
    
    try:
        # Initialize the MCP app
        logger.info(f"Initializing MCP app with config: {config_path}")
        mcp_app = MCPApp(name="quickchart_test", settings=config_path)
        
        # Test the MCP app initialization
        logger.info("Testing MCP app context...")
        async with mcp_app.run() as app_context:
            logger.info("MCP app context initialized successfully")
            
            # Create an agent to test QuickChart server connection
            logger.info("Creating test agent for QuickChart server...")
            test_agent = Agent(
                name="quickchart_test_agent",
                instruction="Test connection to QuickChart server",
                server_names=["quickchart-server"]
            )
            
            # Initialize the agent
            logger.info("Initializing test agent...")
            await test_agent.initialize()
            
            # List the available tools
            logger.info("Listing available tools...")
            tools = await test_agent.list_tools()
            
            # Display the tool names
            tool_names = [tool.name for tool in tools.tools] if hasattr(tools, 'tools') else []
            logger.info(f"Available QuickChart tools: {tool_names}")
            
            # Check for chart generation tools
            has_chart = any("chart" in tool.lower() for tool in tool_names)
            logger.info(f"Chart generation capability: {'Available' if has_chart else 'Not available'}")
            
            # Try to invoke a tool if available
            if has_chart and tool_names:
                chart_tool = next((t for t in tool_names if "chart" in t.lower()), None)
                if chart_tool:
                    logger.info(f"Testing tool: {chart_tool}")
                    try:
                        # Prepare a simple chart config
                        chart_config = {
                            "type": "bar",
                            "data": {
                                "labels": ["Red", "Blue", "Yellow"],
                                "datasets": [{
                                    "label": "Test Dataset",
                                    "data": [5, 10, 15]
                                }]
                            }
                        }
                        
                        # Invoke the tool - this may vary depending on tool name
                        logger.info("Invoking chart tool...")
                        result = await test_agent.call_tool(chart_tool, {
                            "type": "bar", 
                            "labels": ["Red", "Blue", "Yellow"],
                            "datasets": [{
                                "label": "Test Dataset",
                                "data": [5, 10, 15]
                            }]
                        })
                        logger.info(f"Tool result: {result}")
                        
                    except Exception as e:
                        logger.error(f"Error invoking tool: {str(e)}")
            
            return has_chart
    
    except Exception as e:
        logger.error(f"Error testing QuickChart server: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def main():
    """Main function to run the test"""
    logger.info("Starting QuickChart server test")
    
    # Run the test
    success = await test_quickchart_server()
    
    # Report result
    if success:
        logger.info("✅ QuickChart server test PASSED")
        return 0
    else:
        logger.error("❌ QuickChart server test FAILED")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 