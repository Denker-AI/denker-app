"""
Coordinator Workflows - Contains workflow processing logic for the coordinator.

This module implements the router and orchestrator workflow processing functions,
separating them from the main coordinator logic for better code organization.

Agent selection behavior:
- Both the router and orchestrator workflows use the agents specified in request.use_agents
- Orchestrator: If no specified agents are available, falls back to ["finder", "writer"]
- Router: If no specified agents are available, falls back to using all available agents
- Both ensure that all required agents exist before attempting to use them
"""

import logging
import time
import json
from typing import Dict, Any, List, Optional, Callable, Union
from pydantic import BaseModel, Field

from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.orchestrator.orchestrator import Orchestrator
from mcp_agent.workflows.router.router_llm import LLMRouter
from mcp_agent.workflows.router.router_llm_anthropic import AnthropicLLMRouter
from mcp_agent.workflows.llm.augmented_llm_anthropic import AnthropicAugmentedLLM
from mcp_agent.workflows.llm.augmented_llm import RequestParams
from .coordinator_agents_config import DEFAULT_MODEL

logger = logging.getLogger(__name__)

async def create_agent_llm(agent: Agent, create_anthropic_llm_fn: Optional[Callable] = None) -> AnthropicAugmentedLLM:
    """
    Create an LLM for an agent, either using a creation function or creating directly.
    
    Args:
        agent: The agent to create an LLM for
        create_anthropic_llm_fn: Optional function to create an Anthropic LLM
        
    Returns:
        An initialized Anthropic Augmented LLM
    """
    if hasattr(agent, 'augmented_llm') and agent.augmented_llm:
        # Agent already has an LLM
        return agent.augmented_llm
    
    # Use the provided function if available
    if create_anthropic_llm_fn:
        return create_anthropic_llm_fn(agent=agent)
    
    # Create directly if no function provided
    return AnthropicAugmentedLLM(
        agent=agent,
        instruction=agent.instruction
    )

# Request and response models
class AgentRequest(BaseModel):
    """Request model for agent interactions."""
    query: str = Field(..., description="The query to process")
    workflow_type: str = Field("router", description="Type of workflow to use")
    session_id: Optional[str] = Field(None, description="Session ID for tracking")
    use_agents: Optional[List[str]] = Field(None, description="Agents to use")
    processed_message: Optional[Dict[str, Any]] = Field(None, description="Pre-processed message ready for LLM use")
    message_history: Optional[List[Dict[str, Any]]] = Field(None, description="Formatted message history for LLM context")
    file_ids: Optional[List[str]] = Field(None, description="IDs of attached files")

class AgentResponse(BaseModel):
    """Response model from agent processing."""
    session_id: str = Field(..., description="Session ID for tracking")
    result: str = Field(..., description="Result of processing")
    workflow_type: str = Field(..., description="Type of workflow used")
    completion_time: float = Field(..., description="Time to process request")

def extract_query_for_router(processed_message):
    """
    Extract a clean text representation from processed_message for router use.
    Includes text content and mentions of attached images/files.
    
    Args:
        processed_message: The structured message with content blocks
        
    Returns:
        str: A clean text string suitable for routing
    """
    extracted_text = []
    has_image = False
    
    # Process each content block
    for block in processed_message.get('content', []):
        # Extract text blocks
        if block.get('type') == 'text':
            extracted_text.append(block.get('text', ''))
        
        # Note image attachments
        elif block.get('type') == 'image':
            has_image = True
    
    # Add image note once at the end if images are present
    if has_image:
        extracted_text.append("Note: One or more images are attached to this query.")
    
    # Join all text with line breaks
    return "\n".join(extracted_text)

