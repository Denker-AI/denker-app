import logging
import asyncio
from typing import Dict, Any, List, Optional

# Wrap MCP agent imports in try-except to make them optional
try:
    from mcp_agent.app import MCPApp
    from mcp_agent.agents.agent import Agent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logging.warning("MCP Agent not available, Qdrant integration will be disabled")

logger = logging.getLogger(__name__)

class MCPQdrantService:
    """
    Service for interacting with Qdrant through the MCP protocol.
    Uses mcp-server-qdrant to handle vector operations.
    """
    
    def __init__(self):
        """Initialize the MCP Qdrant Service"""
        if not MCP_AVAILABLE:
            self.logger = logging.getLogger(__name__)
            self.logger.warning("MCP Agent not available, Qdrant service is disabled")
            return
            
        self.app = MCPApp(name="qdrant_service")
        self.logger = logging.getLogger(__name__)
    
    async def store_document(
        self, 
        content: str, 
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Store a document in Qdrant using mcp-server-qdrant
        
        Args:
            content: Document content
            metadata: Document metadata
            
        Returns:
            Storage result
        """
        if not MCP_AVAILABLE:
            self.logger.warning("MCP Agent not available, cannot store document")
            return {"error": "MCP Agent not available"}
            
        try:
            async with self.app.run() as app_context:
                # Create agent for Qdrant operations
                qdrant_agent = Agent(
                    name="qdrant_uploader",
                    instruction="Store the provided document content in Qdrant",
                    server_names=["qdrant"]
                )
                
                await qdrant_agent.initialize()
                
                # Just for debugging - list available tools
                tools = await qdrant_agent.list_tools()
                tool_names = [tool.name for tool in tools.tools] if hasattr(tools, 'tools') else []
                self.logger.info(f"Available tools: {tool_names}")
                
                # Use the correct tool name with underscore
                tool_name = "qdrant_qdrant-store"
                self.logger.info(f"Using tool name: {tool_name}")
                
                # Store in Qdrant using mcp-server-qdrant
                result = await qdrant_agent.call_tool(
                    tool_name,
                    {
                        "information": content,
                        "metadata": metadata
                    }
                )
                
                # Convert CallToolResult to a serializable dictionary
                if hasattr(result, 'model_dump'):
                    result_dict = result.model_dump()
                elif hasattr(result, 'dict'):
                    result_dict = result.dict()
                else:
                    # Fallback to a simple dictionary
                    result_dict = {
                        "success": not getattr(result, "isError", False),
                        "message": str(result)
                    }
                
                self.logger.info(f"Stored document in Qdrant: {result_dict}")
                return result_dict
                
        except Exception as e:
            self.logger.error(f"Error storing document in Qdrant: {str(e)}")
            raise
    
    async def search_documents(
        self, 
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for documents in Qdrant using mcp-server-qdrant
        
        Args:
            query: Search query
            limit: Maximum number of results to return
            
        Returns:
            List of matching documents
        """
        if not MCP_AVAILABLE:
            self.logger.warning("MCP Agent not available, cannot search documents")
            return []
            
        try:
            async with self.app.run() as app_context:
                # Create agent for Qdrant operations
                qdrant_agent = Agent(
                    name="qdrant_searcher",
                    instruction="Search for content in Qdrant",
                    server_names=["qdrant"]
                )
                
                await qdrant_agent.initialize()
                
                # Just for debugging - list available tools
                tools = await qdrant_agent.list_tools()
                tool_names = [tool.name for tool in tools.tools] if hasattr(tools, 'tools') else []
                self.logger.info(f"Available tools: {tool_names}")
                
                # Use the correct tool name with underscore
                tool_name = "qdrant_qdrant-find"
                self.logger.info(f"Using tool name: {tool_name}")
                
                # Search in Qdrant using mcp-server-qdrant
                results = await qdrant_agent.call_tool(
                    tool_name,
                    {
                        "query": query
                    }
                )
                
                # Convert results to a serializable format
                if hasattr(results, 'model_dump'):
                    results_dict = results.model_dump()
                elif hasattr(results, 'dict'):
                    results_dict = results.dict()
                else:
                    # Fallback to a simple list or dictionary
                    if isinstance(results, list):
                        results_dict = [{'content': str(r)} for r in results]
                    else:
                        results_dict = {'results': str(results)}
                
                self.logger.info(f"Found {len(results_dict) if isinstance(results_dict, list) else 'N/A'} documents in Qdrant for query: {query}")
                return results_dict
                
        except Exception as e:
            self.logger.error(f"Error searching documents in Qdrant: {str(e)}")
            raise
    
    async def health_check(self) -> bool:
        """
        Check if mcp-server-qdrant is healthy
        
        Returns:
            True if healthy, False otherwise
        """
        if not MCP_AVAILABLE:
            self.logger.warning("MCP Agent not available, health check returns False")
            return False
            
        try:
            async with self.app.run() as app_context:
                # Create agent to test connection
                test_agent = Agent(
                    name="qdrant_tester",
                    instruction="Test connection to Qdrant",
                    server_names=["qdrant"]
                )
                
                await test_agent.initialize()
                
                # List tools to verify connection
                tools = await test_agent.list_tools()
                
                # Check if qdrant-store and qdrant-find are available
                tool_names = [tool.name for tool in tools.tools]
                has_store = "qdrant-store" in tool_names
                has_find = "qdrant-find" in tool_names
                
                self.logger.info(f"Qdrant health check: store={has_store}, find={has_find}")
                return has_store and has_find
                
        except Exception as e:
            self.logger.error(f"Qdrant health check failed: {str(e)}")
            return False

# Create a singleton instance
mcp_qdrant_service = MCPQdrantService() 