import os
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File as FastAPIFile, Form, BackgroundTasks, Body, WebSocket, WebSocketDisconnect, Request
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
import hashlib
import httpx
from services.file_processing import extract_content, chunk_text
from config.settings import settings
from mcp_local.core.cloud_file_repository import CloudFileRepository

# Update these imports to use local-backend dependencies as needed
from mcp_local.coordinator_agent import CoordinatorAgent
from mcp_local.core.websocket_manager import get_websocket_manager
from config.settings import settings
from services.qdrant_service import direct_qdrant_service
from core.global_coordinator import get_coordinator_dependency, initialize_coordinator, cleanup_coordinator, get_user_settings_file_path, get_coordinator, wait_for_coordinator_ready, force_coordinator_reset
from services.health_checks import mcp_health_service
from mcp_local.core.cloud_agent_repository import CloudAgentRepository

# Import LocalUserStore from its new location
from core.user_store import LocalUserStore

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

handler_name = "agents_console_handler"
if not any(getattr(h, "name", None) == handler_name for h in logger.handlers):
    console_handler = logging.StreamHandler()
    console_handler.name = handler_name
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

router = APIRouter()

active_queries = {}
query_lock = threading.Lock()

running_tasks = {}
task_lock = threading.Lock()

class QueryState:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"

_active_processors = {}
_processors_lock = asyncio.Lock()

class CoordinatorRequest(BaseModel):
    query_id: str
    context: Dict[str, Any] = {}
    language: Optional[str] = None
    dataset_id: Optional[str] = None
    time_range: Optional[str] = None
    filters: Optional[Dict[str, Any]] = {}

class HumanInputPayload(BaseModel):
    input: str
    input_id: str
    request_id: Optional[str] = None

def get_current_user_local():
    logger.info("[AUTH_DEBUG] get_current_user_local called.")
    user = LocalUserStore.get_user()
    if not user:
        logger.warning("[AUTH_DEBUG] No user in LocalUserStore. Raising 401.")
        raise HTTPException(status_code=401, detail="No user info set in local backend. Please login via frontend.")
    logger.info(f"[AUTH_DEBUG] User found in LocalUserStore: user_id='{user.get('user_id', 'MISSING')}', has_token={'token' in user}")
    return user

# Update dependency
current_user_dependency = get_current_user_local

@router.post("/coordinator/mcp-agent", response_model=Dict[str, Any])
async def coordinator_mcp_agent(
    request: Dict[str, Any],
    request_obj: Request,
    coordinator: CoordinatorAgent = Depends(get_coordinator_dependency()),
    current_user: dict = Depends(current_user_dependency)
):
    # Generate query ID if not provided
    query_id = request.get("query_id", str(uuid.uuid4()))
    
    try:
        # Check environment for dev mode
        is_dev_mode = os.environ.get("DENKER_DEV_MODE", "false").lower() == "true"
        
        # In dev mode, if no user is set, create a dummy one
        if is_dev_mode and (not current_user or not current_user.get("user_id")):
            current_user = {"user_id": "dev-user-id", "token": "dev-mode-token"}
            
        # Ensure we have a user ID
        user_id = current_user.get("user_id")
        if not user_id:
            # For logging/debugging only
            logger.warning(f"No user ID found in current_user: {current_user}. Expected 'user_id' key.")
            # Use a default for development
            if is_dev_mode:
                logger.info("Using development fallback user ID 'dev-user-id'")
                user_id = "dev-user-id"
            else:
                raise HTTPException(status_code=401, detail="Authentication required: No user ID found in local store")
        
        # Prepare request data
        request["query_id"] = query_id
        context = request.get("context", {})
        if not context:
            context = request
        from_intention_agent = context.get("from_intention_agent", False)
        
        # Generate WebSocket URL
        base_url = str(request_obj.url).replace("http://", "ws://").replace("https://", "wss://")
        ws_base_url = base_url.split("/api/v1")[0]
        websocket_url = f"{ws_base_url}/api/v1/agents/ws/mcp-agent/{query_id}"
        if "conversation_id" in context:
            websocket_url += f"?conversation_id={context['conversation_id']}"
        
        # Create background task for processing
        process_task = asyncio.create_task(coordinator.process_query(
            query_id=query_id,
            context=context,
            user_id=user_id,
            from_intention_agent=from_intention_agent
        ))
        
        # Store task reference for cancellation
        with task_lock:
            running_tasks[query_id] = process_task
        
        # Store task reference to prevent garbage collection
        # This is important to prevent the greenlet error
        if not hasattr(coordinator, '_process_tasks'):
            coordinator._process_tasks = []
        coordinator._process_tasks.append(process_task)
        
        # Clean up old completed tasks
        if hasattr(coordinator, '_process_tasks'):
            coordinator._process_tasks = [t for t in coordinator._process_tasks 
                                         if not t.done() and not t.cancelled()]
        
        # Also clean up completed tasks from running_tasks
        with task_lock:
            completed_query_ids = [qid for qid, task in running_tasks.items() 
                                 if task.done() or task.cancelled()]
            for qid in completed_query_ids:
                del running_tasks[qid]
        
        logger.info(f"Started background processing for query_id: {query_id}")
        return {
            "query_id": query_id,
            "websocket_url": websocket_url,
            "status": "processing_started"
        }
    except Exception as e:
        logging.error(f"Error in coordinator agent endpoint: {str(e)}")
        import traceback
        logging.error(f"Error traceback: {traceback.format_exc()}")
        return {
            "status": "error",
            "message": f"Error processing your request: {str(e)}",
            "query_id": query_id
        }

