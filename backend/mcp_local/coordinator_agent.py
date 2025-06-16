"""
Coordinator Agent - orchestration for MCP Agent with direct Anthropic API integration.

This module provides coordination between the Denker app and the MCP Agent
framework, configuring the Anthropic API usage directly and exposing FastAPI
endpoints for agent interaction with WebSocket progress updates.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, Type, List, Callable, Union, TypeVar, Protocol, Tuple, Literal
import uuid
from datetime import datetime
import re
from pathlib import Path
import traceback
import time

import aiohttp
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm import AugmentedLLM, RequestParams
from mcp_agent.workflows.llm.augmented_llm_anthropic import AnthropicAugmentedLLM
from mcp_agent.workflows.orchestrator.orchestrator import Orchestrator
from mcp_agent.workflows.router.router_llm import LLMRouter
from mcp_agent.workflows.router.router_llm_anthropic import AnthropicLLMRouter
from mcp_agent.logging.logger import LoggingConfig
from mcp_agent.logging.events import Event, EventFilter
from mcp_agent.human_input.types import HumanInputRequest

from .coordinator_memory import CoordinatorMemory
from .pg_memory_tools import memory_tools as pg_memory_tools
from .core.websocket_manager import WebSocketManager, get_websocket_manager
from .core.event_websocket_transport import WebSocketEventTransport
from .core.filesystem_interceptor import FilesystemInterceptor, get_filesystem_interceptor
from .base.server import MCPServer
from .base.protocol import Request, Response, Tool, ListToolsResponse
from .app_extension import create_mcp_app

# Import our modular components
from .coordinator_workflows import AgentRequest, AgentResponse, process_orchestrator_workflow, process_router_workflow
from .coordinator_websocket import handle_websocket_connection
from .coordinator_agents_config import AgentConfiguration, ANTHROPIC_API_KEY, DEFAULT_MODEL
from .coordinator_decisions import DecisionMaker
from .coordinator_filesystem import FilesystemHandler

# Import agent interfaces and configurations

# Import agent context access
from mcp_agent.context import get_current_context as get_agent_context

# --- ADDED: Import necessary DB components ---
from fastapi import Depends
from sqlalchemy.orm import Session
from db.database import get_db
from db.repositories import FileRepository, MessageRepository
from db.models import File as DBFile, Message as DBMessage # Alias to avoid naming clash
# --- END ADDED ---

# --- ADDED: Imports for Retry Logic ---
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, RetryError
from anthropic import RateLimitError, APITimeoutError # Add specific exceptions to retry on
# --- END ADDED ---

# --- ADDED: Imports for Fixed LLM Class ---
from anthropic import Anthropic
from anthropic.types import Message, MessageParam, ToolParam
from mcp.types import CallToolRequest, CallToolRequestParams
# --- END ADDED ---

# Type for WebSocket manager
class WebSocketManagerType:
    async def send_json(self, query_id: str, data: Dict[str, Any]) -> bool: ...
    def is_connected(self, query_id: str) -> bool: ...
    async def connect(self, websocket: WebSocket, query_id: str) -> None: ...
    def disconnect(self, query_id: str) -> None: ...
    async def send_consolidated_update(
        self, 
        query_id: str,
        update_type: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool: ...

logger = logging.getLogger(__name__)

# --- ADDED: Pydantic model for Decider Response --- 
class DecisionResponseModel(BaseModel):
    case: int
    workflow_type: Literal["simple", "router", "orchestrator"]
    explanation: str
    simple_response: Optional[str] = ""
    needs_clarification: bool = False
    clarifying_questions: Optional[List[str]] = Field(default_factory=list)
# --- END ADDED --- 

# Set the Anthropic API key directly
os.environ['ANTHROPIC_API_KEY'] = ANTHROPIC_API_KEY

# Ensure our modular structure is in place
def setup_modular_structure():
    """Create necessary directories and files for the modular structure if they don't exist."""
    module_path = Path(__file__).parent
    
    # Check if our modular files exist, if not create them
    modules = [
        "coordinator_workflows.py",
        "coordinator_websocket.py",
        "coordinator_agents_config.py",
        "coordinator_decisions.py",
        "coordinator_filesystem.py"
    ]
    
    for module in modules:
        module_file = module_path / module
        if not module_file.exists():
            logger.warning(f"Module file {module} not found, you should create it for proper modularization")

# Request and response models
class StreamUpdate(BaseModel):
    session_id: str
    agent: str
    message: str
    timestamp: str
    update_type: str = "progress"  # progress, completed, error

class SemaphoreGuardedLLM:
    """Wraps an LLM to limit concurrent calls using a semaphore."""
    def __init__(self, llm: AnthropicAugmentedLLM, semaphore: asyncio.Semaphore):
        self._llm = llm
        self._semaphore = semaphore
        # Copy relevant attributes if needed for type hinting or direct access elsewhere
        self.default_request_params = getattr(llm, 'default_request_params', None)

    # --- ADDED: Retry Decorator --- 
    # Define the retry strategy: retry on RateLimitError or APITimeoutError, wait exponentially,
    # starting at 2s, max 10s between retries, stop after 3 attempts total.
    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True # Re-raise the exception if all retries fail
    )
    async def _call_llm_with_retry(self, method_name: str, *args, **kwargs):
        """Helper method to call the underlying LLM method with retry logic."""
        # Log before attempt (tenacity handles logging during retries)
        logger.debug(f"Attempting to call self._llm.{method_name}")
        method_to_call = getattr(self._llm, method_name)
        return await method_to_call(*args, **kwargs)
    # --- END ADDED ---

    async def generate_str(self, *args, **kwargs):
        async with self._semaphore:
            llm_name = getattr(self._llm, 'name', 'UnknownLLM')
            logger.debug(f"Semaphore acquired for LLM call by {llm_name}")
            try:
                # --- COMMENTED OUT: Unconditional Proactive Delay --- 
                # logger.debug(f"Applying 0.5s proactive delay before calling {llm_name}.generate_str")
                # await asyncio.sleep(0.5)
                # --- END COMMENTED OUT ---

                # Call helper method which includes tenacity retry logic
                result = await self._call_llm_with_retry("generate_str", *args, **kwargs)
            except RetryError as e:
                # Log final failure after retries
                logger.error(f"LLM call {llm_name}.generate_str failed after multiple retries: {e}", exc_info=True)
                # Re-raise the original exception that caused the failure
                raise e.cause if e.cause else e
            except Exception as e:
                # Catch any other unexpected errors during the call
                logger.error(f"Unexpected error during LLM call {llm_name}.generate_str: {e}", exc_info=True)
                raise
            finally:
                 logger.debug(f"Semaphore released for LLM call by {llm_name}")
            return result
    
    # --- ADDED: Add generate_structured method --- 
    async def generate_structured(self, *args, **kwargs):
        async with self._semaphore:
            llm_name = getattr(self._llm, 'name', 'UnknownLLM')
            logger.debug(f"Semaphore acquired for structured LLM call by {llm_name}")
            try:
                # --- COMMENTED OUT: Unconditional Proactive Delay --- 
                # logger.debug(f"Applying 0.5s proactive delay before calling {llm_name}.generate_structured")
                # await asyncio.sleep(0.5)
                # --- END COMMENTED OUT ---
                
                # Delegate the actual call to the wrapped LLM instance
                if hasattr(self._llm, 'generate_structured'):
                    # Call helper method which includes tenacity retry logic
                    result = await self._call_llm_with_retry("generate_structured", *args, **kwargs)
                else:
                    logger.error(f"Wrapped LLM {llm_name} has no generate_structured method")
                    raise AttributeError(f"Wrapped LLM has no generate_structured method")
            except RetryError as e:
                # Log final failure after retries
                logger.error(f"LLM call {llm_name}.generate_structured failed after multiple retries: {e}", exc_info=True)
                # Re-raise the original exception that caused the failure
                raise e.cause if e.cause else e
            except Exception as e:
                # Catch any other unexpected errors during the call
                logger.error(f"Unexpected error during LLM call {llm_name}.generate_structured: {e}", exc_info=True)
                raise
            finally:
                 logger.debug(f"Semaphore released for structured LLM call by {llm_name}")
            return result
    # --- END ADDED ---

    # --- ADDED: Wrap the base 'generate' method ---
    async def generate(self, *args, **kwargs):
        async with self._semaphore:
            llm_name = getattr(self._llm, 'name', 'UnknownLLM')
            logger.debug(f"Semaphore acquired for base LLM call by {llm_name}")
            try:
                # Delegate the actual call to the wrapped LLM instance
                if hasattr(self._llm, 'generate'):
                    # Call helper method which includes tenacity retry logic
                    result = await self._call_llm_with_retry("generate", *args, **kwargs)
                else:
                    # This shouldn't happen if we're wrapping an AnthropicAugmentedLLM
                    logger.error(f"Wrapped LLM {llm_name} has no generate method")
                    raise AttributeError(f"Wrapped LLM has no generate method")
            except RetryError as e:
                # Log final failure after retries
                logger.error(f"LLM call {llm_name}.generate failed after multiple retries: {e}", exc_info=True)
                # Re-raise the original exception that caused the failure
                raise e.cause if e.cause else e
            except Exception as e:
                # Catch any other unexpected errors during the call
                logger.error(f"Unexpected error during LLM call {llm_name}.generate: {e}", exc_info=True)
                raise
            finally:
                 logger.debug(f"Semaphore released for base LLM call by {llm_name}")
            return result
    # --- END ADDED ---
    
    # Add other methods if the orchestrator/router call anything else directly
    # e.g., async def generate(...) # <-- Now handled above
    # Remember to acquire the semaphore in those methods too.

