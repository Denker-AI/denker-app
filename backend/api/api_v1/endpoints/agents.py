from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks, Body, WebSocket, WebSocketDisconnect, Request
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
from inspect import isawaitable

from db.database import get_db
from db.repositories import AgentLogRepository
from db.models import User
from core.auth import get_current_user_dependency
from agents.intention_agent import IntentionAgent
from services.vertex_ai import vertex_ai_service
from config.settings import settings
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
    screenshot_mime_type: Optional[str] = None
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
            screenshot_mime_type=request.screenshot_mime_type,
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
async def coordinator_mcp_agent_stub(*args, **kwargs):
    """Stub endpoint: MCP agent coordination is now handled by the local backend."""
    return {"status": "error", "message": "MCP agent endpoints are only available in the local backend."}

@router.websocket("/ws/mcp-agent/{query_id}")
async def mcp_agent_websocket_stub(*args, **kwargs):
    """Stub endpoint: MCP agent websocket is now handled by the local backend."""
    # Optionally, close the websocket or just do nothing
    return

@router.websocket("/api/v1/agents/ws/mcp-agent/{query_id}")
async def mcp_agent_websocket_full_path_stub(*args, **kwargs):
    """Stub endpoint: MCP agent websocket is now handled by the local backend."""
    return

@router.get("/status/{query_id}")
async def get_query_status_stub(*args, **kwargs):
    """Stub endpoint: MCP agent status is now handled by the local backend."""
    return {"status": "error", "message": "MCP agent status is only available in the local backend."}

@router.get("/health/mcp-agent")
async def check_mcp_agent_health_stub(*args, **kwargs):
    """Stub endpoint: MCP agent health is only available in the local backend."""
    return {"status": "error", "message": "MCP agent health is only available in the local backend."}

@router.get("/session/{session_id}")
async def get_session_history_stub(*args, **kwargs):
    """Stub endpoint: Session history is only available in the local backend."""
    return {"status": "error", "message": "Session history is only available in the local backend."}

@router.get("/health/mcp-agent/all")
async def check_all_mcp_servers_health_stub(*args, **kwargs):
    """Stub endpoint: MCP agent servers health is only available in the local backend."""
    return {"status": "error", "message": "MCP agent servers health is only available in the local backend."}

@router.post("/input/{query_id}/{tool_name}")
async def submit_human_input_route_stub(*args, **kwargs):
    """Stub endpoint: Human input submission is only available in the local backend."""
    return {"status": "error", "message": "Human input submission is only available in the local backend."}
