from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks, Body, WebSocket, WebSocketDisconnect, Request
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional, Union
from uuid import uuid4
import time
from pydantic import BaseModel
import logging
import traceback
import threading
import asyncio
import uuid
import json
from datetime import datetime

from db.database import get_db
from db.repositories import AgentLogRepository
from db.models import User
from core.auth import get_current_user_dependency
from agents.intention_agent import IntentionAgent
from mcp_local.coordinator_agent import CoordinatorAgent
from mcp_local.core.websocket_manager import get_websocket_manager
from services.vertex_ai import vertex_ai_service
from config.settings import settings
from services.qdrant_service import mcp_qdrant_service
from core.global_coordinator import get_coordinator_dependency
from services.health_checks import mcp_health_service

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Only add the handler if it doesn't already exist
handler_name = "agents_console_handler"
if not any(getattr(h, "name", None) == handler_name for h in logger.handlers):
    console_handler = logging.StreamHandler()
    console_handler.name = handler_name  # Set a name to identify this handler
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

router = APIRouter()

# Get the appropriate user dependency based on DEBUG mode
current_user_dependency = get_current_user_dependency()

# Keeps track of queries being processed to prevent duplicates
active_queries = {}
# Lock for thread safety when modifying active_queries
query_lock = threading.Lock()

# Add a state enum for query processing
class QueryState:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

# Create a dict to track active processor tasks
_active_processors = {}
_processors_lock = asyncio.Lock()

class IntentionRequest(BaseModel):
    query_id: str
    text: Optional[str] = None
    screenshot: Optional[str] = None
    mode: str  # 'text', 'screenshot', or 'both'

class IntentionResponse(BaseModel):
    query_id: str
    options: list
    error: Optional[str] = None

class CoordinatorRequest(BaseModel):
    query_id: str
    context: Dict[str, Any] = {}
    language: Optional[str] = None
    dataset_id: Optional[str] = None
    time_range: Optional[str] = None
    filters: Optional[Dict[str, Any]] = {}

# Define request body model
class HumanInputPayload(BaseModel):
    input: str
    input_id: str
    request_id: Optional[str] = None # Optional but recommended for future robustness

@router.post("/intention", response_model=IntentionResponse)
async def process_intention(request: IntentionRequest):
    """Process user intention based on text and/or screenshot."""
    start_time = time.time()
    logger.info(f"Processing intention for query_id: {request.query_id}")
    logger.info(f"Mode: {request.mode}")
    
    try:
        # Log request in database
        logger.info(f"Request details - Mode: {request.mode}, "
                   f"Has text: {bool(request.text)}, "
                   f"Has screenshot: {bool(request.screenshot)}")
        
        # Initialize intention agent (only once)
        intention_agent = IntentionAgent()
        
        # Process based on mode
        if request.mode == 'text' and not request.text:
            raise HTTPException(status_code=400, detail="Text mode requires text input")
        elif request.mode == 'screenshot' and not request.screenshot:
            raise HTTPException(status_code=400, detail="Screenshot mode requires screenshot input")
        elif request.mode == 'both' and not (request.text and request.screenshot):
            raise HTTPException(status_code=400, detail="Both mode requires both text and screenshot input")
        
        # Process with intention agent
        options = await intention_agent.process(
            text=request.text,
            screenshot=request.screenshot,
            mode=request.mode
        )
        
        # Log processing time
        processing_time = time.time() - start_time
        logger.info(f"Intention processing completed in {processing_time:.2f}s")
        
        return IntentionResponse(
            query_id=request.query_id,
            options=options
        )
        
    except Exception as e:
        logger.error(f"Error processing intention: {str(e)}")
        return IntentionResponse(
            query_id=request.query_id,
            options=[],
            error=str(e)
        )