# --- ADDED: Helper function to extract a focused objective for the orchestrator ---
def extract_objective_for_orchestrator(request: AgentRequest, logger: logging.Logger, query_id: str) -> str:
    """
    Extracts a focused objective string for the orchestrator's planner.
    - For new queries, it uses the content of request.processed_message.
    - For clarification responses, it uses the content of the last few history messages.
    - Appends file context information if available.
    """
    objective_parts = []
    source_description = "" # For logging

    if request.processed_message and request.processed_message.get('content'):
        source_description = "current request.processed_message"
        logger.info(f"[{query_id}] Orchestrator Objective: Extracting from new query (processed_message).")
        for block in request.processed_message['content']:
            if block.get('type') == 'text':
                objective_parts.append(block.get('text', ''))
            # Note: We are omitting image block notes for planner_objective for brevity,
            # assuming file context note is sufficient.
    elif request.message_history:
        source_description = "last messages in history (clarification)"
        logger.info(f"[{query_id}] Orchestrator Objective: Extracting from history (clarification response).")
        # For a focused objective, let's try with the last user message,
        # or last 2-3 messages if more context is needed.
        # Let's start with the last message assuming it's the user's clarification.
        # If it's an assistant message, we might need to go back further.
        # A safer bet for clarification might be last 1-3 messages.
        
        history_to_consider = request.message_history[-3:] # Take last 3 for broader context
        
        for msg in history_to_consider:
            content = msg.get('content', '')
            if isinstance(content, str):
                # If content is a simple string
                if msg.get('role') == 'user': # Prioritize user content for objective
                    objective_parts.append(content)
                else: # Include assistant content more sparingly or not at all for objective
                    objective_parts.append(f"(Context from assistant: {content[:100]}...)")

            elif isinstance(content, list):
                # If content is a list of blocks
                for block in content:
                    if block.get('type') == 'text':
                        if msg.get('role') == 'user':
                             objective_parts.append(block.get('text', ''))
                        # Optionally, add assistant's text blocks for context too, but keep it concise
                        # else:
                        #     objective_parts.append(f"(Context from assistant: {block.get('text', '')[:100]}...)")
    else:
        logger.warning(f"[{query_id}] Orchestrator Objective: No processed_message or message_history to extract objective from.")
        return "" # Return empty if no source

    # Combine parts and clean up
    planner_objective_text = "\n".join(filter(None, objective_parts)).strip()
    
    logger.info(f"[{query_id}] Orchestrator Objective: Text extracted from {source_description} (before file context, first 200 chars): '{planner_objective_text[:200]}...'")

    # Append file context information
    if request.file_ids and len(request.file_ids) > 0:
        file_context_note = f"IMPORTANT CONTEXT: This task involves {len(request.file_ids)} file(s). Their IDs are: {', '.join(request.file_ids)}. Ensure the plan utilizes these files appropriately, likely using a 'finder' or similar agent for relevant information."
        if planner_objective_text:
            planner_objective_text += "\n\n" + file_context_note
        else:
            planner_objective_text = file_context_note
        logger.info(f"[{query_id}] Orchestrator Objective: Appended file context note for {len(request.file_ids)} files.")

    if not planner_objective_text:
        logger.error(f"[{query_id}] Orchestrator Objective: Resulting planner_objective_text is empty after extraction from {source_description}.")
        
    return planner_objective_text
# --- END ADDED helper function ---

# --- Coordinator workflow logic is now handled by the local backend (Electron app) ---
# async def process_orchestrator_workflow(...):
#     ... (comment out full function)
# async def process_router_workflow(...):
#     ... (comment out full function)

def process_orchestrator_workflow(*args, **kwargs):
    raise NotImplementedError("process_orchestrator_workflow is now handled by the local backend (Electron app).")
def process_router_workflow(*args, **kwargs):
    raise NotImplementedError("process_router_workflow is now handled by the local backend (Electron app).")

def process_orchestrator_workflow(*args, **kwargs):
    raise NotImplementedError("process_orchestrator_workflow is now handled by the local backend (Electron app).")
def process_router_workflow(*args, **kwargs):
    raise NotImplementedError("process_router_workflow is now handled by the local backend (Electron app).") 