# --- ADDED: Custom Exceptions ---
class FileProcessingError(Exception):
    """Custom exception for file processing errors detected during wait."""
    pass

class FileProcessingTimeoutError(Exception):
    """Custom exception for timeout waiting for file processing."""
    pass
# --- END ADDED ---

# Type alias for WebSocketManager for cleaner type hinting
WebSocketManagerType = Any 

# --- ADDED: Polling function ---
async def wait_for_files(
    file_ids_to_check: List[str],
    file_repository: FileRepository,
    query_id: str,
    websocket_manager: WebSocketManagerType,
    db: Session,
    timeout: int = 180 # Default timeout 3 minutes
):
    """
    Polls the database to wait for files to reach 'completed' or 'error' status.

    Args:
        file_ids_to_check: List of file IDs to monitor.
        file_repository: Instance of FileRepository.
        query_id: The query ID for logging and WebSocket updates.
        websocket_manager: Instance of WebSocketManager.
        timeout: Maximum time to wait in seconds.

    Raises:
        FileProcessingError: If any file enters an 'error' state.
        FileProcessingTimeoutError: If the timeout is reached before all files complete.
    """
    start_time = time.time()
    logger.info(f"[{query_id}] Starting to wait for files: {file_ids_to_check}")

    # Send initial wait message
    filenames_being_waited_on = []
    try:
         # Get filenames for the message (best effort)
         for file_id in file_ids_to_check:
             record = file_repository.get(file_id)
             filenames_being_waited_on.append(record.filename if record else f"ID: {file_id}")
    except Exception:
        logger.warning(f"[{query_id}] Could not retrieve all filenames for wait message.")
        filenames_being_waited_on = [f"ID: {fid}" for fid in file_ids_to_check] # Fallback

    wait_msg = f"Waiting for processing to complete for file(s): {', '.join(filenames_being_waited_on)}..."
    await websocket_manager.send_consolidated_update(
        query_id=query_id,
        update_type="file_processing_wait", # New specific type
        message=wait_msg,
        data={"status": "waiting_files", "files": file_ids_to_check}
    )

    while time.time() - start_time < timeout:
        all_done = True
        still_processing_count = 0
        current_statuses = {}

        for file_id in file_ids_to_check:
            try:
                file_record = file_repository.get(file_id) # Fetch using repo (uses request session)

                if not file_record:
                     logger.warning(f"[{query_id}] File record {file_id} vanished during wait.")
                     raise FileProcessingError(f"File record {file_id} not found during status wait.")

                # --- ADDED: Refresh object state from DB ---
                try:
                    logger.debug(f"[{query_id}] Refreshing file record {file_id} state from DB...")
                    db.refresh(file_record) # Force reload attributes from DB
                    logger.debug(f"[{query_id}] File record {file_id} refreshed.")
                except Exception as refresh_err:
                     # Log error but maybe continue? Refresh failure is odd.
                     logger.error(f"[{query_id}] Failed to refresh file record {file_id} from DB: {refresh_err}", exc_info=True)
                     # Decide how critical this is - for now, let's proceed with potentially stale data if refresh fails
                # --- END ADDED ---

                # Handle potential non-dict metadata if DB schema allows nulls or other types
                metadata = file_record.meta_data # Now potentially refreshed
                status = None
                if isinstance(metadata, dict):
                     status = metadata.get('processing_status')
                elif metadata is not None:
                     logger.warning(f"[{query_id}] Unexpected metadata type for {file_id}: {type(metadata)}. Treating status as unknown.")

                current_statuses[file_id] = status
                logger.debug(f"[{query_id}] Checked file {file_id}. Refreshed Status: '{status}'") # Log status *after* potential refresh

                if status == 'error':
                    error_detail = metadata.get("processing_error", "Unknown error") if isinstance(metadata, dict) else 'Unknown processing error'
                    logger.error(f"[{query_id}] File {file_id} processing failed during wait: {error_detail}")
                    raise FileProcessingError(f"Processing failed for file {file_record.filename or file_id}: {error_detail}")
                elif status != 'completed':
                    all_done = False
                    if status == 'processing' or status == 'pending':
                        still_processing_count += 1
                # Don't break here, check all files in each poll iteration

            except FileProcessingError: # Re-raise specific errors
                raise
            except Exception as loop_err:
                 # Catch other potential errors during the loop iteration
                 logger.error(f"[{query_id}] Unexpected error processing file {file_id} within wait loop: {loop_err}", exc_info=True)
                 # Decide if this should halt the whole wait or just skip the file check
                 # For now, let's treat it like a processing error for that file
                 raise FileProcessingError(f"Unexpected error checking status for file {file_id}: {loop_err}")


        if all_done:
            logger.info(f"[{query_id}] All files {file_ids_to_check} have completed processing.")
            return True # Success

        # Optional: Send periodic updates? Maybe only if state changes?
        # logger.debug(f"[{query_id}] Still waiting... {still_processing_count} files processing. Statuses: {current_statuses}")

        # Wait before checking again
        await asyncio.sleep(1.5) # Poll every 1.5 seconds (adjust as needed)

    # If loop finishes, timeout occurred
    logger.error(f"[{query_id}] Timeout waiting for files {file_ids_to_check} to be processed after {timeout}s.")
    raise FileProcessingTimeoutError(f"Timeout ({timeout}s) waiting for file processing. Last known statuses: {current_statuses}")
# --- END ADDED ---

# --- CoordinatorAgent logic is now handled by the local backend (Electron app) ---
# class CoordinatorAgent:
#     ... (comment out full class)

