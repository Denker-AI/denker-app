"""
MCP Protocol module for MCP servers.
Basic implementation to satisfy imports in the local websearch server.
"""

from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field


@dataclass
class Request:
    """Request object for MCP."""
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    type: str = "tool_call"
    id: Optional[str] = None


@dataclass
class Response:
    """Response object for MCP."""
    type: str
    tool_result: Any = None
    error: Optional[str] = None


@dataclass
class Tool:
    """Tool definition for MCP."""
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ListToolsResponse(Response):
    """Response for list_tools request."""
    type: str = "list_tools_result"
    tools: List[Tool] = field(default_factory=list)

# Export these classes
__all__ = ["Request", "Response", "Tool", "ListToolsResponse"]