@router.post("/coordinator/mcp-agent", response_model=Dict[str, Any])
async def coordinator_mcp_agent(
    request: Dict[str, Any],
    request_obj: Request,
    coordinator: CoordinatorAgent = Depends(get_coordinator_dependency()),
    current_user: User = Depends(get_current_user_dependency()),
    db: Session = Depends(get_db)
):
    """
    Coordinate MCP agent requests through the universal interface.
    Starts the processing and returns WebSocket info immediately.
    """
    try:
        # Generate a query_id if not provided
        query_id = request.get("query_id", str(uuid.uuid4()))
        
        # Set query_id in the request for consistency
        request["query_id"] = query_id
        
        # Set the user ID for memory/telemetry if available
        user_id = current_user.id
        
        # Extract context from the request
        context = request.get("context", {})
        
        # If no context, use request itself as context
        if not context:
            context = request
        
        # Determine if this is from the intention agent
        from_intention_agent = context.get("from_intention_agent", False)
        
        # Create a WebSocket URL for streaming updates
        base_url = str(request_obj.url).replace("http://", "ws://").replace("https://", "wss://")
        ws_base_url = base_url.split("/api/v1")[0]  # Remove API version path
        websocket_url = f"{ws_base_url}/api/v1/agents/ws/mcp-agent/{query_id}"
        
        # Add conversation_id to WebSocket URL if available
        if "conversation_id" in context:
            websocket_url += f"?conversation_id={context['conversation_id']}"
        
        # Start the actual query processing as a background task
        asyncio.create_task(coordinator.process_query(
            query_id=query_id,
            db=db,
            context=context,
            user_id=user_id,
            from_intention_agent=from_intention_agent
        ))
        logger.info(f"Started background processing for query_id: {query_id}")
        
        # Return immediately with connection info
        return {
            "query_id": query_id,
            "websocket_url": websocket_url,
            "status": "processing_started" # Indicate that processing has begun
        }
    except Exception as e:
        logging.error(f"Error in coordinator agent endpoint: {str(e)}")
        import traceback
        logging.error(f"Error traceback: {traceback.format_exc()}")
        
        return {
            "status": "error",
            "message": f"Error processing your request: {str(e)}",
            "query_id": query_id if 'query_id' in locals() else str(uuid.uuid4())
        }

# Add a periodic cache cleanup function to prevent memory leaks
def cleanup_active_queries():
    """Remove old entries from the active_queries cache to prevent memory leaks"""
    current_time = time.time()
    with query_lock:
        to_remove = []
        for query_id, query_data in active_queries.items():
            # Check if this entry is old enough to remove
            if current_time - query_data["timestamp"] > 3600:  # Keep for 1 hour
                to_remove.append(query_id)
            # Also remove entries in error or completed state after 5 minutes
            elif (query_data["state"] in [QueryState.COMPLETED, QueryState.ERROR] and 
                  current_time - query_data["timestamp"] > 300):  # 5 minutes
                to_remove.append(query_id)
        
        # Remove the identified entries
        for query_id in to_remove:
            del active_queries[query_id]

# Start a background thread to clean up the queries cache every 5 minutes
import threading
def start_cleanup_thread():
    """Start a background thread to periodically clean up the active_queries cache"""
    def _cleanup_loop():
        while True:
            try:
                cleanup_active_queries()
            except Exception as e:
                logger.error(f"Error in query cache cleanup: {str(e)}")
            time.sleep(300)  # Sleep for 5 minutes
    
    cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)
    cleanup_thread.start()

# Start the cleanup thread when the module is loaded
start_cleanup_thread()

@router.websocket("/ws/mcp-agent/{query_id}")
async def mcp_agent_websocket(
    websocket: WebSocket,
    query_id: str,
    coordinator: CoordinatorAgent = Depends(get_coordinator_dependency()),
):
    """WebSocket endpoint for MCP agent interactions."""
    websocket_manager = get_websocket_manager()
    
    try:
        # Make sure to accept the WebSocket connection before doing anything else
        logging.info(f"Accepting WebSocket connection for query_id: {query_id}")
        await websocket.accept()
        logging.info(f"WebSocket connection accepted for query_id: {query_id}")
        
        # Extract conversation ID from query parameters if available
        conversation_id = websocket.query_params.get('conversation_id')
        logging.info(f"Conversation ID from query params: {conversation_id}")
        
        # Handle the case where query_id might have a 'query_' prefix
        actual_query_id = query_id
        if query_id.startswith('query_'):
            actual_query_id = query_id[6:]  # Remove the 'query_' prefix
            logging.info(f"Removed 'query_' prefix from query ID: {query_id} -> {actual_query_id}")
        
        # Connect to the WebSocket manager with conversation ID mapping
        logging.info(f"Connecting to WebSocket manager with query_id: {actual_query_id}, conversation_id: {conversation_id}")
        await websocket_manager.connect(websocket, actual_query_id, conversation_id)
        logging.info(f"Connected to WebSocket manager successfully")
        
        # Send confirmation message
        logging.info(f"Sending connection confirmation message")
        await websocket_manager.send_consolidated_update(
            query_id=actual_query_id,
            update_type="status",
            message="WebSocket connection established",
            data={"status": "connected"}
        )
        logging.info(f"Confirmation message sent")
        
        # Listen for messages from client - mainly for ping/pong
        while True:
            try:
                # Add a log message to show we're waiting for a message
                logging.debug(f"Waiting for client message on query_id: {actual_query_id}")
                data = await websocket.receive_text()
                logging.info(f"Received message from client: {data[:100]}...")
                await websocket_manager.handle_client_message(actual_query_id, data)
            except WebSocketDisconnect:
                logging.info(f"WebSocket disconnected for query {actual_query_id}")
                await websocket_manager.disconnect(actual_query_id)
                break
            except Exception as e:
                # Handle other errors during message receipt
                logging.error(f"Error receiving WebSocket message: {str(e)}")
                if "WebSocket is not connected" in str(e):
                    logging.error("WebSocket connection lost unexpectedly")
                    await websocket_manager.disconnect(actual_query_id)
                    break
    except Exception as e:
        logging.error(f"WebSocket error: {str(e)}")
        import traceback
        logging.error(f"WebSocket error traceback: {traceback.format_exc()}")
        try:
            # Ensure we have a defined actual_query_id before attempting to disconnect
            if 'actual_query_id' in locals():
                logging.info(f"Disconnecting from WebSocket manager after error")
                await websocket_manager.disconnect(actual_query_id)
        except Exception:
            pass