def cleanup_active_queries():
    current_time = time.time()
    with query_lock:
        to_remove = []
        for query_id, query_data in active_queries.items():
            if current_time - query_data["timestamp"] > 3600:
                to_remove.append(query_id)
            elif (query_data["state"] in [QueryState.COMPLETED, QueryState.ERROR] and 
                  current_time - query_data["timestamp"] > 300):
                to_remove.append(query_id)
        for query_id in to_remove:
            del active_queries[query_id]
import threading
def start_cleanup_thread():
    def _cleanup_loop():
        while True:
            try:
                cleanup_active_queries()
            except Exception as e:
                logger.error(f"Error in query cache cleanup: {str(e)}")
            time.sleep(300)
    cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)
    cleanup_thread.start()
start_cleanup_thread()

@router.websocket("/ws/mcp-agent/{query_id}")
async def mcp_agent_websocket(
    websocket: WebSocket,
    query_id: str,
    coordinator: CoordinatorAgent = Depends(get_coordinator_dependency()),
):
    # ... (copy logic from cloud backend)
    websocket_manager = get_websocket_manager()
    try:
        await websocket.accept()
        conversation_id = websocket.query_params.get('conversation_id')
        actual_query_id = query_id
        if query_id.startswith('query_'):
            actual_query_id = query_id[6:]
        await websocket_manager.connect(websocket, actual_query_id, conversation_id)
        await websocket_manager.send_consolidated_update(
            query_id=actual_query_id,
            update_type="status",
            message="WebSocket connection established",
            data={"status": "connected"}
        )
        while True:
            try:
                data = await websocket.receive_text()
                await websocket_manager.handle_client_message(actual_query_id, data)
            except WebSocketDisconnect:
                await websocket_manager.disconnect(actual_query_id)
                break
            except Exception as e:
                if "WebSocket is not connected" in str(e):
                    await websocket_manager.disconnect(actual_query_id)
                    break
    except Exception as e:
        import traceback
        if 'actual_query_id' in locals():
            await websocket_manager.disconnect(actual_query_id)

@router.websocket("/api/v1/agents/ws/mcp-agent/{query_id}")
async def mcp_agent_websocket_full_path(
    websocket: WebSocket,
    query_id: str,
    coordinator: CoordinatorAgent = Depends(get_coordinator_dependency()),
):
    await mcp_agent_websocket(websocket, query_id, coordinator)

@router.get("/health/mcp-agent")
async def check_mcp_agent_health(
    coordinator: CoordinatorAgent = Depends(get_coordinator_dependency())
):
    try:
        coordinator_health_status = await coordinator.check_health()
        if not mcp_health_service.mcp_app:
            await mcp_health_service.initialize()
        service_health_status = await mcp_health_service.check_all_health()
        health_status = {
            "coordinator": coordinator_health_status.get("coordinator", False),
            "mcp_app": coordinator_health_status.get("mcp_app", False),
            "memory": coordinator_health_status.get("memory", False),
            "anthropic_api": coordinator_health_status.get("anthropic_api", False),
            "qdrant": service_health_status.get("qdrant", coordinator_health_status.get("qdrant", False)),
            "fetch": service_health_status.get("fetch", coordinator_health_status.get("fetch", False)),
            "websearch": service_health_status.get("websearch", coordinator_health_status.get("websearch", False)),
            "filesystem": service_health_status.get("filesystem", coordinator_health_status.get("filesystem", False)),
    
            "document-loader": service_health_status.get("document-loader", coordinator_health_status.get("document-loader", False)),
            "markdown-editor": service_health_status.get("markdown-editor", coordinator_health_status.get("markdown-editor", False)),
        }
        is_healthy = health_status.get("coordinator", False)
        server_health = {k: v for k, v in health_status.items() if k not in ["coordinator", "mcp_app", "memory", "anthropic_api"]}
        if is_healthy:
            if all(server_health.values()):
                status = "healthy"
            elif any(server_health.values()):
                status = "degraded"
            else:
                status = "unhealthy"
        else:
            status = "unhealthy"
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
    current_user: dict = Depends(current_user_dependency),
):
    # Use CloudAgentRepository instead of AgentLogRepository
    api_key = getattr(current_user, 'api_key', None) or getattr(current_user, 'token', None)
    agent_log_repo = CloudAgentRepository(api_key=api_key)
    agent_logs = await agent_log_repo.get_by_query_id(query_id)
    if not agent_logs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found"
        )
    intention_log = next((log for log in agent_logs if log.get('agent_type') == "intention"), None)
    coordinator_log = next((log for log in agent_logs if log.get('agent_type') in ["coordinator", "mcp_agent_coordinator"]), None)
    overall_status = "processing"
    if coordinator_log and coordinator_log.get('status') == "completed":
        overall_status = "completed"
    elif any(log.get('status') == "error" for log in agent_logs):
        overall_status = "error"
    result = {
        "query_id": query_id,
        "status": overall_status,
        "agents": {
            "intention": intention_log.get('status') if intention_log else "not_started",
            "coordinator": coordinator_log.get('status') if coordinator_log else "not_started"
        }
    }
    if overall_status == "completed" and coordinator_log:
        result["result"] = coordinator_log.get('output_data')
    return result

