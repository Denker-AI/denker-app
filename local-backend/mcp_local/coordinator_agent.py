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
from .pg_memory_tools import memory_tools
from .core.websocket_manager import WebSocketManager, get_websocket_manager
from .core.event_websocket_transport import WebSocketEventTransport
from .core.filesystem_interceptor import FilesystemInterceptor, get_filesystem_interceptor
from .base.server import MCPServer
from .base.protocol import Request, Response, Tool, ListToolsResponse
from .app_extension import create_mcp_app
from .core.cloud_file_repository import CloudFileRepository
from .core.cloud_message_repository import CloudMessageRepository
from core.user_store import LocalUserStore # ADDED

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
# from fastapi import Depends
# from sqlalchemy.orm import Session
# from db.database import get_db
# from db.repositories import FileRepository, MessageRepository
# from db.models import File as DBFile, Message as DBMessage # Alias to avoid naming clash
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

# --- ADDED: Global circuit breaker for 529 errors ---
class OverloadCircuitBreaker:
    """Circuit breaker to stop all API calls when Anthropic returns 529 errors."""
    def __init__(self):
        self._is_overloaded = False
        self._overload_time = None
        self._reset_timeout = 30  # Reset after 30 seconds
    
    def is_overloaded(self) -> bool:
        """Check if the circuit breaker is currently tripped."""
        if self._is_overloaded and self._overload_time:
            # Auto-reset after timeout
            if time.time() - self._overload_time > self._reset_timeout:
                logger.info("Circuit breaker auto-reset after timeout")
                self.reset()
                return False
        return self._is_overloaded
    
    def trip(self, error_message: str = ""):
        """Trip the circuit breaker due to overload."""
        self._is_overloaded = True
        self._overload_time = time.time()
        logger.error(f"Circuit breaker TRIPPED due to overload: {error_message}")
    
    def reset(self):
        """Reset the circuit breaker."""
        self._is_overloaded = False
        self._overload_time = None
        logger.info("Circuit breaker RESET")

# Global circuit breaker instance
_overload_circuit_breaker = OverloadCircuitBreaker()
# --- END ADDED ---

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
        # Check circuit breaker first
        if _overload_circuit_breaker.is_overloaded():
            raise Exception("Service is currently overloaded (circuit breaker tripped). Please try again later.")
        
        # FIXED: Create deep copies of arguments to prevent mutation during retries
        import copy
        
        # Log before attempt (tenacity handles logging during retries)
        logger.debug(f"Attempting to call self._llm.{method_name}")
        
        # Create deep copies of mutable arguments to prevent inter-retry contamination
        safe_args = copy.deepcopy(args)
        safe_kwargs = copy.deepcopy(kwargs)
        
        try:
            method_to_call = getattr(self._llm, method_name)
            return await method_to_call(*safe_args, **safe_kwargs)
        except Exception as e:
            # Check if this is an OverloadedError and trip the circuit breaker
            if "OverloadedError" in str(type(e)) or "OverloadedError" in str(e) or "529" in str(e) or "overloaded" in str(e).lower():
                _overload_circuit_breaker.trip(f"529 error in {method_name}: {str(e)}")
            raise
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
    file_repository: CloudFileRepository,
    query_id: str,
    websocket_manager: WebSocketManagerType,
    timeout: int = 180 # Default timeout 3 minutes
):
    """
    Polls the cloud backend to wait for files to reach 'completed' or 'error' status.
    """
    start_time = time.time()
    logger.info(f"[{query_id}] Starting to wait for files: {file_ids_to_check}")

    # Send initial wait message
    filenames_being_waited_on = []
    try:
         # Get filenames for the message (best effort)
         for file_id in file_ids_to_check:
             record = await file_repository.get(file_id)
             filenames_being_waited_on.append(record.get('filename', f"ID: {file_id}"))
    except Exception:
        logger.warning(f"[{query_id}] Could not retrieve all filenames for wait message.")
        filenames_being_waited_on = [f"ID: {fid}" for fid in file_ids_to_check] # Fallback

    wait_msg = f"Waiting for processing to complete for file(s): {', '.join(filenames_being_waited_on)}..."
    await websocket_manager.send_consolidated_update(
        query_id=query_id,
        update_type="file_processing_wait",
        message=wait_msg,
        data={"status": "waiting_files", "files": file_ids_to_check}
    )

    while time.time() - start_time < timeout:
        all_done = True
        still_processing_count = 0
        current_statuses = {}

        for file_id in file_ids_to_check:
            try:
                file_record = await file_repository.get(file_id)
                if not file_record:
                     logger.warning(f"[{query_id}] File record {file_id} vanished during wait.")
                     raise FileProcessingError(f"File record {file_id} not found during status wait.")

                # FIXED: Backend API returns 'metadata' not 'meta_data'
                metadata_dict = file_record.get('metadata')
                status = None
                if isinstance(metadata_dict, dict):
                     status = metadata_dict.get('processing_status')
                elif metadata_dict is not None: # Case where 'meta_data' field exists but is not a dictionary
                     logger.warning(f"[{query_id}] Unexpected type for 'meta_data' field in file {file_id}: {type(metadata_dict)}. Treating status as unknown.")

                current_statuses[file_id] = status
                logger.debug(f"[{query_id}] Checked file {file_id}. Refreshed Status: '{status}'")

                if status == 'error':
                    error_detail = metadata_dict.get("processing_error", "Unknown error") if isinstance(metadata_dict, dict) else 'Unknown processing error'
                    logger.error(f"[{query_id}] File {file_id} processing failed during wait: {error_detail}")
                    raise FileProcessingError(f"Processing failed for file {file_record.get('filename', file_id)}: {error_detail}")
                elif status != 'completed':
                    all_done = False
                    if status == 'processing' or status == 'pending':
                        still_processing_count += 1
            except FileProcessingError:
                raise
            except Exception as loop_err:
                 logger.error(f"[{query_id}] Unexpected error processing file {file_id} within wait loop: {loop_err}", exc_info=True)
                 raise FileProcessingError(f"Unexpected error checking status for file {file_id}: {loop_err}")

        if all_done:
            logger.info(f"[{query_id}] All files {file_ids_to_check} have completed processing.")
            return True # Success

        await asyncio.sleep(1.5)

    logger.error(f"[{query_id}] Timeout waiting for files {file_ids_to_check} to be processed after {timeout}s.")
    raise FileProcessingTimeoutError(f"Timeout ({timeout}s) waiting for file processing. Last known statuses: {current_statuses}")
# --- END ADDED ---

