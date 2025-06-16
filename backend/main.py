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
    allow_origins=[
        "http://localhost:5173",  # Frontend development server - explicit
        "http://localhost:3000",
        "http://localhost:8080", 
        "http://localhost:9001",
        "https://denker-frontend.app",
        "denker://*"
    ],  # No longer using wildcards or condition
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Explicitly list methods
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Add CORS debugging middleware
@app.middleware("http")
async def cors_debugging_middleware(request: Request, call_next):
    """Debug middleware to log CORS related headers"""
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    if request.method == "OPTIONS":
        logger.info(f"CORS preflight request detected for {request.url.path}")
        logger.info(f"Origin: {request.headers.get('origin')}")
    
    response = await call_next(request)
    
    # Log CORS headers in response
    if 'origin' in request.headers:
        logger.info(f"CORS Response to {request.url.path}:")
        logger.info(f"  Access-Control-Allow-Origin: {response.headers.get('access-control-allow-origin')}")
        logger.info(f"  Access-Control-Allow-Credentials: {response.headers.get('access-control-allow-credentials')}")
        logger.info(f"  Access-Control-Allow-Methods: {response.headers.get('access-control-allow-methods')}")
    
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
        
        # --- MCP agent/coordinator logic is now handled by the local backend (Electron app) ---
        logger.info("MCP agent/coordinator logic is now handled by the local backend (Electron app). Skipping coordinator and MCP server initialization.")
        # await initialize_coordinator()
        # logger.info("Global coordinator agent initialized")
        # from core.global_coordinator import get_coordinator
        # coordinator = await get_coordinator()
        # health_status = await coordinator.check_health()
        # critical_components = ["coordinator", "mcp_app"]
        # logger.info("MCP Agent health check results:")
        # all_healthy = True
        # critical_failure = False
        # for component, status in health_status.items():
        #     log_level = logging.INFO if status else logging.WARNING
        #     logger.log(log_level, f"  - {component}: {'✅' if status else '❌'}")
        #     if not status:
        #         all_healthy = False
        #         if component in critical_components:
        #             critical_failure = True
        # if all_healthy:
        #     logger.info("✅ MCP Agent is fully operational")
        # elif critical_failure:
        #     error_msg = "❌ Critical MCP Agent components failed to initialize"
        #     logger.error(error_msg)
        #     if getattr(settings, 'STRICT_HEALTH_CHECK', False):
        #         raise RuntimeError(error_msg)
        # else:
        #     logger.warning("⚠️ MCP Agent is partially operational (degraded state)")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        logger.error(traceback.format_exc())

# Add a shutdown event handler to clean up resources
@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on application shutdown"""
    try:
        # --- MCP agent/coordinator logic is now handled by the local backend (Electron app) ---
        logger.info("Skipping global coordinator cleanup; handled by local backend.")
        # await cleanup_coordinator()
        # logger.info("Global coordinator cleaned up")
        # Add other cleanup tasks as needed
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
        logger.error(traceback.format_exc())