@router.get("/qdrant/health")
async def check_qdrant_health():
    try:
        if not mcp_health_service.mcp_app:
            initialized = await mcp_health_service.initialize()
            if not initialized:
                return {
                    "status": "error",
                    "message": "Failed to initialize MCP app for health checks",
                    "timestamp": datetime.utcnow().isoformat()
                }
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
    try:
        if not mcp_health_service.mcp_app:
            initialized = await mcp_health_service.initialize()
            if not initialized:
                return {
                    "status": "error",
                    "message": "Failed to initialize MCP app for health checks",
                    "timestamp": datetime.utcnow().isoformat()
                }
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
    try:
        if not mcp_health_service.mcp_app:
            initialized = await mcp_health_service.initialize()
            if not initialized:
                return {
                    "status": "error",
                    "message": "Failed to initialize MCP app for health checks",
                    "timestamp": datetime.utcnow().isoformat()
                }
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
    try:
        if not mcp_health_service.mcp_app:
            initialized = await mcp_health_service.initialize()
            if not initialized:
                return {
                    "status": "error",
                    "message": "Failed to initialize MCP app for health checks",
                    "timestamp": datetime.utcnow().isoformat()
                }
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



@router.get("/document-loader/health")
async def check_document_loader_health():
    try:
        if not mcp_health_service.mcp_app:
            initialized = await mcp_health_service.initialize()
            if not initialized:
                return {
                    "status": "error",
                    "message": "Failed to initialize MCP app for health checks",
                    "timestamp": datetime.utcnow().isoformat()
                }
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
    try:
        if not mcp_health_service.mcp_app:
            initialized = await mcp_health_service.initialize()
            if not initialized:
                return {
                    "status": "error",
                    "message": "Failed to initialize MCP app for health checks",
                    "timestamp": datetime.utcnow().isoformat()
                }
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
    try:
        if not mcp_health_service.mcp_app:
            await mcp_health_service.initialize()
        health_status = await mcp_health_service.check_all_health()
        if "status" in health_status:
            status = health_status["status"]
        else:
            server_statuses = {
                k: v for k, v in health_status.items() 
                if k in [
                    "qdrant", "fetch", "websearch", "filesystem",
                    "document-loader", "markdown-editor"
                ]
            }
            if all(server_statuses.values()):
                status = "healthy"
            elif any(server_statuses.values()):
                status = "degraded"
            else:
                status = "unhealthy"
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
    input_id = payload.input_id
    logger.info(f"Received human input submission for Query: {query_id}, InputID: {input_id}, Tool: {tool_name}")
    websocket_manager = get_websocket_manager()
    lookup_key = input_id
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
                    pass
            return {"status": "ignored", "message": "Input already received or process cancelled."}
        else:
            logger.warning(f"No pending human input request found for key: {lookup_key}. Input ignored.")
            raise HTTPException(status_code=404, detail=f"No pending human input request found for InputID {input_id} (Query: {query_id})")
    except Exception as e:
        logger.error(f"Error processing human input submission for InputID {input_id} (Query: {query_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error processing input: {str(e)}")

class LocalLoginRequest(BaseModel):
    user_id: str
    token: str

