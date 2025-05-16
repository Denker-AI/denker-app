#!/usr/bin/env python3
"""
Direct test script for MCP Agent interaction with WebSearch server
"""

import asyncio
import logging
import os
import time
import signal
import sys

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from mcp_agent.app import MCPApp
    from mcp_agent.agents.agent import Agent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.error("MCP Agent not available, cannot proceed with test")

# Add timeout handler
def timeout_handler(signum, frame):
    logger.error("TIMEOUT: Operation took too long, process might be stuck")
    sys.exit(1)

async def test_websearch_server():
    """
    Test the WebSearch server directly using MCPApp
    """
    if not MCP_AVAILABLE:
        logger.error("MCP Agent not available, test aborted")
        return False

    logger.info("Starting WebSearch server test via MCP Agent")
    
    # Path to the MCP agent config file
    logger.debug("Checking environment for MCP_CONFIG_PATH")
    config_path = os.environ.get("MCP_CONFIG_PATH") 
    if config_path:
        logger.debug(f"Found MCP_CONFIG_PATH environment variable: {config_path}")
    else:
        config_path = "/app/mcp_agent.config.yaml"
        logger.debug(f"Using default config path: {config_path}")
    
    # Check if file exists
    if os.path.exists(config_path):
        logger.debug(f"Config file exists at {config_path}")
    else:
        logger.error(f"Config file NOT FOUND at {config_path}")
        # Try alternate paths
        alternate_paths = ["/app/mcp_local/mcp_agent.config.yaml", "./mcp_agent.config.yaml"]
        for path in alternate_paths:
            if os.path.exists(path):
                logger.info(f"Found config file at alternate location: {path}")
                config_path = path
                break
    
    try:
        # Create the MCP app with the config path
        logger.info(f"Initializing MCP app with config: {config_path}")
        
        # Set a timeout for this operation
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(30)  # 30 seconds timeout
        
        logger.debug("Creating MCPApp instance")
        mcp_app = MCPApp(name="test_websearch", settings=config_path)
        logger.debug("MCPApp instance created successfully")
        
        # Cancel the timeout for now
        signal.alarm(0)
        
        # Create the test context
        logger.info("Creating MCP app context")
        try:
            # Set a new timeout for context creation
            signal.alarm(30)
            
            logger.debug("Entering MCPApp context manager")
            async with mcp_app.run() as app_context:
                logger.debug("Successfully entered MCPApp context")
                
                # Cancel timeout
                signal.alarm(0)
                
                # Create agent specifically for WebSearch
                logger.info("Creating WebSearch test agent")
                test_agent = Agent(
                    name="websearch_test",
                    instruction="Test WebSearch server capabilities",
                    server_names=["websearch"]
                )
                
                logger.info("Initializing agent...")
                # Set timeout for agent initialization
                signal.alarm(60)  # 60 second timeout for initialization
                
                start_time = time.time()
                await test_agent.initialize()
                end_time = time.time()
                
                # Cancel timeout
                signal.alarm(0)
                
                logger.info(f"Agent initialization completed in {end_time - start_time:.2f} seconds")
                
                # List tools to verify connection
                logger.info("Listing available tools...")
                signal.alarm(30)  # 30 second timeout for tool listing
                
                start_time = time.time()
                tools_response = await test_agent.list_tools()
                end_time = time.time()
                
                # Cancel timeout
                signal.alarm(0)
                
                logger.info(f"Tool listing completed in {end_time - start_time:.2f} seconds")
                
                # Check available tools
                if not hasattr(tools_response, 'tools'):
                    logger.error("No tools attribute in response")
                    return False
                    
                tool_names = [tool.name for tool in tools_response.tools]
                logger.info(f"Available tools: {tool_names}")
                
                # Try to call a tool if we have search capability
                search_tools = [t for t in tool_names if 'search' in t.lower()]
                if search_tools:
                    search_tool = search_tools[0]
                    logger.info(f"Testing search capability using tool: {search_tool}")
                    
                    # Make a simple search request
                    signal.alarm(60)  # 60 second timeout for search
                    
                    start_time = time.time()
                    response = await test_agent.call_tool(
                        tool=search_tool,
                        arguments={"query": "Python programming language"}
                    )
                    end_time = time.time()
                    
                    # Cancel timeout
                    signal.alarm(0)
                    
                    logger.info(f"Search completed in {end_time - start_time:.2f} seconds")
                    
                    # Check the response
                    if hasattr(response, 'tool_result'):
                        logger.info("Search successful!")
                        logger.info(f"Result type: {type(response.tool_result)}")
                        logger.info(f"Result (truncated): {str(response.tool_result)[:500]}...")
                        return True
                    else:
                        logger.error(f"Search failed. Response: {response}")
                        return False
                else:
                    logger.warning("No search tools available")
                    return False
        except asyncio.TimeoutError:
            logger.error("Timeout occurred during MCPApp context execution")
            return False
        finally:
            # Make sure we always cancel any active timeouts
            signal.alarm(0)
                
    except Exception as e:
        logger.error(f"Error testing WebSearch server: {str(e)}")
        # Print stack trace for debugging
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Always cancel timeouts
        signal.alarm(0)

if __name__ == "__main__":
    if MCP_AVAILABLE:
        try:
            signal.signal(signal.SIGALRM, timeout_handler)
            asyncio.run(test_websearch_server())
        except KeyboardInterrupt:
            logger.info("Test interrupted by user")
        finally:
            # Ensure we don't leave any pending alarms
            signal.alarm(0)
    else:
        print("MCP Agent not available, cannot run test") 