class CoordinatorAgent:
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
                
            # Initialize memory with backend-backed tools
            self.memory = CoordinatorMemory(memory_tools)
            await self.memory.initialize()
            logger.info("Memory system initialized")
            
            # Create agent configuration
            self.agent_config = AgentConfiguration()
            self.agent_config.memory = self.memory
            
            # Initialize WebSocket manager (if needed)
            if self.websocket_manager is None:
                logger.warning("No WebSocket manager provided, creating a dummy manager")
                self.websocket_manager = DummyWebSocketManager()
            
            # --- NEW: Initialize proper MCP server prewarming ---
            if self.mcp_app and self.mcp_app.context and self.mcp_app.context.server_registry:
                try:
                    from services.mcp_server_prewarmer import initialize_mcp_prewarmer
                    
                    # Initialize the prewarmer with context
                    self.mcp_prewarmer = initialize_mcp_prewarmer(self.mcp_app.context)
                    
                    # Get list of servers to prewarm
                    all_configured_server_names = list(self.mcp_app.context.server_registry.registry.keys())
                    logger.info(f"Starting background MCP server prewarming for: {all_configured_server_names}")
                    
                    # Start prewarming in background (non-blocking)
                    await self.mcp_prewarmer.start_prewarming(
                        server_names=all_configured_server_names,
                        delay_seconds=3  # Wait 3 seconds before starting
                    )
                    
                    logger.info("MCP Server prewarming scheduled")
                except ImportError as e:
                    logger.warning(f"MCP server prewarmer not available: {e}")
                except Exception as e:
                    logger.error(f"Failed to initialize MCP server prewarming: {e}")
            else:
                logger.warning("MCPApp context or server_registry not available, skipping server prewarming.")
            # --- END NEW ---
            
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
        context: Optional[Dict[str, Any]] = None,
        complex_processing: bool = False,
        from_intention_agent: bool = False,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a query using the appropriate workflow (router or orchestrator).
        
        Args:
            query_id: Unique ID for the query.
            context: Contextual information for the query (e.g., user input, history).
            complex_processing: Flag to indicate complex processing needed.
            from_intention_agent: Flag indicating if the query comes from the intention agent.
            user_id: The ID of the user making the request.
        
        Returns:
            Dictionary containing the final result or an error message.
        """
        start_time = time.time()
        current_logger = logging.getLogger(f"mcp_local.coordinator_agent.query.{query_id}")
        current_logger.info(f"Processing query: {query_id} for user: {user_id} with context: {context}")
        
        # --- ADDED: Attempt to get token from LocalUserStore --- 
        auth_token: Optional[str] = None
        stored_user_info = LocalUserStore.get_user()
        if stored_user_info and stored_user_info.get("user_id") == user_id:
            auth_token = stored_user_info.get("token")
            current_logger.info(f"[{query_id}] Retrieved token from LocalUserStore for user {user_id}: {'Token Present' if auth_token else 'Token NOT Present'}")
        else:
            current_logger.warning(f"[{query_id}] No matching user or token found in LocalUserStore for user {user_id}. Stored info: {stored_user_info}")
        # --- END ADDED ---

        # Initialize repositories with the token if available
        # If a file_repository is already part of self, it might need re-initialization or a method to set token
        # For simplicity, we instantiate a new one here if calls are made directly from process_query
        # However, wait_for_files receives file_repository as an argument, so that's the critical one.

        # Ensure the file_repository used by wait_for_files gets the token.
        # The instance of CloudFileRepository is created in this method's scope or passed to wait_for_files.
        # If it's created here, we pass the token. If passed to wait_for_files, the caller must ensure it has the token.

        # Let's assume file_repository for wait_for_files is instantiated in this scope
        file_repository = CloudFileRepository(token=auth_token)
        message_repository = CloudMessageRepository(token=auth_token)

        try:
            # Check for cancellation at the start
            try:
                await asyncio.sleep(0)  # Allow cancellation to be processed
            except asyncio.CancelledError:
                current_logger.info(f"[{query_id}] Query was cancelled before processing started")
                await self.websocket_manager.send_consolidated_update(
                    query_id=query_id,
                    update_type="status", 
                    message="Query was cancelled",
                    data={"status": "cancelled"}
                )
                return {"status": "cancelled", "message": "Query was cancelled", "query_id": query_id}
            
            await self.websocket_manager.send_consolidated_update(
                query_id=query_id,
                update_type="status",
                message="Processing your request...",
                data={"status": "processing"}
                # No workflow_type known here yet
            )

            if not context or not context.get("query"):
                raise ValueError("Context with a 'query' field is required.")
            
            query = context.get("query")
            # MODIFIED: Define conversation_id and is_clarification_response before logging
            conversation_id = context.get("conversation_id")
            is_clarification_response = context.get("is_clarification_response", False) # Default to False if not present
            
            current_logger.info(f"[{query_id}] Starting query processing. Query: '{query[:50]}...' UserID: {user_id} ConvID: {conversation_id if conversation_id else 'N/A'} IsClarification: {is_clarification_response}")
            
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
                                    # file_record = await file_repository.get(file_id) # Uses request-specific session
                                    # MODIFIED: Ensure file_repository used here has the token.
                                    # The file_repository instance is now created above with the token.
                                    file_record = await file_repository.get(file_id)
                                    if file_record: break
                                    if attempt < 2: await asyncio.sleep(0.2)

                                if not file_record:
                                    current_logger.warning(f"[{query_id}] File record not found for file_id: {file_id} after retries.")
                                    error_files_details.append({"id": file_id, "name": f"File ID {file_id}", "reason": "Record not found in database"})
                                    continue # Check next file

                                # MODIFIED: Access file_record as a dict
                                filename = file_record.get("filename") or f"File {file_id}"

                                # Skip images
                                # MODIFIED: Access file_record as a dict
                                if file_record.get("file_type") and file_record.get("file_type", "").lower().startswith('image/'):
                                    current_logger.info(f"[{query_id}] Skipping status check/wait for image file: {filename} ({file_id})")
                                    continue
                                
                                # Handle metadata and status check (no refresh, use cloud repo result)
                                # FIXED: Backend API returns 'metadata' not 'meta_data'
                                metadata = file_record.get("metadata")
                                status = None
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
                            await self.websocket_manager.send_consolidated_update(
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
                    paginated_result = await message_repository.get_by_conversation(
                        conversation_id=conversation_id, limit=10
                    )
                    db_messages = paginated_result.get("messages", [])
                    message_history = [
                        {
                            "role": "assistant" if msg.get("role") in ["assistant", "system"] else "user", 
                            "content": msg.get("content")
                        } 
                        for msg in db_messages
                    ]
                    current_logger.info(f"[{query_id}] Fetched last {len(message_history)} messages for history.")
                except Exception as hist_err:
                    current_logger.error(f"[{query_id}] Failed to fetch message history: {hist_err}", exc_info=True)
            
            context['message_history'] = message_history
            # --- END Fetch History --- 
            
            # --- Combined Logic for Clarification vs New Query --- 
            # Initialize variables to prevent NameError
            workflow_to_run = None
            original_workflow_type = None
            decision = None
            
            if is_clarification_response:
                # --- This is a Clarification Response --- 
                # Retrieve the original workflow type from pending clarifications
                original_workflow_type = None
                if conversation_id and conversation_id in self.pending_clarifications:
                    pending_info = self.pending_clarifications[conversation_id]
                    original_workflow_type = pending_info.get('workflow', 'router')  # Default to router if missing
                    current_logger.info(f"[{query_id}] Retrieved pending clarification info for conversation {conversation_id}: Query: {pending_info.get('query_id')}, Original Workflow: {original_workflow_type}")
                else:
                    current_logger.warning(f"[{query_id}] No pending clarification found for conversation {conversation_id}, defaulting to router workflow")
                    original_workflow_type = 'router'  # Safe fallback
                
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
                        # MODIFIED: Use self.websocket_manager
                        self.websocket_manager.add_session_mapping(agent_session_id, query_id)
                    else:
                        current_logger.warning(f"[{query_id}] Could not get agent_session_id from agent context")
                except Exception as ctx_err:
                    current_logger.error(f"[{query_id}] Error getting agent context or session_id: {ctx_err}")
                
                # MODIFIED: Use self.websocket_manager
                if conversation_id and self.websocket_manager.is_connected(query_id):
                    if self.websocket_manager.get_conversation_id(query_id) != conversation_id:
                        self.websocket_manager.query_to_conversation[query_id] = conversation_id
                
                # MODIFIED: Use self.websocket_manager
                if self.websocket_manager.is_connected(query_id):
                    await self.websocket_manager.send_consolidated_update(
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
                    processed_message["content"].append({"type": "text", "text": "NOTE: Files have been attached. Use researcher agent to search relevant content. Images can be analyzed directly."})
                    for attachment in context["attachments"]:
                        if isinstance(attachment, dict):
                            if attachment.get("type", "").startswith("image/") and attachment.get("data"):
                                processed_message["content"].append({"type": "image", "source": {"type": "base64", "data": attachment["data"], "media_type": attachment.get("mimeType", "image/jpeg")}}) 
                            else:
                                file_info = {"name": attachment.get("name", "Unnamed"), "type": attachment.get("type", "Unknown type"), "id": attachment.get("id", "") or attachment.get("file_id", ""), "size": attachment.get("size")}
                                processed_message["content"].append({"type": "text", "text": f"Attached file: {file_info['name']} (Type: {file_info['type']}, ID: {file_info['id']}). Use researcher agent for search."})
                context["processed_message"] = processed_message
                current_logger.info(f"[{query_id}] Created structured message with {len(processed_message['content'])} content blocks")
                
                # --- Call Decider --- 
                decision = await self._get_workflow_decision(query, from_intention_agent, query_id, context, message_history)
                current_logger.info(f"[{query_id}] Decider agent decision: {decision.get('explanation', 'N/A')}, Workflow: {decision.get('workflow_type', 'N/A')}")
                
                # --- ADDED: Check for overloaded service first ---
                if decision.get("overloaded"):
                    current_logger.info(f"[{query_id}] Service is overloaded. Returning overload response immediately.")
                    completion_time = time.time() - start_time
                    overload_result = {
                        "query_id": query_id, 
                        "result": decision.get("simple_response", "The service is currently overloaded. Please try again later."), 
                        "workflow_type": "simple", 
                        "completion_time": completion_time, 
                        "decision_explanation": decision.get("explanation", "Service overloaded"),
                        "overloaded": True
                    }
                    # Send final overload result via WebSocket (no further workflow processing)
                    if self.websocket_manager.is_connected(query_id):
                        await self.websocket_manager.send_consolidated_update(
                            query_id=query_id, 
                            update_type="result", 
                            message=overload_result["result"], 
                            data={"result": overload_result["result"], "overloaded": True},
                            workflow_type='simple'
                        )
                    return overload_result
                # --- END ADDED ---
                
                # Handle Simple Workflow Directly
                if decision.get("workflow_type") == "simple":
                    current_logger.info(f"[{query_id}] CONFIRMED: Entering simple workflow path.") # <<< ADDED
                    # ... (existing simple workflow handling logic) ...
                    current_logger.info(f"[{query_id}] Handling simple workflow directly.")
                    simple_response = decision.get("simple_response", "Sorry, I couldn't generate a simple response.")
                    completion_time = time.time() - start_time
                    final_result = {"query_id": query_id, "result": simple_response, "workflow_type": "simple", "completion_time": completion_time, "decision_explanation": decision.get("explanation", "N/A")}
                    if self.websocket_manager.is_connected(query_id):
                        await self.websocket_manager.send_consolidated_update(
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
                    await self.websocket_manager.send_consolidated_update(
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
                    if self.websocket_manager.is_connected(query_id):
                        await self.websocket_manager.send_consolidated_update(
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
                        await wait_for_files(file_ids_to_check=files_needing_wait, file_repository=file_repository, query_id=query_id, websocket_manager=self.websocket_manager, timeout=180)
                        current_logger.info(f"[{query_id}] File processing wait complete for {files_needing_wait}. Proceeding with agent workflow.")
                        if self.websocket_manager.is_connected(query_id):
                            await self.websocket_manager.send_consolidated_update(
                                query_id=query_id, 
                                update_type="status", 
                                message="File processing complete, starting main task...", 
                                data={"status": "starting_workflow"},
                                workflow_type=workflow_to_run # <<< Use the decided workflow
                            )
                    except (FileProcessingError, FileProcessingTimeoutError) as e:
                        current_logger.error(f"[{query_id}] Halting query processing due to file wait issue: {e}")
                        await self.websocket_manager.send_consolidated_update(
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
            
            # Handle mode selection
            mode = context.get("mode", "multiagent")
            single_agent_type = context.get("single_agent_type")
            
            # Determine agents to use based on mode
            if mode == "single" and single_agent_type:
                # For single agent mode, use only the specified agent type
                # Map frontend agent types to backend agent names
                agent_mapping = {
                    "researcher": ["researcher"],
                    "creator": ["creator"], 
                    "editor": ["editor"]
                }
                use_agents = agent_mapping.get(single_agent_type, ["researcher"])
                current_logger.info(f"[{query_id}] Single agent mode: using {single_agent_type} -> {use_agents}")
            else:
                # For multiagent mode, use default agents
                use_agents = context.get('use_agents', ["researcher", "creator", "editor"])
                current_logger.info(f"[{query_id}] Multi-agent mode: using {use_agents}")
            
            # Create AgentRequest
            request = AgentRequest(
                query=query, # Use original query text for the request
                workflow_type=final_workflow_to_run, 
                session_id=conversation_id, 
                use_agents=use_agents,
                processed_message=context.get("processed_message") if not is_clarification_response else None, # Pass processed only for new query
                message_history=context.get('message_history'), # Pass the potentially augmented history
                file_ids=context.get("file_ids", []),
                mode=mode,
                single_agent_type=single_agent_type
            )
            
            current_logger.info(f"[{query_id}] Starting main workflow: {request.workflow_type}")
            
            # Check for cancellation before starting workflow
            try:
                await asyncio.sleep(0)  # Allow cancellation to be processed
            except asyncio.CancelledError:
                current_logger.info(f"[{query_id}] Query was cancelled before workflow execution")
                await self.websocket_manager.send_consolidated_update(
                    query_id=query_id,
                    update_type="status",
                    message="Query was cancelled",
                    data={"status": "cancelled"}
                )
                return {"status": "cancelled", "message": "Query was cancelled", "query_id": query_id}
            
            workflow_processor = await self._get_workflow_processor(request.workflow_type)
            
            try:
                current_logger.info(f"[{query_id}] About to call workflow processor: {workflow_processor.__name__}")
                response = await workflow_processor(request=request, query_id=query_id, websocket_manager=self.websocket_manager) # <<< MODIFIED
                current_logger.info(f"[{query_id}] Workflow processor completed. Response type: {type(response)}, has result: {hasattr(response, 'result')}")
                if hasattr(response, 'result'):
                    current_logger.info(f"[{query_id}] Response result preview: {str(response.result)[:100]}...")
                
                # --- ADDED: Check for overloaded response and stop immediately ---
                if hasattr(response, 'overloaded') and response.overloaded:
                    current_logger.info(f"[{query_id}] Workflow returned overloaded response. Stopping execution immediately.")
                    overload_result = {
                        "query_id": query_id,
                        "result": response.result,
                        "workflow_type": response.workflow_type,
                        "completion_time": time.time() - start_time,
                        "decision_explanation": "Service overloaded during workflow execution",
                        "overloaded": True
                    }
                    # Send overload result via WebSocket - no memory storage
                    if self.websocket_manager.is_connected(query_id):
                        await self.websocket_manager.send_consolidated_update(
                            query_id=query_id,
                            update_type="result",
                            message=overload_result["result"],
                            data={"result": overload_result["result"], "overloaded": True},
                            workflow_type=response.workflow_type
                        )
                    return overload_result
                # --- END ADDED ---
            except asyncio.CancelledError:
                current_logger.info(f"[{query_id}] Workflow was cancelled during execution")
                await self.websocket_manager.send_consolidated_update(
                    query_id=query_id,
                    update_type="status",
                    message="Query was cancelled",
                    data={"status": "cancelled"}
                )
                return {"status": "cancelled", "message": "Query was cancelled during workflow execution", "query_id": query_id}
            except Exception as workflow_error:
                current_logger.error(f"[{query_id}] Workflow processor failed with error: {str(workflow_error)}")
                current_logger.error(f"[{query_id}] Workflow error traceback: {traceback.format_exc()}")
                await self.websocket_manager.send_consolidated_update(
                    query_id=query_id,
                    update_type="error",
                    message=f"Workflow execution failed: {str(workflow_error)}",
                    data={"status": "workflow_error", "error": str(workflow_error)}
                )
                return {"status": "error", "message": f"Workflow execution failed: {str(workflow_error)}", "query_id": query_id}
            
            # --- Format and Return Result (common) ---
            current_logger.info(f"[{query_id}] Processing workflow result into final format...")
            if not response:
                current_logger.error(f"[{query_id}] Workflow processor returned None/empty response!")
                await self.websocket_manager.send_consolidated_update(
                    query_id=query_id,
                    update_type="error",
                    message="Workflow completed but returned no result",
                    data={"status": "empty_response"}
                )
                return {"status": "error", "message": "Workflow completed but returned no result", "query_id": query_id}
            final_result = {
                "query_id": query_id,
                "result": response.result,
                "workflow_type": response.workflow_type,
                "completion_time": time.time() - start_time, # Recalculate here
                "decision_explanation": decision.get("explanation", "N/A") if decision and not is_clarification_response else ("Resumed after clarification" if is_clarification_response else "N/A") # Safe access and appropriate note
            }
            
            # Send final result via WebSocket with streaming
            if self.websocket_manager.is_connected(query_id):
                # ... (existing send final result logic) ...
                current_logger.info(f"[{query_id}] Preparing to send FINAL RESULT update via WebSocket with streaming. Result: {final_result['result'][:100]}...")
                await self.websocket_manager.send_streaming_update(
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
            # MODIFIED: Use self.websocket_manager
            if self.websocket_manager.is_connected(query_id):
                await self.websocket_manager.send_consolidated_update(
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

        # Get workflow configuration from MCP app config
        workflow_config = None
        if hasattr(self.mcp_app, 'config') and self.mcp_app.config:
            # Extract workflows section from config (needs to handle extra fields)
            config_dict = self.mcp_app.config.model_dump() if hasattr(self.mcp_app.config, 'model_dump') else self.mcp_app.config.__dict__
            workflow_config = config_dict.get('workflows', {})
            logger.debug(f"[{query_id}] Loaded workflow configuration: {workflow_config}")
        else:
            logger.debug(f"[{query_id}] No workflow configuration available from MCP app")
        
        # Call the imported function, passing the received websocket_manager and workflow config
        return await _process_router_workflow_func(
            request=request,
            query_id=query_id,
            router=self.router,
            create_router_fn=self.create_router,
            ensure_agents_exist_fn=self.ensure_agents_exist,
            agents=self.agents,
            create_anthropic_llm_fn=self._create_anthropic_llm,
            websocket_manager=websocket_manager, # <<< PASSING RECEIVED ARG
            workflow_config=workflow_config  # <<< PASSING WORKFLOW CONFIG
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
            # Check circuit breaker before making decision call
            if _overload_circuit_breaker.is_overloaded():
                logger.error(f"[{query_id}] Circuit breaker is tripped - service overloaded. Skipping decision call.")
                overloaded_decision = {
                    "workflow_type": "simple",
                    "explanation": "Service is currently overloaded (circuit breaker active)",
                    "simple_response": "The service is currently overloaded. Please try again in a few moments.",
                    "needs_clarification": False,
                    "overloaded": True
                }
                return overloaded_decision
            
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
            # Check if this is an OverloadedError (529 error) from Anthropic - STOP EXECUTION
            if "OverloadedError" in str(type(e)) or "OverloadedError" in str(e) or "529" in str(e) or "overloaded" in str(e).lower():
                logger.error(f"[{query_id}] Anthropic API is overloaded (529 error) in decider. Stopping all execution. Error: {e}")
                
                # Trip the circuit breaker to prevent further calls
                _overload_circuit_breaker.trip(f"529 error in decider for query {query_id}: {str(e)}")
                
                overloaded_decision = {
                    "workflow_type": "simple",
                    "explanation": "Service is currently overloaded",
                    "simple_response": "The service is currently overloaded. Please try again in a few moments.",
                    "needs_clarification": False,
                    "overloaded": True  # Special flag to indicate this is an overload situation
                }
                
                # Send an overload update via WebSocket
                if query_id and self.websocket_manager.is_connected(query_id):
                    await self.websocket_manager.send_consolidated_update(
                        query_id=query_id,
                        update_type="error",
                        message="Service is currently overloaded. Please try again later.",
                        data={"error_type": "overloaded", "error_message": str(e), "status": "overloaded"}
                    )
                
                # Return the overloaded decision - this will stop further workflow execution
                return overloaded_decision
            
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
        # --- Temporarily disable memory operations for debugging timeouts ---
        logger.info(f"[DEBUG] Memory operations in store_response_reference are temporarily disabled for query_id: {query_id}")
        return # Exit early
        # --- End temporary disable ---

        # if not self.memory: # Original check
        #     return
            
        # try:
        #     # Create result entity
        #     result_entity = f"result-{response_id}"
            
        #     # Extract result text
        #     result_text = result.get("result", "")
        #     if not result_text and isinstance(result, dict):
        #         result_text = str(result)
                
        #     # Create a snippet for faster retrieval
        #     snippet = result_text[:150] + "..." if len(result_text) > 150 else result_text
            
        #     # Create the entity
        #     await self.memory.create_entity_if_not_exists(result_entity, "Result")
            
        #     # Add observation with the result
        #     await self.memory.add_observation(result_entity, result_text)
            
        #     # Store the conversation reference
        #     if conversation_id:
        #         await self.memory.store_conversation_reference(
        #             result_entity,
        #             conversation_id,
        #             response_id,
        #             snippet
        #         )
                
        #     # Link to the query
        #     query_entity = f"query-{query_id}"
        #     await self.memory.create_relation(query_entity, "has_result", result_entity)
            
        #     logger.info(f"Stored response reference for query {query_id}, response {response_id}")
            
        # except Exception as e:
        #     logger.error(f"Error storing response reference: {str(e)}")
        #     logger.error(traceback.format_exc())

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
    """Subclass to fix the generate method's check for stop_reason and add prompt caching."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Enable prompt caching by default
        self._enable_prompt_caching = kwargs.pop("enable_prompt_caching", True)
        self._cache_workflow_context = kwargs.pop("cache_workflow_context", True)
        # Use 1-hour cache for long-running workflows (beta feature)
        self._use_long_cache_for_workflows = kwargs.pop("use_long_cache_for_workflows", False) # MODIFIED: Default to False for 5-min cache

        # --- ADDED: Explicitly enable caching for tools and system prompt by default ---
        self.cache_tools = kwargs.pop("cache_tools", True)
        self.cache_system_prompt = kwargs.pop("cache_system_prompt", True)
        
        # --- FIXED: Safe logger access after parent initialization ---
        if hasattr(self, 'logger') and self.logger:
            self.logger.info(f"[FixedAnthropicAugmentedLLM] Initialized with cache_tools={self.cache_tools}, cache_system_prompt={self.cache_system_prompt}")
        else:
            # Fallback to module logger if instance logger not available
            logger.info(f"[FixedAnthropicAugmentedLLM] Initialized with cache_tools={self.cache_tools}, cache_system_prompt={self.cache_system_prompt}")
        # --- END FIXED ---
    
    async def generate_structured(
        self,
        message,
        response_model,
        request_params = None,
    ):
        """
        Override generate_structured to add circuit breaker protection for the instructor API call.
        """
        # Check circuit breaker before proceeding
        if _overload_circuit_breaker.is_overloaded():
            self.logger.error("[FixedAnthropicAugmentedLLM.generate_structured] Circuit breaker is tripped - service overloaded. Aborting structured generation.")
            raise Exception("Service is currently overloaded (circuit breaker tripped). Please try again later.")
        
        # First we invoke the LLM to generate a string response
        # We need to do this in a two-step process because Instructor doesn't
        # know how to invoke MCP tools via call_tool, so we'll handle all the
        # processing first and then pass the final response through Instructor
        import instructor

        try:
            response = await self.generate_str(
                message=message,
                request_params=request_params,
            )
        except Exception as e:
            # Check if this is an OverloadedError (529 error) from the first call
            if "OverloadedError" in str(type(e)) or "OverloadedError" in str(e) or "529" in str(e) or "overloaded" in str(e).lower():
                self.logger.error(f"[FixedAnthropicAugmentedLLM.generate_structured] 529 error during generate_str. Circuit breaker already tripped. Error: {e}")
                raise Exception(f"Service is currently overloaded. Please try again later. Original error: {str(e)}")
            else:
                raise

        # Check circuit breaker again before the second API call
        if _overload_circuit_breaker.is_overloaded():
            self.logger.error("[FixedAnthropicAugmentedLLM.generate_structured] Circuit breaker tripped after generate_str, aborting instructor call.")
            raise Exception("Service is currently overloaded (circuit breaker tripped). Please try again later.")

        # Next we pass the text through instructor to extract structured data
        try:
            # Safely access API key from config, allow fallback to environment variable
            anthropic_api_key_from_config = None
            if self.context and self.context.config and hasattr(self.context.config, 'anthropic') and self.context.config.anthropic and hasattr(self.context.config.anthropic, 'api_key'):
                anthropic_api_key_from_config = self.context.config.anthropic.api_key

            client = instructor.from_anthropic(
                Anthropic(api_key=anthropic_api_key_from_config),
            )

            params = self.get_request_params(request_params)
            model = await self.select_model(params)

            # Extract structured data from natural language - THIS IS THE SECOND API CALL
            structured_response = client.chat.completions.create(
                model=model,
                response_model=response_model,
                messages=[{"role": "user", "content": response}],
                max_tokens=params.maxTokens,
            )

            return structured_response
            
        except Exception as e:
            # Check if this is an OverloadedError (529 error) from the instructor call
            if "OverloadedError" in str(type(e)) or "OverloadedError" in str(e) or "529" in str(e) or "overloaded" in str(e).lower():
                self.logger.error(f"[FixedAnthropicAugmentedLLM.generate_structured] 529 error during instructor call. Tripping circuit breaker. Error: {e}")
                _overload_circuit_breaker.trip(f"529 error in FixedAnthropicAugmentedLLM.generate_structured instructor call: {str(e)}")
                raise Exception(f"Service is currently overloaded. Please try again later. Original error: {str(e)}")
            else:
                raise

    def _estimate_tokens(self, content: str) -> int:
        """
        Rough estimation of token count (approximately 4 characters per token).
        For more accurate counting, you could integrate tiktoken or similar.
        """
        return len(content) // 4
    
    def _meets_minimum_cache_requirements(self, content: str, model: str = None) -> bool:
        """
        Check if content meets Anthropic's minimum token requirements for caching.
        
        Args:
            content: The content to check
            model: The model being used (to determine token threshold)
            
        Returns:
            bool: Whether content meets minimum requirements
        """
        if not content:
            return False
            
        estimated_tokens = self._estimate_tokens(content)
        
        # Use model from default_request_params if not provided
        if not model and hasattr(self, 'default_request_params') and self.default_request_params:
            model = self.default_request_params.model
        
        # Determine minimum tokens based on model
        if model and 'haiku' in model.lower():
            min_tokens = 2048  # Haiku models require 2048 tokens minimum
        else:
            min_tokens = 1024  # Other models require 1024 tokens minimum
            
        return estimated_tokens >= min_tokens
    
    def _should_cache_content(self, content: str, role: str) -> bool:
        """
        Determine if content should be cached based on size and content type.
        
        Args:
            content: The content to potentially cache
            role: The role of the message (system, user, assistant)
            
        Returns:
            bool: Whether this content should be cached
        """
        # Only cache if caching is enabled
        if not self._enable_prompt_caching:
            return False
        
        # Check minimum token requirements first
        if not self._meets_minimum_cache_requirements(content):
            return False
        
        # Cache large system prompts and agent instructions
        if role == "system" and len(content) > 1000:
            return True
        
        # Enhanced workflow context detection for user messages
        if role == "user" and len(content) > 2000:
            # Original orchestrator workflow keywords
            orchestrator_keywords = [
                "results so far", "progress so far", "workflow", "plan objective",
                "steps completed", "context:", "sources:"
            ]
            
            # Additional context patterns
            context_patterns = [
                "previous analysis", "background:", "history:", "summary:",
                "prior work", "earlier findings", "completed tasks",
                "available information", "research findings", "data gathered",
                "analysis results", "current state", "status update"
            ]
            
            # Agent coordination patterns  
            coordination_keywords = [
                "agent_name", "tool_call", "calling tool", "task:", "subtask:",
                "step:", "result:", "output:", "finding:", "conclusion:"
            ]
            
            all_keywords = orchestrator_keywords + context_patterns + coordination_keywords
            content_lower = content.lower()
            
            # Check for keyword presence
            keyword_matches = sum(1 for keyword in all_keywords if keyword in content_lower)
            
            # Cache if multiple keywords found (indicates structured workflow content)
            if keyword_matches >= 2:
                return True
                
            # Cache if content has structured patterns (multiple colons, brackets, etc.)
            structural_indicators = content.count(':') + content.count('[') + content.count('Step ')
            if structural_indicators > 5:
                return True
                
            # Cache if content contains repeated agent/tool patterns
            if any(pattern in content for pattern in ['[Calling tool', 'Tool Result:', 'Agent:', '##']):
                return True
            
        return False
    
    def _get_cache_control_type(self, content: str, role: str) -> dict:
        """
        Determine the appropriate cache control type based on content characteristics.
        
        Args:
            content: The content being cached
            role: The role of the message
            
        Returns:
            dict: Cache control configuration
        """
        # Use 1-hour cache for static content and long-running workflows
        if self._use_long_cache_for_workflows:
            # Tools should always use 1-hour cache since they rarely change
            if role == "tools":
                self.logger.debug(f"[Cache Strategy] Tools content → 1-hour cache (static)")
                return {"type": "ephemeral", "ttl": "1h"}
            
            # System instructions should use 1-hour cache since they're static
            if role == "system":
                self.logger.debug(f"[Cache Strategy] System instructions → 1-hour cache (static)")
                return {"type": "ephemeral", "ttl": "1h"}
            
            # Conversation history should use 1-hour cache for long workflows
            if role == "conversation_history":
                self.logger.debug(f"[Cache Strategy] Conversation history → 1-hour cache (long workflow)")
                return {"type": "ephemeral", "ttl": "1h"}
            
            # Check if this looks like workflow or coordination content
            workflow_indicators = [
                "results so far", "progress so far", "workflow", "agent_name",
                "tool_call", "previous analysis", "background:", "history:"
            ]
            
            if role in ["user", "assistant"] and any(indicator in content.lower() for indicator in workflow_indicators):
                self.logger.debug(f"[Cache Strategy] Workflow content ({role}) → 1-hour cache (workflow patterns detected)")
                return {"type": "ephemeral", "ttl": "1h"}  # 1-hour cache for workflows
        
        # Default to 5-minute cache
        self.logger.debug(f"[Cache Strategy] Regular content ({role}) → 5-minute cache (default)")
        return {"type": "ephemeral"}
    
    def _add_cache_control_to_messages(self, messages: List[MessageParam]) -> List[MessageParam]:
        """
        Add cache_control to appropriate messages to enable prompt caching.
        
        Args:
            messages: List of messages to process
            
        Returns:
            List of messages with cache_control added where appropriate
        """
        if not self._enable_prompt_caching:
            return messages
        
        # FIXED: Create deep copies to avoid mutating original messages during retries
        import copy
        cached_messages = copy.deepcopy(messages)
        cache_breakpoints_used = 0
        max_cache_breakpoints = 4  # Anthropic allows up to 4 cache breakpoints
        
        # --- ADDED: Multi-turn conversation caching logic ---
        # Cache conversation history if we have multiple turns (more than 3 messages)
        conversation_cache_applied = False
        if len(cached_messages) >= 3:
            # Find a good breakpoint in the conversation history
            # Cache everything except the last 1-2 messages to allow for new conversation flow
            conversation_cache_index = len(cached_messages) - 2  # Cache all but the last message
            
            # Only cache if the conversation history is substantial
            total_conversation_length = 0
            for msg in cached_messages[:conversation_cache_index]:
                content = msg.get("content", "")
                if isinstance(content, str):
                    total_conversation_length += len(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            total_conversation_length += len(block.get("text", ""))
            
            # Apply conversation caching if the history is substantial (> 2000 chars)
            if total_conversation_length > 2000 and conversation_cache_index > 0 and cache_breakpoints_used < max_cache_breakpoints:
                # FIXED: Work with the deep copy, check if cache control already exists
                cache_msg = cached_messages[conversation_cache_index]
                
                # Check if cache control was already applied (prevent double application)
                already_has_cache = False
                content = cache_msg.get("content", "")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("cache_control"):
                            already_has_cache = True
                            break
                
                if not already_has_cache:
                    # Handle different content formats
                    if isinstance(content, str):
                        # Convert string to list format with cache control
                        cache_msg["content"] = [
                            {
                                "type": "text",
                                "text": content,
                                "cache_control": self._get_cache_control_type(content, "conversation_history")
                            }
                        ]
                    elif isinstance(content, list) and content:
                        # Add cache control to the last text block in the message
                        for i in range(len(content) - 1, -1, -1):
                            if isinstance(content[i], dict) and content[i].get("type") == "text":
                                content[i]["cache_control"] = self._get_cache_control_type(content[i].get("text", ""), "conversation_history")
                                break
                    
                    cache_breakpoints_used += 1
                    conversation_cache_applied = True
                    self.logger.info(f"[FixedAnthropicAugmentedLLM] Added conversation history cache breakpoint at message {conversation_cache_index} (total history: {total_conversation_length} chars)")
        # --- END ADDED ---
        
        for i, msg in enumerate(cached_messages):
            # Skip if this message already has conversation caching applied
            if conversation_cache_applied and i == len(cached_messages) - 2:
                continue  # Already processed above
            
            # Handle different content types
            content = msg.get("content", "")
            role = msg.get("role", "")
            
            # FIXED: Check if cache control was already applied to prevent double application
            already_has_cache = False
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("cache_control"):
                        already_has_cache = True
                        break
            
            if already_has_cache:
                continue  # Skip this message, already has cache control
            
            should_cache = False
            
            if isinstance(content, str):
                should_cache = self._should_cache_content(content, role)
                
                if should_cache and cache_breakpoints_used < max_cache_breakpoints:
                    # For string content, we need to convert to the new format
                    msg["content"] = [
                        {
                            "type": "text",
                            "text": content,
                            "cache_control": self._get_cache_control_type(content, role)
                        }
                    ]
                    cache_breakpoints_used += 1
                    self.logger.info(f"[FixedAnthropicAugmentedLLM] Added cache control to {role} message (breakpoint {cache_breakpoints_used})")
                    
            elif isinstance(content, list):
                # Handle list content (multiple content blocks)
                for j, content_block in enumerate(content):
                    if isinstance(content_block, dict) and content_block.get("type") == "text":
                        text_content = content_block.get("text", "")
                        if self._should_cache_content(text_content, role) and cache_breakpoints_used < max_cache_breakpoints:
                            # Add cache control to the last large text block in this message
                            if j == len(content) - 1 or not any(
                                isinstance(block, dict) and block.get("type") == "text" and 
                                self._should_cache_content(block.get("text", ""), role) 
                                for block in content[j+1:]
                            ):
                                content_block["cache_control"] = self._get_cache_control_type(content_block.get("text", ""), role)
                                cache_breakpoints_used += 1
                                self.logger.info(f"[FixedAnthropicAugmentedLLM] Added cache control to {role} message content block (breakpoint {cache_breakpoints_used})")
                                break
        
        return cached_messages
    
    def _extract_workflow_context(self, messages: List[MessageParam]) -> tuple[List[MessageParam], Optional[str]]:
        """
        Extract workflow context that can be cached separately.
        
        Args:
            messages: Original messages
            
        Returns:
            Tuple of (messages without workflow context, extracted workflow context)
        """
        if not self._cache_workflow_context:
            return messages, None
        
        workflow_context = None
        filtered_messages = []
        
        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "")
            
            # Look for workflow context in user messages
            if (role == "user" and isinstance(content, str) and 
                "Results so far that may provide helpful context:" in content):
                
                # Split the message to separate workflow context from the actual query
                parts = content.split("Results so far that may provide helpful context:")
                if len(parts) == 2:
                    actual_query = parts[0].strip()
                    workflow_context = "Results so far that may provide helpful context:" + parts[1]
                    
                    # FIXED: Only create filtered message if actual_query is not empty
                    if actual_query:  # Prevent empty content messages
                        filtered_msg = dict(msg)
                        filtered_msg["content"] = actual_query
                        filtered_messages.append(filtered_msg)
                    else:
                        # If the actual query is empty, just use the original message
                        self.logger.warning(f"[FixedAnthropicAugmentedLLM] Workflow context extraction would create empty message, using original")
                        filtered_messages.append(msg)
                        workflow_context = None  # Don't extract empty context
                else:
                    filtered_messages.append(msg)
            else:
                filtered_messages.append(msg)
        
        return filtered_messages, workflow_context
    
    async def generate(
        self,
        message,
        request_params: RequestParams | None = None,
    ):
        # --- THIS IS A COPY OF THE ORIGINAL generate METHOD WITH CACHING AND FIX APPLIED ---
        """
        Process a query using an LLM and available tools with prompt caching support.
        """
        # --- ADDED: Check circuit breaker before proceeding ---
        if _overload_circuit_breaker.is_overloaded():
            self.logger.error("[FixedAnthropicAugmentedLLM.generate] Circuit breaker is tripped - service overloaded. Aborting LLM call.")
            raise Exception("Service is currently overloaded (circuit breaker tripped). Please try again later.")
        # --- END ADDED ---
        
        # --- ADDED LOGGING ---
        self.logger.info(f"[FixedAnthropicAugmentedLLM.generate] Received message type: {type(message)}")
        self.logger.info(f"[FixedAnthropicAugmentedLLM.generate] Received message content (first 500 chars): {str(message)[:500]}")
        # --- END ADDED LOGGING ---
        
        # Safely access API key from config, allow fallback to environment variable
        anthropic_api_key_from_config = None
        if self.context and self.context.config and hasattr(self.context.config, 'anthropic') and self.context.config.anthropic and hasattr(self.context.config.anthropic, 'api_key'):
            anthropic_api_key_from_config = self.context.config.anthropic.api_key
            if anthropic_api_key_from_config:
                self.logger.info("[FixedAnthropicAugmentedLLM.generate] Using Anthropic API key from MCPAppConfig.")
            else:
                self.logger.info("[FixedAnthropicAugmentedLLM.generate] MCPAppConfig.anthropic.api_key is present but empty/None. Anthropic client will try env var.")
        else:
            self.logger.info("[FixedAnthropicAugmentedLLM.generate] Anthropic API key not found in MCPAppConfig (self.context.config.anthropic.api_key). Anthropic client will try environment variable.")

        anthropic_client = Anthropic(api_key=anthropic_api_key_from_config)
        
        messages: List[MessageParam] = []
        params = self.get_request_params(request_params)

        if params.use_history:
            self.logger.info(f"[FixedAnthropicAugmentedLLM.generate] use_history is TRUE. Extending messages with history.")
            # --- FIXED: Safe history access ---
            if hasattr(self, 'history') and self.history:
                messages.extend(self.history.get())
            else:
                self.logger.warning("[FixedAnthropicAugmentedLLM.generate] History not available, continuing without history")
            # --- END FIXED ---
        else:
            self.logger.info(f"[FixedAnthropicAugmentedLLM.generate] use_history is FALSE. Not using history.")

        if isinstance(message, str):
            # FIXED: Only add message if content is not empty
            if message.strip():  # Prevent empty string messages
                messages.append({"role": "user", "content": message})
            else:
                self.logger.warning("[FixedAnthropicAugmentedLLM.generate] Received empty string message, skipping")
        elif isinstance(message, list):
            # FIXED: Filter out empty messages from list
            for msg in message:
                if isinstance(msg, dict):
                    content = msg.get("content", "")
                    if isinstance(content, str) and content.strip() == "":
                        self.logger.warning(f"[FixedAnthropicAugmentedLLM.generate] Skipping empty message from list: Role='{msg.get('role')}'")
                        continue
                    elif isinstance(content, list) and not content:
                        self.logger.warning(f"[FixedAnthropicAugmentedLLM.generate] Skipping message with empty content list: Role='{msg.get('role')}'")
                        continue
                messages.append(msg)
        else:
            # FIXED: Validate single message object
            if isinstance(message, dict):
                content = message.get("content", "")
                if isinstance(content, str) and content.strip() == "":
                    self.logger.warning(f"[FixedAnthropicAugmentedLLM.generate] Received empty single message: Role='{message.get('role')}', creating fallback")
                    messages.append({"role": "user", "content": "Hello"})  # Fallback
                elif isinstance(content, list) and not content:
                    self.logger.warning(f"[FixedAnthropicAugmentedLLM.generate] Received message with empty content list: Role='{message.get('role')}', creating fallback")
                    messages.append({"role": "user", "content": "Hello"})  # Fallback
                else:
                    messages.append(message)
            else:
                messages.append(message)

        # --- MODIFIED: Effectively disable _extract_workflow_context logic ---
        if False and self._cache_workflow_context: # Added 'False and' to disable this block
            self.logger.debug("[FixedAnthropicAugmentedLLM.generate] _cache_workflow_context is TRUE but bypassed. Attempting to extract.")
            original_messages_count = len(messages)
            messages, workflow_context = self._extract_workflow_context(messages)
            if workflow_context:
                # Add workflow context as a separate cached message
                workflow_msg = {
                    "role": "user", 
                    "content": [
                        {
                            "type": "text",
                            "text": workflow_context,
                            "cache_control": self._get_cache_control_type(workflow_context, "user") # Uses its own caching logic
                        }
                    ]
                }
                # Insert workflow context before the last user message or at the end if only one message
                if messages: # Ensure messages list is not empty
                    # Try to insert before the last actual user message, assuming it's the current task.
                    # If the list was manipulated to only have context, this might need adjustment.
                    # For now, let's assume there's at least one message that isn't the context itself.
                    insert_index = -1 
                    if len(messages) == 1 and messages[0].get("role") == "user" and messages[0].get("content")[0].get("text") == workflow_context:
                        # This case implies _extract_workflow_context returned only the context, which shouldn't happen if it also returns messages.
                        # However, if it did, and `messages` was just the workflow_context itself, we might append or prepend.
                        # Based on `messages, workflow_context = self._extract_workflow_context(messages)`, 
                        # `messages` should be the original messages *minus* the extracted context.
                        # So, if messages is not empty, we can likely insert at -1 (before the last item, which should be the current query)
                        # or at len(messages) -1.
                        # To be safe, if messages has content, insert before the last element.
                        # If messages became empty after extraction (unlikely), this logic would need review.
                        pass # Let it be appended by messages.insert if list was [context_msg] -> [] -> [new_workflow_msg]
                    
                    # Check if messages still has the main query.
                    # If messages is empty or the last message IS the workflow_context (meaning it was the only thing),
                    # then just append the workflow_msg. This scenario is less likely given the _extract logic.
                    if not messages or (messages[-1].get("role") == "user" and messages[-1].get("content")[0].get("text") == workflow_context):
                        messages.append(workflow_msg)
                        self.logger.debug("[FixedAnthropicAugmentedLLM.generate] Appended workflow context as no suitable prior message.")
                    else:
                        # Default: insert before the last message, assuming last message is the current user query.
                        messages.insert(len(messages) -1 if len(messages) > 0 else 0, workflow_msg)
                        self.logger.debug(f"[FixedAnthropicAugmentedLLM.generate] Inserted workflow context at index {len(messages) -2 if len(messages) > 1 else 0}.")

                    self.logger.info(f"[FixedAnthropicAugmentedLLM.generate] Extracted and cached workflow context separately. Messages count before: {original_messages_count}, after: {len(messages)}")
                else: # workflow_context was None or empty
                    self.logger.debug("[FixedAnthropicAugmentedLLM.generate] No workflow context extracted or it was empty.")
        else: # self._cache_workflow_context is False (or block is bypassed)
           self.logger.debug("[FixedAnthropicAugmentedLLM.generate] _cache_workflow_context is FALSE or bypassed. Skipping extraction.")
        # --- END MODIFIED ---

        # --- FIXED: Safe aggregator access ---
        if hasattr(self, 'aggregator') and self.aggregator:
            list_tools_response = await self.aggregator.list_tools()
        else:
            self.logger.warning("[FixedAnthropicAugmentedLLM.generate] Aggregator not available, continuing without tools")
            list_tools_response = None
        # --- END FIXED ---
        
        available_tools_raw: List[ToolParam] = [] # Ensure this variable holds the raw tools
        if list_tools_response and list_tools_response.tools:
            available_tools_raw = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema,
            }
            for tool in list_tools_response.tools
        ]

        # --- BEGIN CRITICAL PREPARATION LOGIC ---
        # Prepare tools for the API call, considering caching
        final_tools_for_api = []
        if available_tools_raw:
            # self.logger.info(f"[FixedAnthropicAugmentedLLM.generate] {len(available_tools_raw)} tools available.") # Simplified logging
            if self.cache_tools and self._enable_prompt_caching:
                # self.logger.info("[FixedAnthropicAugmentedLLM.generate] Attempting to cache tools.") # Simplified logging
                final_tools_for_api = self._add_cache_control_to_tools(list(available_tools_raw))
            else:
                # self.logger.info("[FixedAnthropicAugmentedLLM.generate] Not caching tools. Using raw tool definitions.") # Simplified logging
                final_tools_for_api = available_tools_raw
        # else:
            # self.logger.info("[FixedAnthropicAugmentedLLM.generate] No available tools.") # Simplified logging

        # Prepare system prompt for the API call, considering caching
        # system_prompt_content is assumed to be defined earlier (from params.pop or self.instruction)
        # --- FIXED: Safe instruction access ---
        system_prompt_content = None
        if hasattr(params, 'instruction') and params.instruction is not None:
            system_prompt_content = params.instruction
        elif hasattr(self, 'instruction') and self.instruction:
            system_prompt_content = self.instruction
        else:
            self.logger.warning("[FixedAnthropicAugmentedLLM.generate] No instruction available, continuing without system prompt")
        # --- END FIXED ---
        final_system_prompt_for_api = None
        if system_prompt_content:
            # self.logger.info(f"[FixedAnthropicAugmentedLLM.generate] System prompt content provided.") # Simplified logging
            if self.cache_system_prompt and self._enable_prompt_caching:
                # self.logger.info("[FixedAnthropicAugmentedLLM.generate] Attempting to cache system prompt.") # Simplified logging
                system_prompt_as_list = [{"type": "text", "text": system_prompt_content}] if isinstance(system_prompt_content, str) else list(system_prompt_content or [])
                if system_prompt_as_list: # Only call if there's content
                    final_system_prompt_for_api = self._add_cache_control_to_system_prompt(system_prompt_as_list)
                else:
                    final_system_prompt_for_api = None # Or pass original empty if that's preferred by API
            else:
                # self.logger.info("[FixedAnthropicAugmentedLLM.generate] Not caching system prompt.") # Simplified logging
                final_system_prompt_for_api = system_prompt_content
        # else:
            # self.logger.info("[FixedAnthropicAugmentedLLM.generate] No system prompt content provided.") # Simplified logging
        # --- END CRITICAL PREPARATION LOGIC ---

        responses: List[Message] = []
        model = await self.select_model(params)
        previous_llm_response = None

        # --- ADDED: Apply prompt caching to messages ---
        # This was missing and causing the NameError
        cached_messages = self._add_cache_control_to_messages(list(messages))
        # --- END ADDED ---

        for i in range(params.max_iterations):
            # --- UPDATE cached_messages if messages were modified ---
            # This ensures cached_messages is always in sync with the current state of messages
            cached_messages = self._add_cache_control_to_messages(list(messages))
            # --- END UPDATE ---
            
            # --- FIX APPLIED HERE --- 
            if i == params.max_iterations - 1 and previous_llm_response and previous_llm_response.stop_reason == "tool_use":
                final_prompt_message = MessageParam(
                    role="user",
                    content="""We've reached the maximum number of iterations. 
                    Please stop using tools now and provide your final comprehensive answer based on all tool results so far. 
                    At the beginning of your response, clearly indicate that your answer may be incomplete due to reaching the maximum number of tool usage iterations, 
                    and explain what additional information you would have needed to provide a more complete answer.""",
                )
                messages.append(final_prompt_message)

            # --- ADDED: Apply prompt caching to messages ---
            # Ensure variable processed_messages is used if it holds results of _add_cache_control_to_messages
            # Assuming processed_messages = self._add_cache_control_to_messages(list(messages)) was done earlier
            # For this edit, let's assume `messages` has already been processed for caching if needed,
            # or that `cached_messages` is the correct variable name from previous context.
            # The most important part is `system` and `tools`.
            
            # The variable `cached_messages` is used below, which should be the output of `_add_cache_control_to_messages`
            # Let's assume `processed_messages` from my prior (unapplied) edit suggestions is equivalent to `cached_messages` used here in existing code.
            # If not, this should be `messages=processed_messages` if `processed_messages` is the correctly cached version.
            # For now, I will stick to modifying only system and tools based on the provided context.
            
            arguments = {
                "model": model,
                "max_tokens": params.maxTokens,
                "messages": cached_messages,  # Assuming cached_messages is correctly prepared with message caching
                "system": final_system_prompt_for_api, # MODIFIED: Use the prepared system prompt
                "stop_sequences": params.stopSequences,
                "tools": final_tools_for_api,  # MODIFIED: Use the prepared tools (already changed in previous successful edit)
            }

            # --- ADDED: Cache system prompt if it's large ---
            # This block seems redundant if final_system_prompt_for_api is already prepared with caching.
            # I will comment it out to avoid conflicts with the new preparation logic.
            # if self._enable_prompt_caching and arguments["system"] and self._meets_minimum_cache_requirements(str(arguments["system"])): 
            #     # Convert system to list format with cache control
            #     if isinstance(arguments["system"], str):
            #         arguments["system"] = [
            #             {
            #                 "type": "text",
            #                 "text": arguments["system"],
            #                 "cache_control": self._get_cache_control_type(arguments["system"], "system")
            #             }
            #         ]
            #     self.logger.info("[FixedAnthropicAugmentedLLM.generate] Added cache control to system prompt")
            # --- END COMMENTED OUT BLOCK ---

            if params.metadata:
                arguments = {**arguments, **params.metadata}

            # --- ADDED: Check if we need extended cache TTL header ---
            extra_headers = {}
            if self._use_long_cache_for_workflows and self._has_extended_cache_content(cached_messages, arguments.get("system"), final_tools_for_api):
                extra_headers["anthropic-beta"] = "extended-cache-ttl-2025-04-11"
                self.logger.info("[FixedAnthropicAugmentedLLM.generate] Added extended cache TTL beta header")
            # --- END ADDED ---
            
            # Log cache strategy
            cache_count = 0
            extended_cache_count = 0
            tools_cached = False
            system_cached = False
            
            # Check tools caching
            if final_tools_for_api:
                for tool in final_tools_for_api:
                    if isinstance(tool, dict) and tool.get("cache_control"):
                        tools_cached = True
                        cache_count += 1
                        if tool.get("cache_control", {}).get("ttl") == "1h":
                            extended_cache_count += 1
            
            # Check system caching  
            if arguments.get("system"):
                system_content = arguments["system"]
                if isinstance(system_content, list):
                    for block in system_content:
                        if isinstance(block, dict) and block.get("cache_control"):
                            system_cached = True
                            cache_count += 1
                            if block.get("cache_control", {}).get("ttl") == "1h":
                                extended_cache_count += 1
            
            # Check messages caching
            for msg in cached_messages:
                content = msg.get("content", "")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("cache_control"):
                            cache_count += 1
                            if block.get("cache_control", {}).get("ttl") == "1h":
                                extended_cache_count += 1
            
            self.logger.info(f"[FixedAnthropicAugmentedLLM.generate] Cache Strategy Applied - Tools: {tools_cached}, System: {system_cached}, Total Blocks: {cache_count} ({extended_cache_count} with 1h TTL)")
            # --- END ADDED ---

            self.logger.debug(f"{arguments}")
            # --- ADDED LOGGING ---
            self.logger.info(f"[FixedAnthropicAugmentedLLM.generate] Messages before API call (length {len(cached_messages)}):")
            for idx, msg in enumerate(cached_messages):
                self.logger.info(f"[FixedAnthropicAugmentedLLM.generate] Message [{idx}]: Role='{msg.get('role')}', Content (first 200 chars of str, or type if not str): {str(msg.get('content'))[:200] if isinstance(msg.get('content'), str) else type(msg.get('content'))}")
                if isinstance(msg.get('content'), list):
                    for j, content_item in enumerate(msg.get('content')):
                        cache_info = " [CACHED]" if content_item.get("cache_control") else ""
                        self.logger.info(f"[FixedAnthropicAugmentedLLM.generate]   Content item [{j}]: Type='{content_item.get('type') if isinstance(content_item, dict) else type(content_item)}', Text (first 100 chars): {str(content_item.get('text') if isinstance(content_item, dict) else content_item)[:100]}{cache_info}")
            # --- END ADDED LOGGING ---
            self._log_chat_progress(chat_turn=(len(cached_messages) + 1) // 2, model=model)

            # --- ADDED: Filter out messages with empty content before API call ---
            final_messages_for_api = []
            for m in cached_messages:
                content = m.get("content")
                is_empty_content = False
                
                # Check for None or completely missing content
                if content is None:
                    is_empty_content = True
                    self.logger.debug(f"[FixedAnthropicAugmentedLLM.generate] Message has None content: Role='{m.get('role')}'")
                elif isinstance(content, str):
                    if content.strip() == "":
                        is_empty_content = True
                        self.logger.debug(f"[FixedAnthropicAugmentedLLM.generate] Message has empty string content: Role='{m.get('role')}'")
                elif isinstance(content, list):
                    if not content:
                        is_empty_content = True
                        self.logger.debug(f"[FixedAnthropicAugmentedLLM.generate] Message has empty list content: Role='{m.get('role')}'")
                    else:
                        non_empty_part_exists = False
                        for part in content:
                            if isinstance(part, dict):
                                part_type = part.get("type", "")
                                if part_type == "text":
                                    text_content = part.get("text", "")
                                    if isinstance(text_content, str) and text_content.strip() != "":
                                        non_empty_part_exists = True
                                        break
                                elif part_type in ["image", "tool_use", "tool_result"]:
                                    # Non-text content types are considered non-empty
                                    non_empty_part_exists = True
                                    break
                                else:
                                    # Unknown content type, treat as potentially valid
                                    self.logger.debug(f"[FixedAnthropicAugmentedLLM.generate] Unknown content block type: {part_type}")
                                    non_empty_part_exists = True
                                    break
                            elif isinstance(part, str) and part.strip() != "":
                                non_empty_part_exists = True 
                                break 
                        if not non_empty_part_exists:
                            is_empty_content = True
                            self.logger.debug(f"[FixedAnthropicAugmentedLLM.generate] Message list content has no non-empty parts: Role='{m.get('role')}'")
                else:
                    # Unknown content type, log but allow it through
                    self.logger.debug(f"[FixedAnthropicAugmentedLLM.generate] Unknown content type {type(content)}: Role='{m.get('role')}'")
                
                if is_empty_content:
                    self.logger.warning(f"[FixedAnthropicAugmentedLLM.generate] Filtering out message due to empty/whitespace content: Role='{m.get('role')}', OriginalContent='{str(content)[:100]}...'")
                else:
                    final_messages_for_api.append(m)

            if not final_messages_for_api:
                self.logger.error(f"[FixedAnthropicAugmentedLLM.generate] No valid messages to send after filtering for empty content. Original message count: {len(cached_messages)}")
                # Instead of raising an error, create a minimal valid message
                self.logger.info("[FixedAnthropicAugmentedLLM.generate] Creating minimal fallback message to prevent API error")
                final_messages_for_api = [{"role": "user", "content": "Hello"}]
            
            arguments["messages"] = final_messages_for_api
            # --- END ADDED FILTER ---

            # --- FIXED: Safe executor access with 529 error handling ---
            if hasattr(self, 'executor') and self.executor:
                try:
                    executor_result = await self.executor.execute(
                        anthropic_client.messages.create, 
                        **arguments,
                        extra_headers=extra_headers if extra_headers else None
                    )
                except Exception as e:
                    # Check if this is an OverloadedError (529 error) from Anthropic
                    if "OverloadedError" in str(type(e)) or "OverloadedError" in str(e) or "529" in str(e) or "overloaded" in str(e).lower():
                        self.logger.error(f"[FixedAnthropicAugmentedLLM.generate] Anthropic API is overloaded (529 error). Tripping circuit breaker. Error: {e}")
                        _overload_circuit_breaker.trip(f"529 error in FixedAnthropicAugmentedLLM: {str(e)}")
                        raise Exception(f"Service is currently overloaded. Please try again later. Original error: {str(e)}")
                    else:
                        # Re-raise other exceptions
                        raise
            else:
                self.logger.error("[FixedAnthropicAugmentedLLM.generate] Executor not available, cannot proceed with API call")
                raise AttributeError("Executor not available for LLM execution")
            # --- END FIXED ---

            llm_response = executor_result[0]

            if isinstance(llm_response, BaseException):
                # Check if this BaseException is a 529 error
                if "OverloadedError" in str(type(llm_response)) or "OverloadedError" in str(llm_response) or "529" in str(llm_response) or "overloaded" in str(llm_response).lower():
                    self.logger.error(f"[FixedAnthropicAugmentedLLM.generate] Anthropic API is overloaded (529 error in response). Tripping circuit breaker. Error: {llm_response}")
                    _overload_circuit_breaker.trip(f"529 error in FixedAnthropicAugmentedLLM response: {str(llm_response)}")
                    raise Exception(f"Service is currently overloaded. Please try again later. Original error: {str(llm_response)}")
                self.logger.error(f"Error: {executor_result}")
                previous_llm_response = None
                break

            # --- ADDED: Log cache performance ---
            if hasattr(llm_response, 'usage'):
                usage = llm_response.usage
                cache_creation = getattr(usage, 'cache_creation_input_tokens', 0)
                cache_read = getattr(usage, 'cache_read_input_tokens', 0)
                input_tokens = getattr(usage, 'input_tokens', 0)
                
                if cache_creation > 0 or cache_read > 0:
                    self.logger.info(f"[FixedAnthropicAugmentedLLM.generate] Cache Performance - Created: {cache_creation} tokens, Read: {cache_read} tokens, New Input: {input_tokens} tokens")
                    cache_hit_ratio = cache_read / (cache_read + input_tokens + cache_creation) if (cache_read + input_tokens + cache_creation) > 0 else 0
                    self.logger.info(f"[FixedAnthropicAugmentedLLM.generate] Cache hit ratio: {cache_hit_ratio:.2%}")
            # --- END ADDED ---

            self.logger.debug(f"{model} response:", data=llm_response)

            response_as_message = self.convert_message_to_message_param(llm_response)
            messages.append(response_as_message)
            responses.append(llm_response)

            previous_llm_response = llm_response

            if llm_response.stop_reason == "end_turn":
                self.logger.debug(f"Iteration {i}: Stopping because finish_reason is 'end_turn'")
                break
            elif llm_response.stop_reason == "stop_sequence":
                self.logger.debug(f"Iteration {i}: Stopping because finish_reason is 'stop_sequence'")
                break
            elif llm_response.stop_reason == "max_tokens":
                self.logger.debug(f"Iteration {i}: Stopping because finish_reason is 'max_tokens'")
                break
            else:  # llm_response.stop_reason == "tool_use":
                for content in llm_response.content:
                    if content.type == "tool_use":
                        tool_name = content.name
                        tool_args = content.input
                        tool_use_id = content.id

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
            # --- FIXED: Safe history access for setting ---
            if hasattr(self, 'history') and self.history:
                self.history.set(messages)
            else:
                self.logger.warning("[FixedAnthropicAugmentedLLM.generate] History not available for setting, skipping history update")
            # --- END FIXED ---

        self._log_chat_finished(model=model)

        return responses
    # --- END ADDED ---

    def _has_extended_cache_content(self, messages: List[MessageParam], system_content: Any = None, tools: List[ToolParam] = None) -> bool:
        """
        Check if any cached content is using extended TTL (1-hour cache).
        
        Args:
            messages: List of messages to check
            system_content: System content to check
            tools: List of tools to check
            
        Returns:
            bool: True if any content uses extended cache TTL
        """
        # Check tools
        if tools:
            for tool in tools:
                if isinstance(tool, dict) and tool.get("cache_control", {}).get("ttl") == "1h":
                    return True
        
        # Check system content
        if system_content:
            if isinstance(system_content, list):
                for block in system_content:
                    if isinstance(block, dict) and block.get("cache_control", {}).get("ttl") == "1h":
                        return True
            elif isinstance(system_content, str):
                # If system is still a string, check if it would get 1h cache
                cache_control = self._get_cache_control_type(system_content, "system")
                if cache_control.get("ttl") == "1h":
                    return True
        
        # Check messages
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("cache_control", {}).get("ttl") == "1h":
                        return True
        
        return False

    def _add_cache_control_to_tools(self, tools: List[ToolParam]) -> List[ToolParam]:
        """
        Add cache_control to tool definitions following Anthropic's best practices.
        
        Cache breakpoint 1: Tools cache - caches all tool definitions by marking the last tool.
        
        Args:
            tools: List of tool definitions
            
        Returns:
            List of tools with cache_control added to the last tool (if appropriate)
        """
        if not self._enable_prompt_caching or not tools:
            return tools
        
        # Calculate total size of all tool definitions to check if worth caching
        total_tool_content = ""
        for tool in tools:
            # Rough estimation of tool definition size
            tool_content = str(tool.get("description", "")) + str(tool.get("input_schema", ""))
            total_tool_content += tool_content
        
        # Only cache if tools meet minimum requirements
        if not self._meets_minimum_cache_requirements(total_tool_content):
            return tools
        
        # FIXED: Create deep copy of tools to avoid mutating original during retries
        import copy
        cached_tools = copy.deepcopy(tools)
        
        if cached_tools:
            # Check if the last tool already has cache control (prevent double application)
            last_tool = cached_tools[-1]
            if isinstance(last_tool, dict) and last_tool.get("cache_control"):
                self.logger.debug("[FixedAnthropicAugmentedLLM] Tools already have cache control, skipping")
                return cached_tools
            
            # Add cache control to the last tool
            if isinstance(last_tool, dict):
                last_tool["cache_control"] = self._get_cache_control_type(total_tool_content, "tools")
            else:
                # Convert to dict and add cache control
                last_tool_dict = dict(last_tool)
                last_tool_dict["cache_control"] = self._get_cache_control_type(total_tool_content, "tools")
                cached_tools[-1] = last_tool_dict
            
            self.logger.info(f"[FixedAnthropicAugmentedLLM] Added cache control to tools (caching {len(tools)} tool definitions)")
        
        return cached_tools

    def _add_cache_control_to_system_prompt(self, system_content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Add cache_control to system prompt content following Anthropic's best practices.
        
        Args:
            system_content: List of system content blocks (already in list format)
            
        Returns:
            List of system content blocks with cache_control added to the last block (if appropriate)
        """
        if not self._enable_prompt_caching or not system_content:
            return system_content
        
        # Calculate total size of all system content to check if worth caching
        total_system_content = ""
        for block in system_content:
            if isinstance(block, dict) and block.get("type") == "text":
                total_system_content += block.get("text", "")
        
        # Only cache if system content meets minimum requirements
        if not self._meets_minimum_cache_requirements(total_system_content):
            return system_content
        
        # FIXED: Create deep copy of system content to avoid mutating original during retries
        import copy
        cached_system_content = copy.deepcopy(system_content)
        
        if cached_system_content:
            # Check if the last block already has cache control (prevent double application)
            last_block = cached_system_content[-1]
            if isinstance(last_block, dict) and last_block.get("cache_control"):
                self.logger.debug("[FixedAnthropicAugmentedLLM] System prompt already has cache control, skipping")
                return cached_system_content
            
            # Add cache control to the last text block
            if isinstance(last_block, dict) and last_block.get("type") == "text":
                last_block["cache_control"] = self._get_cache_control_type(total_system_content, "system")
                self.logger.info(f"[FixedAnthropicAugmentedLLM] Added cache control to system prompt (caching {len(cached_system_content)} blocks)")
        
        return cached_system_content