# Modified to accept restart_coordinator parameter
async def fetch_and_save_remote_settings(user_id: str, token: str, restart_coordinator: bool = True):
    """
    Fetch remote settings and optionally restart coordinator.
    Now includes settings comparison to avoid unnecessary restarts.
    """
    remote_settings_url = f"{settings.BACKEND_URL}/api/v1/users/settings"
    headers = {"Authorization": f"Bearer {token}"}
    
    logger.info(f"[FETCH_SETTINGS] Attempting to fetch settings for user {user_id} from {remote_settings_url}")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(remote_settings_url, headers=headers)
        
        if response.status_code == 200:
            remote_settings = response.json()
            logger.info(f"[FETCH_SETTINGS] Successfully fetched remote settings for user {user_id}: {json.dumps(remote_settings)}")
            
            # Load existing local settings for comparison
            settings_file_path = get_user_settings_file_path()
            existing_settings = {}
            settings_changed = True  # Default to changed if no local file
            
            if os.path.exists(settings_file_path):
                try:
                    with open(settings_file_path, 'r') as f:
                        existing_settings = json.load(f)
                    
                    # Compare settings (deep comparison)
                    settings_changed = existing_settings != remote_settings
                    logger.info(f"[FETCH_SETTINGS] Settings comparison: changed={settings_changed}")
                    
                except Exception as e:
                    logger.warning(f"[FETCH_SETTINGS] Could not read existing settings file: {e}")
                    settings_changed = True
            
            # Save new settings
            try:
                with open(settings_file_path, 'w') as f:
                    json.dump(remote_settings, f, indent=2)
                logger.info(f"[FETCH_SETTINGS] Saved remote settings to local file: {settings_file_path}")
                
                # Only restart coordinator if settings actually changed AND restart is requested
                if restart_coordinator:
                    if settings_changed:
                        logger.info("[FETCH_SETTINGS] Settings changed, restarting coordinator...")
                        await cleanup_coordinator()
                        await initialize_coordinator()
                        logger.info("[FETCH_SETTINGS] Coordinator restarted due to settings change.")
                        return {"success": True, "settings": remote_settings, "message": "Settings changed, coordinator restarted.", "settings_changed": True}
                    else:
                        logger.info("[FETCH_SETTINGS] Settings unchanged, skipping coordinator restart.")
                        return {"success": True, "settings": remote_settings, "message": "Settings unchanged, no restart needed.", "settings_changed": False}
                else:
                    logger.info("[FETCH_SETTINGS] Skipping coordinator restart as requested.")
                    return {"success": True, "settings": remote_settings, "message": "Settings fetched and saved locally.", "settings_changed": settings_changed}
                    
            except IOError as e:
                logger.error(f"[FETCH_SETTINGS] Failed to write settings to {settings_file_path}: {e}")
                return {"success": False, "error": f"Failed to write local settings file: {e}"}
                
        elif response.status_code == 404:
            logger.warning(f"[FETCH_SETTINGS] No settings found for user {user_id} on remote (404). Using defaults.")
            settings_file_path = get_user_settings_file_path()
            if not os.path.exists(settings_file_path):
                try:
                    with open(settings_file_path, 'w') as f:
                        json.dump({}, f)
                    logger.info(f"[FETCH_SETTINGS] Created empty local settings file as remote returned 404: {settings_file_path}")
                except IOError as e_io:
                    logger.error(f"[FETCH_SETTINGS] Failed to create empty local settings file: {e_io}")
            return {"success": True, "settings": {}, "message": "No remote settings found, local defaults will be used.", "settings_changed": False}
        else:
            logger.error(f"[FETCH_SETTINGS] Failed to fetch remote settings for user {user_id}. Status: {response.status_code}, Response: {response.text}")
            return {"success": False, "error": f"Failed to fetch remote settings (status {response.status_code})"}
            
    except httpx.RequestError as e:
        logger.error(f"[FETCH_SETTINGS] HTTPX request error fetching remote settings for user {user_id}: {e}")
        return {"success": False, "error": f"Network error fetching settings: {e}"}
    except Exception as e:
        logger.error(f"[FETCH_SETTINGS] Unexpected error fetching/saving settings for user {user_id}: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {e}"}

# ADDED: Internal helper for post-authentication setup
async def _perform_post_authentication_setup(user_id: str, token: str, existing_user_info_for_scenario: Optional[Dict[str, Any]]):
    """
    Internal function to handle post-authentication tasks like determining auth scenario
    and triggering coordinator setup/restart.
    """
    logger.info(f"[_perform_post_authentication_setup] Called for user_id: {user_id}")

    # Determine the authentication scenario based on the state *before* the current login/validation attempt
    auth_scenario = determine_auth_scenario(existing_user_info_for_scenario, user_id, token)
    logger.info(f"[_perform_post_authentication_setup] Determined auth_scenario: {auth_scenario} for user_id: {user_id}")

    coordinator_action_message = await handle_coordinator_for_auth_scenario(
        auth_scenario, user_id, token
    )
    logger.info(f"[_perform_post_authentication_setup] Coordinator action: {coordinator_action_message} for user_id: {user_id}")
    return coordinator_action_message, auth_scenario

@router.post("/auth/restart-coordinator")
async def restart_coordinator_endpoint():
    """
    Manual endpoint to restart the coordinator.
    Useful for resolving login/restart dependency cycles.
    """
    logger.info("[RESTART_COORDINATOR] Manual coordinator restart requested")
    try:
        # Get the current user for restart
        stored_user_info = LocalUserStore.get_user()
        if not stored_user_info:
            logger.warning("[RESTART_COORDINATOR] No user found in LocalUserStore, cannot restart coordinator")
            raise HTTPException(status_code=401, detail="No authenticated user found")
        
        user_id = stored_user_info.get("user_id")
        token = stored_user_info.get("token")
        
        if not user_id or not token:
            logger.warning("[RESTART_COORDINATOR] Incomplete user data in LocalUserStore")
            raise HTTPException(status_code=401, detail="Incomplete user authentication data")
        
        logger.info(f"[RESTART_COORDINATOR] Restarting coordinator for user: {user_id}")
        
        # Force restart by fetching settings with restart_coordinator=True
        await fetch_and_save_remote_settings(
            user_id=user_id,
            token=token,
            restart_coordinator=True  # Force restart
        )
        
        logger.info("[RESTART_COORDINATOR] Coordinator restart completed successfully")
        return {
            "status": "success",
            "message": "Coordinator restarted successfully",
            "user_id": user_id
        }
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"[RESTART_COORDINATOR] Error during manual restart: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to restart coordinator: {str(e)}")