# Add a duplicate endpoint to handle the full path pattern
@router.websocket("/api/v1/agents/ws/mcp-agent/{query_id}")
async def mcp_agent_websocket_full_path(
    websocket: WebSocket,
    query_id: str,
    coordinator: CoordinatorAgent = Depends(get_coordinator_dependency()),
):
    """Duplicate WebSocket endpoint for MCP agent interactions using the full path pattern."""
    logging.info(f"WebSocket connection via full path pattern for query_id: {query_id}")
    # Delegate to the main handler
    await mcp_agent_websocket(websocket, query_id, coordinator)

@router.get("/health/mcp-agent")
async def check_mcp_agent_health(
    coordinator: CoordinatorAgent = Depends(get_coordinator_dependency())
):
    """Check health of MCP-Agent servers"""
    try:
        # Use the provided coordinator to check server health
        coordinator_health_status = await coordinator.check_health()
        
        # Get direct health status from the health service
        # First initialize the health service if needed
        if not mcp_health_service.mcp_app:
            await mcp_health_service.initialize()
            
        # Check health of all servers directly
        service_health_status = await mcp_health_service.check_all_health()
        
        # Merge results, giving preference to direct service checks when available
        health_status = {
            "coordinator": coordinator_health_status.get("coordinator", False),
            "mcp_app": coordinator_health_status.get("mcp_app", False),
            "memory": coordinator_health_status.get("memory", False),
            "anthropic_api": coordinator_health_status.get("anthropic_api", False),
            # Use service health check results for servers
            "qdrant": service_health_status.get("qdrant", coordinator_health_status.get("qdrant", False)),
            "fetch": service_health_status.get("fetch", coordinator_health_status.get("fetch", False)),
            "websearch": service_health_status.get("websearch", coordinator_health_status.get("websearch", False)),
            "filesystem": service_health_status.get("filesystem", coordinator_health_status.get("filesystem", False)),
            "quickchart-server": service_health_status.get("quickchart-server", coordinator_health_status.get("quickchart-server", False)),
            "document-loader": service_health_status.get("document-loader", coordinator_health_status.get("document-loader", False)),
            "markdown-editor": service_health_status.get("markdown-editor", coordinator_health_status.get("markdown-editor", False)),
        }
        
        # Determine overall status based on health check results
        is_healthy = health_status.get("coordinator", False)
        server_health = {k: v for k, v in health_status.items() if k not in ["coordinator", "mcp_app", "memory", "anthropic_api"]}
        
        # If at least one server is healthy, consider it degraded
        # If no servers are healthy, consider it unhealthy
        if is_healthy:
            if all(server_health.values()):
                status = "healthy"
            elif any(server_health.values()):
                status = "degraded"
            else:
                status = "unhealthy"
        else:
            status = "unhealthy"
            
        # Return detailed health status
        return {
            "status": status,
            "services": health_status,
            "message": f"MCP Agent status: {status}"
        }
    except Exception as e:
        logger.error(f"Error checking MCP agent health: {str(e)}")
        return {
            "status": "unhealthy",
            "message": f"Error checking MCP agent health: {str(e)}",
            "services": {
                "error": str(e)
            }
        }