class CoordinatorAgent:
    def __init__(self, *args, **kwargs):
        raise NotImplementedError("CoordinatorAgent is now handled by the local backend (Electron app).")
    async def process_query(self, *args, **kwargs):
        raise NotImplementedError("process_query is now handled by the local backend (Electron app).")

    async def setup(self):
        """Setup and initialize agent components."""
        try:
            logger.info("Setting up CoordinatorAgent")
            
    """
    Coordinator for MCP Agents using Direct Anthropic integration.
    
    This class handles the creation and coordination of agents, setting up
    the necessary configurations for direct Anthropic API usage, and exposing
    FastAPI endpoints for interaction.
    """
    
    def __init__(self, config_path: Optional[str] = None, app: Optional[FastAPI] = None):
        """
        Initialize the coordinator with optional configuration path.
        
        Args:
            config_path: Path to configuration file (optional)
            app: FastAPI app instance (optional)
        """
        # Ensure our modular structure is set up
        setup_modular_structure()
        
        # Limit concurrent Anthropic calls from this instance (adjust value as needed)
        self.llm_semaphore = asyncio.Semaphore(2)
        
        # --- ADDED: Initialize instance logger ---
        self.logger = logger # Use the module-level logger
        # --- END ADDED ---
        
        self.mcp_app = create_mcp_app(name="denker_mcp_agent", settings=config_path)
        self.fast_api = app
        
        # Use the centralized WebSocketManager
        self.websocket_manager = get_websocket_manager()
        
        # Initialize memory manager (will be populated during setup)
        self.memory = None
        
        # Make sure the API key is set
        if 'ANTHROPIC_API_KEY' not in os.environ:
            os.environ['ANTHROPIC_API_KEY'] = ANTHROPIC_API_KEY
            
        # Session storage
        self.sessions = {}
        # --- ADDED: State for pending clarifications --- 
        self.pending_clarifications: Dict[str, Dict[str, Any]] = {} # {conversation_id: {query_id: str, workflow: str}}
        # --- END ADDED ---
        
        # --- ADDED: Cache for agent LLM instances ---
        self.agent_llm_cache: Dict[str, SemaphoreGuardedLLM] = {}
        # --- END ADDED ---
        
        # Initialize modular components
        self.agent_config = AgentConfiguration(
            websocket_manager=self.websocket_manager,
            memory=self.memory,
            create_llm_fn=self._create_anthropic_llm # Pass the LLM factory
        )
        
        # Initialize agent registry
        self.agents = {}
        self.orchestrator = None
        self.router = None
        
        # Initialize decision maker
        self.decision_maker = DecisionMaker(
            websocket_manager=self.websocket_manager,
            agents_registry=self.agents
        )
        
        # Initialize filesystem handler
        self.filesystem_interceptor = get_filesystem_interceptor()
        self.filesystem_handler = FilesystemHandler(
            websocket_manager=self.websocket_manager,
            filesystem_interceptor=self.filesystem_interceptor
        )
        
        # Share entity tracking between components
        self.agent_config.task_entities = {}
        self.agent_config.query_entities = {}
        self.agent_config.session_entities = {}
        
        # Don't create_task in __init__ as there might not be a running event loop
        # We'll initialize MCP during the setup method instead
    
    async def setup(self):
        """Setup and initialize agent components."""
        try:
            logger.info("Setting up CoordinatorAgent")
            
            # Create WebSocket transport for MCP agent events
            websocket_transport = WebSocketEventTransport()
            
            # Configure MCP Agent's logging system with our WebSocket transport
            await LoggingConfig.configure(
                transport=websocket_transport,
                progress_display=True,
                batch_size=10,  # Send events more frequently
                flush_interval=0.5  # Flush faster for near real-time updates
            )
            
            # Initialize MCP app first if needed
            if self.mcp_app and not getattr(self.mcp_app, '_initialized', False):
                logger.info("Initializing MCP App")
                await self.mcp_app.initialize()
                self.mcp_app._initialized = True
                
            # Initialize memory with PostgreSQL-backed tools
            self.memory = CoordinatorMemory(pg_memory_tools)
            await self.memory.initialize()
            logger.info("Memory system initialized")
            
            # Create agent configuration
            self.agent_config = AgentConfiguration()
            self.agent_config.memory = self.memory
            
            # Initialize WebSocket manager (if needed)
            if self.websocket_manager is None:
                logger.warning("No WebSocket manager provided, creating a dummy manager")
                self.websocket_manager = DummyWebSocketManager()
            
            # --- ADDED: Pre-warm critical MCP servers ---
            # Ensure MCPApp and its context are initialized before this
            if self.mcp_app and self.mcp_app.context and self.mcp_app.context.server_registry:
                # Get server names from your agent_configs or a predefined list
                # For this example, using keys from agent_configs that might have server_names
                # A more robust way would be to get all keys from self.mcp_app.context.server_registry if available,
                # or maintain a separate list of critical server names.
                
                all_configured_server_names = list(self.mcp_app.context.server_registry.registry.keys()) # Corrected line
                logger.info(f"Attempting to pre-warm MCP servers: {all_configured_server_names}")

                # Import MCPAggregator here if not already at the top level
                from mcp_agent.mcp.mcp_aggregator import MCPAggregator

                for server_name in all_configured_server_names:
                    if not server_name: # Skip if server_name is empty or None
                        continue
                    logger.info(f"Pre-warming server: {server_name}...")
                    try:
                        # Create a temporary aggregator for this server to trigger connection manager
                        # Assuming connection_persistence=True is the desired default for pre-warming
                        temp_aggregator = MCPAggregator(
                            server_names=[server_name],
                            connection_persistence=True, 
                            context=self.mcp_app.context
                        )
                        await temp_aggregator.initialize(force=True) # force=True to ensure it tries
                        # Optionally, you could call a lightweight method like list_tools or get_capabilities
                        # await temp_aggregator.list_tools() 
                        await temp_aggregator.close() # Clean up the temporary aggregator
                        logger.info(f"Successfully pre-warmed server: {server_name}")
                    except Exception as e:
                        logger.error(f"Failed to pre-warm server '{server_name}': {e}", exc_info=True)
                logger.info("MCP Server pre-warming attempt finished.")
            else:
                logger.warning("MCPApp context or server_registry not available, skipping server pre-warming.")
            # --- END ADDED ---
            
            self.is_setup = True
            logger.info("CoordinatorAgent setup completed successfully")
            
        except Exception as e:
            logger.error(f"Error setting up CoordinatorAgent: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    async def _create_required_agents(self):
        """Create only the essential agents needed at startup."""
        # Decider agent is required for workflow decisions
        self.create_agent(name="decider")
        logger.info("Created required agents for startup")
    
    async def _create_default_agents(self):
        """
        Deprecated: Use _create_required_agents instead.
        This method is kept for backward compatibility.
        """
        self._create_required_agents()
    
    def create_agent(self, name: str, instruction: str = None, server_names: List[str] = None) -> Agent:
        """
        Create a new agent with the given configuration or use defaults if available.
        
        Args:
            name: Name of the agent
            instruction: Optional system instruction (uses default if not provided)
            server_names: Optional list of servers (uses default if not provided)
            
        Returns:
            The created and initialized agent
        
        Raises:
            ValueError: If the agent name is unknown and no instruction is provided
        """
        return self.agent_config.create_agent(
            agent_registry=self.agents, 
            name=name,
            instruction=instruction,
            server_names=server_names,
            context=self.mcp_app.context,
        )
    
    async def create_orchestrator(self, available_agents: Optional[List[str]] = None):
        """
        Create an orchestrator with the specified agents.
        
        Args:
            available_agents: List of agent names the orchestrator can use
            
        Returns:
            The created orchestrator
        """
        self.orchestrator = await self.agent_config.create_orchestrator(
            agent_registry=self.agents,
            create_anthropic_llm_fn=self._create_anthropic_llm,
            available_agents=available_agents,
            context=self.mcp_app.context
        )
        return self.orchestrator
    
    async def create_router(self, available_agents: Optional[List[str]] = None):
        """
        Create a router workflow with the specified agents.
        
        Args:
            available_agents: List of agent names the router can use
            
        Returns:
            The created router
        """
        self.router = await self.agent_config.create_router(
            agent_registry=self.agents,
            create_anthropic_llm_fn=self._create_anthropic_llm,
            available_agents=available_agents,
            context=self.mcp_app.context
        )
        return self.router
    
    def _create_anthropic_llm(self, *args, **kwargs) -> AnthropicAugmentedLLM:
        """
        Factory function to create an Anthropic LLM instance.
        
        This ensures the API key is set and the proper model is used.
        
        Args:
            *args: Variable length argument list
            **kwargs: Arbitrary keyword arguments
            
        Returns:
            Configured Anthropic LLM instance
        """
        # Update memory manager reference if needed
        self.agent_config.memory = self.memory
        
        # Ensure context is passed
        if 'context' not in kwargs and self.mcp_app and hasattr(self.mcp_app, 'context'):
            kwargs['context'] = self.mcp_app.context
        
        # Handle agent parameter - this is used by Orchestrator's llm_factory
        agent = kwargs.get('agent')
        agent_name_for_config_lookup = None

        if agent and hasattr(agent, 'name'):
            # When an Agent object is passed directly (from Orchestrator)
            agent_name = agent.name
            kwargs['agent_name'] = agent_name
            agent_name_for_config_lookup = agent_name
            
            # Use the agent's instruction directly if available
            if hasattr(agent, 'instruction') and agent.instruction:
                kwargs['instruction'] = agent.instruction
            # Otherwise, try to get the instruction from agent_config
            elif agent_name in self.agent_config.agent_configs:
                kwargs['instruction'] = self.agent_config.agent_configs[agent_name]['instruction']
        else:
            # Get agent name from kwargs if available
            agent_name_for_config_lookup = kwargs.get('agent_name')
            
            # Get instruction from agent config if available
            if agent_name_for_config_lookup and agent_name_for_config_lookup in self.agent_config.agent_configs:
                kwargs['instruction'] = self.agent_config.agent_configs[agent_name_for_config_lookup]['instruction']
        
        print(f"[_create_anthropic_llm] DEBUG: Initial agent_name_for_config_lookup: {agent_name_for_config_lookup}")

        # --- ADDED: Check cache first ---
        if agent_name_for_config_lookup and agent_name_for_config_lookup in self.agent_llm_cache:
            logger.info(f"Returning cached LLM instance for agent '{agent_name_for_config_lookup}'")
            print(f"[_create_anthropic_llm] DEBUG: Returning cached LLM for {agent_name_for_config_lookup}")
            return self.agent_llm_cache[agent_name_for_config_lookup]
        # --- END ADDED ---

        chosen_model = DEFAULT_MODEL # Start with the system default
        print(f"[_create_anthropic_llm] DEBUG: Initial chosen_model (from DEFAULT_MODEL): {chosen_model}")

        if agent_name_for_config_lookup and agent_name_for_config_lookup in self.agent_config.agent_configs:
            agent_specific_config = self.agent_config.agent_configs[agent_name_for_config_lookup]
            print(f"[_create_anthropic_llm] DEBUG: Found config for {agent_name_for_config_lookup}: {agent_specific_config.get('model')}")
            if 'model' in agent_specific_config and agent_specific_config['model']:
                chosen_model = agent_specific_config['model']
                logger.info(f"Using agent-specific model '{chosen_model}' for agent '{agent_name_for_config_lookup}'")
                print(f"[_create_anthropic_llm] DEBUG: Overridden chosen_model with agent-specific: {chosen_model} for agent {agent_name_for_config_lookup}")
            else:
                logger.info(f"No specific model in config for agent '{agent_name_for_config_lookup}', using default '{chosen_model}'")
                print(f"[_create_anthropic_llm] DEBUG: No specific model in config for {agent_name_for_config_lookup}, chosen_model remains: {chosen_model}")
        else:
            logger.info(f"No agent_name_for_config_lookup or agent config found, using default model '{chosen_model}' for this LLM instance.")
            print(f"[_create_anthropic_llm] DEBUG: No agent_name_for_config_lookup or agent config found, chosen_model remains: {chosen_model}")

        # --- MODIFIED: Use Fixed Subclass and pass chosen_model to constructor ---
        llm = FixedAnthropicAugmentedLLM(*args, **kwargs, model=chosen_model)
        # --- END MODIFIED ---
        
        # Explicitly set the model in the default request params to override model selection
        # This is somewhat redundant if the constructor handles it, but ensures consistency
        if not hasattr(llm, 'default_request_params') or llm.default_request_params is None:
            llm.default_request_params = RequestParams(model=chosen_model)
        else:
            llm.default_request_params.model = chosen_model
        
        print(f"[_create_anthropic_llm] DEBUG: Final llm.default_request_params.model: {llm.default_request_params.model} for agent {agent_name_for_config_lookup}")
        logger.info(f"Created AnthropicAugmentedLLM instance, configured to use model: {chosen_model}")
        
        # --- MODIFICATION: Return wrapped LLM --- 
        guarded_llm = SemaphoreGuardedLLM(llm, self.llm_semaphore)
        # --- END MODIFICATION ---

        # --- ADDED: Store in cache before returning ---
        if agent_name_for_config_lookup:
            self.agent_llm_cache[agent_name_for_config_lookup] = guarded_llm
            logger.info(f"Cached new LLM instance for agent '{agent_name_for_config_lookup}'")
            print(f"[_create_anthropic_llm] DEBUG: Cached new LLM for {agent_name_for_config_lookup}")
        # --- END ADDED ---
        
        return guarded_llm
    
    async def process_query(
        self,
        query_id: str,
        db: Session,
        context: Optional[Dict[str, Any]] = None,
        complex_processing: bool = False,
        from_intention_agent: bool = False,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a query using the appropriate workflow (router or orchestrator).
        
        Args:
            query_id: Unique ID for the query.
            db: Database session dependency.
            context: Contextual information for the query (e.g., user input, history).
            complex_processing: Flag to indicate complex processing needed.
            from_intention_agent: Flag indicating if the query comes from the intention agent.
            user_id: The ID of the user making the request.
        
        Returns:
            Dictionary containing the final result or an error message.
        """
        # Use the request-specific DB session for the repository
        file_repository = FileRepository(db)
        message_repository = MessageRepository(db) # Initialize once
        start_time = time.time()
        final_result = {"error": "Processing failed", "query_id": query_id}
        websocket_manager = get_websocket_manager() # Get singleton manager instance
        current_logger = getattr(self, 'logger', logger) # Use instance logger if available
        original_workflow_type = None # Store original workflow if clarification
        is_clarification_response = False
        previous_query_id = None # Keep this for potential logging/future use
        
        # --- Get Conversation ID early --- 
        conversation_id = context.get("conversation_id") if context else None

        try:
            # --- Check for Pending Clarification using internal state --- 
            if conversation_id and conversation_id in self.pending_clarifications:
                pending_info = self.pending_clarifications.pop(conversation_id) # Get and remove state
                is_clarification_response = True
                original_workflow_type = pending_info['workflow']
                previous_query_id = pending_info['query_id'] # Store for reference
                current_logger.info(f"[{query_id}] Identified as clarification response for ConvID {conversation_id}. Original Query: {previous_query_id}, Original Workflow: {original_workflow_type}")
            # --- Removed check for frontend context flag ---
            # additional_context = context.get("additionalContext")
            # if additional_context and additional_context.get("is_clarification"):
            #    ...
            # --- END REMOVED --- 

            if not context or not context.get("query"):
                raise ValueError("Context with a 'query' field is required.")
            
            query = context.get("query")
            # conversation_id is already fetched above
            
            current_logger.info(f"[{query_id}] Starting query processing. Query: '{query[:50]}...' UserID: {user_id} ConvID: {conversation_id} IsClarification: {is_clarification_response}")
            
            # --- MODIFIED: File Status Check - Identify files needing wait (Only run for NEW queries) ---
            files_to_process_initially = []
            files_needing_wait = []
            error_files_details = [] # Store details for reporting
            attachments = [] # Define attachments early

            if not is_clarification_response and context: # Only check files for new queries
                attachments = context.get('attachments', [])
                if attachments:
                    raw_file_ids = [att.get('id') for att in attachments if isinstance(att, dict) and att.get('id')]
                    if not raw_file_ids:
                        current_logger.info(f"[{query_id}] No valid file IDs found in attachments list.")
                    else:
                        current_logger.info(f"[{query_id}] Initial check for file statuses: {raw_file_ids}")
                        files_to_process_initially = raw_file_ids

                        for file_id in files_to_process_initially:
                            # ... (existing file checking logic remains here) ...
                            # Ensure try-except block for individual file checks
                            try:
                                file_record: Optional[DBFile] = None
                                # Retry logic for fetching the record
                                for attempt in range(3):
                                    file_record = file_repository.get(file_id) # Uses request-specific session
                                    if file_record: break
                                    if attempt < 2: await asyncio.sleep(0.2)

                                if not file_record:
                                    current_logger.warning(f"[{query_id}] File record not found for file_id: {file_id} after retries.")
                                    error_files_details.append({"id": file_id, "name": f"File ID {file_id}", "reason": "Record not found in database"})
                                    continue # Check next file

                                filename = file_record.filename or f"File {file_id}"

                                # Skip images
                                if file_record.file_type and file_record.file_type.lower().startswith('image/'):
                                    current_logger.info(f"[{query_id}] Skipping status check/wait for image file: {filename} ({file_id})")
                                    continue
                                
                                # Handle metadata and status check (including refresh)
                                metadata = file_record.meta_data
                                status = None
                                try:
                                    logger.debug(f"[{query_id}] Refreshing file record {file_id} state from DB...")
                                    db.refresh(file_record)
                                    metadata = file_record.meta_data # Get potentially refreshed data
                                    logger.debug(f"[{query_id}] File record {file_id} refreshed.")
                                except Exception as refresh_err:
                                    logger.error(f"[{query_id}] Failed to refresh file record {file_id} from DB: {refresh_err}", exc_info=True)
                                
                                if isinstance(metadata, dict):
                                    status = metadata.get('processing_status')
                                elif metadata is not None:
                                    logger.warning(f"[{query_id}] Unexpected metadata type for {file_id}: {type(metadata)}. Treating status as unknown.")
                                    status = 'unknown'

                                current_logger.info(f"[{query_id}] File {filename} ({file_id}): Initial status='{status}'")

                                if status == 'error':
                                    error_detail = metadata.get("processing_error", "Unknown error") if isinstance(metadata, dict) else 'Unknown processing error'
                                    current_logger.warning(f"[{query_id}] File '{filename}' ({file_id}) has processing error: {error_detail}")
                                    error_files_details.append({"id": file_id, "name": filename, "reason": error_detail})
                                elif status != 'completed':
                                    current_logger.info(f"[{query_id}] File '{filename}' ({file_id}) requires waiting (status: {status}).")
                                    files_needing_wait.append(file_id)

                            except Exception as e:
                                current_logger.error(f"[{query_id}] Error during initial status check for file_id {file_id}: {str(e)}", exc_info=True)
                                error_files_details.append({"id": file_id, "name": f"File {file_id}", "reason": f"Error checking status: {str(e)}"})                    

                        # --- Handling after initial check loop ---
                        if error_files_details:
                            error_msg = f"Encountered errors with {len(error_files_details)} file(s) during initial check: " + ", ".join([f"'{f['name']}' ({f['reason']})" for f in error_files_details])
                            current_logger.error(f"[{query_id}] {error_msg}")
                            # Send error update via WebSocket
                            await websocket_manager.send_consolidated_update(
                                query_id=query_id,
                                update_type="error", # Use standard error type
                                message=error_msg,
                                data={"status": "file_check_error", "errors": error_files_details},
                                # No workflow type known here yet
                            )
                            # Return early - processing cannot proceed
                            return {"error": error_msg, "query_id": query_id, "status": "file_check_error"}

            # Store file IDs in context *after* initial checks (only for new queries)
            if not is_clarification_response and context:
                context["file_ids"] = [att.get("id") for att in attachments if isinstance(att, dict) and att.get("id") and not any(e['id'] == att.get("id") for e in error_files_details)]
                current_logger.info(f"Stored valid file IDs in context: {context.get('file_ids', [])}")
            elif context: # Ensure file_ids key exists even for clarification if context is there
                 context["file_ids"] = context.get("file_ids", []) # Keep existing or default to empty
            # --- END FILE CHECK MOVEMENT --- 
            
            # --- Get Conversation ID (already done) --- 
            # conversation_id = context.get("conversation_id") ...
            
            # --- Fetch Message History (common to both paths) --- 
            message_history = []
            if conversation_id:
                try:
                    paginated_result = message_repository.get_by_conversation(
                        conversation_id=conversation_id, limit=10
                    )
                    db_messages = paginated_result.get("messages", [])
                    message_history = [
                        {
                            "role": "assistant" if msg.role in ["assistant", "system"] else "user", 
                            "content": msg.content
                        } 
                        for msg in db_messages
                    ]
                    current_logger.info(f"[{query_id}] Fetched last {len(message_history)} messages for history.")
                except Exception as hist_err:
                    current_logger.error(f"[{query_id}] Failed to fetch message history: {hist_err}", exc_info=True)
            
            context['message_history'] = message_history
            # --- END Fetch History --- 
            
            # --- Combined Logic for Clarification vs New Query --- 
            if is_clarification_response:
                # --- This is a Clarification Response --- 
                current_logger.info(f"[{query_id}] Processing as clarification response using stored workflow: {original_workflow_type}")
                
                # Format the user's clarification answer
                clarification_answer_text = context.get("query")
                if not clarification_answer_text:
                    raise ValueError("Clarification response context missing the actual answer query.")
                answer_message = {"role": "user", "content": clarification_answer_text}
                
                # Append answer to history (history was fetched above)
                if not isinstance(message_history, list): message_history = [] 
                message_history.append(answer_message)
                context['message_history'] = message_history
                
                # Skip file waiting for clarification responses
                # Skip decider call
                # workflow_to_run is not set here, will use original_workflow_type later
                workflow_to_run = None # Explicitly set to None
                decision = None # No decision made for clarification responses

            else: 
                # --- This is a New Query --- 
                # Establish Agent Session ID Mapping, send initial status, etc.
                # ... (existing logic for mapping, websocket status) ...
                try:
                    agent_context = get_agent_context() # Get current MCP agent context
                    agent_session_id = agent_context.session_id
                    if agent_session_id:
                        websocket_manager.add_session_mapping(agent_session_id, query_id)
                    else:
                        current_logger.warning(f"[{query_id}] Could not get agent_session_id from agent context")
                except Exception as ctx_err:
                    current_logger.error(f"[{query_id}] Error getting agent context or session_id: {ctx_err}")
                
                if conversation_id and websocket_manager.is_connected(query_id):
                    if websocket_manager.get_conversation_id(query_id) != conversation_id:
                        websocket_manager.query_to_conversation[query_id] = conversation_id
                
                if websocket_manager.is_connected(query_id):
                    await websocket_manager.send_consolidated_update(
                        query_id=query_id,
                        update_type="status",
                        message="Processing your request...",
                        data={"status": "processing"}
                        # No workflow_type known here yet
                    )
                
                if context is None: context = {}
                context["query_id"] = query_id
                
                # --- Processed message creation --- 
                processed_message = { "role": "user", "content": [] }
                # ... (existing logic for creating processed_message from query, date, attachments) ...
                current_date_str = datetime.now().strftime("%Y-%m-%d")
                processed_message["content"].append({"type": "text", "text": f"Current Date: {current_date_str}"})
                processed_message["content"].append({"type": "text", "text": f"Query: {query}\nSource: {'Intention Agent' if from_intention_agent else 'Main Window'}"})
                if context.get("description"):
                    processed_message["content"].append({"type": "text", "text": f"Additional Context: {context['description']}"})
                if context.get("attachments") and len(context["attachments"]) > 0:
                    processed_message["content"].append({"type": "text", "text": "NOTE: Files have been attached. Use finder agent to search relevant content. Images can be analyzed directly."})
                    for attachment in context["attachments"]:
                        if isinstance(attachment, dict):
                            if attachment.get("type", "").startswith("image/") and attachment.get("data"):
                                processed_message["content"].append({"type": "image", "source": {"type": "base64", "data": attachment["data"], "media_type": attachment.get("mimeType", "image/jpeg")}}) 
                            else:
                                file_info = {"name": attachment.get("name", "Unnamed"), "type": attachment.get("type", "Unknown type"), "id": attachment.get("id", "") or attachment.get("file_id", ""), "size": attachment.get("size")}
                                processed_message["content"].append({"type": "text", "text": f"Attached file: {file_info['name']} (Type: {file_info['type']}, ID: {file_info['id']}). Use finder agent for search."})
                context["processed_message"] = processed_message
                current_logger.info(f"[{query_id}] Created structured message with {len(processed_message['content'])} content blocks")
                
                # --- Call Decider --- 
                decision = await self._get_workflow_decision(query, from_intention_agent, query_id, context, message_history)
                current_logger.info(f"[{query_id}] Decider agent decision: {decision.get('explanation', 'N/A')}, Workflow: {decision.get('workflow_type', 'N/A')}")
                
                # Handle Simple Workflow Directly
                if decision.get("workflow_type") == "simple":
                    current_logger.info(f"[{query_id}] CONFIRMED: Entering simple workflow path.") # <<< ADDED
                    # ... (existing simple workflow handling logic) ...
                    current_logger.info(f"[{query_id}] Handling simple workflow directly.")
                    simple_response = decision.get("simple_response", "Sorry, I couldn't generate a simple response.")
                    completion_time = time.time() - start_time
                    final_result = {"query_id": query_id, "result": simple_response, "workflow_type": "simple", "completion_time": completion_time, "decision_explanation": decision.get("explanation", "N/A")}
                    if websocket_manager.is_connected(query_id):
                        await websocket_manager.send_consolidated_update(
                            query_id=query_id, 
                            update_type="result", 
                            message=final_result["result"], 
                            data={"result": final_result["result"]},
                            workflow_type='simple' # <<< ADDED
                        )
                    if self.memory and user_id and final_result and final_result.get('result'):
                        response_id = str(uuid.uuid4())
                        await self.store_response_reference(query_id=query_id, result=final_result, response_id=response_id, conversation_id=conversation_id)
                    return final_result
                
                # Check if clarification is needed and store state
                if decision.get("needs_clarification"):
                    # ... (existing clarification needed logic, including storing state in self.pending_clarifications) ...
                    current_logger.info(f"[{query_id}] Clarification needed. Halting workflow execution and sending request to client.")
                    if conversation_id:
                        # <<< Use the DECIDED workflow type here for storing state >>>
                        decided_workflow = decision.get("workflow_type", "router")
                        self.pending_clarifications[conversation_id] = {"query_id": query_id, "workflow": decided_workflow}
                        current_logger.info(f"Stored pending clarification state for conversation {conversation_id} (Query: {query_id}, Workflow: {self.pending_clarifications[conversation_id]['workflow']})")
                    else:
                        current_logger.warning(f"[{query_id}] Cannot store pending clarification state: conversation_id is missing.")
                    await websocket_manager.send_consolidated_update(
                        query_id=query_id, 
                        update_type="clarification", 
                        message=decision.get("explanation", "Clarification required"), 
                        data={"needsClarification": True, "clarifyingQuestions": decision.get("clarifying_questions", []), "explanation": decision.get("explanation")},
                        workflow_type=decision.get("workflow_type") # <<< Use decided workflow type
                    )
                    return {"status": "pending_clarification", "message": "Waiting for user clarification.", "query_id": query_id, "details": {"questions": decision.get("clarifying_questions", []), "explanation": decision.get("explanation")}}
                
                # Handle complex_processing override
                if complex_processing:
                    # ... (existing override logic) ...
                    original_decision_workflow = decision.get('workflow_type', 'unknown')
                    current_logger.warning(f"[{query_id}] Overriding workflow type '{original_decision_workflow}' with 'orchestrator'")
                    decision["workflow_type"] = "orchestrator"
                    if websocket_manager.is_connected(query_id):
                        await websocket_manager.send_consolidated_update(
                            query_id, 
                            "status", 
                            "Using orchestrator workflow (override)", 
                            {"status": "workflow_selected", "workflow_type": "orchestrator", "is_override": True},
                            workflow_type='orchestrator' # <<< ADDED
                        )

                # Determine workflow for new query
                workflow_to_run = decision.get("workflow_type", "router")

                # Wait for files if necessary (Moved after decision, before workflow execution)
                if files_needing_wait:
                    # ... (existing file waiting logic, call wait_for_files) ...
                    current_logger.info(f"[{query_id}] Proceeding to wait for background processing of files: {files_needing_wait}")
                    try:
                        # <<< Update call inside wait_for_files if needed, but maybe not here >>>
                        # <<< wait_for_files itself calls send_consolidated_update, consider if it needs workflow type >>>
                        await wait_for_files(file_ids_to_check=files_needing_wait, file_repository=file_repository, query_id=query_id, websocket_manager=websocket_manager, db=db, timeout=180)
                        current_logger.info(f"[{query_id}] File processing wait complete for {files_needing_wait}. Proceeding with agent workflow.")
                        if websocket_manager.is_connected(query_id):
                            await websocket_manager.send_consolidated_update(
                                query_id=query_id, 
                                update_type="status", 
                                message="File processing complete, starting main task...", 
                                data={"status": "starting_workflow"},
                                workflow_type=workflow_to_run # <<< Use the decided workflow
                            )
                    except (FileProcessingError, FileProcessingTimeoutError) as e:
                        current_logger.error(f"[{query_id}] Halting query processing due to file wait issue: {e}")
                        await websocket_manager.send_consolidated_update(
                            query_id=query_id, 
                            update_type="error", 
                            message=str(e), 
                            data={"status": "file_wait_failed", "error_message": str(e)},
                            workflow_type=workflow_to_run # <<< Use the decided workflow
                        )
                        return {"error": str(e), "query_id": query_id, "status": "file_wait_failed"}
                else:
                    current_logger.info(f"[{query_id}] No files require waiting, proceeding directly to workflow.")
            
            # --- END Combined Logic --- 
            
            # --- Main Workflow Execution (common to both paths) --- 
            # Use workflow_to_run if it was set in the 'New Query' branch, otherwise use original_workflow_type
            final_workflow_to_run = workflow_to_run if not is_clarification_response else original_workflow_type
            current_logger.info(f"[{query_id}] Determined final workflow to run: {final_workflow_to_run}")
            
            # Create AgentRequest
            request = AgentRequest(
                query=query, # Use original query text for the request
                workflow_type=final_workflow_to_run, 
                session_id=conversation_id, 
                use_agents=context.get('use_agents', ["websearcher", "finder", "structure", "writer", "proofreader", "factchecker", "formatter", "styleenforcer"]), # Get from context or default
                processed_message=context.get("processed_message") if not is_clarification_response else None, # Pass processed only for new query
                message_history=context.get('message_history'), # Pass the potentially augmented history
                file_ids=context.get("file_ids", [])
            )
            
            current_logger.info(f"[{query_id}] Starting main workflow: {request.workflow_type}")
            workflow_processor = await self._get_workflow_processor(request.workflow_type)
            response = await workflow_processor(request=request, query_id=query_id, websocket_manager=websocket_manager) # <<< MODIFIED
            
            # --- Format and Return Result (common) ---
            final_result = {
                "query_id": query_id,
                "result": response.result,
                "workflow_type": response.workflow_type,
                "completion_time": time.time() - start_time, # Recalculate here
                "decision_explanation": decision.get("explanation", "N/A") if not is_clarification_response else "Resumed after clarification" # Add appropriate note
            }
            
            # Send final result via WebSocket
            if websocket_manager.is_connected(query_id):
                # ... (existing send final result logic) ...
                current_logger.info(f"[{query_id}] Preparing to send FINAL RESULT update via WebSocket. Result: {final_result['result'][:100]}...")
                await websocket_manager.send_consolidated_update(
                    query_id=query_id, 
                    update_type="result", 
                    message=final_result["result"], 
                    data={"result": final_result["result"]},
                    workflow_type=final_workflow_to_run # <<< Use final workflow type
                )
            
            # Store response reference
            if self.memory and user_id and final_result and final_result.get('result'):
                # ... (existing store response logic) ...
                response_id = str(uuid.uuid4())
                await self.store_response_reference(query_id=query_id, result=final_result, response_id=response_id, conversation_id=conversation_id)
            
            return final_result
            
        except Exception as e:
            # ... (existing exception handling) ...
            current_logger = getattr(self, 'logger', logger)
            current_logger.error(f"[{query_id}] Unhandled error in process_query: {str(e)}")
            current_logger.error(f"Traceback: {traceback.format_exc()}")
            if websocket_manager.is_connected(query_id):
                await websocket_manager.send_consolidated_update(
                    query_id=query_id, 
                    update_type="error", 
                    message=f"An unexpected error occurred: {str(e)}", 
                    data={"error_message": str(e), "status": "processing_error"}
                    # workflow_type is unknown here
                )
            return {"status": "error", "message": f"Error processing query: {str(e)}", "query_id": query_id}
    
    async def setup_api(self, app: FastAPI) -> bool:
        """
        Set up the API endpoints for the coordinator.
        
        Args:
            app: FastAPI application instance
            
        Returns:
            True if setup succeeds, False otherwise
        """
        self.fast_api = app
        
        # Define the API routes - direct MCP agent endpoint removed to avoid duplication
        # We now use only the /api/v1/agents/coordinator/mcp-agent endpoint
        
        # Session history endpoint moved to API routes
        # Now using /api/v1/agents/session/{session_id} instead
        
        # WebSocket endpoint removed - using only the /api/v1/agents/ws/mcp-agent/{query_id} endpoint
        
        logger.info("API routes set up successfully")
        return True
    
    async def close(self):
        """
        Clean up resources and gracefully shut down all components.
        """
        logger.info("Shutting down CoordinatorAgent...")
        
        # Close all agents
        for agent_name, agent in list(self.agents.items()):
            try:
                await agent.shutdown()
                logger.info(f"Shut down agent '{agent_name}'")
            except Exception as e:
                logger.warning(f"Error shutting down agent '{agent_name}': {str(e)}")
        
        # Clean up router and orchestrator
        if self.router:
            try:
                logger.info("Shutting down router")
                if hasattr(self.router, 'shutdown'):
                    await self.router.shutdown()
                elif hasattr(self.router, 'close'):
                    await self.router.close()
                logger.info("Router shut down successfully")
            except Exception as e:
                logger.warning(f"Error shutting down router: {str(e)}")
        
        if self.orchestrator:
            try:
                logger.info("Shutting down orchestrator")
                if hasattr(self.orchestrator, 'shutdown'):
                    await self.orchestrator.shutdown()
                elif hasattr(self.orchestrator, 'close'):
                    await self.orchestrator.close()
                logger.info("Orchestrator shut down successfully")
            except Exception as e:
                logger.warning(f"Error shutting down orchestrator: {str(e)}")
        
        # Clean up MCP app
        try:
            await self.mcp_app.cleanup()
            logger.info("MCP app cleaned up successfully")
        except Exception as e:
            logger.warning(f"Error cleaning up MCP app: {str(e)}")
        
        logger.info("Coordinator agent resources cleaned up")

    async def _initialize_mcp(self):
        """Initialize MCP connections."""
        try:
            # Make sure the MCP app is initialized
            if not hasattr(self, 'mcp_app') or not self.mcp_app:
                logger.info("Creating and initializing MCP app")
                
                # If we need to run the MCP app in a context manager, we'll need to adjust the architecture
                # For now, just ensure it's initialized
                self.mcp_app_context = self.mcp_app.run()
                await self.mcp_app_context.__aenter__()
                
                logger.info("MCP app initialized and running in context")
            else:
                # Already have an app, make sure it's initialized
                if not getattr(self.mcp_app, '_initialized', False):
                    logger.info("Initializing existing MCP app")
                    await self.mcp_app.initialize()
                    
            # Set a flag to track initialization state
            self.mcp_app._initialized = True
            
            logger.info("MCP initialization complete")
        except Exception as e:
            logger.error(f"Failed to initialize MCP: {str(e)}")
            raise

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
        return await self.filesystem_handler.handle_mcp_filesystem_operation(
                query_id=query_id,
            tool_name=tool_name,
            arguments=arguments
        )

    async def _get_workflow_processor(self, workflow_type: str) -> Callable:
        """
        Get the appropriate workflow processor function based on the workflow type.
        
        Args:
            workflow_type: The type of workflow to process ('orchestrator' or 'router')
            
        Returns:
            A callable function that processes the request with the specified workflow
            
        Raises:
            ValueError: If an unsupported workflow type is specified
        """
        if workflow_type == "orchestrator":
            return self.process_orchestrator_workflow
        elif workflow_type == "router":
            return self.process_router_workflow
        else:
            raise ValueError(f"Unsupported workflow type: {workflow_type}")
    
    def ensure_agents_exist(self, agent_names: List[str]) -> List[Agent]:
        """
        Ensure that all specified agents exist, creating them if needed.
        
        Args:
            agent_names: List of agent names to check/create
            
        Returns:
            List of agent objects
        """
        return self.agent_config.ensure_agents_exist(
            agent_registry=self.agents,
            agent_names=agent_names,
            context=self.mcp_app.context
        )
    
    async def process_orchestrator_workflow(self, request: AgentRequest, query_id: str, websocket_manager=None) -> AgentResponse:
        """
        Process a request using the orchestrator workflow.
        
        Args:
            request: The agent request to process
            query_id: Unique identifier for this query
            websocket_manager: WebSocketManager instance # <<< ADDED DOC
            
        Returns:
            AgentResponse with the orchestrator result
        """
        # Import the actual function from the other module
        from .coordinator_workflows import process_orchestrator_workflow as _process_orchestrator_workflow_func

        # Call the imported function, passing the received websocket_manager
        return await _process_orchestrator_workflow_func(
            request=request,
            query_id=query_id,
            orchestrator=self.orchestrator,
            create_orchestrator_fn=self.create_orchestrator,
            ensure_agents_exist_fn=self.ensure_agents_exist,
            create_anthropic_llm_fn=self._create_anthropic_llm,
            websocket_manager=websocket_manager # <<< PASSING RECEIVED ARG
        )
    
    async def process_router_workflow(self, request: AgentRequest, query_id: str, websocket_manager=None) -> AgentResponse:
        """
        Process a request using the router workflow.
        
        Args:
            request: The agent request to process
            query_id: Unique identifier for this query
            websocket_manager: WebSocketManager instance # <<< ADDED DOC
            
        Returns:
            AgentResponse with the router result
        """
        # Import the actual function from the other module
        from .coordinator_workflows import process_router_workflow as _process_router_workflow_func

        # Call the imported function, passing the received websocket_manager
        return await _process_router_workflow_func(
            request=request,
            query_id=query_id,
            router=self.router,
            create_router_fn=self.create_router,
            ensure_agents_exist_fn=self.ensure_agents_exist,
            agents=self.agents,
            create_anthropic_llm_fn=self._create_anthropic_llm,
            websocket_manager=websocket_manager # <<< PASSING RECEIVED ARG
        )

    async def _get_workflow_decision(
        self, 
        query: str, 
        from_intention_agent: bool = False, 
        query_id: str = None, 
        context: Optional[Dict[str, Any]] = None,
        message_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Use the decider agent to determine the appropriate workflow.
        
        Args:
            query: The user's query text
            from_intention_agent: Whether this request came from the intention agent
            query_id: The query ID for WebSocket updates (optional)
            context: Additional context for the query (contains processed_message)
            message_history: Optional list of previous user/assistant messages
    
        Returns:
            Dict containing workflow type and response for simple conversations
        """
        # Ensure we're using the consistent query_id from context if available
        if context and "query_id" in context:
            query_id = context["query_id"]
        
        # Extract just the processed_message from context
        processed_message = context.get("processed_message") if context else None
        if not processed_message:
            # Fallback if processed_message wasn't created
            processed_message = {"role": "user", "content": [{"type": "text", "text": query}]}
        
        # Get the decider agent
        decider_agent = self.agents.get("decider")
        if not decider_agent:
            logger.warning("Decider agent not found, defaulting to router workflow")
            return {"workflow_type": "router", "explanation": "Decider agent unavailable"}
        
        # Create an LLM instance specifically for the decider
        # We pass the agent object itself here
        decider_llm = self._create_anthropic_llm(agent=decider_agent)
        
        # --- ADDED: Construct full message list for decider --- 
        history = message_history or [] 
        # Ensure the current processed message is not None before appending
        full_messages_for_decider = history + ([processed_message] if processed_message else [])
        if len(history) > 0:
            logger.info(f"[{query_id}] Passing {len(history)} history messages to decider agent.")
        # --- END ADDED ---
        
        try:
            # Use generate_structured for Pydantic model output
            structured_response = await decider_llm.generate_structured(
                message=full_messages_for_decider,
                response_model=DecisionResponseModel
            )
            logger.debug(f"Decider LLM structured response type: {type(structured_response)}")

            # Validate the response type
            if not isinstance(structured_response, DecisionResponseModel):
                logger.error(f"Decider LLM did not return DecisionResponseModel. Got: {type(structured_response)}. Response: {structured_response}")
                raise TypeError(f"LLM response validation failed. Expected DecisionResponseModel, got {type(structured_response)}.")

            # Convert the validated Pydantic model to a dictionary
            decision = structured_response.model_dump()
            logger.info(f"Successfully received and validated DecisionResponseModel: {decision}")

            # Send the decision update via WebSocket and wait for it
            if query_id and self.websocket_manager.is_connected(query_id):
                logger.info(f"[{query_id}] Sending 'decision' update via WebSocket...")
                await self.websocket_manager.send_consolidated_update(
                    query_id=query_id,
                    update_type="decision",
                    message=f"Selected {decision.get('workflow_type')} workflow: {decision.get('explanation')}",
                    data=decision # Pass the decision dict as data
                )
                logger.info(f"[{query_id}] Finished sending 'decision' update.")

            # Return the decision dictionary
            return decision

        except Exception as e:
            # Log the error during the decision process
            logger.error(f"Error getting or processing workflow decision for query {query_id}: {str(e)}", exc_info=True)

            # Create a default decision (router workflow)
            default_decision = {"workflow_type": "router", "explanation": f"Error in decision making: {str(e)}. Falling back to router."}

            # Send an error update via WebSocket (fire and forget)
            if query_id and self.websocket_manager.is_connected(query_id):
                 logger.warning(f"[{query_id}] Sending error update due to decision failure.")
                 asyncio.create_task(self.websocket_manager.send_consolidated_update(
                     query_id=query_id,
                     update_type="error",
                     message=f"Error determining workflow: {str(e)}. Falling back to router.",
                     data={"error_message": str(e), "status": "decision_error", "fallback_decision": default_decision}
                 ))

            # Return the default decision dictionary
            return default_decision

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
        return await self.filesystem_handler.handle_filesystem_operation(
            query_id=query_id,
            operation=operation,
            path=path,
            **kwargs
        )

    async def check_health(self) -> Dict[str, bool]:
        """
        Check the health of the MCP agent and its components.
        
        Returns:
            Dict[str, bool]: A dictionary with health status of components
        """
        health_result = {
            "coordinator": True  # The coordinator is running if this method is called
        }
        
        try:
            # Check if MCP app is initialized
            if hasattr(self, 'mcp_app') and self.mcp_app:
                health_result["mcp_app"] = True
            else:
                health_result["mcp_app"] = False
                # If MCP app is not available, all servers are unavailable
                health_result["qdrant"] = False
                health_result["fetch"] = False
                health_result["websearch"] = False
                health_result["filesystem"] = False

                health_result["document-loader"] = False
                health_result["markdown-editor"] = False
                return health_result
            
            # Check if memory is available
            if self.memory is not None:
                health_result["memory"] = True
            else:
                health_result["memory"] = False
            
            # Check if Qdrant service is available and functional
            try:
                if hasattr(self.mcp_app, 'servers') and 'qdrant' in self.mcp_app.servers:
                    qdrant_server = self.mcp_app.servers['qdrant']
                    
                    # Create a test agent to verify tool availability
                    test_agent = Agent(
                        name="qdrant_health_check",
                        instruction="Test connection to Qdrant",
                        server_names=["qdrant"]
                    )
                    
                    await test_agent.initialize()
                    tools = await test_agent.list_tools()
                    tool_names = [tool.name for tool in tools.tools] if hasattr(tools, 'tools') else []
                    
                    # Check for required Qdrant tools
                    has_store = any("qdrant-store" in tool for tool in tool_names)
                    has_find = any("qdrant-find" in tool for tool in tool_names)
                    
                    health_result["qdrant"] = has_store and has_find
                    logger.info(f"Qdrant health check: store={has_store}, find={has_find}")
                else:
                    health_result["qdrant"] = False
                    logger.warning("Qdrant server not found in MCP servers")
            except Exception as e:
                logger.warning(f"Error checking Qdrant health: {str(e)}")
                health_result["qdrant"] = False
            
            # Check if Fetch service is available and functional
            try:
                if hasattr(self.mcp_app, 'servers') and 'fetch' in self.mcp_app.servers:
                    fetch_server = self.mcp_app.servers['fetch']
                    
                    # Create a test agent to verify tool availability
                    test_agent = Agent(
                        name="fetch_health_check",
                        instruction="Test connection to Fetch server",
                        server_names=["fetch"]
                    )
                    
                    await test_agent.initialize()
                    tools = await test_agent.list_tools()
                    tool_names = [tool.name for tool in tools.tools] if hasattr(tools, 'tools') else []
                    
                    # Check for fetch tools
                    has_fetch = any("fetch" in tool for tool in tool_names)
                    
                    health_result["fetch"] = has_fetch
                    logger.info(f"Fetch health check: fetch={has_fetch}")
                else:
                    health_result["fetch"] = False
                    logger.warning("Fetch server not found in MCP servers")
            except Exception as e:
                logger.warning(f"Error checking Fetch health: {str(e)}")
                health_result["fetch"] = False
            
            # Check if WebSearch service is available and functional
            try:
                if hasattr(self.mcp_app, 'servers') and 'websearch' in self.mcp_app.servers:
                    websearch_server = self.mcp_app.servers['websearch']
                    
                    # Create a test agent to verify tool availability
                    test_agent = Agent(
                        name="websearch_health_check",
                        instruction="Test connection to WebSearch server",
                        server_names=["websearch"]
                    )
                    
                    await test_agent.initialize()
                    tools = await test_agent.list_tools()
                    tool_names = [tool.name for tool in tools.tools] if hasattr(tools, 'tools') else []
                    
                    # Check for websearch tools
                    has_search = any("search" in tool for tool in tool_names)
                    
                    health_result["websearch"] = has_search
                    logger.info(f"WebSearch health check: search={has_search}")
                else:
                    health_result["websearch"] = False
                    logger.warning("WebSearch server not found in MCP servers")
            except Exception as e:
                logger.warning(f"Error checking WebSearch health: {str(e)}")
                health_result["websearch"] = False
            
            # Check if Filesystem service is available and functional
            try:
                if hasattr(self.mcp_app, 'servers') and 'filesystem' in self.mcp_app.servers:
                    filesystem_server = self.mcp_app.servers['filesystem']
                    
                    # Create a test agent to verify tool availability
                    test_agent = Agent(
                        name="filesystem_health_check",
                        instruction="Test connection to Filesystem server",
                        server_names=["filesystem"]
                    )
                    
                    await test_agent.initialize()
                    tools = await test_agent.list_tools()
                    tool_names = [tool.name for tool in tools.tools] if hasattr(tools, 'tools') else []
                    
                    # Check for filesystem tools
                    has_read = any("read" in tool for tool in tool_names)
                    has_write = any("write" in tool for tool in tool_names)
                    has_list = any("list" in tool for tool in tool_names)
                    
                    health_result["filesystem"] = has_read and has_list
                    logger.info(f"Filesystem health check: read={has_read}, write={has_write}, list={has_list}")
                else:
                    health_result["filesystem"] = False
                    logger.warning("Filesystem server not found in MCP servers")
                    
                # Additional check if filesystem interceptor is available
                if self.filesystem_interceptor is not None:
                    health_result["filesystem_interceptor"] = True
                else:
                    health_result["filesystem_interceptor"] = False
            except Exception as e:
                logger.warning(f"Error checking Filesystem health: {str(e)}")
                health_result["filesystem"] = False
                

                
            # Check if Document Loader service is available and functional
            try:
                if hasattr(self.mcp_app, 'servers') and 'document-loader' in self.mcp_app.servers:
                    document_loader_server = self.mcp_app.servers['document-loader']
                    
                    # Create a test agent to verify tool availability
                    test_agent = Agent(
                        name="document_loader_health_check",
                        instruction="Test connection to Document Loader server",
                        server_names=["document-loader"]
                    )
                    
                    await test_agent.initialize()
                    tools = await test_agent.list_tools()
                    tool_names = [tool.name for tool in tools.tools] if hasattr(tools, 'tools') else []
                    
                    # Check for document processing tools
                    has_load = any(("load" in tool.lower() or "extract" in tool.lower()) for tool in tool_names)
                    
                    health_result["document-loader"] = has_load
                    logger.info(f"Document Loader health check: has_load={has_load}")
                else:
                    health_result["document-loader"] = False
                    logger.warning("Document Loader server not found in MCP servers")
            except Exception as e:
                logger.warning(f"Error checking Document Loader health: {str(e)}")
                health_result["document-loader"] = False
                
            # Check if Markdown Editor service is available and functional
            try:
                if hasattr(self.mcp_app, 'servers') and 'markdown-editor' in self.mcp_app.servers:
                    markdown_editor_server = self.mcp_app.servers['markdown-editor']
                    
                    # Create a test agent to verify tool availability
                    test_agent = Agent(
                        name="markdown_editor_health_check",
                        instruction="Test connection to Markdown Editor server",
                        server_names=["markdown-editor"]
                    )
                    
                    await test_agent.initialize()
                    tools = await test_agent.list_tools()
                    tool_names = [tool.name for tool in tools.tools] if hasattr(tools, 'tools') else []
                    
                    # Check for markdown editing tools
                    has_create = any("create" in tool.lower() for tool in tool_names)
                    has_edit = any("edit" in tool.lower() or "append" in tool.lower() for tool in tool_names)
                    
                    health_result["markdown-editor"] = has_create or has_edit
                    logger.info(f"Markdown Editor health check: has_create={has_create}, has_edit={has_edit}")
                else:
                    health_result["markdown-editor"] = False
                    logger.warning("Markdown Editor server not found in MCP servers")
            except Exception as e:
                logger.warning(f"Error checking Markdown Editor health: {str(e)}")
                health_result["markdown-editor"] = False
            
            # Check Anthropic API key is set
            if 'ANTHROPIC_API_KEY' in os.environ and os.environ['ANTHROPIC_API_KEY']:
                health_result["anthropic_api"] = True
            else:
                health_result["anthropic_api"] = False
                
        except Exception as e:
            logger.error(f"Error checking MCP agent health: {str(e)}")
            health_result["error"] = str(e)
            health_result["coordinator"] = False
        
        return health_result

    async def store_response_reference(
        self,
        query_id: str,
        result: Dict[str, Any],
        response_id: str,
        conversation_id: Optional[str] = None
    ):
        """
        Store a reference to a response in the memory system.
        
        Args:
            query_id: The unique query identifier
            result: The result data to store
            response_id: The unique response identifier
            conversation_id: Optional conversation ID
        """
        if not self.memory:
            return
            
        try:
            # Create result entity
            result_entity = f"result-{response_id}"
            
            # Extract result text
            result_text = result.get("result", "")
            if not result_text and isinstance(result, dict):
                result_text = str(result)
                
            # Create a snippet for faster retrieval
            snippet = result_text[:150] + "..." if len(result_text) > 150 else result_text
            
            # Create the entity
            await self.memory.create_entity_if_not_exists(result_entity, "Result")
            
            # Add observation with the result
            await self.memory.add_observation(result_entity, result_text)
            
            # Store the conversation reference
            if conversation_id:
                await self.memory.store_conversation_reference(
                    result_entity,
                    conversation_id,
                    response_id,
                    snippet
                )
                
            # Link to the query
            query_entity = f"query-{query_id}"
            await self.memory.create_relation(query_entity, "has_result", result_entity)
            
            logger.info(f"Stored response reference for query {query_id}, response {response_id}")
            
        except Exception as e:
            logger.error(f"Error storing response reference: {str(e)}")
            logger.error(traceback.format_exc())

    # --- ADDED: Human Input Callback --- 
    async def _handle_human_input_request(self, request: HumanInputRequest) -> str:
        """
        Callback passed to Agents to handle human input requests via WebSocket.
        """
        current_logger = getattr(self, 'logger', logger)
        current_logger.info(f"[Callback] Handling human input request ID: {request.request_id}") # Removed query_id
        try:
            # --- Workaround: Hardcode tool_name as __human_input__ --- 
            tool_name_for_manager = "__human_input__"
            # --- End Workaround ---
            
            # --- PROBLEM: We still need query_id here, but request doesn't have it --- 
            # How do we get the correct query_id for the WebSocketManager?
            # Placeholder - this will likely fail or use the wrong connection:
            # A more robust solution needs a way to map request.request_id or agent context to query_id.
            placeholder_query_id = "UNKNOWN_QUERY_ID" # Replace with actual logic if possible
            self.logger.warning(f"[Callback] Unable to determine correct query_id for human input request {request.request_id}. Using placeholder: {placeholder_query_id}")
            # --- END PROBLEM --- 

            response_dict = await self.websocket_manager.request_human_input(
                query_id=placeholder_query_id, # <<< Using placeholder
                input_prompt=request.prompt, 
                tool_description=request.description, 
                tool_name=tool_name_for_manager, # <<< Use the hardcoded name
                timeout=request.timeout_seconds 
            )
            
            if response_dict and response_dict.get("success"):
                user_input = response_dict.get("input", "") # Get the input string
                current_logger.info(f"[Callback] Received input for {request.request_id}: '{user_input[:50]}...'")
                return user_input # Return the string input received
            else:
                error_msg = response_dict.get("error", "Unknown error receiving input")
                current_logger.warning(f"[Callback] Failed to get human input for {request.request_id}: {error_msg}")
                return f"Error: {error_msg}" # Return an error string

        except TimeoutError: # This might be caught internally by the manager now, but keep for safety
            current_logger.warning(f"[Callback] Human input timed out for request: {request.request_id}")
            return "Error: Human input timed out."
        except Exception as e:
            current_logger.error(f"[Callback] Error during human input handling for {request.request_id}: {e}", exc_info=True)
            return f"Error: Failed to get human input - {str(e)}"
    # --- END ADDED ---

# --- ADDED: Fixed Anthropic LLM Subclass ---
class FixedAnthropicAugmentedLLM(AnthropicAugmentedLLM):
    """Subclass to fix the generate method's check for stop_reason."""
    async def generate(
        self,
        message,
        request_params: RequestParams | None = None,
    ):
        # --- THIS IS A COPY OF THE ORIGINAL generate METHOD WITH THE FIX APPLIED ---
        # --- Source: mcp-agent v0.0.18 augmented_llm_anthropic.py ---
        """
        Process a query using an LLM and available tools.
        The default implementation uses Claude as the LLM.
        Override this method to use a different LLM.
        """
        # --- ADDED LOGGING ---
        self.logger.info(f"[FixedAnthropicAugmentedLLM.generate] Received message type: {type(message)}")
        self.logger.info(f"[FixedAnthropicAugmentedLLM.generate] Received message content (first 500 chars): {str(message)[:500]}")
        # --- END ADDED LOGGING ---

        config = self.context.config
        anthropic = Anthropic(api_key=config.anthropic.api_key)
        messages: List[MessageParam] = []
        params = self.get_request_params(request_params)

        if params.use_history:
            self.logger.info(f"[FixedAnthropicAugmentedLLM.generate] use_history is TRUE. Extending messages with history.")
            messages.extend(self.history.get())
        else:
            self.logger.info(f"[FixedAnthropicAugmentedLLM.generate] use_history is FALSE. Not using history.")

        if isinstance(message, str):
            messages.append({"role": "user", "content": message})
        elif isinstance(message, list):
            messages.extend(message)
        else:
            messages.append(message)

        list_tools_response = await self.aggregator.list_tools()
        available_tools: List[ToolParam] = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema,
            }
            for tool in list_tools_response.tools
        ]

        responses: List[Message] = []
        model = await self.select_model(params)
        # Initialize previous_llm_response variable
        previous_llm_response = None

        for i in range(params.max_iterations):
            # --- FIX APPLIED HERE --- 
            # Check if it's the last iteration AND the PREVIOUS response indicated tool use
            if i == params.max_iterations - 1 and previous_llm_response and previous_llm_response.stop_reason == "tool_use":
            # --- END FIX --- 
                final_prompt_message = MessageParam(
                    role="user",
                    content="""We've reached the maximum number of iterations. 
                    Please stop using tools now and provide your final comprehensive answer based on all tool results so far. 
                    At the beginning of your response, clearly indicate that your answer may be incomplete due to reaching the maximum number of tool usage iterations, 
                    and explain what additional information you would have needed to provide a more complete answer.""",
                )
                messages.append(final_prompt_message)

            arguments = {
                "model": model,
                "max_tokens": params.maxTokens,
                "messages": messages,
                "system": self.instruction or params.systemPrompt,
                "stop_sequences": params.stopSequences,
                "tools": available_tools,
            }

            if params.metadata:
                arguments = {**arguments, **params.metadata}

            self.logger.debug(f"{arguments}")
            # --- ADDED LOGGING ---
            self.logger.info(f"[FixedAnthropicAugmentedLLM.generate] Messages before API call (length {len(messages)}):")
            for i, msg in enumerate(messages):
                self.logger.info(f"[FixedAnthropicAugmentedLLM.generate] Message [{i}]: Role='{msg.get('role')}', Content (first 200 chars of str, or type if not str): {str(msg.get('content'))[:200] if isinstance(msg.get('content'), str) else type(msg.get('content'))}")
                if isinstance(msg.get('content'), list):
                    for j, content_item in enumerate(msg.get('content')):
                        self.logger.info(f"[FixedAnthropicAugmentedLLM.generate]   Content item [{j}]: Type='{content_item.get('type') if isinstance(content_item, dict) else type(content_item)}', Text (first 100 chars): {str(content_item.get('text') if isinstance(content_item, dict) else content_item)[:100]}")
            # --- END ADDED LOGGING ---
            self._log_chat_progress(chat_turn=(len(messages) + 1) // 2, model=model)

            executor_result = await self.executor.execute(
                anthropic.messages.create, **arguments
            )

            llm_response = executor_result[0]

            if isinstance(llm_response, BaseException):
                self.logger.error(f"Error: {executor_result}")
                # Store the error as the "previous response" to prevent further loops if needed
                previous_llm_response = None # Or potentially store error info if useful
                break # Exit loop on error

            self.logger.debug(
                f"{model} response:",
                data=llm_response,
            )

            response_as_message = self.convert_message_to_message_param(llm_response)
            messages.append(response_as_message)
            responses.append(llm_response) # Store the actual LLM response

            # --- Store for next iteration's check --- 
            previous_llm_response = llm_response
            # --- End Store ---

            if llm_response.stop_reason == "end_turn":
                self.logger.debug(
                    f"Iteration {i}: Stopping because finish_reason is 'end_turn'"
                )
                break
            elif llm_response.stop_reason == "stop_sequence":
                # We have reached a stop sequence
                self.logger.debug(
                    f"Iteration {i}: Stopping because finish_reason is 'stop_sequence'"
                )
                break
            elif llm_response.stop_reason == "max_tokens":
                # We have reached the max tokens limit
                self.logger.debug(
                    f"Iteration {i}: Stopping because finish_reason is 'max_tokens'"
                )
                # TODO: saqadri - would be useful to return the reason for stopping to the caller
                break
            else:  # llm_response.stop_reason == "tool_use":
                for content in llm_response.content:
                    if content.type == "tool_use":
                        tool_name = content.name
                        tool_args = content.input
                        tool_use_id = content.id

                        # TODO -- productionize this human input check
                        # if tool_name == HUMAN_INPUT_TOOL_NAME: ...

                        tool_call_request = CallToolRequest(
                            method="tools/call",
                            params=CallToolRequestParams(
                                name=tool_name, arguments=tool_args
                            ),
                        )

                        result = await self.call_tool(
                            request=tool_call_request, tool_call_id=tool_use_id
                        )

                        message = self.from_mcp_tool_result(result, tool_use_id)

                        messages.append(message)

        if params.use_history:
            self.history.set(messages)

        self._log_chat_finished(model=model)

        return responses
    # --- END ADDED ---