@router.post("/auth/force-reset-coordinator")
async def force_reset_coordinator_endpoint():
    """
    Force reset the coordinator when it's stuck in initialization.
    This is a last resort option that cancels any ongoing initialization.
    """
    logger.warning("[FORCE_RESET] Force coordinator reset requested")
    try:
        # Check if coordinator is actually stuck
        is_ready, status, details = await wait_for_coordinator_ready(timeout_seconds=5)
        
        if is_ready:
            return {
                "status": "unnecessary",
                "message": "Coordinator is already ready, no reset needed",
                "details": details
            }
        
        elapsed = details.get("elapsed_seconds", 0)
        if elapsed < 30:  # Don't allow force reset too early
            return {
                "status": "too_early",
                "message": f"Coordinator has only been initializing for {elapsed:.1f}s. Wait longer before force reset.",
                "details": details
            }
        
        # Perform the force reset
        reset_success, reset_message = await force_coordinator_reset()
        
        if reset_success:
            logger.info("[FORCE_RESET] Force reset completed successfully")
            
            # Try to reinitialize with current user if available
            stored_user_info = LocalUserStore.get_user()
            if stored_user_info:
                user_id = stored_user_info.get("user_id")
                token = stored_user_info.get("token")
                
                if user_id and token:
                    logger.info(f"[FORCE_RESET] Attempting to reinitialize coordinator for user: {user_id}")
                    try:
                        await fetch_and_save_remote_settings(
                            user_id=user_id,
                            token=token,
                            restart_coordinator=True
                        )
                        return {
                            "status": "success",
                            "message": "Coordinator force reset and reinitialized successfully",
                            "user_id": user_id,
                            "reset_details": reset_message
                        }
                    except Exception as reinit_error:
                        logger.error(f"[FORCE_RESET] Error during reinitialization: {reinit_error}")
                        return {
                            "status": "partial_success",
                            "message": "Coordinator reset but reinitialization failed",
                            "error": str(reinit_error),
                            "reset_details": reset_message
                        }
            
            return {
                "status": "success",
                "message": "Coordinator force reset completed (no user for reinitialization)",
                "reset_details": reset_message
            }
        else:
            logger.error(f"[FORCE_RESET] Force reset failed: {reset_message}")
            raise HTTPException(status_code=500, detail=f"Force reset failed: {reset_message}")
            
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"[FORCE_RESET] Error during force reset: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to force reset coordinator: {str(e)}")

@router.post("/auth/local-login")
async def local_login(request: LocalLoginRequest):
    logger.info(f"[AUTH_DEBUG] /auth/local-login called with user_id: {request.user_id}, token: {'********' if request.token else 'None'}")
    try:
        logger.info(f"Authentication attempt for user_id: {request.user_id}")
        
        # Get existing user data to determine the scenario *before* updating the store
        existing_user_before_set = LocalUserStore.get_user()
        
        # Store the new user data (this is critical, makes this the source of truth for current session)
        user_data_to_store = {"user_id": request.user_id, "token": request.token}
        LocalUserStore.set_user(user_data_to_store)
        logger.info(f"Authentication successful for user_id: {request.user_id}. User info stored in LocalUserStore.")

        # Now perform post-auth setup using the *prior* state for scenario calculation
        coordinator_action_message, auth_scenario = await _perform_post_authentication_setup(
            user_id=request.user_id,
            token=request.token,
            existing_user_info_for_scenario=existing_user_before_set # Pass the state *before* this login
        )
        
        return {
            "status": "success", 
            "message": f"Authentication successful ({auth_scenario})", 
            "user_id": request.user_id,
            "auth_scenario": auth_scenario,
            "coordinator_action": coordinator_action_message # Use the message from the helper
        }
        
    except Exception as e:
        logger.error(f"Error during authentication: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Authentication failed")

def determine_auth_scenario(existing_user, new_user_id, new_token):
    """
    Determine what type of authentication scenario this is:
    - 'first_time': No existing user data (fresh app start)
    - 'user_switch': Different user logging in
    - 'token_refresh': Same user, different token
    - 'duplicate_auth': Same user, same token (unnecessary call)
    """
    if not existing_user:
        return 'first_time'
    
    existing_user_id = existing_user.get("user_id")
    existing_token = existing_user.get("token")
    
    if existing_user_id != new_user_id:
        return 'user_switch'
    
    if existing_token != new_token:
        return 'token_refresh'
    
    return 'duplicate_auth'