@router.get("/status/{query_id}")
async def get_query_status(
    query_id: str,
    current_user: User = Depends(current_user_dependency),
    db: Session = Depends(get_db)
):
    """
    Get status of a query
    """
    agent_log_repo = AgentLogRepository(db)
    agent_logs = agent_log_repo.get_by_query_id(query_id)
    
    if not agent_logs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found"
        )
    
    # Get status of each agent
    intention_log = next((log for log in agent_logs if log.agent_type == "intention"), None)
    coordinator_log = next((log for log in agent_logs if log.agent_type in ["coordinator", "mcp_agent_coordinator"]), None)
    
    # Determine overall status
    overall_status = "processing"
    
    if coordinator_log and coordinator_log.status == "completed":
        overall_status = "completed"
    elif any(log.status == "error" for log in agent_logs):
        overall_status = "error"
    
    # Return result
    result = {
        "query_id": query_id,
        "status": overall_status,
        "agents": {
            "intention": intention_log.status if intention_log else "not_started",
            "coordinator": coordinator_log.status if coordinator_log else "not_started"
        }
    }
    
    # Include result if completed
    if overall_status == "completed" and coordinator_log:
        result["result"] = coordinator_log.output_data
    
    return result

@router.post("/generate-text", response_model=Dict[str, Any])
async def generate_text(prompt: str = Body(..., embed=True)):
    """Generate text using Vertex AI"""
    if not settings.VERTEX_AI_ENABLED:
        return {"error": "Vertex AI is not enabled"}
    
    result = await vertex_ai_service.generate_text(prompt)
    if result:
        return {"text": result}
    else:
        return {"error": "Failed to generate text"}

@router.post("/gemini", response_model=Dict[str, Any])
async def generate_with_gemini(
    data: Dict[str, Any],
    current_user: User = Depends(current_user_dependency),
    db: Session = Depends(get_db)
):
    """Generate text using Gemini 2.0 Flash model"""
    if not settings.VERTEX_AI_ENABLED:
        return {"error": "Vertex AI is not enabled"}
    
    # Extract data
    prompt = data.get("prompt", "")
    max_tokens = data.get("max_tokens", 1024)
    temperature = data.get("temperature", 0.2)
    
    # Generate a unique query ID
    query_id = str(uuid4())
    
    # Log agent request
    agent_log_repo = AgentLogRepository(db)
    agent_log_repo.create({
        "agent_type": "gemini",
        "query_id": query_id,
        "input_data": {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature
        },
        "status": "processing"
    })
    
    try:
        # Generate text with Gemini
        start_time = time.time()
        result = await vertex_ai_service.generate_text(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )
        processing_time = int((time.time() - start_time) * 1000)  # Convert to milliseconds
        
        if not result:
            raise Exception("Failed to generate text with Gemini")
        
        # Log agent response
        agent_log_repo.update(query_id, {
            "output_data": {"text": result},
            "processing_time": processing_time,
            "status": "success"
        })
        
        return {
            "query_id": query_id,
            "text": result,
            "status": "success"
        }
    
    except Exception as e:
        # Log error
        agent_log_repo.update(query_id, {
            "status": "error",
            "error_message": str(e)
        })
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate text with Gemini: {str(e)}"
        )

