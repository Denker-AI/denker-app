import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Any, Optional, Set, Callable, List, Union
from fastapi import WebSocket
from datetime import datetime
import websockets
from db.repositories import MessageRepository
from db.database import SessionLocal

logger = logging.getLogger(__name__)

# Connection states
CONNECTION_STATE_CONNECTED = "connected"
CONNECTION_STATE_CLOSING = "closing"
CONNECTION_STATE_CLOSED = "closed"

class WebSocketManager:
    """
    WebSocket manager for handling connections and message broadcasting
    """
    
    def __init__(self, message_handler: Optional[Callable] = None):
        """
        Initialize the WebSocket manager.
        
        Args:
            message_handler: Optional callback for handling specific client messages
        """
        self.active_connections: Dict[str, WebSocket] = {}
        # Track connection states
        self.connection_states: Dict[str, str] = {}
        self.logger = logging.getLogger(__name__)
        # Set logger to INFO level to ensure messages are displayed
        self.logger.setLevel(logging.INFO)
        # Add timestamp of last successful message for each connection
        self.last_successful_message: Dict[str, float] = {}
        # Track the conversation ID for each query ID
        self.query_to_conversation: Dict[str, str] = {}
        # Map agent session IDs to backend query IDs
        self.agent_session_to_query_id: Dict[str, str] = {}
        self.message_handler = message_handler
        self._lock = asyncio.Lock()
        self.conversation_ids: Dict[str, str] = {}  # Maps query_id to conversation_id
        self.pending_operations = {}  # For operation coordination
        self.pending_human_inputs: Dict[str, asyncio.Future] = {}  # For human input coordination
        
        # Log initialization
        self.logger.info("WebSocketManager initialized")
    
    def add_session_mapping(self, agent_session_id: str, query_id: str):
        """Store the mapping between an agent's session ID and the backend query ID."""
        if agent_session_id and query_id:
            self.agent_session_to_query_id[agent_session_id] = query_id
            self.logger.info(f"Added session mapping: Agent Session {agent_session_id} -> Query {query_id}")
        else:
            self.logger.warning(f"Attempted to add invalid session mapping: Agent Session={agent_session_id}, Query={query_id}")

    def get_query_id_for_session(self, agent_session_id: str) -> Optional[str]:
        """Retrieve the backend query ID corresponding to an agent's session ID."""
        query_id = self.agent_session_to_query_id.get(agent_session_id)
        if query_id:
            self.logger.debug(f"Found query ID {query_id} for agent session {agent_session_id}")
        else:
            self.logger.warning(f"Could not find query ID mapping for agent session {agent_session_id}")
        return query_id

    def remove_session_mapping_by_query_id(self, query_id: str):
        """Remove mapping entries associated with a specific query_id (e.g., on disconnect)."""
        sessions_to_remove = [agent_sid for agent_sid, qid in self.agent_session_to_query_id.items() if qid == query_id]
        if sessions_to_remove:
            for agent_sid in sessions_to_remove:
                del self.agent_session_to_query_id[agent_sid]
                self.logger.info(f"Removed session mapping for agent session {agent_sid} (query {query_id})")

    async def connect(self, websocket: WebSocket, query_id: str, conversation_id: Optional[str] = None):
        """
        Accept and store a new WebSocket connection

        Args:
            websocket: The WebSocket connection
            query_id: Unique ID for the query this connection will receive updates about
            conversation_id: Optional ID of the conversation this query belongs to
        """
        async with self._lock:
            try:
                # Check if we already have a connection for this query_id
                if query_id in self.active_connections:
                    self.logger.warning(f"⚠️ Existing connection found for {query_id}. Closing old connection.")
                    try:
                        # Try to close the old connection gracefully
                        if self.connection_states.get(query_id) != CONNECTION_STATE_CLOSING and self.connection_states.get(query_id) != CONNECTION_STATE_CLOSED:
                            self.connection_states[query_id] = CONNECTION_STATE_CLOSING
                            await self.active_connections[query_id].close()
                            self.connection_states[query_id] = CONNECTION_STATE_CLOSED
                            self.logger.info(f"✅ Successfully closed previous connection for {query_id}")
                    except Exception as e:
                        self.logger.error(f"❌ Error closing existing connection: {str(e)}")
                    finally:
                        # Make sure we remove the old connection anyway
                        if query_id in self.active_connections:
                            del self.active_connections[query_id]
                        if query_id in self.connection_states:
                            del self.connection_states[query_id]
                        if query_id in self.last_successful_message:
                            del self.last_successful_message[query_id]
                        self.logger.info(f"🧹 Cleaned up previous connection resources for {query_id}")
                
                # Record conversation ID if provided
                if conversation_id:
                    self.query_to_conversation[query_id] = conversation_id
                    self.logger.info(f"📝 Recorded conversation ID mapping: {query_id} -> {conversation_id}")
                
                # Record successful connection timestamp
                self.last_successful_message[query_id] = time.time()
                
                # Store the connection
                self.active_connections[query_id] = websocket
                self.connection_states[query_id] = CONNECTION_STATE_CONNECTED
                
                # Add a small delay before sending the ping to allow the connection to stabilize
                await asyncio.sleep(0.5)  # 500ms delay
                
                # Send ping with proper error handling
                # Ping failure doesn't invalidate the connection anymore
                try:
                    if self.connection_states.get(query_id) == CONNECTION_STATE_CONNECTED:
                        self.logger.info(f"🔄 Sending initial ping test to {query_id}...")
                        await websocket.send_text("ping")
                        self.logger.info(f"✅ Initial ping test sent successfully to {query_id}")
                except Exception as ping_error:
                    self.logger.warning(f"⚠️ Failed initial ping test for {query_id}: {str(ping_error)}")
                    self.logger.info(f"👉 Continuing with connection despite ping failure - this is normal for some clients")
                    # We don't consider the connection invalid just because ping failed
                
                # Log total active connections
                self.logger.info(f"🔢 Total active WebSocket connections: {len(self.active_connections)}")
                
            except Exception as e:
                self.logger.error(f"❌ Error in WebSocket connection process: {str(e)}")
                import traceback
                self.logger.error(f"WebSocket connection error traceback: {traceback.format_exc()}")
                
                # If we already stored the connection but had an error elsewhere, 
                # make sure we clean it up to prevent leaks
                if query_id in self.active_connections:
                    del self.active_connections[query_id]
                if query_id in self.connection_states:
                    del self.connection_states[query_id]
                self.logger.info(f"🧹 Cleaned up connection for {query_id} after error")
                
                # Rethrow the exception
                raise
    
    async def disconnect(self, query_id: str):
        """
        Disconnect a client
        
        Args:
            query_id: The query ID for the connection
        """
        if query_id in self.active_connections:
            # Check if already in closing state
            if self.connection_states.get(query_id) == CONNECTION_STATE_CLOSING or self.connection_states.get(query_id) == CONNECTION_STATE_CLOSED:
                self.logger.info(f"Connection {query_id} already in {self.connection_states.get(query_id)} state, skipping disconnect")
                
                # Still remove from our tracking
                if query_id in self.active_connections:
                    del self.active_connections[query_id]
                if query_id in self.connection_states:
                    del self.connection_states[query_id]
                if query_id in self.last_successful_message:
                    del self.last_successful_message[query_id]
                if query_id in self.query_to_conversation:
                    del self.query_to_conversation[query_id]
                # Also remove any associated session mappings
                self.remove_session_mapping_by_query_id(query_id)
                return
                
            # Get the websocket before removing it
            websocket = self.active_connections[query_id]
            
            # Mark as closing
            self.connection_states[query_id] = CONNECTION_STATE_CLOSING
            
            # Remove from active connections
            del self.active_connections[query_id]
            
            # Remove from last successful message tracking if present
            if query_id in self.last_successful_message:
                del self.last_successful_message[query_id]
            
            # Remove from query-to-conversation mapping
            if query_id in self.query_to_conversation:
                del self.query_to_conversation[query_id]
            
            # Also remove any associated session mappings
            self.remove_session_mapping_by_query_id(query_id)
                
            self.logger.info(f"Client disconnected: {query_id}. Remaining connections: {len(self.active_connections)}")
            
            # Try to close the websocket gracefully - but don't block on it
            try:
                # Close directly instead of scheduling as a task
                await self._close_websocket_gracefully(websocket, query_id)
            except Exception as e:
                self.logger.warning(f"Non-critical error when closing websocket for {query_id}: {str(e)}")
        else:
            self.logger.warning(f"Attempted to disconnect non-existent connection: {query_id}")
            
    async def _close_websocket_gracefully(self, websocket, query_id: str):
        """
        Helper method to close a websocket gracefully with error handling
        
        Args:
            websocket: The websocket to close
            query_id: The query ID for logging
        """
        try:
            if self.connection_states.get(query_id) != CONNECTION_STATE_CLOSED:
                await websocket.close(code=1000, reason="Graceful disconnect")
                self.connection_states[query_id] = CONNECTION_STATE_CLOSED
                self.logger.info(f"🔌 Successfully closed websocket for {query_id}")
        except Exception as e:
            self.logger.warning(f"⚠️ Error during graceful websocket close for {query_id}: {str(e)}")
            # Non-critical error, just log it
        finally:
            # Ensure connection state is updated even if close fails
            self.connection_states[query_id] = CONNECTION_STATE_CLOSED
    
    def is_connected(self, query_id: str) -> bool:
        """
        Check if a client is connected
        
        Args:
            query_id: The query ID to check
            
        Returns:
            bool: True if connected, False otherwise
        """
        return query_id in self.active_connections and self.connection_states.get(query_id) == CONNECTION_STATE_CONNECTED
    
    def get_conversation_id(self, query_id: str) -> Optional[str]:
        """
        Get the conversation ID for a query ID
        
        Args:
            query_id: The query ID
            
        Returns:
            Optional[str]: The conversation ID, or None if not found
        """
        return self.query_to_conversation.get(query_id)
    
    async def send_message(self, query_id: str, message: str):
        """
        Send a raw text message to a specific client
        
        Args:
            query_id: The query ID for the connection
            message: The message to send
        """
        # Check if we can send messages to this connection
        if not self.is_connected(query_id):
            self.logger.warning(f"⚠️ Cannot send message - {query_id} not connected or in closing state")
            return False
        
        try:
            await self.active_connections[query_id].send_text(message)
            # Record successful message timestamp
            self.last_successful_message[query_id] = time.time()
            return True
        except Exception as e:
            self.logger.error(f"Error sending message to WebSocket {query_id}: {str(e)}")
            if "close message has been sent" in str(e) or "connection closed" in str(e).lower():
                self.logger.warning(f"Connection {query_id} appears to be closed, marking as closing")
                self.connection_states[query_id] = CONNECTION_STATE_CLOSING
            await self.disconnect(query_id)
            return False
    
    async def send_json(self, query_id: str, data: Dict[str, Any]):
        """
        Send JSON data to a specific client

        Args:
            query_id: The query ID for the connection
            data: The data to send
        """
        sent_successfully = False
        websocket = None # Initialize websocket variable
        
        for attempt in range(3): # Try up to 3 times (0, 1, 2)
            async with self._lock: # Lock during check
                websocket = self.active_connections.get(query_id)
                connection_state = self.connection_states.get(query_id)

            if websocket and connection_state == CONNECTION_STATE_CONNECTED:
                try:
                    json_message = json.dumps(data)
                    await websocket.send_text(json_message)
                    self.logger.info(f"📤 Sending WebSocket message to {query_id} (type: {data.get('update_type', 'unknown')})")
                    self.last_successful_message[query_id] = time.time()
                    sent_successfully = True
                    break # Exit loop on success
                except (websockets.exceptions.ConnectionClosedOK, websockets.exceptions.ConnectionClosedError) as e:
                    self.logger.warning(f"🔌 Connection closed for {query_id} while trying to send (attempt {attempt + 1}): {type(e).__name__}")
                    # Schedule disconnect non-blockingly
                    asyncio.create_task(self.disconnect(query_id))
                    sent_successfully = False # Ensure we log the final warning if disconnect fails somehow
                    break # Don't retry if connection is closed
                except Exception as e:
                    self.logger.error(f"❌ Error sending WebSocket message to {query_id} (attempt {attempt + 1}): {str(e)}", exc_info=False) # Avoid overly verbose logs for common send errors
                    # Optionally disconnect on persistent errors?
                    # asyncio.create_task(self.disconnect(query_id))
                    sent_successfully = False # Treat other errors as temporary? Could retry.
                    # Let's break for now to avoid potential infinite loops on bad data
                    break 
            
            # If not connected/found or send failed temporarily, wait before retrying (unless it's the last attempt)
            if not sent_successfully and attempt < 2: 
                self.logger.debug(f"Connection for {query_id} not ready or send failed, attempt {attempt + 1}. Retrying in 200ms...")
                await asyncio.sleep(0.2)

        # If loop finishes without success, log the final warning
        if not sent_successfully:
             # Re-check state just before logging final warning
             async with self._lock:
                websocket = self.active_connections.get(query_id)
                connection_state = self.connection_states.get(query_id)
             current_state = connection_state if websocket else "not found"
             # Avoid logging overly alarming warnings if it simply disconnected during the process
             if current_state != CONNECTION_STATE_CLOSED and current_state != CONNECTION_STATE_CLOSING:
                self.logger.warning(f"⚠️ Cannot send JSON - {query_id} not connected or ready after retries (final state: {current_state})")
             else:
                 self.logger.info(f"Did not send message to {query_id} as connection was closed/closing (final state: {current_state})")

    def _get_client_id(self, websocket: WebSocket) -> Optional[str]:
        """Get client ID for a WebSocket connection."""
        for client_id, conn in self.active_connections.items():
            if conn == websocket:
                return client_id
        return None
    
    async def send_consolidated_update(
        self, 
        query_id: str,
        update_type: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        workflow_type: Optional[str] = None
    ):
        """
        Send a structured update message to a specific client via WebSocket.
        
        Args:
            query_id: The query ID of the client to send the message to.
            update_type: The category of the update (e.g., 'status', 'step', 'result', 'error', 'clarification').
            message: A human-readable message summarizing the update.
            data: Optional dictionary containing additional structured data.
            workflow_type: Optional string indicating the workflow ('router', 'orchestrator', etc.)
        """
        # Log the workflow type if provided
        if workflow_type:
            self.logger.debug(f"[{query_id}] send_consolidated_update called with workflow_type: {workflow_type}")
        else:
            self.logger.debug(f"[{query_id}] send_consolidated_update called without specific workflow_type.")
            
        # <<< START Conditional Logic Placeholder >>>
        # Example of how you might use the workflow_type later:
        if workflow_type == 'orchestrator':
            # Specific handling/formatting for orchestrator updates
            self.logger.info(f"[{query_id}] Handling update specifically for orchestrator workflow.")
            # Modify message or data based on orchestrator needs if necessary
            pass
        elif workflow_type == 'router':
            # Specific handling/formatting for router updates
            self.logger.info(f"[{query_id}] Handling update specifically for router workflow.")
            # Modify message or data based on router needs if necessary
            pass
        else:
            # Default handling for unspecified or other workflow types
            self.logger.info(f"[{query_id}] Handling update with default logic (workflow: {workflow_type or 'None'}).")
            pass
        # <<< END Conditional Logic Placeholder >>>
        
        full_payload = {
            "update_type": update_type,
            "queryId": query_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "message": message,
            "data": data if data is not None else {},
        }
        
        # <<< ADDED: Log the payload being sent >>>
        self.logger.info(f"📤 Sending WebSocket message to {query_id} (Type: {full_payload.get('update_type', 'MISSING')}, Workflow: {workflow_type or 'N/A'}) - Payload Summary: {str(full_payload)[:200]}...")
        # <<< END ADDED >>>

        await self.send_json(query_id, full_payload)
        
    async def handle_client_message(self, query_id: str, message_data: str):
        """
        Handle messages from the client, including permission responses
        
        Args:
            query_id: The query ID for the connection
            message_data: Raw message data from client
        """
        try:
            data = json.loads(message_data)
            message_type = data.get('type', '')
            
            self.logger.info(f"📥 Received message from client {query_id}: {message_type}")
            
            # Log full message for debugging in a safe way (limit size)
            log_message = message_data[:200] + '...' if len(message_data) > 200 else message_data
            self.logger.info(f"📥 Message content: {log_message}")
            
            # Handle filesystem permission response
            if message_type == 'filesystem_permission_response':
                operation_id = data.get('operation_id')
                approved = data.get('approved', False)
                
                # Get the filesystem interceptor
                from .filesystem_interceptor import get_filesystem_interceptor
                filesystem_interceptor = get_filesystem_interceptor()
                
                # Resolve the pending operation future
                if operation_id in filesystem_interceptor.pending_operations:
                    future = filesystem_interceptor.pending_operations[operation_id]
                    future.set_result({
                        "allowed": approved,
                        "operation_id": operation_id,
                        "reason": "User response"
                    })
                    del filesystem_interceptor.pending_operations[operation_id]
                    self.logger.info(f"✅ Received permission response for {operation_id}: {approved}")
                else:
                    self.logger.warning(f"⚠️ Received permission response for unknown operation: {operation_id}")
            
            # Handle human input response
            elif message_type == 'human_input_response':
                input_id = data.get('input_id')
                user_input = data.get('input', '')
                query_id = data.get('query_id') # Get query_id from the message payload
                
                if not query_id:
                    self.logger.error(f"Received human_input_response without query_id. Cannot save to history.")
                    # Attempt to resolve future anyway if input_id exists
                    if input_id in self.pending_human_inputs:
                         future = self.pending_human_inputs[input_id]
                         future.set_result({
                             "input": user_input,
                             "input_id": input_id,
                             "timestamp": datetime.now().isoformat(),
                             "success": False, # Indicate failure due to missing context
                             "error": "Missing query_id in response"
                         })
                         del self.pending_human_inputs[input_id]
                    return # Use return instead of continue

                # Save human input to message history
                conversation_id = self.query_to_conversation.get(query_id)
                if conversation_id:
                    try:
                        # Get a new DB session (important for background tasks/async context)
                        db = SessionLocal()
                        try:
                            message_repo = MessageRepository(db)
                            # Save as a 'user' message (or potentially a dedicated 'human_input' role?)
                            message_repo.create({
                                "conversation_id": conversation_id,
                                "content": user_input, # Save the actual user input
                                "role": "user", # Treat human input as a user message
                                "metadata": { # Add metadata for context
                                    "query_id": query_id,
                                    "human_input_request_id": input_id,
                                    "is_human_input_response": True
                                }
                            })
                            self.logger.info(f"Saved human input for query {query_id} to conversation {conversation_id}")
                        finally:
                            db.close() # Ensure session is closed
                    except Exception as db_err:
                        self.logger.error(f"Failed to save human input to DB for conversation {conversation_id}: {db_err}")
                else:
                    self.logger.warning(f"Could not find conversation_id for query {query_id} to save human input.")
                
                # Resolve the pending human input future if it exists
                if input_id in self.pending_human_inputs:
                    future = self.pending_human_inputs[input_id]
                    future.set_result({
                        "input": user_input,
                        "input_id": input_id,
                        "timestamp": datetime.now().isoformat()
                    })
                    del self.pending_human_inputs[input_id]
                    self.logger.info(f"✅ Received human input for request {input_id}")
                else:
                    self.logger.warning(f"⚠️ Received human input for unknown request: {input_id}")
            
            # Handle initialization message
            elif message_type == 'init':
                self.logger.info(f"🔧 Initialization message received from {query_id}")
                # Send back a confirmation that we received the init
                await self.send_consolidated_update(
                    query_id=query_id,
                    update_type="status",
                    message="WebSocket connection verified",
                    data={"status": "ready"}
                )
                self.logger.info(f"✅ Responded to init message for {query_id}")
            
            # Handle ping/pong
            elif message_type == 'ping':
                # Send pong response
                await self.send_json(query_id, {"type": "pong", "timestamp": datetime.now().isoformat()})
                self.logger.debug(f"🏓 Ping/pong with {query_id}")
            
            # Handle close
            elif message_type == 'close':
                self.logger.info(f"🔌 Client requested close for {query_id}")
                # Client wants to close, disconnect them
                await self.disconnect(query_id)
            
            # Handle unknown message types  
            else:
                self.logger.warning(f"⚠️ Unknown message type received: {message_type}")
                # Still send a response so client knows message was received
                await self.send_json(query_id, {
                    "type": "response", 
                    "to": message_type,
                    "status": "unknown_type",
                    "timestamp": datetime.now().isoformat()
                })
                
        except json.JSONDecodeError:
            self.logger.error(f"❌ Invalid JSON received from client: {message_data}")
            try:
                # Try to send an error response
                await self.send_consolidated_update(
                    query_id=query_id,
                    update_type="error",
                    message="Invalid JSON received",
                    data={"error": "json_decode_error"}
                )
            except Exception:
                self.logger.error("Failed to send error response for invalid JSON")
        except Exception as e:
            self.logger.error(f"❌ Error handling client message: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())

    async def request_human_input(
        self, 
        query_id: str, 
        tool_name: str, 
        input_prompt: str,
        tool_description: Optional[str] = None,
        timeout: int = 300  # 5 minute timeout
    ) -> Dict[str, Any]:
        """
        Request human input via WebSocket and wait for response
        
        Args:
            query_id: The client/query ID to request input from
            tool_name: The name of the tool requesting input
            input_prompt: The prompt to show to the user
            tool_description: Optional description of why the input is needed
            timeout: Timeout in seconds for the request
            
        Returns:
            Dict containing the user's input and status
        """
        # --- ADDED: Logging Start --- 
        self.logger.info(f"Attempting to request human input for query: {query_id}, tool: {tool_name}")
        # --- END ADDED ---

        # Check if client is connected
        if not self.is_connected(query_id):
            self.logger.warning(f"Cannot request human input - client {query_id} not connected")
            return {"success": False, "error": "Client not connected", "input": None}
            
        # Generate a unique ID for this input request
        input_id = f"input_{tool_name}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Create a future to wait for the response
        future = asyncio.Future()
        self.pending_human_inputs[input_id] = future
        self.logger.info(f"Created Future and stored pending input for key: {input_id}") # Log future creation
        
        # Send the request via WebSocket
        try:
            # --- ADDED: Logging Before Send --- 
            self.logger.info(f"Attempting to send 'human_input' update via WebSocket for query: {query_id}, input_id: {input_id}")
            # --- END ADDED ---
            await self.send_consolidated_update(
                query_id=query_id,
                update_type="human_input",
                message=input_prompt,
                data={
                    "input_id": input_id,
                    "tool_name": tool_name,
                    "tool_description": tool_description,
                    "timeout": timeout
                }
            )
            self.logger.info(f"Successfully sent 'human_input' update via WebSocket for query: {query_id}, input_id: {input_id}") # Log success
            
            self.logger.info(f"Human input requested with ID {input_id} for tool {tool_name}")
            
            # Wait for the response with timeout
            try:
                response = await asyncio.wait_for(future, timeout)
                self.logger.info(f"Received human input for request {input_id}")
                return {
                    "success": True, 
                    "input": response.get("input", ""),
                    "input_id": input_id
                }
            except asyncio.TimeoutError:
                self.logger.warning(f"Human input request {input_id} timed out after {timeout}s")
                if input_id in self.pending_human_inputs:
                    del self.pending_human_inputs[input_id]
                return {"success": False, "error": "Request timed out", "input": None}
                
        except Exception as e:
            self.logger.error(f"Error requesting human input: {str(e)}")
            if input_id in self.pending_human_inputs:
                del self.pending_human_inputs[input_id]
            return {"success": False, "error": str(e), "input": None}

# Singleton instance
_websocket_manager = None

def get_websocket_manager() -> WebSocketManager:
    """
    Get the singleton WebSocketManager instance
    
    Returns:
        The WebSocketManager instance
    """
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    return _websocket_manager 