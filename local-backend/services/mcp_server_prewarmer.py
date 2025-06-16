"""
MCP Server Prewarming Service
Keeps persistent connections to MCP servers alive for instant access
"""
import asyncio
import logging
import sys
from typing import Dict, Optional, Set
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class MCPServerPrewarmer:
    def __init__(self, context=None):
        self.context = context
        self._prewarmed_servers: Dict[str, any] = {}
        self._prewarming_lock = asyncio.Lock()
        self._is_prewarming = False
        self._prewarming_completed = False
        self._failed_servers: Set[str] = set()
        
    async def start_prewarming(self, server_names: list, delay_seconds: int = 2):
        """Start prewarming MCP servers in background"""
        if self._is_prewarming:
            logger.info("MCP server prewarming already in progress")
            return
            
        # Start prewarming in background task
        asyncio.create_task(self._prewarming_task(server_names, delay_seconds))
        
    async def _prewarming_task(self, server_names: list, delay_seconds: int):
        """Background task for prewarming servers"""
        try:
            await asyncio.sleep(delay_seconds)
            async with self._prewarming_lock:
                if self._is_prewarming:
                    return
                self._is_prewarming = True
                
            logger.info(f"Starting MCP server prewarming for {len(server_names)} servers...")
            
            # Filter out servers that are known to fail in PyInstaller
            if getattr(sys, 'frozen', False):
                working_servers = self._filter_working_servers(server_names)
                logger.info(f"PyInstaller mode: prewarming {len(working_servers)}/{len(server_names)} servers")
                logger.info(f"Skipped servers: {list(self._failed_servers)}")
            else:
                # Development mode - try all servers but still log if we detect Node.js ones
                working_servers = []
                for server_name in server_names:
                    # Still check for Node.js servers in dev mode for logging
                    if self.context and hasattr(self.context, 'server_registry'):
                        try:
                            server_config = self.context.server_registry.registry.get(server_name)
                            if server_config:
                                command = getattr(server_config, 'command', '')
                                if command in {'npx', 'node', 'npm'}:
                                    logger.info(f"Note: Server '{server_name}' uses Node.js command '{command}' - ensure Node.js is available")
                        except Exception:
                            pass
                    working_servers.append(server_name)
                logger.info(f"Development mode: attempting to prewarm all {len(working_servers)} servers")
                
            # Prewarm servers in parallel batches to avoid overwhelming
            await self._prewarm_servers_parallel(working_servers)
            
            self._prewarming_completed = True
            logger.info(f"MCP server prewarming completed. Active: {len(self._prewarmed_servers)}, Failed: {len(self._failed_servers)}")
            
        except Exception as e:
            logger.error(f"Error during MCP server prewarming: {e}")
            self._is_prewarming = False
            
    def _filter_working_servers(self, server_names: list) -> list:
        """Filter servers that work in PyInstaller mode"""
        
        working_servers = []
        for server_name in server_names:
            # Since PyInstaller backend runs in electron app context which has access to npx/node,
            # we no longer filter out Node.js-based servers
            if self.context and hasattr(self.context, 'server_registry'):
                try:
                    server_config = self.context.server_registry.registry.get(server_name)
                    if server_config:
                        command = getattr(server_config, 'command', '')
                        if command in {'npx', 'node', 'npm'}:
                            logger.info(f"Server '{server_name}' uses Node.js command '{command}' - attempting to prewarm in electron context")
                except Exception as e:
                    logger.warning(f"Could not check config for server '{server_name}': {e}")
            
            # Include all servers for prewarming
            working_servers.append(server_name)
                
        return working_servers
        
    async def _prewarm_servers_parallel(self, server_names: list):
        """Prewarm servers in parallel batches"""
        batch_size = 3  # Process 3 servers at a time to avoid overwhelming
        
        for i in range(0, len(server_names), batch_size):
            batch = server_names[i:i + batch_size]
            logger.info(f"Prewarming batch {i//batch_size + 1}: {batch}")
            
            # Process batch in parallel
            tasks = [self._prewarm_single_server(server_name) for server_name in batch]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Small delay between batches
            if i + batch_size < len(server_names):
                await asyncio.sleep(0.5)
                
    async def _prewarm_single_server(self, server_name: str):
        """Prewarm a single server and keep connection alive"""
        try:
            logger.info(f"Prewarming server: {server_name}")
            
            # Import here to avoid circular imports
            from mcp_agent.mcp.mcp_aggregator import MCPAggregator
            
            # Create persistent aggregator - this is the KEY difference
            aggregator = MCPAggregator(
                server_names=[server_name],
                connection_persistence=True,  # Keep connections alive
                context=self.context,
                name=f"prewarmed_{server_name}"
            )
            
            # Initialize and test
            await aggregator.initialize(force=True)
            
            # Test basic functionality to ensure it's working
            try:
                tools = await aggregator.list_tools()
                logger.info(f"Server '{server_name}' prewarmed successfully with {len(tools)} tools")
            except Exception as e:
                logger.warning(f"Server '{server_name}' started but tool listing failed: {e}")
            
            # Store the aggregator to keep connection alive
            self._prewarmed_servers[server_name] = aggregator
            
        except Exception as e:
            logger.error(f"Failed to prewarm server '{server_name}': {e}")
            self._failed_servers.add(server_name)
            
    async def get_prewarmed_server(self, server_name: str):
        """Get a prewarmed server aggregator if available"""
        return self._prewarmed_servers.get(server_name)
        
    def is_server_prewarmed(self, server_name: str) -> bool:
        """Check if a server is prewarmed and ready"""
        return server_name in self._prewarmed_servers
        
    @property
    def prewarming_status(self) -> dict:
        """Get prewarming status"""
        return {
            "is_prewarming": self._is_prewarming,
            "completed": self._prewarming_completed,
            "prewarmed_count": len(self._prewarmed_servers),
            "failed_count": len(self._failed_servers),
            "prewarmed_servers": list(self._prewarmed_servers.keys()),
            "failed_servers": list(self._failed_servers)
        }
        
    async def cleanup(self):
        """Clean shutdown of all prewarmed connections"""
        logger.info("Cleaning up prewarmed MCP server connections...")
        
        for server_name, aggregator in self._prewarmed_servers.items():
            try:
                await aggregator.close()
                logger.info(f"Closed prewarmed connection to {server_name}")
            except Exception as e:
                logger.error(f"Error closing connection to {server_name}: {e}")
                
        self._prewarmed_servers.clear()
        self._is_prewarming = False
        self._prewarming_completed = False

# Global singleton instance
mcp_prewarmer: Optional[MCPServerPrewarmer] = None

def get_mcp_prewarmer() -> MCPServerPrewarmer:
    """Get the global MCP prewarmer instance"""
    global mcp_prewarmer
    if mcp_prewarmer is None:
        raise RuntimeError("MCP prewarmer not initialized")
    return mcp_prewarmer

def initialize_mcp_prewarmer(context) -> MCPServerPrewarmer:
    """Initialize the global MCP prewarmer"""
    global mcp_prewarmer
    if mcp_prewarmer is None:
        mcp_prewarmer = MCPServerPrewarmer(context)
    return mcp_prewarmer 