@router.get("/qdrant/health")
async def check_qdrant_health():
    """
    Check if the mcp-server-qdrant is healthy
    """
    try:
        # First initialize the health service if needed
        if not mcp_health_service.mcp_app:
            initialized = await mcp_health_service.initialize()
            if not initialized:
                return {
                    "status": "error",
                    "message": "Failed to initialize MCP app for health checks",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
        # Check Qdrant health directly through the service
        is_healthy = await mcp_health_service.check_qdrant_health()
        
        if is_healthy:
            return {
                "status": "ok",
                "message": "MCP Qdrant server is healthy",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "status": "error",
                "message": "MCP Qdrant server is not healthy",
                "timestamp": datetime.utcnow().isoformat()
            }
    except Exception as e:
        logger.error(f"Error checking Qdrant health: {str(e)}")
        return {
            "status": "error",
            "message": f"Error checking Qdrant health: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }

@router.get("/fetch/health")
async def check_fetch_health():
    """
    Check if the mcp-server-fetch is healthy
    """
    try:
        # First initialize the health service if needed
        if not mcp_health_service.mcp_app:
            initialized = await mcp_health_service.initialize()
            if not initialized:
                return {
                    "status": "error",
                    "message": "Failed to initialize MCP app for health checks",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
        # Check Fetch health directly through the service
        is_healthy = await mcp_health_service.check_fetch_health()
        
        if is_healthy:
            return {
                "status": "ok",
                "message": "MCP Fetch server is healthy",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "status": "error",
                "message": "MCP Fetch server is not healthy",
                "timestamp": datetime.utcnow().isoformat()
            }
    except Exception as e:
        logger.error(f"Error checking Fetch health: {str(e)}")
        return {
            "status": "error",
            "message": f"Error checking Fetch health: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }

@router.get("/websearch/health")
async def check_websearch_health():
    """
    Check if the MCP WebSearch server is healthy
    """
    try:
        # First initialize the health service if needed
        if not mcp_health_service.mcp_app:
            initialized = await mcp_health_service.initialize()
            if not initialized:
                return {
                    "status": "error",
                    "message": "Failed to initialize MCP app for health checks",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
        # Check WebSearch health directly through the service
        is_healthy = await mcp_health_service.check_websearch_health()
        
        if is_healthy:
            return {
                "status": "ok",
                "message": "MCP WebSearch server is healthy",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "status": "error",
                "message": "MCP WebSearch server is not healthy",
                "timestamp": datetime.utcnow().isoformat()
            }
    except Exception as e:
        logger.error(f"Error checking WebSearch health: {str(e)}")
        return {
            "status": "error",
            "message": f"Error checking WebSearch health: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }

@router.get("/filesystem/health")
async def check_filesystem_health():
    """
    Check if the MCP filesystem server is healthy
    """
    try:
        # First initialize the health service if needed
        if not mcp_health_service.mcp_app:
            initialized = await mcp_health_service.initialize()
            if not initialized:
                return {
                    "status": "error",
                    "message": "Failed to initialize MCP app for health checks",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
        # Check Filesystem health directly through the service
        is_healthy = await mcp_health_service.check_filesystem_health()
        
        if is_healthy:
            return {
                "status": "ok",
                "message": "MCP Filesystem server is healthy",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "status": "error",
                "message": "MCP Filesystem server is not healthy",
                "timestamp": datetime.utcnow().isoformat()
            }
    except Exception as e:
        logger.error(f"Error checking Filesystem health: {str(e)}")
        return {
            "status": "error",
            "message": f"Error checking Filesystem health: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }

@router.get("/quickchart/health")
async def check_quickchart_health():
    """
    Check if the MCP QuickChart server is healthy
    """
    try:
        # First initialize the health service if needed
        if not mcp_health_service.mcp_app:
            initialized = await mcp_health_service.initialize()
            if not initialized:
                return {
                    "status": "error",
                    "message": "Failed to initialize MCP app for health checks",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
        # Check QuickChart health directly through the service
        is_healthy = await mcp_health_service.check_quickchart_health()
        
        if is_healthy:
            return {
                "status": "ok",
                "message": "MCP QuickChart server is healthy",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "status": "error",
                "message": "MCP QuickChart server is not healthy",
                "timestamp": datetime.utcnow().isoformat()
            }
    except Exception as e:
        logger.error(f"Error checking QuickChart health: {str(e)}")
        return {
            "status": "error",
            "message": f"Error checking QuickChart health: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }

@router.get("/document-loader/health")
async def check_document_loader_health():
    """
    Check if the MCP Document Loader server is healthy
    """
    try:
        # First initialize the health service if needed
        if not mcp_health_service.mcp_app:
            initialized = await mcp_health_service.initialize()
            if not initialized:
                return {
                    "status": "error",
                    "message": "Failed to initialize MCP app for health checks",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
        # Check Document Loader health directly through the service
        is_healthy = await mcp_health_service.check_document_loader_health()
        
        if is_healthy:
            return {
                "status": "ok",
                "message": "MCP Document Loader server is healthy",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "status": "error",
                "message": "MCP Document Loader server is not healthy",
                "timestamp": datetime.utcnow().isoformat()
            }
    except Exception as e:
        logger.error(f"Error checking Document Loader health: {str(e)}")
        return {
            "status": "error",
            "message": f"Error checking Document Loader health: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }

@router.get("/markdown-editor/health")
async def check_markdown_editor_health():
    """
    Check if the MCP Markdown Editor server is healthy
    """
    try:
        # First initialize the health service if needed
        if not mcp_health_service.mcp_app:
            initialized = await mcp_health_service.initialize()
            if not initialized:
                return {
                    "status": "error",
                    "message": "Failed to initialize MCP app for health checks",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
        # Check Markdown Editor health directly through the service
        is_healthy = await mcp_health_service.check_markdown_editor_health()
        
        if is_healthy:
            return {
                "status": "ok",
                "message": "MCP Markdown Editor server is healthy",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "status": "error",
                "message": "MCP Markdown Editor server is not healthy",
                "timestamp": datetime.utcnow().isoformat()
            }
    except Exception as e:
        logger.error(f"Error checking Markdown Editor health: {str(e)}")
        return {
            "status": "error",
            "message": f"Error checking Markdown Editor health: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }

@router.get("/session/{session_id}")
async def get_session_history(
    session_id: str,
    coordinator: CoordinatorAgent = Depends(get_coordinator_dependency())
):
    """
    Get session history with queries and results
    
    This endpoint retrieves the history of a session, including all queries 
    and their results, using the memory graph.
    """
    if not coordinator.memory:
        raise HTTPException(status_code=400, detail="Memory system not available")
        
    if session_id not in coordinator.agent_config.session_entities:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
    session_entity = coordinator.agent_config.session_entities.get(session_id)
    history = await coordinator.memory.get_session_history(session_entity)
    
    if not history:
        raise HTTPException(status_code=404, detail=f"Session history for {session_id} not found")
        
    return history

@router.get("/health/mcp-agent/all")
async def check_all_mcp_servers_health():
    """
    Check the health of all MCP Agent servers
    """
    try:
        # First initialize the health service if needed
        if not mcp_health_service.mcp_app:
            await mcp_health_service.initialize()
            
        # Check health of all servers in parallel
        health_status = await mcp_health_service.check_all_health()
        
        # If there's a status field in the health_status, use it
        if "status" in health_status:
            status = health_status["status"]
        else:
            # Otherwise determine status from individual components
            server_statuses = {
                k: v for k, v in health_status.items() 
                if k in [
                    "qdrant", "fetch", "websearch", "filesystem",
                    "quickchart-server", "document-loader", "markdown-editor"
                ]
            }
            
            if all(server_statuses.values()):
                status = "healthy"
            elif any(server_statuses.values()):
                status = "degraded"
            else:
                status = "unhealthy"
        
        # Return detailed health status
        return {
            "status": status,
            "services": health_status,
            "message": f"MCP Agent servers status: {status}",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error checking all MCP servers health: {str(e)}")
        return {
            "status": "error",
            "message": f"Error checking all MCP servers health: {str(e)}",
            "services": {
                "qdrant": False,
                "fetch": False, 
                "websearch": False,
                "filesystem": False,
                "quickchart-server": False,
                "document-loader": False,
                "markdown-editor": False,
                "error": str(e)
            },
            "timestamp": datetime.utcnow().isoformat()
        }

@router.post("/input/{query_id}/{tool_name}")
async def submit_human_input_route(
    query_id: str,
    tool_name: str, # Keep for logging/context, but lookup uses input_id
    payload: HumanInputPayload
):
    """
    Receives human input submitted via the frontend
    and signals the appropriate waiting agent process.
    """
    input_id = payload.input_id
    logger.info(f"Received human input submission for Query: {query_id}, InputID: {input_id}, Tool: {tool_name}")
    websocket_manager = get_websocket_manager()

    lookup_key = input_id # Use the specific input_id for lookup

    try:
        future = websocket_manager.pending_human_inputs.get(lookup_key)
        
        if future and not future.done():
            logger.info(f"Found pending future for key: {lookup_key}. Resolving with input.")
            future.set_result(payload.input)
            try:
                del websocket_manager.pending_human_inputs[lookup_key]
            except KeyError:
                logger.warning(f"Future for key {lookup_key} was already removed before explicit deletion.")
            return {"status": "success", "message": "Input submitted and process signaled."}
        elif future and future.done():
            logger.warning(f"Future for key {lookup_key} was already resolved. Input ignored.")
            if lookup_key in websocket_manager.pending_human_inputs:
                try:
                    del websocket_manager.pending_human_inputs[lookup_key]
                except KeyError:
                    pass # Already gone
            return {"status": "ignored", "message": "Input already received or process cancelled."}
        else:
            logger.warning(f"No pending human input request found for key: {lookup_key}. Input ignored.")
            raise HTTPException(status_code=404, detail=f"No pending human input request found for InputID {input_id} (Query: {query_id})")

    except Exception as e:
        logger.error(f"Error processing human input submission for InputID {input_id} (Query: {query_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error processing input: {str(e)}")
