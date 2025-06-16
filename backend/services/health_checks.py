import logging
import os
from typing import Dict, Any, Optional, List, Tuple, Union
import asyncio

# Wrap MCP agent imports in try-except to make them optional
try:
    from mcp_agent.app import MCPApp
    from mcp_agent.agents.agent import Agent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logging.warning("MCP Agent not available, health checks will be disabled")

logger = logging.getLogger(__name__)

class MCPHealthService:
    """
    Service for checking the health of MCP servers and components.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the MCP Health Service"""
        if not MCP_AVAILABLE:
            self.logger = logging.getLogger(__name__)
            self.logger.warning("MCP Agent not available, health checks are disabled")
            self.mcp_app = None
            return
        
        # Initialize MCP app for health checks
        self.config_path = config_path
        self.mcp_app = None
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self) -> bool:
        """Initialize the MCP app for health checks"""
        if not MCP_AVAILABLE:
            self.logger.warning("MCP Agent is not available, cannot initialize")
            return False
            
        try:
            # Look for mcp_agent.config.yaml in default locations if config_path is not provided
            if not self.config_path:
                possible_paths = [
                    "mcp_agent.config.yaml",
                    "backend/mcp_agent.config.yaml",
                    "/app/mcp_agent.config.yaml"  # For Docker container
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        self.config_path = path
                        self.logger.info(f"Found MCP agent config at {path}")
                        break
            
            # Create the MCP app with the config path
            self.logger.info(f"Initializing MCP app with config path: {self.config_path}")
            self.mcp_app = MCPApp(name="health_check_service", settings=self.config_path)
            
            # Test initialization by running a basic command
            async with self.mcp_app.run() as ctx:
                self.logger.info("Successfully initialized MCP app and tested context manager")
                
            return True
        except Exception as e:
            self.logger.error(f"Error initializing MCP app for health checks: {str(e)}")
            return False
    
    # --- MCP agent/server health checks are now handled by the local backend (Electron app) ---
    # async def check_qdrant_health(self) -> bool:
    #     ... (comment out full function)

    def check_qdrant_health(*args, **kwargs):
        raise NotImplementedError("Qdrant health check is now handled by the local backend (Electron app).")
    
    async def check_fetch_health(self) -> bool:
        """
        Check if the Fetch server is healthy
        
        Returns:
            bool: True if healthy, False otherwise
        """
        if not MCP_AVAILABLE or not self.mcp_app:
            self.logger.warning("MCP Agent not available or not initialized")
            return False
            
        try:
            async with self.mcp_app.run() as app_context:
                # Create agent to test connection
                test_agent = Agent(
                    name="fetch_health_check",
                    instruction="Test connection to Fetch server",
                    server_names=["fetch"]
                )
                
                await test_agent.initialize()
                
                # List tools to verify connection
                tools = await test_agent.list_tools()
                
                # Check for fetch tools - look for exact tool names
                tool_names = [tool.name for tool in tools.tools] if hasattr(tools, 'tools') else []
                self.logger.info(f"Available Fetch tools: {tool_names}")
                
                # Look for exact fully-qualified tool name
                has_fetch = "fetch-fetch" in tool_names
                
                # Fallback to checking variations if exact match fails
                if not has_fetch:
                    has_fetch = any(name.startswith("fetch-") and "fetch" in name for name in tool_names)
                
                self.logger.info(f"Fetch health check: has_fetch={has_fetch}")
                return has_fetch
                
        except Exception as e:
            self.logger.error(f"Fetch health check failed: {str(e)}")
            return False
    
    async def check_websearch_health(self) -> bool:
        """
        Check if the WebSearch server is healthy
        
        Returns:
            bool: True if healthy, False otherwise
        """
        if not MCP_AVAILABLE or not self.mcp_app:
            self.logger.warning("MCP Agent not available or not initialized")
            return False
            
        try:
            self.logger.info("Starting WebSearch health check")
            async with self.mcp_app.run() as app_context:
                # Create agent to test connection
                test_agent = Agent(
                    name="websearch_health_check",
                    instruction="Test connection to WebSearch server",
                    server_names=["websearch"]
                )
                
                await test_agent.initialize()
                
                # List tools to verify connection
                tools = await test_agent.list_tools()
                
                # Check for websearch tools - using the same pattern as Qdrant
                tool_names = [tool.name for tool in tools.tools] if hasattr(tools, 'tools') else []
                self.logger.info(f"Available WebSearch tools: {tool_names}")
                
                # Check for exact tool name (fully-qualified) - matching our server implementation
                has_search = "websearch-websearch-search" in tool_names
                
                # Fallback to check other variations if exact match fails
                if not has_search:
                    # Try server-prefixed version
                    has_search = any(name.startswith("websearch-") and "search" in name.lower() for name in tool_names)
                
                # Final fallback to any search-related tool
                if not has_search:
                    has_search = any("search" in name.lower() for name in tool_names)
                
                self.logger.info(f"WebSearch health check result: has_search={has_search}")
                return has_search
                
        except Exception as e:
            self.logger.error(f"WebSearch health check failed: {str(e)}")
            return False
    
    async def check_filesystem_health(self) -> bool:
        """
        Check if the Filesystem server is healthy
        
        Returns:
            bool: True if healthy, False otherwise
        """
        if not MCP_AVAILABLE or not self.mcp_app:
            self.logger.warning("MCP Agent not available or not initialized")
            return False
            
        try:
            async with self.mcp_app.run() as app_context:
                # Create agent to test connection
                test_agent = Agent(
                    name="filesystem_health_check",
                    instruction="Test connection to Filesystem server",
                    server_names=["filesystem"]
                )
                
                await test_agent.initialize()
                
                # List tools to verify connection
                tools = await test_agent.list_tools()
                
                # Check for filesystem tools - look for exact tool names
                tool_names = [tool.name for tool in tools.tools] if hasattr(tools, 'tools') else []
                self.logger.info(f"Available Filesystem tools: {tool_names}")
                
                # Look for exact fully-qualified tool names
                has_read = "filesystem-read" in tool_names
                has_write = "filesystem-write" in tool_names 
                has_list = "filesystem-list" in tool_names
                
                # Fallback to checking variations if exact matches fail
                if not has_read:
                    has_read = any(name.startswith("filesystem-") and "read" in name for name in tool_names)
                if not has_write:
                    has_write = any(name.startswith("filesystem-") and "write" in name for name in tool_names)
                if not has_list:
                    has_list = any(name.startswith("filesystem-") and "list" in name for name in tool_names)
                
                self.logger.info(f"Filesystem health check: read={has_read}, write={has_write}, list={has_list}")
                return has_read and has_list  # Require at least read and list capabilities
                
        except Exception as e:
            self.logger.error(f"Filesystem health check failed: {str(e)}")
            return False
            

            
    async def check_document_loader_health(self) -> bool:
        """
        Check if the Document Loader server is healthy
        
        Returns:
            bool: True if healthy, False otherwise
        """
        if not MCP_AVAILABLE or not self.mcp_app:
            self.logger.warning("MCP Agent not available or not initialized")
            return False
            
        try:
            self.logger.info("Starting Document Loader health check")
            async with self.mcp_app.run() as app_context:
                # Create agent to test connection
                test_agent = Agent(
                    name="document_loader_health_check",
                    instruction="Test connection to Document Loader server",
                    server_names=["document-loader"]
                )
                
                await test_agent.initialize()
                
                # List tools to verify connection
                tools = await test_agent.list_tools()
                
                # Check for document processing tools
                tool_names = [tool.name for tool in tools.tools] if hasattr(tools, 'tools') else []
                self.logger.info(f"Available Document Loader tools: {tool_names}")
                
                # Check for load/extract functionality
                has_load = any(("load" in tool.lower() or "extract" in tool.lower()) for tool in tool_names)
                
                self.logger.info(f"Document Loader health check result: has_load={has_load}")
                return has_load
                
        except Exception as e:
            self.logger.error(f"Document Loader health check failed: {str(e)}")
            return False
            
    async def check_markdown_editor_health(self) -> bool:
        """
        Check if the Markdown Editor server is healthy
        
        Returns:
            bool: True if healthy, False otherwise
        """
        if not MCP_AVAILABLE or not self.mcp_app:
            self.logger.warning("MCP Agent not available or not initialized")
            return False
            
        try:
            self.logger.info("Starting Markdown Editor health check")
            async with self.mcp_app.run() as app_context:
                # Create agent to test connection
                test_agent = Agent(
                    name="markdown_editor_health_check",
                    instruction="Test connection to Markdown Editor server",
                    server_names=["markdown-editor"]
                )
                
                await test_agent.initialize()
                
                # List tools to verify connection
                tools = await test_agent.list_tools()
                
                # Check for markdown editing tools
                tool_names = [tool.name for tool in tools.tools] if hasattr(tools, 'tools') else []
                self.logger.info(f"Available Markdown Editor tools: {tool_names}")
                
                # Check for core editing functionality
                has_create = any("create" in tool.lower() for tool in tool_names)
                has_edit = any("edit" in tool.lower() or "append" in tool.lower() for tool in tool_names)
                
                self.logger.info(f"Markdown Editor health check result: has_create={has_create}, has_edit={has_edit}")
                return has_create or has_edit  # Only need one of the core functions to be working
                
        except Exception as e:
            self.logger.error(f"Markdown Editor health check failed: {str(e)}")
            return False
    
    async def check_all_health(self) -> Dict[str, bool]:
        """
        Check health of all MCP servers
        
        Returns:
            Dict[str, bool]: Health status of all components
        """
        # Initial health status - everything is unhealthy by default
        health_status = {
            "qdrant": False,
            "fetch": False,
            "websearch": False,
            "filesystem": False,
            "document-loader": False,
            "markdown-editor": False,
            "mcp_available": MCP_AVAILABLE
        }
        
        if not MCP_AVAILABLE:
            self.logger.warning("MCP Agent not available, all health checks returning False")
            return health_status
        
        try:
            # Initialize MCP app if needed
            if not self.mcp_app:
                self.logger.info("Initializing MCP app for health checks")
                initialized = await self.initialize()
                if not initialized:
                    self.logger.error("Failed to initialize MCP app for health checks")
                    health_status["initialization_failed"] = True
                    return health_status
            
            # Run health checks in parallel for efficiency
            self.logger.info("Running health checks for all MCP servers")
            
            # Create and gather all health check tasks
            tasks = {
                "qdrant": asyncio.create_task(self.check_qdrant_health()),
                "fetch": asyncio.create_task(self.check_fetch_health()),
                "websearch": asyncio.create_task(self.check_websearch_health()),
                "filesystem": asyncio.create_task(self.check_filesystem_health()),
                "document-loader": asyncio.create_task(self.check_document_loader_health()),
                "markdown-editor": asyncio.create_task(self.check_markdown_editor_health())
            }
            
            # Wait for all tasks to complete, handling errors individually
            for server, task in tasks.items():
                try:
                    health_status[server] = await task
                    self.logger.info(f"{server.capitalize()} health check result: {'healthy' if health_status[server] else 'unhealthy'}")
                except Exception as e:
                    self.logger.error(f"Error checking {server} health: {str(e)}")
                    health_status[server] = False
            
            # Determine overall health
            is_all_healthy = all(health_status.values())
            is_any_healthy = any([
                health_status["qdrant"], 
                health_status["fetch"], 
                health_status["websearch"], 
                health_status["filesystem"],
                health_status["document-loader"],
                health_status["markdown-editor"]
            ])
            
            if is_all_healthy:
                health_status["status"] = "healthy"
            elif is_any_healthy:
                health_status["status"] = "degraded"
            else:
                health_status["status"] = "unhealthy"
                
            return health_status
                
        except Exception as e:
            self.logger.error(f"Error running health checks: {str(e)}")
            health_status["error"] = str(e)
            return health_status

# Create a singleton instance with the default config path
config_path = os.environ.get("MCP_CONFIG_PATH") or "backend/mcp_agent.config.yaml"
mcp_health_service = MCPHealthService(config_path=config_path) 