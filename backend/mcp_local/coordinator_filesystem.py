"""
Coordinator Filesystem - Filesystem operation handling for Coordinator Agent.

This module contains functionality for safely intercepting and handling
filesystem operations from agents, applying security restrictions and
sending notifications.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class FilesystemHandler:
    """Handler for filesystem operations from agents."""
    
    def __init__(self, websocket_manager, filesystem_interceptor):
        """
        Initialize the filesystem handler.
        
        Args:
            websocket_manager: WebSocket manager for sending update notifications
            filesystem_interceptor: Interceptor for filesystem operations
        """
        self.websocket_manager = websocket_manager
        self.filesystem_interceptor = filesystem_interceptor
    
    async def handle_mcp_filesystem_operation(
        self,
        query_id: str,
        tool_name: str, 
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Intercept and handle MCP filesystem operations with the security model.
        
        This method sits between the agent and the actual MCP filesystem server,
        intercepting operations to enforce the security model and send notifications.
        
        Args:
            query_id: The query ID for the user session
            tool_name: The name of the tool to call (e.g., write_file)
            arguments: Arguments for the tool
        
        Returns:
            The result of the operation
        """
        try:
            # Map MCP tool names to our operation types
            operation_map = {
                "write_file": "write_file",
                "create_file": "write_file",
                "read_file": "read_file",
                "list_directory": "list_directory",
                "create_directory": "create_directory"
            }
            
            # Get the operation type
            operation = operation_map.get(tool_name)
            if not operation:
                raise ValueError(f"Unsupported filesystem operation: {tool_name}")
            
            # Get the path from arguments
            path = arguments.get("path")
            if not path:
                raise ValueError(f"No path provided for {operation} operation")
            
            # Intercept the operation
            interception_result = await self.handle_filesystem_operation(
                query_id=query_id,
                operation=operation,
                path=path,
                **arguments
            )
            
            # If this is a write operation, also send a WebSocket notification
            if operation == "write_file" and interception_result.get("notification_sent"):
                logger.info(f"📢 Notification sent for file creation: {path}")
            
            # At this point, you would normally proceed with the actual MCP operation
            # For now, we're just setting up the intercept layer
            
            return {
                "success": True,
                "operation": operation,
                "tool_name": tool_name,
                "path": path,
                "message": f"Filesystem operation {tool_name} intercepted and processed"
            }
            
        except ValueError as e:
            # Operation not allowed
            logger.warning(f"⚠️ Filesystem operation denied: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            # Other errors
            logger.error(f"❌ Error processing filesystem operation: {str(e)}")
            return {
                "success": False,
                "error": f"Internal error: {str(e)}"
            }
    
    async def handle_filesystem_operation(
        self,
        query_id: str,
        operation: str,
        path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Handle a filesystem operation, applying security restrictions and sending notifications.
        
        Args:
            query_id: The query ID for the user session
            operation: Type of operation (write_file, read_file, etc.)
            path: Path to the file being operated on
            **kwargs: Additional arguments for the operation
            
        Returns:
            Dict containing result of the operation
            
        Raises:
            ValueError: If the operation is not allowed
        """
        # Intercept the operation
        interception_result = await self.filesystem_interceptor.intercept_operation(
            query_id=query_id,
            operation=operation,
            path=path,
            is_coordinator=True,  # This is the coordinator agent
            **kwargs
        )
        
        # If the operation is allowed, perform it
        if interception_result.get("allowed", False):
            logger.info(f"✅ Filesystem operation {operation} allowed for {path}")
            
            # At this point, you would typically perform the actual filesystem operation
            # For now, we're just intercepting and notifying, not actually performing operations
            
            return {
                "success": True,
                "operation": operation,
                "path": path,
                "notification_sent": interception_result.get("notification_sent", False),
                "message": f"Filesystem operation {operation} processed successfully"
            }
        else:
            # Operation was not allowed
            logger.warning(f"⚠️ Filesystem operation {operation} denied for {path}")
            raise ValueError(f"Operation {operation} not allowed for {path}") 