async def handle_coordinator_for_auth_scenario(auth_scenario, user_id, token):
    """
    Handle coordinator initialization/restart based on authentication scenario
    """
    try:
        # Check if coordinator restart is already in progress to prevent race conditions
        from core.global_coordinator import is_coordinator_restart_in_progress
        if is_coordinator_restart_in_progress():
            logger.info("[AUTH_FLOW] Coordinator initialization already in progress, skipping duplicate request")
            return "initialization_in_progress_skipped"
        
        # CRITICAL FIX: Check coordinator readiness with short timeout (5 seconds max)
        # If coordinator is already ready or fails quickly, don't block auth
        is_ready, status, details = await wait_for_coordinator_ready(timeout_seconds=5)
        
        # Check the current coordinator status (this is fast)
        try:
            coordinator = await get_coordinator()
            coordinator_running = (coordinator and 
                                 hasattr(coordinator, '_initialized') and 
                                 coordinator._initialized)
        except Exception as e:
            logger.warning(f"Could not check coordinator status: {e}")
            coordinator_running = False
        
        # If coordinator is already running and ready, minimal action needed
        if is_ready and coordinator_running:
            logger.info("[AUTH_FLOW] Coordinator already ready and running")
            
            if auth_scenario == 'first_time':
                # Just sync settings for first time, coordinator already ready
                await fetch_and_save_remote_settings(
                    user_id=user_id, token=token, restart_coordinator=False
                )
                return "first_time_coordinator_already_ready"
            
            elif auth_scenario == 'user_switch':
                # Different user - need to restart for new context
                await fetch_and_save_remote_settings(
                    user_id=user_id, token=token, restart_coordinator=True
                )
                return "user_switch_coordinator_restarted"
            
            elif auth_scenario == 'token_refresh':
                # Sync settings, restart only if they changed
                settings_result = await fetch_and_save_remote_settings(
                    user_id=user_id, token=token, restart_coordinator=True
                )
                if settings_result.get("settings_changed", False):
                    return "token_refresh_restarted_due_to_settings_change"
                else:
                    return "token_refresh_settings_synced_no_restart"
            
            elif auth_scenario == 'duplicate_auth':
                return "no_action_needed"
        
        # Coordinator not ready or not running - handle each scenario
        if auth_scenario == 'first_time':
            # First time login: fetch settings and initialize coordinator
            logger.info("[AUTH_FLOW] First time login - fetching settings and initializing coordinator")
            settings_result = await fetch_and_save_remote_settings(
                user_id=user_id, token=token, restart_coordinator=False
            )
            
            # Initialize coordinator with proper race protection
            from core.global_coordinator import initialize_coordinator
            await initialize_coordinator()
            return "first_time_initialized_with_settings"
        
        elif auth_scenario == 'user_switch':
            # Different user - fetch their settings and restart coordinator
            logger.info("[AUTH_FLOW] User switch detected - fetching new user settings and restarting coordinator")
            settings_result = await fetch_and_save_remote_settings(
                user_id=user_id, token=token, restart_coordinator=True
            )
            return "user_switch_restarted_with_new_settings"
        
        elif auth_scenario == 'token_refresh':
            if coordinator_running:
                # Same user, new token - sync settings, restart if changed
                logger.info("[AUTH_FLOW] Token refresh - syncing settings, restart if changed")
                settings_result = await fetch_and_save_remote_settings(
                    user_id=user_id, token=token, restart_coordinator=True
                )
                
                if settings_result.get("success") and settings_result.get("settings_changed", False):
                    return "token_refresh_restarted_due_to_settings_change"
                else:
                    return "token_refresh_settings_synced_no_restart"
            else:
                # Coordinator not running - restart it
                logger.info("[AUTH_FLOW] Token refresh but coordinator not running - restarting")
                await fetch_and_save_remote_settings(
                    user_id=user_id, token=token, restart_coordinator=True
                )
                return "token_refresh_coordinator_restarted"
        
        elif auth_scenario == 'duplicate_auth':
            if coordinator_running:
                return "no_action_needed"
            else:
                # Duplicate auth during startup - skip to avoid race condition
                logger.info("[AUTH_FLOW] Duplicate auth during startup - skipping to avoid race condition")
                return "startup_race_condition_skipped"
        
        return "unknown"
    except Exception as e:
        logger.error(f"Error handling coordinator initialization: {str(e)}")
        return "unknown"

