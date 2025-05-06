"""
Human Input Tool - Allows agents to request input from the user via WebSocket.

This tool handles requesting input from the user through a WebSocket interface,
providing a mechanism for agents to collect additional information during execution.
"""

import asyncio
import logging
from typing import Dict, Any, Optional

from ..websocket_manager import get_websocket_manager

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Only add handler if it doesn't already exist
handler_name = "human_input_tool_handler"
if not any(getattr(h, "name", None) == handler_name for h in logger.handlers):
    console_handler = logging.StreamHandler()
    console_handler.name = handler_name
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

async def human_input(
    query_id: str,
    input_prompt: str,
    tool_name: str = "_human_input",
    tool_description: Optional[str] = None,
    timeout: int = 300
) -> Dict[str, Any]:
    """
    Request human input via WebSocket.
    
    Args:
        query_id: The query ID for the WebSocket connection
        input_prompt: The prompt to show the user
        tool_name: The name of the tool requesting input (helpful for UI)
        tool_description: Optional description of the tool/why input is needed
        timeout: Timeout in seconds (default: 5 minutes)
        
    Returns:
        Dict containing the result of the human input request
    """
    logger.info(f"Requesting human input for query {query_id}")
    
    # Get WebSocket manager instance
    websocket_manager = get_websocket_manager()
    
    # Check if client is connected
    if not websocket_manager.is_connected(query_id):
        logger.warning(f"WebSocket not connected for query {query_id}")
        return {
            "success": False,
            "error": "WebSocket not connected",
            "input": None
        }
    
    try:
        # Request input via WebSocket
        result = await websocket_manager.request_human_input(
            query_id=query_id,
            tool_name=tool_name,
            input_prompt=input_prompt,
            tool_description=tool_description,
            timeout=timeout
        )
        
        logger.info(f"Human input request result: {result['success']}")
        
        return result
    except Exception as e:
        logger.error(f"Error requesting human input: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        return {
            "success": False,
            "error": str(e),
            "input": None
        } 