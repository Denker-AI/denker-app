"""
Coordinator Workflows - Contains workflow processing logic for the coordinator.

This module implements the router and orchestrator workflow processing functions,
separating them from the main coordinator logic for better code organization.

Agent selection behavior:
- Both the router and orchestrator workflows use the agents specified in request.use_agents
- Orchestrator: If no specified agents are available, falls back to ["researcher", "creator"]
- Router: If no specified agents are available, falls back to using all available agents
- Both ensure that all required agents exist before attempting to use them
"""

import logging
import time
import json
import re
from typing import Dict, Any, List, Optional, Callable, Union
from pydantic import BaseModel, Field

from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.orchestrator.orchestrator import Orchestrator
from mcp_agent.workflows.router.router_llm import LLMRouter
from .fixed_router_anthropic import FixedAnthropicLLMRouter as AnthropicLLMRouter
from mcp_agent.workflows.llm.augmented_llm_anthropic import AnthropicAugmentedLLM
from mcp_agent.workflows.llm.augmented_llm import RequestParams
from .coordinator_agents_config import DEFAULT_MODEL

logger = logging.getLogger(__name__)

# REMOVED: _clean_agent_result function - not needed as frontend handles tool call separation

# --- ADDED: Import circuit breaker from coordinator_agent ---
def get_circuit_breaker():
    """Get the global circuit breaker instance from coordinator_agent module."""
    try:
        from .coordinator_agent import _overload_circuit_breaker
        return _overload_circuit_breaker
    except ImportError:
        logger.warning("Could not import circuit breaker, overload protection disabled")
        return None

def _extract_final_message_from_router_result(result: str) -> str:
    """
    Extract the final assistant message from a router workflow result.
    Router workflows return the complete conversation including tool calls,
    but we only want to display the final message to the user.
    
    Args:
        result: The complete result string from the router workflow
        
    Returns:
        str: The cleaned final message
    """
    if not result or not isinstance(result, str):
        return result
    
    try:
        # Split the result into lines for processing
        lines = result.split('\n')
        
        # Look for the pattern where tool calls end and the final message begins
        # Tool calls typically follow the pattern: [Calling tool ... with args {...}]
        # We need to handle nested brackets in JSON arguments
        
        final_message_lines = []
        in_final_message = False
        
        # Improved pattern to handle nested brackets in tool calls
        # This pattern matches "[Calling tool" and finds the matching closing bracket
        def is_tool_call_line(line: str) -> bool:
            """Check if a line contains a tool call, handling nested brackets properly."""
            stripped = line.strip()
            if not stripped.startswith('[Calling tool'):
                return False
            
            # Count brackets to find the matching closing bracket
            bracket_count = 0
            in_quotes = False
            escape_next = False
            
            for char in stripped:
                if escape_next:
                    escape_next = False
                    continue
                    
                if char == '\\':
                    escape_next = True
                    continue
                    
                if char == '"' and not escape_next:
                    in_quotes = not in_quotes
                    continue
                    
                if not in_quotes:
                    if char == '[':
                        bracket_count += 1
                    elif char == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            # Found the matching closing bracket
                            return True
            
            return False  # Unmatched brackets or incomplete tool call
        
        # Process lines from the end to find the final assistant message
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            
            # Skip empty lines at the end
            if not line and not in_final_message:
                continue
                
            # If we hit a tool call pattern, we've found where the final message starts
            if is_tool_call_line(line):
                break
                
            # Add this line to the final message (we're going backwards)
            if line:  # Only add non-empty lines
                final_message_lines.insert(0, line)
                in_final_message = True
            elif in_final_message:
                # Add empty lines within the final message
                final_message_lines.insert(0, '')
        
        # If we found final message lines, join them
        if final_message_lines:
            cleaned_result = '\n'.join(final_message_lines).strip()
            logger.info(f"Extracted final message from router result: {len(cleaned_result)} chars vs original {len(result)} chars")
            return cleaned_result
        
        # Fallback: if no tool call pattern found, look for the last substantial text block
        # This handles cases where the format might be different
        substantial_lines = [line for line in lines if line.strip() and not is_tool_call_line(line)]
        
        if substantial_lines:
            # Take the last few substantial lines as the final message
            # Look for a natural break point (empty line) working backwards
            for i in range(len(lines) - 1, -1, -1):
                if not lines[i].strip():  # Empty line might indicate a section break
                    # Check if this empty line separates tool calls from final message
                    lines_after = [l for l in lines[i+1:] if l.strip()]
                    if lines_after and not any(is_tool_call_line(l) for l in lines_after):
                        # Found the start of the final message section
                        final_message_lines = [l for l in lines[i+1:] if l.strip()]
                        if final_message_lines:
                            cleaned_result = '\n'.join(final_message_lines).strip()
                            logger.info(f"Extracted final message using empty line separator: {len(cleaned_result)} chars")
                            return cleaned_result
                        break
        
        # Final fallback: return the last 500 characters if no clear pattern found
        if len(result) > 500:
            logger.warning("Could not identify clear final message pattern, using last 500 characters")
            return "..." + result[-500:].strip()
        
        logger.info("No tool call pattern found, returning original result")
        return result
        
    except Exception as e:
        logger.error(f"Error extracting final message from router result: {e}")
        return result