@router.post("/files/process-local")
async def process_file_local(
    background_tasks: BackgroundTasks,
    file: UploadFile = FastAPIFile(...),
    user_id: str = Form(...),
    original_path: str = Form(...),
    query_id: str = Form(None),
    message_id: str = Form(None),
):
    logger = logging.getLogger(__name__)
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()

    # Retrieve token from LocalUserStore
    stored_user_info = LocalUserStore.get_user()
    token_from_store = None
    if stored_user_info:
        if stored_user_info.get("user_id") == user_id:
            token_from_store = stored_user_info.get("token")
        else:
            logger.warning(f"[ProcessFileLocal] User ID mismatch: form ({user_id}), store ({stored_user_info.get('user_id')}). Token not used.")

    if not token_from_store:
        logger.error(f"[ProcessFileLocal] No token for user {user_id} for CloudFileRepository. Cloud calls may fail.")

    file_repo = CloudFileRepository(token=token_from_store)

    # 1. Check for duplicate file via its hash
    logger.info(f"[ProcessFileLocal] About to check if file exists. User ID: {user_id}, File Hash: {file_hash}")
    try:
        exists_result = await file_repo.exists(file_hash, user_id)
        logger.info(f"[ProcessFileLocal] Result from file_repo.exists: {exists_result}")
    except Exception as e_exists:
        logger.error(f"[ProcessFileLocal] Error calling file_repo.exists for hash {file_hash}, user {user_id}: {e_exists}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error checking for existing file: {str(e_exists)}")

    if exists_result and exists_result.get("exists"):
        existing_file_id = exists_result["file_id"]
        # Safely get filename, provide a default if not found
        existing_metadata = exists_result.get("metadata", {})
        existing_filename = existing_metadata.get("filename", file.filename or "Unknown filename")
        
        logger.info(f"[ProcessFileLocal] Duplicate file DETECTED for user {user_id}. Existing file ID: {existing_file_id}. Hash: {file_hash}, Filename: {existing_filename}")
        
        websocket_manager = get_websocket_manager()
        if query_id and websocket_manager:
            try:
                await websocket_manager.send_consolidated_update(
                    query_id=query_id,
                    update_type="file_processed", # Using "file_processed" as requested
                    message=f"File '{existing_filename}' already exists.", # Clearer message
                    data={"file_id": existing_file_id, "filename": existing_filename, "status": "completed", "duplicate": True } # Explicit duplicate flag and completed status
                )
                logger.info(f"Sent WebSocket notification for duplicate file {existing_file_id} (filename: {existing_filename}) on query {query_id}")
            except Exception as ws_err:
                logger.error(f"Failed to send WebSocket notification for duplicate file: {ws_err}", exc_info=True)

        return {
            "id": existing_file_id,
            "filename": existing_filename,
            "file_type": existing_metadata.get("file_type"),
            "file_size": existing_metadata.get("file_size"),
            "created_at": existing_metadata.get("created_at"),
            "duplicate": True
        }

    # 2. Not a duplicate: Proceed to create metadata and process the file
    new_file_id = str(uuid4()) # Consistently use new_file_id for new files
    current_filename = file.filename # Use the uploaded file's name
    logger.info(f"[ProcessFileLocal] No duplicate found by file_repo.exists. Proceeding to create new file metadata for filename: {current_filename}, new_file_id: {new_file_id}")
    file_extension = os.path.splitext(current_filename)[1] if "." in current_filename else ""
    
    temp_dir = os.path.join("/tmp", "denker_uploads", str(user_id))
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = os.path.join(temp_dir, f"{new_file_id}{file_extension}")
    
    with open(temp_file_path, "wb") as f:
        f.write(content)
    
    # storage_path here refers to the original path from the user's system
    # It's stored for informational purposes. The actual content for processing is in temp_file_path.
    storage_path_info = original_path 
    
    cloud_metadata_payload = {
        "file_id": new_file_id,
        "user_id": user_id,
        "filename": current_filename,
        "file_type": file.content_type,
        "file_size": len(content),
        "storage_path": storage_path_info, 
        "processing_status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "file_hash": file_hash 
    }
    
    try:
        await file_repo.create_metadata(cloud_metadata_payload)
        logger.info(f"Successfully created initial metadata in cloud for new file {new_file_id} (filename: {current_filename}). Hash: {file_hash}")
    except Exception as e_meta:
        logger.error(f"Failed to create initial metadata in cloud for file {new_file_id} (filename: {current_filename}): {e_meta}", exc_info=True)
        # Clean up temp file if metadata creation fails, as processing won't happen.
        if os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e_unlink:
                logger.error(f"Error removing temporary file {temp_file_path} after metadata creation failure: {e_unlink}")
        raise HTTPException(status_code=500, detail=f"Failed to register file metadata in cloud: {str(e_meta)}")

    # 3. Add background task to process the file
    background_tasks.add_task(
        process_file_with_mcp_qdrant_local,
        file_id=new_file_id,
        file_content=content, 
        file_type=file.content_type,
        filename=current_filename,
        user_id=user_id,
        storage_path=storage_path_info, 
        file_repo=file_repo,
        websocket_manager=get_websocket_manager(),
        query_id=query_id,
        message_id=message_id,
        temp_file_path=temp_file_path 
    )

    return {
        "id": new_file_id,
        "filename": current_filename,
        "file_type": file.content_type,
        "file_size": len(content),
        "created_at": cloud_metadata_payload["created_at"],
        "duplicate": False
    }

