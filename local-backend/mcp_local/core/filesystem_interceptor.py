"""
Filesystem operations interceptor for MCP filesystem server.
Monitors file operations and sends notifications for specific actions.
"""

import logging
import os
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, Callable, Awaitable

from .websocket_manager import WebSocketManager, get_websocket_manager

logger = logging.getLogger(__name__)

class FilesystemInterceptor:
    """
    Intercepts filesystem operations and sends notifications about file operations.
    
    This class implements the restricted file operations model where:
    1. Only coordinator agents can create and read files
    2. No editing of existing files is permitted
    3. Users are notified of file creations with file name and location
    4. User permission is required for write operations
    """
    
    def __init__(self, websocket_manager: Optional[WebSocketManager] = None):
        """
        Initialize the FilesystemInterceptor
        
        Args:
            websocket_manager: The WebSocket manager to use for notifications
        """
        self.websocket_manager = websocket_manager or get_websocket_manager()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        # Store pending permission requests
        self.pending_operations = {}
        
    async def request_permission(
        self,
        query_id: str,
        operation: str,
        path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Request user permission for a filesystem operation
        
        Args:
            query_id: The query ID for the user session
            operation: Type of operation (write_file, read_file, etc.)
            path: Path to the file being operated on
            **kwargs: Additional operation arguments
            
        Returns:
            Dict with permission result
        """
        # Generate unique operation ID
        operation_id = str(uuid.uuid4())
        
        # Build permission request
        permission_request = {
            "operation_id": operation_id,
            "operation": operation,
            "path": path,
            "arguments": kwargs
        }
        
        # Create readable message based on operation type
        message = f"Permission requested for {operation} on {path}"
        if operation == "write_file":
            content = kwargs.get("content", "")
            content_preview = content[:100] + "..." if len(content) > 100 else content
            message = f"Permission requested to write to file: {path}"
        elif operation == "create_directory":
            message = f"Permission requested to create directory: {path}"
        elif operation == "move_file":
            source = kwargs.get("source", "")
            destination = kwargs.get("destination", "")
            message = f"Permission requested to move file from {source} to {destination}"
            
        # Send permission request via WebSocket
        self.logger.info(f"Requesting permission for {operation} on {path}")
        await self.websocket_manager.send_consolidated_update(
            query_id=query_id,
            update_type="filesystem_permission",
            message=message,
            data=permission_request
        )
        
        # Store pending operation and create Future for response
        permission_future = asyncio.Future()
        self.pending_operations[operation_id] = permission_future
        
        # Wait for response with timeout
        try:
            self.logger.info(f"Waiting for permission response for {operation_id}")
            result = await asyncio.wait_for(permission_future, timeout=60)  # 60-second timeout
            self.logger.info(f"Permission response received for {operation_id}: {result}")
            return result
        except asyncio.TimeoutError:
            # Default to deny on timeout
            self.logger.warning(f"⚠️ Permission request timed out for {operation} on {path}")
            if operation_id in self.pending_operations:
                del self.pending_operations[operation_id]
            return {"allowed": False, "reason": "Request timed out"}
        
    async def intercept_operation(
        self,
        query_id: str,
        operation: str,
        path: str,
        is_coordinator: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Intercept a filesystem operation, apply access rules, and notify users
        
        Args:
            query_id: The query ID for the user session
            operation: Type of operation (write_file, read_file, etc.)
            path: Path to the file being operated on
            is_coordinator: Whether this operation is from the coordinator agent
            **kwargs: Additional arguments for the operation
            
        Returns:
            Dict containing result of the operation interception
            
        Raises:
            ValueError: If the operation is not allowed
        """
        # Security check - only coordinator can create/read files
        if not is_coordinator:
            self.logger.warning(f"⚠️ Non-coordinator agent attempted {operation} on {path}")
            raise ValueError(f"Operation {operation} not allowed: only coordinator agents can perform file operations")
            
        # Restricted operations - no editing
        if operation in ["edit_file"]:
            self.logger.warning(f"⚠️ Edit operation attempted on {path} - disallowed by security policy")
            raise ValueError(f"Operation {operation} not allowed: editing existing files is disabled")
        
        # Log the operation
        self.logger.info(f"📂 Intercepted {operation} on {path}")
        
        # Operations that require permission
        permission_required_operations = ["write_file", "create_directory", "move_file"]
        
        if operation in permission_required_operations and is_coordinator:
            # Request user permission
            permission_result = await self.request_permission(
                query_id=query_id, 
                operation=operation, 
                path=path, 
                **kwargs
            )
            
            if not permission_result.get("allowed", False):
                reason = permission_result.get("reason", "Permission denied by user")
                self.logger.warning(f"⚠️ {operation} on {path} denied: {reason}")
                raise ValueError(f"Operation {operation} not allowed: {reason}")
            
            # Continue with the operation if permission was granted
            self.logger.info(f"✅ {operation} on {path} approved by user")
            
            # Handle file creation operation (write_file)
            if operation == "write_file":
                file_name = os.path.basename(path)
                directory = os.path.dirname(path)
                
                # Send notification about file creation
                await self.websocket_manager.send_consolidated_update(
                    query_id=query_id,
                    update_type="filesystem",
                    message=f"New file created: {file_name} in {directory}",
                    data={
                        "operation": "create",
                        "file_path": path,
                        "file_name": file_name,
                        "directory": directory
                    }
                )
                
                return {
                    "allowed": True,
                    "operation": operation,
                    "path": path,
                    "notification_sent": True
                }
                
            # Handle directory creation
            elif operation == "create_directory":
                directory_name = os.path.basename(path)
                parent_dir = os.path.dirname(path)
                
                # Send notification about directory creation
                await self.websocket_manager.send_consolidated_update(
                    query_id=query_id,
                    update_type="filesystem",
                    message=f"New directory created: {directory_name} in {parent_dir}",
                    data={
                        "operation": "create_directory",
                        "directory_path": path,
                        "directory_name": directory_name,
                        "parent_directory": parent_dir
                    }
                )
                
                return {
                    "allowed": True,
                    "operation": operation,
                    "path": path,
                    "notification_sent": True
                }
                
            # Handle move file
            elif operation == "move_file":
                source = kwargs.get("source", path)
                destination = kwargs.get("destination", "")
                source_name = os.path.basename(source)
                destination_name = os.path.basename(destination)
                
                # Send notification about move operation
                await self.websocket_manager.send_consolidated_update(
                    query_id=query_id,
                    update_type="filesystem",
                    message=f"File moved: {source_name} to {destination_name}",
                    data={
                        "operation": "move_file",
                        "source_path": source,
                        "destination_path": destination,
                        "source_name": source_name,
                        "destination_name": destination_name
                    }
                )
                
                return {
                    "allowed": True,
                    "operation": operation,
                    "path": path,
                    "notification_sent": True
                }
            
        # Allow read operations without permission
        elif operation == "read_file" and is_coordinator:
            return {
                "allowed": True,
                "operation": operation,
                "path": path,
                "notification_sent": False
            }
            
        # Handle directory list operations without permission
        elif operation == "list_directory" and is_coordinator:
            return {
                "allowed": True,
                "operation": operation,
                "path": path,
                "notification_sent": False
            }
            
        else:
            # Default case - deny any other operations
            self.logger.warning(f"⚠️ Unsupported operation {operation} on {path}")
            raise ValueError(f"Operation {operation} not supported or not allowed")

# Singleton instance
_filesystem_interceptor = None

def get_filesystem_interceptor() -> FilesystemInterceptor:
    """
    Get the singleton FilesystemInterceptor instance
    
    Returns:
        The FilesystemInterceptor instance
    """
    global _filesystem_interceptor
    if _filesystem_interceptor is None:
        _filesystem_interceptor = FilesystemInterceptor()
    return _filesystem_interceptor 