def test_extract_final_message_function():
    """
    Test the _extract_final_message_from_router_result function with various scenarios
    including nested brackets in tool calls.
    """
    
    # Test case 1: Simple tool call with final message
    test1 = """I'll help you create a chart.

[Calling tool create_chart with args {"type": "pie", "data": [1, 2, 3]}]

✅ I've successfully created your chart. The chart shows the data you requested."""
    
    expected1 = "✅ I've successfully created your chart. The chart shows the data you requested."
    result1 = _extract_final_message_from_router_result(test1)
    
    # Test case 2: Nested brackets in tool arguments
    test2 = """Let me process your request.

[Calling tool create_chart_from_data with args {"chart_type": "pie", "data": {"labels": ["A", "B"], "datasets": [{"data": [50, 50], "backgroundColor": ["#FF6384", "#36A2EB"]}]}, "title": "50/50 Split"}]

Now I'll create a document:
[Calling tool create_document with args {"content": "# Chart\\n\\nHere's your chart with nested data: {\\"nested\\": {\\"value\\": [1, 2, 3]}}", "file_path": "chart.md"}]

✅ I've created a 50/50 pie chart and saved it to your workspace. The chart displays two equal sections as requested."""
    
    expected2 = "✅ I've created a 50/50 pie chart and saved it to your workspace. The chart displays two equal sections as requested."
    result2 = _extract_final_message_from_router_result(test2)
    
    # Test case 3: Multiple tool calls with complex arguments
    test3 = """I'll help you with this task.

[Calling tool filesystem_search_files with args {"query": "documents", "path": "/workspace"}]
[Calling tool create_chart with args {"data": {"complex": {"nested": {"array": [{"key": "value"}, {"key2": "value2"}]}}}, "type": "bar"}]

Let me try a different approach:
[Calling tool filesystem_move_file with args {"source": "/tmp/file.png", "destination": "/Downloads/file.png"}]

Perfect! I've completed all the requested operations. The files have been moved and the chart has been created successfully."""
    
    expected3 = "Perfect! I've completed all the requested operations. The files have been moved and the chart has been created successfully."
    result3 = _extract_final_message_from_router_result(test3)
    
    # Test case 4: No tool calls (should return original)
    test4 = "This is just a simple response without any tool calls."
    expected4 = test4
    result4 = _extract_final_message_from_router_result(test4)
    
    # Test case 5: Tool call with escaped quotes and brackets
    test5 = """Processing your request.

[Calling tool create_document with args {"content": "This has \\"escaped quotes\\" and [brackets] in content", "path": "test.md"}]

Your document has been created with the special characters properly handled."""
    
    expected5 = "Your document has been created with the special characters properly handled."
    result5 = _extract_final_message_from_router_result(test5)
    
    # Log test results
    logger.info("=== Testing _extract_final_message_from_router_result ===")
    
    logger.info(f"Test 1 - Simple tool call:")
    logger.info(f"  Expected: {expected1}")
    logger.info(f"  Got:      {result1}")
    logger.info(f"  Pass:     {result1.strip() == expected1}")
    
    logger.info(f"Test 2 - Nested brackets:")
    logger.info(f"  Expected: {expected2}")
    logger.info(f"  Got:      {result2}")
    logger.info(f"  Pass:     {result2.strip() == expected2}")
    
    logger.info(f"Test 3 - Multiple complex tool calls:")
    logger.info(f"  Expected: {expected3}")
    logger.info(f"  Got:      {result3}")
    logger.info(f"  Pass:     {result3.strip() == expected3}")
    
    logger.info(f"Test 4 - No tool calls:")
    logger.info(f"  Expected: {expected4}")
    logger.info(f"  Got:      {result4}")
    logger.info(f"  Pass:     {result4.strip() == expected4}")
    
    logger.info(f"Test 5 - Escaped quotes and brackets:")
    logger.info(f"  Expected: {expected5}")
    logger.info(f"  Got:      {result5}")
    logger.info(f"  Pass:     {result5.strip() == expected5}")
    
    # Count passing tests
    tests_passed = sum([
        result1.strip() == expected1,
        result2.strip() == expected2,
        result3.strip() == expected3,
        result4.strip() == expected4,
        result5.strip() == expected5
    ])
    
    logger.info(f"=== Test Summary: {tests_passed}/5 tests passed ===")
    
    return tests_passed == 5

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
    
    # Create directly if no function provided - use our Fixed implementation
    from .coordinator_agent import FixedAnthropicAugmentedLLM
    return FixedAnthropicAugmentedLLM(
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
    mode: Optional[str] = Field("multiagent", description="Agent mode: 'multiagent' or 'single'")
    single_agent_type: Optional[str] = Field(None, description="Type of single agent when mode is 'single'")

class AgentResponse(BaseModel):
    """Response model from agent processing."""
    session_id: str = Field(..., description="Session ID for tracking")
    result: str = Field(..., description="Result of processing")
    workflow_type: str = Field(..., description="Type of workflow used")
    completion_time: float = Field(..., description="Time to process request")
    overloaded: bool = Field(False, description="Whether the response is due to service overload")

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
        file_context_note = f"IMPORTANT CONTEXT: This task involves {len(request.file_ids)} file(s). Their IDs are: {', '.join(request.file_ids)}. Ensure the plan utilizes these files appropriately, likely using a 'researcher' or similar agent for relevant information."
        if planner_objective_text:
            planner_objective_text += "\n\n" + file_context_note
        else:
            planner_objective_text = file_context_note
        logger.info(f"[{query_id}] Orchestrator Objective: Appended file context note for {len(request.file_ids)} files.")

    if not planner_objective_text:
        logger.error(f"[{query_id}] Orchestrator Objective: Resulting planner_objective_text is empty after extraction from {source_description}.")
        
    return planner_objective_text
# --- END ADDED helper function ---

async def process_orchestrator_workflow(
    request: AgentRequest,
    query_id: str,
    orchestrator: Optional[Orchestrator] = None,
    create_orchestrator_fn: Optional[Callable] = None,
    ensure_agents_exist_fn: Optional[Callable] = None,
    create_anthropic_llm_fn: Optional[Callable] = None,
    websocket_manager = None
) -> AgentResponse:
    """
    Process a user query using the orchestrator workflow.
    
    Args:
        request: The agent request object
        query_id: Session identifier for the request
        orchestrator: Optional pre-initialized orchestrator (uses create_orchestrator_fn if not provided)
        create_orchestrator_fn: Function to create an orchestrator if needed
        ensure_agents_exist_fn: Function to ensure agents exist
        create_anthropic_llm_fn: Function to create an Anthropic LLM
        websocket_manager: WebSocket manager instance
        
    Returns:
        AgentResponse with the final result
    """
    start_time = time.time()
    workflow_type = "orchestrator"
    result = ""
    
    try:
        logger.info(f"[{query_id}] Processing query with orchestrator workflow: {request.query}")
        
        # Check circuit breaker before proceeding
        circuit_breaker = get_circuit_breaker()
        if circuit_breaker and circuit_breaker.is_overloaded():
            logger.error(f"[{query_id}] Circuit breaker is tripped - service overloaded. Aborting orchestrator workflow.")
            return AgentResponse(
                session_id=query_id,
                result="The service is currently overloaded. Please try again later.",
                workflow_type=workflow_type,
                completion_time=time.time() - start_time,
                overloaded=True
            )
        
        # Create the Anthropic LLM if needed
        if not create_anthropic_llm_fn:
            logger.warning("No function provided to create Anthropic LLM, orchestrator might fail")
            
        # Ensure agents exist if needed
        if ensure_agents_exist_fn and request.use_agents:
            ensure_agents_exist_fn(["researcher", "creator", "editor", "decider"])
            logger.info(f"Ensured existence of required agents")
        
        # Create the orchestrator if not provided
        if not orchestrator and create_orchestrator_fn:
            # This will create the orchestrator with the agents in request.use_agents
            orchestrator = await create_orchestrator_fn(request.use_agents)
            
        if not orchestrator:
            logger.warning(f"[{query_id}] No orchestrator or create_orchestrator_fn provided, cannot orchestrate request")
            return AgentResponse(
                session_id=query_id,
                result="Unable to process request: Orchestrator not available",
                workflow_type=workflow_type,
                completion_time=time.time() - start_time
            )
        
        # <<< Send WebSocket Update >>>
        if websocket_manager:
            logger.info(f"[{query_id}] Sending orchestration start status update.")
            await websocket_manager.send_consolidated_update(
                query_id=query_id,
                update_type="status",
                message="Starting orchestrator workflow...",
                data={
                    "status": "starting_orchestration", 
                    "workflow_type": "orchestrator",
                    "agents_involved": request.use_agents or [] # Indicate intended agents
                },
                workflow_type='orchestrator'
            )
        # <<< End WebSocket Update >>>
            
        # Explicitly set the model for the orchestrator's planner LLM to override model selection
        if hasattr(orchestrator, 'planner') and orchestrator.planner is not None:
            ORCHESTRATOR_PLANNER_MODEL = "claude-3-7-sonnet@20250219" # Use high-quality Sonnet for better plans
            if not hasattr(orchestrator.planner, 'default_request_params') or orchestrator.planner.default_request_params is None:
                orchestrator.planner.default_request_params = RequestParams(model=ORCHESTRATOR_PLANNER_MODEL, maxTokens=8192)  # Restore higher limit for complex plans
            else:
                orchestrator.planner.default_request_params.model = ORCHESTRATOR_PLANNER_MODEL
                orchestrator.planner.default_request_params.maxTokens = 8192  # Good token limit for planning
            logger.info(f"Set orchestrator's internal planner LLM to use high-quality model: {ORCHESTRATOR_PLANNER_MODEL}")
            logger.warning(f"Ensure model {ORCHESTRATOR_PLANNER_MODEL} supports the max_tokens (e.g., 8192) passed by the Orchestrator class.")

        # --- MODIFIED: Use the new helper function to get a focused objective --- 
        planner_objective_text = extract_objective_for_orchestrator(request, logger, query_id)

        if not planner_objective_text:
            logger.error(f"[{query_id}] Orchestrator: planner_objective_text is empty. Cannot proceed.")
            return AgentResponse(
                session_id=query_id,
                result="Error: Could not derive a valid objective for the orchestrator planner.",
                workflow_type=workflow_type,
                completion_time=time.time() - start_time
            )
        logger.info(f"[{query_id}] Orchestrator: Using focused objective for planner (first 100 chars): '{planner_objective_text[:100]}...'")
        # --- END MODIFIED --- 

        # --- ADDED: Log Orchestrator's internal agents and their LLM status ---
        if orchestrator and hasattr(orchestrator, 'agents') and isinstance(orchestrator.agents, dict):
            logger.info(f"[{query_id}] Orchestrator Pre-Execution Check: Orchestrator has {len(orchestrator.agents)} agents configured: {list(orchestrator.agents.keys())}")
            for agent_name, agent_instance in orchestrator.agents.items():
                llm_status = "LLM MISSING or UNKNOWN TYPE"
                if hasattr(agent_instance, 'augmented_llm') and agent_instance.augmented_llm is not None:
                    llm_type = type(agent_instance.augmented_llm).__name__
                    actual_llm_inside_guard = None
                    guarded_llm_model = "N/A"

                    # FIXED: Handle different wrapper types properly
                    if llm_type == "AgentSpecificWrapper":
                        # For AgentSpecificWrapper, check the base_llm
                        if hasattr(agent_instance.augmented_llm, 'base_llm') and agent_instance.augmented_llm.base_llm is not None:
                            actual_llm_inside_guard = agent_instance.augmented_llm.base_llm
                            base_llm_type = type(actual_llm_inside_guard).__name__
                            
                            # Check if the base LLM has model info
                            if (hasattr(actual_llm_inside_guard, 'default_request_params') and 
                                actual_llm_inside_guard.default_request_params and
                                hasattr(actual_llm_inside_guard.default_request_params, 'model')):
                                guarded_llm_model = actual_llm_inside_guard.default_request_params.model
                            
                            llm_status = f"LLM Present (AgentSpecificWrapper wrapping {base_llm_type} using model '{guarded_llm_model}')"
                        else:
                            llm_status = "LLM Present (AgentSpecificWrapper), but base_llm is missing"
                    elif llm_type == "SemaphoreGuardedLLM" and hasattr(agent_instance.augmented_llm, '_llm'):
                        # For SemaphoreGuardedLLM, check the _llm attribute (not .llm)
                        actual_llm_inside_guard = agent_instance.augmented_llm._llm
                        if (hasattr(actual_llm_inside_guard, 'default_request_params') and 
                            actual_llm_inside_guard.default_request_params and
                            hasattr(actual_llm_inside_guard.default_request_params, 'model')):
                            guarded_llm_model = actual_llm_inside_guard.default_request_params.model
                        llm_status = f"LLM Present (SemaphoreGuardedLLM wrapping {type(actual_llm_inside_guard).__name__} using model '{guarded_llm_model}')"
                    elif (hasattr(agent_instance.augmented_llm, 'default_request_params') and 
                          agent_instance.augmented_llm.default_request_params and
                          hasattr(agent_instance.augmented_llm.default_request_params, 'model')):
                        # Direct LLM with model info
                        guarded_llm_model = agent_instance.augmented_llm.default_request_params.model
                        llm_status = f"LLM Present ({llm_type} using model '{guarded_llm_model}')"
                    else:
                        llm_status = f"LLM Present ({llm_type}), but model unknown or default_request_params not set."
                logger.info(f"[{query_id}] Orchestrator Agent Check: '{agent_name}' -> {llm_status}")
        else:
            logger.error(f"[{query_id}] Orchestrator Pre-Execution Check: Orchestrator object or its 'agents' attribute is missing/invalid.")
        # --- END ADDED ---

        # The old logic for constructing full_messages and then extracting from it is now replaced by the call above.
        
        # --- MODIFIED: Define and pass specific RequestParams to orchestrator.generate_str ---
        orchestrator_call_params = RequestParams(
            model="claude-3-7-sonnet@20250219",  # Use high-quality Sonnet for better results
            maxTokens=4096,  # Good balance for orchestrator calls
            use_history=False # Orchestrator's generate method itself does not use history for planning
        )
        
        # --- ADDED: Set workflow context on orchestrator so its events include workflow_type ---
        if hasattr(orchestrator, 'context') and orchestrator.context:
            # Set workflow context for event emission
            if hasattr(orchestrator.context, 'workflow_type'):
                orchestrator.context.workflow_type = workflow_type
            else:
                # Add workflow_type as an attribute if it doesn't exist
                setattr(orchestrator.context, 'workflow_type', workflow_type)
            
            # ADDED: Also set agent_name for orchestrator events
            if hasattr(orchestrator.context, 'agent_name'):
                orchestrator.context.agent_name = "orchestrator"
            else:
                setattr(orchestrator.context, 'agent_name', "orchestrator")
            
            logger.info(f"[{query_id}] Set workflow_type='{workflow_type}' and agent_name='orchestrator' on orchestrator context for event emission")
        
        # Also try to set it on the planner's context if available
        if hasattr(orchestrator, 'planner') and orchestrator.planner and hasattr(orchestrator.planner, 'context'):
            if hasattr(orchestrator.planner.context, 'workflow_type'):
                orchestrator.planner.context.workflow_type = workflow_type
            else:
                setattr(orchestrator.planner.context, 'workflow_type', workflow_type)
            
            # ADDED: Also set agent_name for planner events
            if hasattr(orchestrator.planner.context, 'agent_name'):
                orchestrator.planner.context.agent_name = "planner"
            else:
                setattr(orchestrator.planner.context, 'agent_name', "planner")
            
            logger.info(f"[{query_id}] Set workflow_type='{workflow_type}' and agent_name='planner' on planner context for event emission")
        # --- END ADDED ---
        
        logger.info(f"[{query_id}] Orchestrator: About to call orchestrator.generate_str with objective (first 50 chars): '{planner_objective_text[:50]}...'")
        logger.info(f"[{query_id}] Orchestrator: RequestParams for this call: model='{orchestrator_call_params.model}', maxTokens={orchestrator_call_params.maxTokens}, use_history={orchestrator_call_params.use_history}")

        # Process the request with the orchestrator using the extracted text and specific params
        try:
            result = await orchestrator.generate_str(
                planner_objective_text,
                request_params=orchestrator_call_params
            )
            logger.info(f"[{query_id}] Orchestrator: orchestrator.generate_str call COMPLETED.")
            logger.info(f"[{query_id}] Orchestrator: Final result from orchestrator (first 200 chars): {str(result)[:200]}...")
        except Exception as e:
            # Check if this is an OverloadedError (529 error) from Anthropic
            if "OverloadedError" in str(type(e)) or "OverloadedError" in str(e) or "529" in str(e) or "overloaded" in str(e).lower():
                logger.error(f"[{query_id}] Anthropic API is overloaded (529 error) in orchestrator. Stopping workflow. Error: {e}")
                
                # Trip the circuit breaker to prevent further calls
                circuit_breaker = get_circuit_breaker()
                if circuit_breaker:
                    circuit_breaker.trip(f"529 error in orchestrator for query {query_id}: {str(e)}")
                
                return AgentResponse(
                    session_id=query_id,
                    result="The service is currently overloaded. Please try again later.",
                    workflow_type=workflow_type,
                    completion_time=time.time() - start_time,
                    overloaded=True
                )
            else:
                logger.error(f"Error in orchestrator generate_str call: {str(e)}")
                return AgentResponse(
                    session_id=query_id,
                    result=f"Error processing query with orchestrator: {str(e)}",
                    workflow_type=workflow_type,
                    completion_time=time.time() - start_time
                )
        # --- END MODIFIED ---
        
        # Calculate completion time
        completion_time = time.time() - start_time
        
        return AgentResponse(
            session_id=query_id,
            result=result,
            workflow_type=workflow_type,
            completion_time=completion_time
        )
        
    except Exception as e:
        logger.error(f"Error in orchestrator workflow: {str(e)}")
        return AgentResponse(
            session_id=query_id,
            result=f"Error processing query with orchestrator: {str(e)}",
            workflow_type=workflow_type,
            completion_time=time.time() - start_time
        )

async def process_router_workflow(
    request: AgentRequest,
    query_id: str,
    router: Optional[AnthropicLLMRouter] = None,
    create_router_fn: Optional[Callable] = None,
    ensure_agents_exist_fn: Optional[Callable] = None,
    agents: Optional[Dict[str, Agent]] = None,
    create_anthropic_llm_fn: Optional[Callable] = None,
    websocket_manager = None,
    workflow_config: Optional[Dict[str, Any]] = None
) -> AgentResponse:
    """
    Process a user query using the router workflow.
    
    Args:
        request: The agent request object
        query_id: The query ID for the session
        router: Optional pre-initialized router (uses the provided function to create one if not provided)
        create_router_fn: Function to create the router
        ensure_agents_exist_fn: Function to ensure agents exist
        agents: Dictionary of pre-initialized agents
        create_anthropic_llm_fn: Function to create an Anthropic LLM
        websocket_manager: WebSocket manager for sending updates to clients
        workflow_config: Optional workflow configuration from YAML file
        
    Returns:
        AgentResponse with the final result
    """
    start_time = time.time()
    workflow_type = "router"
    result = ""
    
    try:
        logger.info(f"Processing query with router workflow: {request.query}")
        
        # Check circuit breaker before proceeding
        circuit_breaker = get_circuit_breaker()
        if circuit_breaker and circuit_breaker.is_overloaded():
            logger.error(f"[{query_id}] Circuit breaker is tripped - service overloaded. Aborting router workflow.")
            return AgentResponse(
                session_id=query_id,
                result="The service is currently overloaded. Please try again later.",
                workflow_type=workflow_type,
                completion_time=time.time() - start_time,
                overloaded=True
            )
        
        # Create the Anthropic LLM if needed
        if not create_anthropic_llm_fn:
            logger.warning("No function provided to create Anthropic LLM, router will fail")
            return AgentResponse(
                session_id=query_id,
                result="Unable to process request: Router requires an Anthropic LLM",
                workflow_type=workflow_type,
                completion_time=time.time() - start_time
            )
            
        # Ensure agents exist if needed
        if ensure_agents_exist_fn and request.use_agents:
            ensure_agents_exist_fn(["researcher", "creator", "editor", "decider"])
            logger.info(f"Ensured existence of required agents")
            
        # Create the router if not provided
        if not router and create_router_fn:
            # This will create the router with the agents in request.use_agents
            # If none of those agents are available, it falls back to using all available agents
            router = await create_router_fn(request.use_agents)
            
        if not router:
            logger.warning("No router or create_router_fn provided, cannot route request")
            return AgentResponse(
                session_id=query_id,
                result="Unable to process request: Router not available",
                workflow_type=workflow_type,
                completion_time=time.time() - start_time
            )
        
        # --- ADDED: Set workflow context on router so its events include workflow_type ---
        if hasattr(router, 'context') and router.context:
            # Set workflow context for event emission
            if hasattr(router.context, 'workflow_type'):
                router.context.workflow_type = workflow_type
            else:
                # Add workflow_type as an attribute if it doesn't exist
                setattr(router.context, 'workflow_type', workflow_type)
            
            # ADDED: Also set agent_name for router events
            if hasattr(router.context, 'agent_name'):
                router.context.agent_name = "router"
            else:
                setattr(router.context, 'agent_name', "router")
            
            logger.info(f"[{query_id}] Set workflow_type='{workflow_type}' and agent_name='router' on router context for event emission")
        
        # Also try to set it on the router's LLM context if available
        if hasattr(router, 'augmented_llm') and router.augmented_llm and hasattr(router.augmented_llm, 'context'):
            if hasattr(router.augmented_llm.context, 'workflow_type'):
                router.augmented_llm.context.workflow_type = workflow_type
            else:
                setattr(router.augmented_llm.context, 'workflow_type', workflow_type)
            
            # ADDED: Also set agent_name for router LLM events
            if hasattr(router.augmented_llm.context, 'agent_name'):
                router.augmented_llm.context.agent_name = "router"
            else:
                setattr(router.augmented_llm.context, 'agent_name', "router")
            
            logger.info(f"[{query_id}] Set workflow_type='{workflow_type}' and agent_name='router' on router LLM context for event emission")
        # --- END ADDED ---
        
        # Explicitly set the model for the router's LLM to override model selection
        if hasattr(router, 'augmented_llm') and router.augmented_llm is not None:
            if not hasattr(router.augmented_llm, 'default_request_params') or router.augmented_llm.default_request_params is None:
                router.augmented_llm.default_request_params = RequestParams(model=DEFAULT_MODEL)
            else:
                router.augmented_llm.default_request_params.model = DEFAULT_MODEL
            logger.info(f"Set router LLM model to {DEFAULT_MODEL}")
            
        # --- ADDED: Apply workflow configuration settings ---
        if workflow_config and hasattr(router, 'augmented_llm') and router.augmented_llm is not None:
            router_config = workflow_config.get('router', {})
            max_iterations = router_config.get('max_iterations')
            
            if max_iterations is not None:
                # Ensure default_request_params exists
                if not hasattr(router.augmented_llm, 'default_request_params') or router.augmented_llm.default_request_params is None:
                    router.augmented_llm.default_request_params = RequestParams(model=DEFAULT_MODEL)
                
                # Set max_iterations from configuration
                router.augmented_llm.default_request_params.max_iterations = max_iterations
                logger.info(f"[{query_id}] Set router max_iterations to {max_iterations} from workflow configuration")
            else:
                logger.debug(f"[{query_id}] No max_iterations found in router workflow configuration, using default")
        else:
            if not workflow_config:
                logger.debug(f"[{query_id}] No workflow configuration provided to router workflow")
            else:
                logger.debug(f"[{query_id}] Router LLM not available for configuration application")
        # --- END ADDED ---
            
        # Use the processed_message directly from the request or history for clarification
        full_message = None
        # --- MODIFIED: Handle clarification case --- 
        if not request.processed_message:
            # Check if history exists (clarification case)
            if not request.message_history:
                logger.error("No processed_message or message_history found in request! Cannot proceed with router.")
                return AgentResponse(
                    session_id=query_id,
                    result="Error: Missing message context for router. Please try again.",
                    workflow_type=workflow_type,
                    completion_time=time.time() - start_time
                )
            else:
                # Use history for clarification flow
                logger.info("Proceeding with router using message history (clarification response).")
                history = request.message_history
                # Construct the full list to send to the final agent
                full_messages_for_agent = history # Includes the latest answer
                
                # --- MODIFIED: Generate richer routing_text for router --- 
                routing_text = ""
                if history:
                    # Try to get last 3 messages: User Answer, Assistant Question, Original Query User Message
                    last_three = history[-3:]
                    # Extract text content from each message safely
                    extracted_texts = []
                    for msg in last_three:
                        content = msg.get('content', '')
                        if isinstance(content, str):
                            extracted_texts.append(content)
                        elif isinstance(content, list):
                            # Extract text from complex content parts
                            text_parts = ' '.join([item.get('text', '') for item in content if item.get('type') == 'text']).strip()
                            if text_parts: extracted_texts.append(text_parts)
                    
                    # Combine the extracted texts, separated by newlines, for routing context
                    routing_text = "\n---\n".join(extracted_texts)
                    logger.info(f"Using combined text from last {len(last_three)} messages for routing.")
                
                if not routing_text:
                     # Fallback: Use only the last message if extraction failed or history < 3
                    logger.warning("Could not generate multi-message routing context, falling back to last message.")
                    last_message = history[-1] if history else None
                    if last_message:
                        content = last_message.get('content', '')
                        if isinstance(content, str):
                            routing_text = content
                        elif isinstance(content, list):
                            routing_text = ' '.join([item.get('text', '') for item in content if item.get('type') == 'text']).strip()
                    else:
                         routing_text = "" # Final fallback
        else:
            # Normal case: Use the provided processed_message
            full_messages_for_agent = [request.processed_message] # Start with the current message
            # Extract text for routing decision from the processed message
            routing_text = extract_query_for_router(request.processed_message)
            logger.info(f"Using processed message from request with {len(request.processed_message.get('content',[]))} content blocks")
            logger.debug(f"Router message content summary: {[block.get('type') for block in request.processed_message.get('content',[])]}")
            # Prepend history if it exists (even in non-clarification case if needed, though usually handled by llm internal memory)
            if request.message_history:
                 logger.info(f"Prepending {len(request.message_history)} history messages to router request.")
                 full_messages_for_agent = request.message_history + full_messages_for_agent
        # --- END MODIFIED ---
        
        # Add file IDs information to message if available (already part of processed_message)
        # if request.file_ids and len(request.file_ids) > 0:
        #     logger.info(f"Request includes {len(request.file_ids)} file IDs for context")

        logger.info(f"Extracted routing text (first 100 chars): {routing_text[:100]}...")
        
        # Set the message to be used for routing decision
        message_for_routing = routing_text
        
        # Pass context (AgentRequest) to router for potential use in prompt generation
        # --- MODIFIED: Use router.route and handle result --- 
        try:
            routing_results = await router.route(message_for_routing, top_k=1) 
        except Exception as e:
            # Check if this is an OverloadedError (529 error) from Anthropic
            if "OverloadedError" in str(type(e)) or "529" in str(e) or "overloaded" in str(e).lower():
                logger.error(f"[{query_id}] Anthropic API is overloaded (529 error). Stopping workflow. Error: {e}")
                
                # Trip the circuit breaker to prevent further calls
                circuit_breaker = get_circuit_breaker()
                if circuit_breaker:
                    circuit_breaker.trip(f"529 error in router.route for query {query_id}: {str(e)}")
                
                return AgentResponse(
                    session_id=query_id,
                    result="The service is currently overloaded. Please try again later.",
                    workflow_type=workflow_type,
                    completion_time=time.time() - start_time,
                    overloaded=True
                )
            else:
                logger.error(f"Error in router workflow: {str(e)}")
                return AgentResponse(
                    session_id=query_id,
                    result=f"Error processing query with router: {str(e)}",
                    workflow_type=workflow_type,
                    completion_time=time.time() - start_time
                )
        
        if not routing_results:
            logger.warning(f"Router returned no agent selection for query: {request.query}")
            return AgentResponse(
                session_id=query_id,
                result="Could not determine appropriate agent for this request.",
                workflow_type=workflow_type,
                completion_time=time.time() - start_time
            )
            
        # Extract top result
        top_result = routing_results[0]
        selected_agent_obj = top_result.result
        
        # Ensure the result is an Agent object
        if not isinstance(selected_agent_obj, Agent):
            logger.error(f"Router returned an unexpected result type: {type(selected_agent_obj)}")
            selected_agent_name = str(selected_agent_obj) # Fallback to string representation
        else:
            selected_agent_name = selected_agent_obj.name
        # --- END MODIFIED --- 
        
        logger.info(f"Router selected agent: {selected_agent_name}. Confidence: {getattr(top_result, 'confidence', 'N/A')}, Reasoning: {getattr(top_result, 'reasoning', 'N/A')}")
        
        if selected_agent_name in agents:
            selected_agent = agents[selected_agent_name]
            
            # --- ADDED: Construct full message list with history for selected agent ---
            history = request.message_history or []
            history_for_llm = history # <<< Default to full history
            
            # --- MODIFIED: Use last message from history if processed_message is None --- 
            # The construction of full_messages_for_agent is now handled above
            # if request.processed_message:
            #     current_message = request.processed_message
            #     history_for_llm = history # <<< Explicitly set for normal case
            # elif history: # If no processed_message, use the last message in history (the user's answer)
            #     current_message = history[-1]
            #     # Ensure history passed to LLM doesn't duplicate the last message
            #     history_for_llm = history[:-1] # <<< Overwrite for clarification case
            # else: # Should not happen if validation is correct, but handle defensively
            #     current_message = None
            #     history_for_llm = [] # <<< Set for edge case
            
            # # Ensure the current message is not None before appending
            # full_messages_for_agent = history_for_llm + ([current_message] if current_message else [])
            if len(full_messages_for_agent) > 1: # Check if history was prepended or constructed
                logger.info(f"Prepended {len(full_messages_for_agent) -1} history messages for selected agent '{selected_agent_name}'.")
            # --- END MODIFIED ---
            
            # Send update via WebSocket
            if websocket_manager:
                await websocket_manager.send_consolidated_update(
                    query_id=query_id,
                    update_type="routing",
                    message=f"Selected {selected_agent_name}",
                    data={
                        "selected_agent": selected_agent_name
                    },
                    workflow_type='router'
                )

            # --- MODIFIED: Create LLM for the agent and call generate_str on the LLM ---
            if not full_messages_for_agent:
                logger.warning(f"No history or current message to send to agent '{selected_agent_name}'. Sending empty list.")

            try:
                agent_llm = create_anthropic_llm_fn(agent=selected_agent)
                
                # --- ADDED: Set context on the agent LLM for proper event emission ---
                if hasattr(agent_llm, 'context') and agent_llm.context:
                    # Set workflow context for event emission
                    if hasattr(agent_llm.context, 'workflow_type'):
                        agent_llm.context.workflow_type = workflow_type
                    else:
                        setattr(agent_llm.context, 'workflow_type', workflow_type)
                    
                    # Set agent name for proper identification
                    if hasattr(agent_llm.context, 'agent_name'):
                        agent_llm.context.agent_name = selected_agent_name
                    else:
                        setattr(agent_llm.context, 'agent_name', selected_agent_name)
                    
                    logger.info(f"[{query_id}] Set workflow_type='{workflow_type}' and agent_name='{selected_agent_name}' on agent LLM context")
                # --- END ADDED ---
                
                # --- ADDED: Apply workflow configuration to agent LLM ---
                if workflow_config:
                    router_config = workflow_config.get('router', {})
                    max_iterations = router_config.get('max_iterations')
                    
                    if max_iterations is not None:
                        # Ensure default_request_params exists
                        if not hasattr(agent_llm, 'default_request_params') or agent_llm.default_request_params is None:
                            agent_llm.default_request_params = RequestParams(model=DEFAULT_MODEL)
                        
                        # Set max_iterations from configuration
                        agent_llm.default_request_params.max_iterations = max_iterations
                        logger.info(f"[{query_id}] Set agent '{selected_agent_name}' max_iterations to {max_iterations} from workflow configuration")
                # --- END ADDED ---
                
                logger.info(f"Created LLM for agent '{selected_agent_name}'")
                result = await agent_llm.generate_str(full_messages_for_agent)
                
                # ADDED: Clean router result to extract only the final message for display
                # Router workflows return complete conversation with tool calls, but users only need the final answer
                result = _extract_final_message_from_router_result(result)
            except Exception as llm_error:
                # Check if this is an OverloadedError (529 error) from Anthropic
                if "OverloadedError" in str(type(llm_error)) or "OverloadedError" in str(llm_error) or "529" in str(llm_error) or "overloaded" in str(llm_error).lower():
                    logger.error(f"[{query_id}] Anthropic API is overloaded (529 error) in agent '{selected_agent_name}'. Stopping workflow. Error: {llm_error}")
                    
                    # Trip the circuit breaker to prevent further calls
                    circuit_breaker = get_circuit_breaker()
                    if circuit_breaker:
                        circuit_breaker.trip(f"529 error in agent '{selected_agent_name}' for query {query_id}: {str(llm_error)}")
                    
                    return AgentResponse(
                        session_id=query_id,
                        result="The service is currently overloaded. Please try again later.",
                        workflow_type=workflow_type,
                        completion_time=time.time() - start_time,
                        overloaded=True
                    )
                else:
                    logger.error(f"Error creating or using LLM for agent '{selected_agent_name}': {llm_error}")
                    result = f"Error invoking agent '{selected_agent_name}': {llm_error}"
            # --- END MODIFIED ---

        else:
            result = f"Router selected agent '{selected_agent_name}' but it was not found."
            
        # Calculate completion time
        completion_time = time.time() - start_time
        
        return AgentResponse(
            session_id=query_id,
            result=result,
            workflow_type=workflow_type,
            completion_time=completion_time
        )
        
    except Exception as e:
        logger.error(f"Error in router workflow: {str(e)}")
        # --- ADDED: Check for OverloadedError in string representation for broader safety ---
        # This is a fallback in case the exception is wrapped and not caught directly.
        if "OverloadedError" in str(type(e)) or "OverloadedError" in str(e) or "529" in str(e) or "overloaded" in str(e).lower():
            logger.error(f"[{query_id}] Detected OverloadedError within a general exception. Stopping workflow.")
            
            # Trip the circuit breaker to prevent further calls
            circuit_breaker = get_circuit_breaker()
            if circuit_breaker:
                circuit_breaker.trip(f"529 error in router workflow fallback for query {query_id}: {str(e)}")
            
            return AgentResponse(
                session_id=query_id,
                result="The service is currently overloaded and could not proceed. Please try again later.",
                workflow_type=workflow_type,
                completion_time=time.time() - start_time,
                overloaded=True
            )
        # --- END ADDED ---
        return AgentResponse(
            session_id=query_id,
            result=f"Error processing query with router: {str(e)}",
            workflow_type=workflow_type,
            completion_time=time.time() - start_time
        ) 