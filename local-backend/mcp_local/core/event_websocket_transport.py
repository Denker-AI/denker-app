"""
Event transport that bridges MCP agent events to Denker's WebSocket.

This module connects MCP agent's event system to Denker's WebSocket server,
allowing frontend clients to receive detailed information about agent activities.
"""

import logging
from typing import Any, Dict, Optional
# Add OTel imports
from opentelemetry import baggage, context as otel_context
import json

from mcp_agent.logging.transport import EventTransport
from mcp_agent.logging.events import Event
from mcp_agent.event_progress import ProgressAction

from .websocket_manager import get_websocket_manager

logger = logging.getLogger(__name__)

class WebSocketEventTransport(EventTransport):
    """
    Transport that sends MCP agent events to connected WebSocket clients.
    This bridges MCP agent's internal event system to Denker's WebSocket server.
    """
    
    def __init__(self, query_context_key: str = "query_id"):
        """
        Initialize the WebSocket event transport.
        
        Args:
            query_context_key: The key used to identify query IDs in event context
        """
        self.websocket_manager = get_websocket_manager()
        self.query_context_key = query_context_key
        logger.info("WebSocketEventTransport initialized")
    
    def _extract_query_id(self, event: Event) -> Optional[str]:
        """
        Extract the query ID from an event.
        
        It checks event context, trace context, event data, and finally OTel baggage.
        
        Args:
            event: The event to extract the query ID from
            
        Returns:
            The query ID if found, None otherwise
        """
        # Log the incoming event context for debugging
        logger.debug(f"Attempting to extract query_id. Event Context: {getattr(event, 'context', 'N/A')}")
        
        query_id = None
        source = "unknown"
        
        # --- Priority 1: Check Agent Session ID Mapping --- 
        agent_session_id = None
        if event.context and hasattr(event.context, 'session_id') and event.context.session_id:
            agent_session_id = event.context.session_id
            logger.debug(f"Found agent_session_id '{agent_session_id}' in event.context")
            if self.websocket_manager:
                query_id = self.websocket_manager.get_query_id_for_session(agent_session_id)
                if query_id:
                    source = "agent_session_id_map"
                else:
                    # Log if mapping wasn't found for this specific session ID
                    logger.warning(f"Found agent_session_id '{agent_session_id}' in event context, but no query_id mapping exists.")
            else:
                 logger.warning("WebSocketManager not available to perform session ID lookup.")

        # --- Fallback Checks (Context, Data, Baggage) --- 
        # Only proceed if mapping didn't yield a query_id
        if not query_id:
            logger.debug("Agent session ID mapping did not yield query_id, proceeding to fallback checks.")
            # Check event context first (using original key)
        if event.context and self.query_context_key in event.context:
            query_id = event.context[self.query_context_key]
            source = "event.context"
        
        # Try trace context if available 
        elif hasattr(event, 'trace_context') and event.trace_context:
            if isinstance(event.trace_context, dict) and self.query_context_key in event.trace_context:
                query_id = event.trace_context[self.query_context_key]
                source = "event.trace_context"
        
        # Try to find in event data
        elif event.data:
            # Check if query_id is directly in data
            if isinstance(event.data, dict) and self.query_context_key in event.data:
                query_id = event.data[self.query_context_key]
                source = "event.data"
            
            # Check nested data structure
            elif isinstance(event.data, dict) and 'data' in event.data and isinstance(event.data['data'], dict):
                data = event.data['data']
                if self.query_context_key in data:
                    query_id = data[self.query_context_key]
                    source = "event.data.data"
            
            # Check context field in data
            elif isinstance(event.data, dict) and 'context' in event.data and isinstance(event.data['context'], dict):
                    context_data = event.data['context'] # Renamed to avoid conflict with outer context
                    if self.query_context_key in context_data:
                        query_id = context_data[self.query_context_key]
                    source = "event.data.context"
            
            # If not found yet, try OpenTelemetry Baggage (as final fallback)
            if not query_id:
                # Get query_id from current OTel context's baggage
                current_otel_ctx = otel_context.get_current()
                current_baggage = baggage.get_all(context=current_otel_ctx) # Pass context explicitly
                logger.debug(f"Checking OTel Baggage. Context: {current_otel_ctx}, Baggage found: {current_baggage}") # Enhanced logging
                if self.query_context_key in current_baggage:
                     query_id = current_baggage[self.query_context_key]
                     source = "otel_baggage"
        
        # Log the source of the query ID if found
        if query_id:
            logger.debug(f"Found query_id '{query_id}' in {source}")
        else:
             # Add a debug log if query_id is still not found after all checks
             logger.debug(f"Could not extract query_id using key '{self.query_context_key}' from event context, data, or OTel baggage for event in namespace: {event.namespace}")
        
        return query_id
    
    # --- ADDED: Helper to extract workflow type --- 
    def _extract_workflow_type(self, event: Event) -> Optional[str]:
        """
        Extract workflow type from event data, with fallback detection based on namespace.
        """
        # --- ADDED: Check event context first ---
        if event.context:
            try:
                # Check for direct workflow_type in context
                if hasattr(event.context, 'workflow_type') and getattr(event.context, 'workflow_type', None):
                    return event.context.workflow_type
                    
                # Check if context is dict-like
                if isinstance(event.context, dict):
                    if 'workflow_type' in event.context and event.context['workflow_type']:
                        return event.context['workflow_type']
            except (AttributeError, TypeError) as e:
                logger.debug(f"Error accessing event context for workflow type extraction: {e}")
        # --- END ADDED ---
        
        if not event.data:
            return None
        
        # Check for workflow_type in various nested structures
        if isinstance(event.data, dict):
            # Direct workflow_type field
            if 'workflow_type' in event.data:
                return event.data['workflow_type']
            
            # Check nested data
            if 'data' in event.data and isinstance(event.data['data'], dict):
                nested_data = event.data['data']
                if 'workflow_type' in nested_data:
                    return nested_data['workflow_type']
            
            # Check context
            if 'context' in event.data and isinstance(event.data['context'], dict):
                context_data = event.data['context']
                if 'workflow_type' in context_data:
                    return context_data['workflow_type']
        
        # --- ADDED: Intelligent fallback based on namespace patterns ---
        if event.namespace:
            # Detect orchestrator workflow components
            if ('planner' in event.namespace.lower() or
                'orchestrator' in event.namespace.lower()):
                return "orchestrator"
            
            # Detect router workflow components
            if ('router' in event.namespace.lower() or 
                'router_llm' in event.namespace):
                return "router"
        
        return None

    def _extract_real_agent_name(self, event: Event, namespace: str) -> str:
        """
        Extract the real agent name from event context, data, or namespace.
        
        Priority:
        1. Event context with agent_name or real_agent
        2. Event data with agent_name 
        3. Namespace extraction (fallback)
        """
        # Priority 1: Check event context for injected agent name
        if event.context:
            try:
                # Check for direct agent_name in context
                if hasattr(event.context, 'agent_name') and getattr(event.context, 'agent_name', None):
                    return event.context.agent_name
                if hasattr(event.context, 'real_agent') and getattr(event.context, 'real_agent', None):
                    return event.context.real_agent
                    
                # Check if context is dict-like
                if isinstance(event.context, dict):
                    if 'agent_name' in event.context and event.context['agent_name']:
                        return event.context['agent_name']
                    if 'real_agent' in event.context and event.context['real_agent']:
                        return event.context['real_agent']
            except (AttributeError, TypeError) as e:
                logger.debug(f"Error accessing event context for agent name extraction: {e}")
        
        # Priority 2: Check event data for agent name
        if event.data and isinstance(event.data, dict):
            # Direct agent_name in data
            if 'agent_name' in event.data and event.data['agent_name']:
                return event.data['agent_name']
            if 'real_agent' in event.data and event.data['real_agent']:
                return event.data['real_agent']
                
            # Check nested data structure
            if 'data' in event.data and isinstance(event.data['data'], dict):
                nested_data = event.data['data']
                if 'agent_name' in nested_data and nested_data['agent_name']:
                    return nested_data['agent_name']
                if 'real_agent' in nested_data and nested_data['real_agent']:
                    return nested_data['real_agent']
        
        # Priority 3: Fallback to namespace extraction
        agent_name = namespace.split('.')[-1] if namespace else 'Unknown'
        
        # Handle specific shared LLM cases
        if agent_name in ['SharedCacheLLMAggregator', 'cachesharedllm']:
            # If we can't find the real agent name, return a generic name
            return 'Assistant'
            
        return agent_name
    # --- END ADDED --- 
    
    def _get_step_type(self, event: Event) -> str:
        """
        Determine step type from event data. Handles dict or object types.
        
        Args:
            event: The event to determine the step type for
            
        Returns:
            The step type directly from event_progress.py action types
        """
        # Handle cases where event.data might be None or not have attributes
        if not event.data:
            return "Unknown"
            
        event_data_obj = event.data  # Use event.data directly

        # --- PRIORITY 1: Check progress_action --- 
        progress_action = None
        # Check nested first
        if isinstance(event_data_obj, dict) and 'data' in event_data_obj and isinstance(event_data_obj['data'], dict):
            nested_data = event_data_obj['data']
            progress_action = nested_data.get('progress_action')
            if not progress_action and 'progress_action' in nested_data: # Handle case where value might be None but key exists
                 progress_action = nested_data['progress_action']
        # Check direct attribute/key if not found nested
        if progress_action is None: 
            progress_action = getattr(event_data_obj, 'progress_action', event_data_obj.get('progress_action') if isinstance(event_data_obj, dict) else None)

        if progress_action:
             action_str = str(progress_action.value) if hasattr(progress_action, 'value') else str(progress_action)
             logger.debug(f"Detected progress_action: {action_str}")
             # Map specific actions to desired step types
             if action_str == 'Chatting':
                 return "Chatting"
             elif action_str == 'Thinking':
                 return "Thinking"
             # Add other mappings if needed
             else:
                 return action_str # Use the action name directly as step type
        # --- END PRIORITY 1 ---

        # --- PRIORITY 2: Check for tool indicators (tool_use block or client session tools/call) --- 
        # Check client session structure first (more specific)
        if event.namespace == "mcp_agent.mcp.mcp_agent_client_session":
            if (
                isinstance(event_data_obj, dict) and 
                'data' in event_data_obj and isinstance(event_data_obj['data'], dict) and
                event_data_obj['data'].get('method') == 'tools/call' and
                'params' in event_data_obj['data'] and isinstance(event_data_obj['data']['params'], dict) and
                'name' in event_data_obj['data']['params']
            ):
                logger.debug("Found 'tools/call' method in mcp_agent_client_session, setting step_type to 'Calling Tool'")
                return "Calling Tool"
                
        # Check Anthropic-style 'content' list for tool_use
        content_blocks = None
        target_obj_for_content = event_data_obj['data'] if isinstance(event_data_obj, dict) and 'data' in event_data_obj else event_data_obj
        if hasattr(target_obj_for_content, 'content') and isinstance(getattr(target_obj_for_content, 'content', None), list):
            content_blocks = target_obj_for_content.content
        elif isinstance(target_obj_for_content, dict) and 'content' in target_obj_for_content and isinstance(target_obj_for_content.get('content'), list):
            content_blocks = target_obj_for_content['content']

        if content_blocks:
            for block in content_blocks:
                block_type = getattr(block, 'type', block.get('type') if isinstance(block, dict) else None)
                if block_type == 'tool_use':
                    logger.debug("Found 'tool_use' block in event.data.content, setting step_type to 'Calling Tool'")
                    return "Calling Tool"
        # --- END PRIORITY 2 ---

        # --- PRIORITY 3: Check for Tool Result structure --- 
        if (
            isinstance(event_data_obj, dict) and 
            'data' in event_data_obj and isinstance(event_data_obj['data'], dict) and
            'content' in event_data_obj['data'] and isinstance(event_data_obj['data']['content'], list) and
            'isError' in event_data_obj['data']
        ):
             logger.debug("Detected Tool Result structure, classifying step_type as 'Tool Result'")
             return "Tool Result"
        # --- END PRIORITY 3 ---
            
        # --- PRIORITY 4: Check namespace for indicators --- 
        if event.namespace:
            # <<< Check for any Planner >>>
            current_planner_type_for_log = None
            if 'planner' in event.namespace.lower():
                current_planner_type_for_log = "Planner"
            
            if current_planner_type_for_log: # If a planner namespace was identified
                logger.debug(f"Detected {current_planner_type_for_log} namespace: {event.namespace}")
                try:
                    # --- ENHANCED: More flexible plan detection ---
                    text_content = None
                    
                    # Method 1: Try the existing nested structure
                    planner_data = event.data.get('data') if isinstance(event.data, dict) else None
                    if planner_data and hasattr(planner_data, 'content') and isinstance(planner_data.content, list) and planner_data.content:
                        first_block = planner_data.content[0]
                        if hasattr(first_block, 'type') and first_block.type == 'text' and hasattr(first_block, 'text'):
                            text_content = first_block.text
                            logger.debug(f"Found plan text via Method 1 (nested structure): {text_content[:100]}...")
                    
                    # Method 2: Try direct event.data structure
                    if not text_content and isinstance(event.data, dict):
                        if 'content' in event.data and isinstance(event.data['content'], list) and event.data['content']:
                            first_block = event.data['content'][0]
                            if isinstance(first_block, dict) and first_block.get('type') == 'text':
                                text_content = first_block.get('text')
                                logger.debug(f"Found plan text via Method 2 (direct structure): {text_content[:100]}...")
                    
                    # Method 3: Try event.message directly 
                    if not text_content and hasattr(event, 'message') and event.message:
                        text_content = event.message
                        logger.debug(f"Found plan text via Method 3 (event.message): {text_content[:100]}...")
                    
                    # Method 4: Check if event.data itself contains the plan text
                    if not text_content and isinstance(event.data, str):
                        text_content = event.data
                        logger.debug(f"Found plan text via Method 4 (event.data string): {text_content[:100]}...")

                    if text_content:
                        # Try parsing the text as JSON
                        try:
                            parsed_plan = json.loads(text_content)
                            # Check if it looks like a plan (has 'steps' key)
                            if isinstance(parsed_plan, dict) and 'steps' in parsed_plan:
                                logger.debug(f"✅ Identified valid Plan JSON from {current_planner_type_for_log} with {len(parsed_plan['steps'])} steps.")
                                return "Plan"
                            else:
                                logger.debug(f"❌ {current_planner_type_for_log} output was JSON but did not contain 'steps' key. Keys: {list(parsed_plan.keys()) if isinstance(parsed_plan, dict) else 'not dict'}")
                        except json.JSONDecodeError as e:
                            logger.debug(f"❌ {current_planner_type_for_log} output text was not valid JSON: {str(e)[:100]}")
                            # Sometimes plans might be in markdown or other formats, so don't immediately discard
                            if 'step' in text_content.lower() and ('plan' in text_content.lower() or 'task' in text_content.lower()):
                                logger.debug(f"🔄 Detected potential non-JSON plan content, classifying as Plan anyway")
                                return "Plan"
                    else:
                         logger.debug(f"❌ {current_planner_type_for_log} event did not contain any extractable text content.")
                         logger.debug(f"Event data structure: {type(event.data)}, hasattr content: {hasattr(event.data, 'content') if hasattr(event, 'data') else False}")

                except Exception as e:
                    logger.warning(f"Error checking {current_planner_type_for_log} output for plan structure: {e}", exc_info=False)
                
                # If it wasn't identified as a Plan, DON'T return 'Running' here.
                # Let it fall through to other checks (like augmented_llm or progress_action).
                logger.debug(f"Did not classify {current_planner_type_for_log} output as 'Plan', falling through...")
            
            # <<< Continue with other namespace checks >>>
            elif 'router_llm' in event.namespace:
                return "Routing"
            elif 'augmented_llm' in event.namespace:
                 # Use a generic LLM state if progress_action didn't specify
                 return "Running" # Default for LLM
            
        # Default fallback
        logger.debug(f"Could not determine specific step type for namespace '{event.namespace}', falling back to Unknown.")
        return "Unknown"
    
    async def send_event(self, event: Event):
        """
        Send an event to the single active WebSocket client, if one exists.
        Includes detailed parsing of event data structures.

        Args:
            event: The event to send
        """
        query_id = None
        workflow_type = None # <<< ADDED: Variable to hold workflow type
        try:
            if not self.websocket_manager:
                logger.warning("WebSocket manager not available, cannot send event.")
                return

            # --- Workaround: Check for exactly ONE active connection --- 
            active_connections = self.websocket_manager.active_connections
            num_connections = len(active_connections)
            single_connection_found = False

            if num_connections == 1:
                query_id = next(iter(active_connections))
                single_connection_found = True
            elif num_connections == 0:
                logger.debug(f"Skipping event - No active WebSocket connection found. Namespace: {event.namespace}")
                return
            else: # More than one connection
                logger.warning(f"Skipping event - Expected exactly one active WebSocket connection for workaround, found {num_connections}. Namespace: {event.namespace}")
                return
                
            if not single_connection_found:
                return 
                
            if not self.websocket_manager.is_connected(query_id):
                 logger.debug(f"WebSocket connection for single query_id '{query_id}' not connected or ready. Skipping send for event in namespace '{event.namespace}'.")
                 return
            # --- End Workaround --- 

            # --- ADDED: Extract workflow_type --- 
            workflow_type = self._extract_workflow_type(event)
            # --- END ADDED --- 

            # --- Start Detailed Parsing Logic --- 
            namespace = getattr(event, 'namespace', 'unknown')
            original_message = getattr(event, 'message', '')
            raw_event_data = getattr(event, 'data', None) # Keep original data
            
            # ENHANCED: Better agent name extraction
            agent_name = self._extract_real_agent_name(event, namespace)
            
            # If the namespace is 'augmented_llm_anthropic', set agent_name to "Denker"
            if namespace == 'mcp_agent.workflows.llm.augmented_llm_anthropic':
                agent_name = "Denker"
            
            step_type = self._get_step_type(event) # Determine step type
            
            # --- ADDED: Filter out specific "Calling Tool" events from any Planner --- 
            # BUT: Never filter out Plan events - they should always be sent
            if step_type == "Plan":
                logger.info(f"[{query_id}] 🎯 PLAN EVENT DETECTED: Agent='{agent_name}', Namespace='{namespace}', allowing through all filters")
            elif 'planner' in agent_name.lower() and step_type == "Calling Tool":
                logger.info(f"[{query_id}] FILTERED WebSocket update: Skipping 'Calling Tool' event from '{agent_name}'. Original message: '{original_message[:100]}...'")
                return # Skip sending this specific update
            # --- END ADDED --- 

            # --- ADDED: Log Raw Event --- 
            try:
                # Use repr for potentially complex objects, limit length
                raw_data_repr = repr(raw_event_data)
                truncated_raw_data = raw_data_repr[:500] + ('...' if len(raw_data_repr) > 500 else '')
            except Exception:
                truncated_raw_data = "<Error representing raw_event_data>"
            logger.debug(f"[{query_id}] Processing Event - Namespace: {namespace}, StepType: {step_type}, Workflow: {workflow_type or 'N/A'}, OrigMsg: '{original_message[:100]}...', RawData: {truncated_raw_data}")
            # --- END ADDED ---

            parsed_details = {}
            first_text_block_content = None # Variable to store text
            tool_call_result_text = None # Variable for tool result text
            is_tool_response = False # Flag from parsing
            try:
                # <<< START Conditional Parsing Placeholder >>>
                # Here you could add logic like:
                # if workflow_type == 'orchestrator':
                #    # Use orchestrator-specific parsing logic
                #    parsed_details, first_text_block_content, tool_call_result_text, is_tool_response = self._parse_orchestrator_event_data(raw_event_data)
                # elif workflow_type == 'router':
                #    # Use router-specific parsing logic
                #    parsed_details, first_text_block_content, tool_call_result_text, is_tool_response = self._parse_router_event_data(raw_event_data)
                # else:
                #    # Use default parsing logic (current implementation)
                #    ...
                # For now, we'll keep the existing general parsing logic:
                content_blocks = None
                target_data_obj = raw_event_data
                
                if isinstance(raw_event_data, dict) and 'data' in raw_event_data:
                    nested_data = raw_event_data['data']
                    if isinstance(nested_data, dict) and 'content' in nested_data and 'isError' in nested_data:
                        target_data_obj = nested_data 
                        is_tool_response = True # Set flag here
                    else:
                        target_data_obj = nested_data
                
                if hasattr(target_data_obj, 'content') and isinstance(getattr(target_data_obj, 'content', None), list):
                    content_blocks = target_data_obj.content
                elif isinstance(target_data_obj, dict) and 'content' in target_data_obj and isinstance(target_data_obj.get('content'), list):
                    content_blocks = target_data_obj['content']
                # --- Fallback: Check for 'messages' list --- 
                elif hasattr(target_data_obj, 'messages') and isinstance(getattr(target_data_obj, 'messages', None), list):
                    content_blocks = target_data_obj.messages
                    logger.debug("Found 'messages' attribute list (fallback).")
                elif isinstance(target_data_obj, dict) and 'messages' in target_data_obj and isinstance(target_data_obj.get('messages'), list):
                    content_blocks = target_data_obj['messages']
                    logger.debug("Found 'messages' key list (fallback).")
                elif isinstance(target_data_obj, list): # Check if target data itself is the list
                    if target_data_obj and (isinstance(target_data_obj[0], dict) or hasattr(target_data_obj[0], 'type')):
                         content_blocks = target_data_obj
                         logger.debug("Raw event data itself appears to be a list of message blocks.")

                if content_blocks:
                    extracted_texts = []
                    for block in content_blocks:
                        block_type = None
                        block_data = None
                        if isinstance(block, dict):
                            block_type = block.get('type')
                            block_data = block
                        elif hasattr(block, 'type'):
                            block_type = block.type
                            if hasattr(block, 'model_dump'): block_data = block.model_dump(mode='json')
                            elif hasattr(block, 'dict'): block_data = block.dict()
                            else: block_data = {} # Fallback
                        
                        if not isinstance(block_data, dict): continue

                        if block_type == 'tool_use':
                            tool_name = block_data.get('name')
                            parsed_details['tool_name'] = tool_name
                            tool_input = block_data.get('input')
                            try: parsed_details['tool_args'] = json.dumps(tool_input) if isinstance(tool_input, (dict, list)) else str(tool_input)
                            except TypeError: parsed_details['tool_args'] = str(tool_input)
                            if not tool_name: logger.warning(f"[{query_id or 'unknown'}] Parsed tool_use block but tool_name was missing. Block data: {block_data}")
                            # else: logger.debug(f"Parsed tool_use: Name={tool_name}, Input={parsed_details['tool_args']}") # Already logged
                        elif block_type == 'tool_result':
                            parsed_details['tool_result_id'] = block_data.get('tool_use_id')
                            result_content_raw = block_data.get('content')
                            parsed_details['tool_result_summary'] = str(result_content_raw)[:100] + '...' if result_content_raw else '[No Content]'
                            # logger.debug(...) # Already logged
                        elif block_type == 'text':
                            text_content = block_data.get('text')
                            if text_content:
                                if is_tool_response:
                                    extracted_texts.append(str(text_content).strip())
                                elif first_text_block_content is None: 
                                    first_text_block_content = str(text_content).strip()
                                    # logger.debug(...) # Already logged
                    
                    if is_tool_response and extracted_texts:
                        tool_call_result_text = "\n".join(extracted_texts)
                        parsed_details['tool_call_result'] = tool_call_result_text
                # <<< END Conditional Parsing Placeholder >>>
            except Exception as parse_err:
                 logger.warning(f"Error parsing event data details: {parse_err}", exc_info=False)
            # --- END MODIFIED PARSING ---

            # --- Determine final message to send --- 
            final_message_to_send = None
            tool_name = parsed_details.get('tool_name')
            tool_args_str = parsed_details.get('tool_args', '{}')
            
            # <<< START Conditional Message Placeholder >>>
            # Example:
            # if workflow_type == 'orchestrator' and step_type == 'Thinking':
            #    final_message_to_send = f"Orchestrator Planning..."
            # else:
            #    # Default message construction
            #    ...
            # For now, keep the existing message construction logic:
            if tool_name:
                tool_call_msg = f"[Calling tool {tool_name or 'Unknown Tool'} with args {tool_args_str}]"
                if first_text_block_content:
                    final_message_to_send = f"{first_text_block_content}\n{tool_call_msg}"
                else:
                    final_message_to_send = tool_call_msg
            elif is_tool_response and tool_call_result_text:
                 # Use the actual result text, truncated for the main message
                 result_summary = tool_call_result_text[:150] + ('... (see details)' if len(tool_call_result_text) > 150 else '')
                 final_message_to_send = f"Tool Result: {result_summary}" # Changed message format
                 if 'tool_call_result' not in parsed_details:
                     parsed_details['tool_call_result'] = tool_call_result_text
            elif first_text_block_content:
                final_message_to_send = first_text_block_content
                if 'llm_text_output' not in parsed_details: parsed_details['llm_text_output'] = first_text_block_content
            elif original_message and original_message != "send_request: response=":
                final_message_to_send = original_message
            
            if final_message_to_send is None:
                # Add agent name/namespace for better context if other messages fail
                default_context = namespace.split('.')[-1] if namespace != 'unknown' else 'Agent'
                final_message_to_send = f"{default_context}: {step_type}"
            # <<< END Conditional Message Placeholder >>>
            # --- End message determination ---

            # --- ADDED: Log parsed details and final message (Moved slightly earlier) ---
            logger.debug(f"[{query_id}] PRE-SEND CHECK - StepType: {step_type}, IsToolResponse: {is_tool_response}, ToolName: {tool_name}, FirstText: '{first_text_block_content}', ResultText: '{tool_call_result_text}'")
            logger.debug(f"[{query_id}] PRE-SEND CHECK - Parsed Details: {parsed_details}")
            logger.debug(f"[{query_id}] PRE-SEND CHECK - Final Message to Send: '{final_message_to_send[:200]}'")
            # --- END ADDED ---

            # Prepare data payload
            # Use a helper function to safely get attributes
            def get_event_attr(attr_name, default=None):
                # --- PRIORITY 1: Check specific client_session structure (tools/call) --- 
                if namespace == "mcp_agent.mcp.mcp_agent_client_session" and isinstance(raw_event_data, dict):
                    inner_data = raw_event_data.get('data', {})
                    if isinstance(inner_data, dict) and inner_data.get('method') == 'tools/call':
                        params = inner_data.get('params', {})
                        if isinstance(params, dict):
                           if attr_name == 'tool_name':
                               # Tool name is directly under params['name']
                               val = params.get('name')
                               return val if val is not None else default
                           elif attr_name == 'tool_args':
                               # Arguments are under params['arguments']
                               val = params.get('arguments') # Correct key is 'arguments' not 'args' based on log?
                               return val if val is not None else default
                           # If asking for something else, continue to other checks
                
                # --- PRIORITY 2: Check event.data object/dict --- 
                # (Keep the rest of the priority checks as they were)
                val = getattr(raw_event_data, attr_name, None) if raw_event_data else None
                if val is not None: return val
                if isinstance(raw_event_data, dict):
                    val = raw_event_data.get(attr_name)
                    if val is not None: return val
                    nested_data = raw_event_data.get('data')
                    if isinstance(nested_data, dict):
                        val = nested_data.get(attr_name)
                        if val is not None: return val
                    nested_context = raw_event_data.get('context')
                    if isinstance(nested_context, dict):
                        val = nested_context.get(attr_name)
                        if val is not None: return val
                return default

            # Prepare payload using helper
            payload_data = {
                "agent": agent_name,
                "agent_name": agent_name,  # ADDED: Include explicit agent_name field
                "step_type": step_type,
                "raw_message": original_message, # Keep original for reference
                "workflow_type": workflow_type # <<< ADDED: Include workflow type in payload
            }
            
            # --- RE-APPLY HELPER CALLS AFTER MODIFICATION --- 
            tool_name = get_event_attr('tool_name')
            if tool_name:
                payload_data['tool_name'] = tool_name
                
            tool_args = get_event_attr('tool_args')
            if tool_args:
                 try:
                    # Ensure args are JSON serializable
                    json.dumps(tool_args)
                    payload_data['tool_args'] = tool_args
                 except TypeError:
                     payload_data['tool_args'] = "<Non-serializable args>"
            
            progress_action = get_event_attr('progress_action')
            if progress_action:
                payload_data['progress_action'] = str(progress_action.value) if hasattr(progress_action, 'value') else str(progress_action)
            # --- END RE-APPLY --- 
            
            # Add parsed details (like tool_call_result, llm_text_output if parsed earlier)
            payload_data.update(parsed_details)

            payload_data['trace_id'] = getattr(event, 'trace_id', None)
            payload_data['span_id'] = getattr(event, 'span_id', None)
            payload_data['timestamp'] = event.timestamp.isoformat() if hasattr(event, 'timestamp') else None
            payload_data['namespace'] = namespace
            
            # Remove None values for cleaner output
            payload_data = {k: v for k, v in payload_data.items() if v is not None}

            # --- Determine final update type --- 
            final_update_type = "step" # Default
            if step_type == "Plan":
                final_update_type = "plan"
                # <<< ADDED: Try to parse and add plan details to data >>>
                if first_text_block_content:
                    try:
                        plan_json = json.loads(first_text_block_content)
                        payload_data['plan_details'] = plan_json # Add parsed plan to data
                        final_message_to_send = "Generated plan" # Use a clearer message
                    except json.JSONDecodeError:
                        logger.warning(f"[{query_id}] Could not parse plan JSON from planner output.")
                        payload_data['plan_details'] = first_text_block_content # Send raw text if not JSON
                        final_message_to_send = "Generated plan (raw text)"
                # <<< END ADDED >>>
            
            # --- Existing Filtering Logic --- 
            # CRITICAL: Never filter out Plan events - they should always be delivered
            if step_type == "Plan":
                logger.info(f"[{query_id}] 🚀 PLAN EVENT: Bypassing all filters to ensure delivery")
            elif step_type == "Unknown" or step_type == "Initialized": # Match the actual StepType string
                logger.debug(f"[{query_id}] Skipping WebSocket update for irrelevant step type: {step_type}")
                return
            # Skip specific internal 'Calling Tool' events
            elif step_type == "Calling Tool" and \
                 (namespace == "mcp_agent.mcp.mcp_agent_client_session" or \
                  namespace == "mcp_agent.mcp.mcp_aggregator"): # Also skip aggregator tool calls
                logger.debug(f"[{query_id}] Skipping WebSocket update for internal framework tool call event from namespace {namespace}.")
                return
            # Skip "Calling Tool" if the message indicates it's a human input request
            elif step_type == "Calling Tool" and original_message and "Requesting tool call" in original_message:
                logger.debug(f"[{query_id}] Skipping WebSocket update for 'Calling Tool' event that is general tool calling. Original message: '{original_message[:100]}...'")
                return
            # --- END Filtering Logic --- 

            # <<< ADDED: Log the final_update_type before sending >>>
            logger.info(f"[{query_id}] Transport determined final_update_type='{final_update_type}' for StepType='{step_type}', Workflow='{workflow_type}'")
            # <<< END ADDED >>>

            # Send the update using the manager
            await self.websocket_manager.send_consolidated_update(
                query_id=query_id, # Use the query_id found
                update_type=final_update_type, # <<< Use determined update type
                message=final_message_to_send, # Use the potentially updated message
                data=payload_data, # Use the enriched payload
                workflow_type=workflow_type # Pass workflow_type down
            )

        except Exception as e:
            logger.error(f"Error in WebSocketEventTransport sending event (Query ID: '{query_id or 'unknown'}'): {str(e)}", exc_info=True) 