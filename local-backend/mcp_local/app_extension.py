"""
MCP App Extension

This module extends the MCPApp class from the mcp_agent repo
to add memory tools integration.
"""

import logging
from typing import Optional, Union

from mcp_agent.app import MCPApp
from mcp_agent.config import Settings

from .memory_tools import memory_tools

logger = logging.getLogger(__name__)

class ExtendedMCPApp(MCPApp):
    """
    Extended version of MCPApp that includes memory tools.
    
    This class adds memory tools integration to the standard MCPApp
    to enable knowledge graph persistence.
    """
    
    def __init__(
        self,
        name: str = "mcp_application",
        settings: Optional[Union[Settings, str]] = None,
        **kwargs
    ):
        """
        Initialize the extended MCPApp with memory tools.
        
        Args:
            name: Name of the application
            settings: Application configuration
            **kwargs: Additional arguments to pass to MCPApp
        """
        super().__init__(name=name, settings=settings, **kwargs)
        
        # Add memory tools to the instance
        self.memory_tools = memory_tools
        logger.info("Extended MCPApp initialized with memory tools")

def create_mcp_app(
    name: str = "denker_mcp_agent",
    settings: Optional[Union[Settings, str]] = None,
    **kwargs
) -> ExtendedMCPApp:
    """
    Create an extended MCP App instance with memory tools.
    
    Args:
        name: Name of the application
        settings: Application configuration
        **kwargs: Additional arguments to pass to MCPApp
        
    Returns:
        An initialized ExtendedMCPApp instance
    """
    return ExtendedMCPApp(
        name=name, 
        settings=settings, 
        human_input_callback=None,
        **kwargs
    ) 