async def process_file_with_mcp_qdrant_local(
    file_id: str,
    file_content: bytes,
    file_type: str,
    filename: str,
    user_id: str,
    storage_path: str,  # This is the original_path
    file_repo: CloudFileRepository,
    websocket_manager,
    query_id: str = None,
    message_id: str = None,
    temp_file_path: str = None
):
    import os
    from datetime import datetime
    import logging
    logger = logging.getLogger(__name__)
    try:
        # Use provided temp_file_path for processing
        content = extract_content(temp_file_path)
        if not content:
            raise ValueError(f"Failed to extract content from {filename}")

        # Chunk the content
        chunk_docs = chunk_text(content)
        if not chunk_docs:
            raise ValueError(f"Failed to chunk content from {filename}")

        # Update file status to processing
        await file_repo.update_metadata(file_id, {
            "meta_data": {
                "indexed_in_qdrant": False,
                "processing_status": "processing",
                "chunk_count": len(chunk_docs)
            }
        })

        # Prepare lists for batch processing
        chunks_content = [doc.page_content for doc in chunk_docs]
        chunks_metadata = []
        for i, doc in enumerate(chunk_docs):
            qdrant_payload_metadata = { 
                "file_id": file_id,
                "user_id": user_id,
                "filename": filename,
                "file_type": file_type,
                "created_at": datetime.utcnow().isoformat(),
                "source_type": "user_upload",
                "storage_path": storage_path,
                "chunk_index": i,
                "start_index": doc.metadata.get("start_index", -1)
            }
            chunks_metadata.append(qdrant_payload_metadata)

        # Store all chunks in a single batch call
        store_result = await direct_qdrant_service.store_chunks(
            chunks=chunks_content,
            metadatas=chunks_metadata
        )

        if store_result.get("status") == "error":
            raise Exception(f"Failed to store chunks in Qdrant: {store_result.get('message')}")
        
        logger.info(f"Batch stored {len(chunk_docs)} chunks for file {file_id} in Qdrant.")

        # After all chunks are stored, update the final status
        metadata_to_set = {
            "meta_data": {
                "indexed_in_qdrant": True,
                "processing_status": "completed",
                "processed_at": datetime.utcnow().isoformat(),
                "storage_path": storage_path
            }
        }
        logger.info(f"[{file_id}] Attempting to update cloud DB metadata to: {metadata_to_set}")
        await file_repo.update_metadata(file_id, metadata_to_set)
        logger.info(f"[{file_id}] Updated cloud DB after successful status update.")

        # Attach file to message if message_id is provided
        if message_id:
            try:
                logger.info(f"[{file_id}] Attempting to attach to message {message_id} in cloud DB.")
                await file_repo.attach_to_message(file_id=file_id, message_id=message_id)
                logger.info(f"[{file_id}] Successfully attached to message {message_id}.")
            except Exception as attach_err:
                logger.error(f"[{file_id}] Failed to attach to message {message_id}: {attach_err}", exc_info=True)
                # Continue even if attachment fails, as file processing itself was successful

        # --- WebSocket notification on success ---
        if websocket_manager and query_id:
            await websocket_manager.send_consolidated_update(
                query_id=query_id,
                update_type="file_processed",
                message=f"File {filename} processed successfully.",
                data={"file_id": file_id, "status": "completed"}
            )
        logger.info(f"Successfully processed file {file_id} using direct Qdrant service")
    except Exception as e:
        logger.error(f"Error processing file locally: {str(e)}", exc_info=True)
        # WebSocket error notification
        if websocket_manager and query_id:
            await websocket_manager.send_consolidated_update(
                query_id=query_id,
                update_type="file_processing_error",
                message=f"Error processing file {filename}: {str(e)}",
                data={"file_id": file_id, "status": "error"}
            )
        # Optionally update status to error in cloud DB
        try:
            await file_repo.update_metadata(file_id, {"meta_data": {"processing_status": "error", "processing_error": str(e), "storage_path": storage_path}})
        except Exception as inner_e:
            logger.error(f"Failed to update error status in cloud DB: {inner_e}", exc_info=True)
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.error(f"Error removing temporary file: {str(e)}")

@router.post("/cancel/{query_id}")
async def cancel_query(
    query_id: str,
    current_user: dict = Depends(current_user_dependency)
):
    """
    Cancel a running query by its ID
    """
    try:
        logger.info(f"Received cancel request for query_id: {query_id}")
        
        # Check if task exists and is running
        with task_lock:
            if query_id not in running_tasks:
                logger.warning(f"Query {query_id} not found in running tasks")
                raise HTTPException(
                    status_code=404, 
                    detail=f"Query {query_id} not found or already completed"
                )
            
            task = running_tasks[query_id]
            
            # Check if task is already done or cancelled
            if task.done() or task.cancelled():
                logger.info(f"Query {query_id} already completed or cancelled")
                del running_tasks[query_id]
                return {
                    "query_id": query_id,
                    "status": "already_completed",
                    "message": "Query was already completed or cancelled"
                }
            
            # Cancel the task
            task.cancel()
            logger.info(f"Cancelled task for query_id: {query_id}")
        
        # Update query state
        with query_lock:
            if query_id in active_queries:
                active_queries[query_id]["state"] = QueryState.CANCELLED
                active_queries[query_id]["timestamp"] = time.time()
        
        # Send cancellation update via WebSocket
        websocket_manager = get_websocket_manager()
        if websocket_manager.is_connected(query_id):
            await websocket_manager.send_consolidated_update(
                query_id=query_id,
                update_type="status",
                message="Query has been cancelled",
                data={"status": "cancelled"}
            )
            logger.info(f"Sent cancellation notification via WebSocket for query_id: {query_id}")
        
        return {
            "query_id": query_id,
            "status": "cancelled",
            "message": "Query has been successfully cancelled"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling query {query_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error cancelling query: {str(e)}"
        )

api_router = router
