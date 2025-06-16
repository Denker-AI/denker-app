"""
Coordinator WebSocket - WebSocket handling for Coordinator Agent.

This module contains the WebSocket endpoint and message processing logic, 
separating it from the main coordination logic for better organization.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Callable

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from .core.websocket_manager import WebSocketManager
from mcp_agent.event_progress import ProgressAction

# Add OTel imports
from opentelemetry import context as otel_context, baggage

logger = logging.getLogger(__name__)

class AgentRequest(BaseModel):
    """Agent request received through WebSocket."""
    query: str
    workflow_type: str = "router"
    session_id: Optional[str] = None
    use_agents: list = []
    temperature: float = 0.3
    max_tokens: int = 4096
    role: str = "user"

async def send_agent_update(websocket_manager: WebSocketManager, query_id: str, message: str, data: Optional[Dict[str, Any]] = None):
    """
    Send a simple update message to a client via WebSocket.
    This is a utility function for testing WebSocket connectivity.
    
    Args:
        websocket_manager: The WebSocket manager instance
        query_id: The client ID to send the update to
        message: The message to send
        data: Additional data to include (optional)
    
    Returns:
        bool: Whether the message was sent successfully
    """
    try:
        if not websocket_manager:
            logger.error("Cannot send update: WebSocket manager is None")
            return False
            
        if not query_id:
            logger.error("Cannot send update: query_id is empty")
            return False
            
        # Check if client is connected
        if not websocket_manager.is_connected(query_id):
            logger.warning(f"Client {query_id} not connected, cannot send update")
            return False
            
        # Create default data if not provided
        update_data = data or {}
        update_data.update({
            "timestamp": datetime.now().isoformat(),
            "agent": "test_agent",
            "role": "system"
        })
        
        # Send the update
        logger.info(f"Sending manual update to client {query_id}: {message}")
        success = await websocket_manager.send_consolidated_update(
            query_id=query_id,
            update_type="step",
            message=message,
            data=update_data
        )
        
        if success:
            logger.info(f"Successfully sent manual update to client {query_id}")
        else:
            logger.warning(f"Failed to send manual update to client {query_id}")
            
        return success
    except Exception as e:
        logger.error(f"Error sending manual update: {str(e)}")
        import traceback
        logger.error(f"Manual update error traceback: {traceback.format_exc()}")
        return False

async def handle_websocket_connection(
    websocket: WebSocket, 
    client_id: str,
    websocket_manager: WebSocketManager,
    process_query_fn: Callable
):
    """
    Handle a WebSocket connection from a client.
    
    Args:
        websocket: The WebSocket connection
        client_id: The client ID for the connection
        websocket_manager: The WebSocket manager instance
        process_query_fn: Function to process queries
    """
    connection_success = False
    
    try:
        # First accept the connection
        await websocket.accept()
        logger.info(f"WebSocket connection accepted for client: {client_id}")
        
        # Add a small delay to ensure the connection is stable
        await asyncio.sleep(0.1)
        
        # Then connect with the WebSocket manager
        try:
            await websocket_manager.connect(websocket, client_id)
            connection_success = True
            logger.info(f"Client {client_id} successfully connected to WebSocket manager")
        except Exception as connect_error:
            logger.error(f"Failed to register client {client_id} with WebSocket manager: {str(connect_error)}")
            # Add more detailed error logging
            import traceback
            logger.error(f"Connection error traceback: {traceback.format_exc()}")
            await websocket.close(code=1011, reason="Failed to register with WebSocket manager")
            return
        
        # Send connection confirmation only if connection was successful
        if connection_success:
            try:
                success = await websocket_manager.send_consolidated_update(
                    query_id=client_id,
                    update_type="status",
                    message="WebSocket connection established",
                    data={
                        "status": "connected",
                        "timestamp": datetime.now().isoformat(),
                        "role": "system"
                    }
                )
                if not success:
                    logger.warning(f"Failed to send connection confirmation to client {client_id}")
                else:
                    # Also send a test update to verify the WebSocket is fully functional
                    await asyncio.sleep(1)  # Wait a moment to ensure the client has processed the first message
                    test_update_success = await send_agent_update(
                        websocket_manager, 
                        client_id, 
                        "WebSocket connection test message",
                        {"test": True, "status": "test_message"}
                    )
                    if test_update_success:
                        logger.info(f"Test update sent successfully to client {client_id}")
                    else:
                        logger.warning(f"Failed to send test update to client {client_id}")
            except Exception as confirmation_error:
                logger.error(f"Error sending connection confirmation to client {client_id}: {str(confirmation_error)}")
                # Don't close the connection for confirmation failure
        
        # --- MODIFICATION: Remove main query processing loop --- 
        # The main agent processing is now triggered by the REST endpoint.
        # This WebSocket connection is primarily for receiving status/step updates 
        # pushed from the backend and handling control messages from the client.
        
        # We still need a loop to keep the connection alive and handle client control messages.
        while connection_success and client_id in websocket_manager.active_connections:
            try:
                # Wait for incoming messages with a timeout
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                except asyncio.TimeoutError:
                    # Send a keep-alive ping to keep the connection open
                    if websocket_manager.is_connected(client_id):
                        try:
                            await websocket.send_text('{\"type\":\"keep-alive\",\"timestamp\":\"' + datetime.now().isoformat() + '\"}')
                        except Exception as ping_error:
                            logger.warning(f"Failed to send keep-alive ping to client {client_id}: {str(ping_error)}")
                            break # Assume connection broken if ping fails
                    else:
                        logger.warning(f"Connection {client_id} no longer in connected state during keep-alive, breaking loop")
                        break
                    continue # Continue loop after timeout/ping
                
                # Process only known control messages from the client
                try:
                    message_data = json.loads(data)
                    message_type = message_data.get("type", "")
                    
                    # Handle specific control messages (close, permissions, ping confirmation?)
                    # Let WebSocketManager handle relevant messages directly
                    if message_type in ["filesystem_permission_response", "ping", "close", "human_input_response"]:
                        logger.info(f"Received control message from client {client_id}: {message_type}")
                        await websocket_manager.handle_client_message(client_id, data)
                        # If the message was 'close', handle_client_message calls disconnect, 
                        # which should remove client_id from active_connections, breaking the loop.
                    else:
                        # Ignore other message types received from client in this context
                        logger.warning(f"Ignoring unexpected message type '{message_type}' from client {client_id} via WebSocket.")
                        
                except json.JSONDecodeError as json_error:
                    logger.error(f"Invalid JSON received from client {client_id}: {str(json_error)}")
                    # Consider sending an error message back? 
                    # Probably not necessary if client shouldn't be sending arbitrary JSON.
            
            except Exception as e:
                # Catch potential errors in the receive/process loop 
                logger.error(f"Error in WebSocket receive loop for {client_id}: {str(e)}")
                import traceback
                logger.error(f"WebSocket receive loop error traceback: {traceback.format_exc()}")
                # If an error occurs, break the loop to disconnect
                break 
        # --- END MODIFICATION ---

    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected during connection setup")
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
        import traceback
        logger.error(f"Error traceback: {traceback.format_exc()}")
    
    finally:
        # Clean up the connection
        if websocket_manager and websocket_manager.is_connected(client_id):
            logger.info(f"Closing WebSocket connection for client {client_id}")
            await websocket_manager.disconnect(client_id)
            logger.info(f"WebSocket connection closed for client {client_id}") 