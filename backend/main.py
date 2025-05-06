"""
Denker App Backend Server

This is the main entry point for the Denker App backend.
It combines FastAPI routes for standard backend functionality with the MCP Agent coordinator.
"""

import logging
import sys
import traceback
from config.logging_config import setup_logging
import asyncio
import os
from config.settings import settings
from db.database import engine
from api.api_v1.api import api_router
from db.init_db import init_postgres
from services.vertex_ai import vertex_ai_service
from core.auth import setup_auth
from services.scheduler import SchedulerService
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from mcp_local.coordinator_agent import CoordinatorAgent
from core.global_coordinator import initialize_coordinator, cleanup_coordinator

# Set up logging first, before any other imports
setup_logging()
logger = logging.getLogger(__name__)

import uvicorn

app = FastAPI(
    title="Denker App Backend",
    description="Backend services for the Denker App, including MCP Agent integration",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add WebSocket-specific CORS headers
@app.middleware("http")
async def add_websocket_cors_headers(request, call_next):
    # Log incoming WebSocket requests for debugging
    if "upgrade" in request.headers and request.headers["upgrade"].lower() == "websocket":
        logger.info(f"🔌 Incoming WebSocket connection attempt: {request.url.path}")
        logger.info(f"🔌 Request headers: {request.headers}")
        
        # For WebSocket connections, check if it's an MCP agent endpoint
        # Check both patterns - with and without the /api/v1/agents prefix
        if "/ws/mcp-agent/" in request.url.path or "/api/v1/agents/ws/mcp-agent/" in request.url.path:
            logger.info(f"🔌 WebSocket agent connection detected and approved: {request.url.path}")
            # Let the connection proceed directly to the WebSocket handler
            return await call_next(request)
        else:
            logger.warning(f"🔌 WebSocket connection with unrecognized path: {request.url.path}")
    
    # For regular HTTP requests, proceed with normal handling
    response = await call_next(request)
    
    # Add CORS headers for WebSocket paths (both with and without prefix)
    if "/ws/" in request.url.path or "/api/v1/agents/ws/" in request.url.path:
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
    
    return response

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests with method and path"""
    logger.info(f"Request: {request.method} {request.url.path}")
    response = await call_next(request)
    return response

# Include API routes
app.include_router(api_router, prefix="/api/v1")

# Initialize database at startup if enabled
@app.on_event("startup")
async def startup_event():
    """Initialize database and other components at startup"""
    try:
        # Initialize database
        if settings.AUTO_INIT_DB:
            await init_postgres()
            logger.info("Database initialized successfully")
        
        # Vertex AI is already initialized in its constructor
        if settings.VERTEX_AI_ENABLED:
            logger.info("Vertex AI initialized successfully")
            
        # Setup authentication
        setup_auth(app)
        logger.info("Authentication setup completed")
        
        # Initialize scheduler if enabled
        if settings.SCHEDULER_ENABLED:
            scheduler = SchedulerService()
            scheduler.start()
            logger.info("Scheduler service started")
            
        # Initialize the global coordinator agent
        await initialize_coordinator()
        logger.info("Global coordinator agent initialized")
        
        # Perform health check to verify MCP Agent is properly started
        from core.global_coordinator import get_coordinator
        coordinator = await get_coordinator()
        health_status = await coordinator.check_health()
        
        # Define critical components that must be healthy for the app to function
        # This can be customized or made configurable through settings
        critical_components = ["coordinator", "mcp_app"]
        
        # Log the health status of each component
        logger.info("MCP Agent health check results:")
        all_healthy = True
        critical_failure = False
        
        for component, status in health_status.items():
            log_level = logging.INFO if status else logging.WARNING
            logger.log(log_level, f"  - {component}: {'✅' if status else '❌'}")
            
            if not status:
                all_healthy = False
                if component in critical_components:
                    critical_failure = True
        
        # Determine overall health
        if all_healthy:
            logger.info("✅ MCP Agent is fully operational")
        elif critical_failure:
            error_msg = "❌ Critical MCP Agent components failed to initialize"
            logger.error(error_msg)
            
            # Option 1: Fail hard if STRICT_HEALTH_CHECK is enabled (configurable)
            if getattr(settings, 'STRICT_HEALTH_CHECK', False):
                raise RuntimeError(error_msg)
            # Option 2: Continue with warnings otherwise
        else:
            logger.warning("⚠️ MCP Agent is partially operational (degraded state)")
            
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        logger.error(traceback.format_exc())

# Add a shutdown event handler to clean up resources
@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on application shutdown"""
    try:
        # Clean up the global coordinator
        await cleanup_coordinator()
        logger.info("Global coordinator cleaned up")
        
        # Add other cleanup tasks as needed
        
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
        logger.error(traceback.format_exc())