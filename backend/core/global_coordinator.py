"""
Global Coordinator Singleton

This module provides a singleton instance of the CoordinatorAgent with
proper lifecycle management for application-wide usage.
"""

import logging
import asyncio
from typing import Optional, Dict, Any
import inspect

from fastapi import Depends
from mcp_local.coordinator_agent import CoordinatorAgent

logger = logging.getLogger(__name__)

# Global coordinator instance
_coordinator: Optional[CoordinatorAgent] = None
_initialization_lock = asyncio.Lock()
_initialization_task = None
_cleanup_task = None
_initialized = False

async def initialize_coordinator():
    """
    Initialize the global coordinator.
    This function is idempotent - calling it multiple times will only
    initialize the coordinator once.
    """
    global _coordinator, _initialized, _initialization_task
    
    # Use a lock to prevent multiple concurrent initializations
    async with _initialization_lock:
        if _initialized:
            logger.info("Global coordinator already initialized")
            return
            
        if _initialization_task is not None and not _initialization_task.done():
            logger.info("Coordinator initialization already in progress")
            return
        
        logger.info("Initializing global coordinator instance")
        try:
            # Create the coordinator instance if it doesn't exist
            if _coordinator is None:
                _coordinator = CoordinatorAgent()
                logger.info("Created global coordinator instance")
            
            # Setup the coordinator
            await _coordinator.setup()
            logger.info("Global coordinator setup complete")
            
            # Initialize the decider agent as soon as the coordinator is set up
            await _coordinator._create_required_agents()
            logger.info("Decider agent initialized successfully")
            
            _initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize global coordinator: {str(e)}")
            # If initialization fails, reset the coordinator for potential retry
            _coordinator = None
            _initialized = False
            raise

async def get_coordinator() -> CoordinatorAgent:
    """
    Get the global coordinator instance.
    If the coordinator is not initialized, it will be initialized automatically.
    This function can be used as a FastAPI dependency.
    """
    global _coordinator, _initialized
    
    if not _initialized:
        await initialize_coordinator()
    
    if not _coordinator:
        raise RuntimeError("Coordinator not available - initialization may have failed")
    
    return _coordinator

async def cleanup_coordinator():
    """
    Clean up the global coordinator.
    This function should be called when the application is shutting down.
    """
    global _coordinator, _initialized
    
    if _coordinator is not None:
        logger.info("Cleaning up global coordinator instance")
        try:
            await _coordinator.close()
            logger.info("Global coordinator cleanup complete")
        except Exception as e:
            logger.error(f"Error during coordinator cleanup: {str(e)}")
        finally:
            # Even if cleanup fails, mark as uninitialized
            _coordinator = None
            _initialized = False
    else:
        logger.info("No coordinator instance to clean up")

# FastAPI dependency for injecting the coordinator
def get_coordinator_dependency():
    """
    A FastAPI dependency that provides the global coordinator instance.
    This is an awaitable function that can be used with Depends().
    
    Example:
        @router.post("/endpoint")
        async def endpoint(coordinator: CoordinatorAgent = Depends(get_coordinator_dependency())):
            # Use coordinator here
    """
    async def _get_coordinator_dependency():
        return await get_coordinator()
    
    return _get_coordinator_dependency 