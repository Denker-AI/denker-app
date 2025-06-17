"""
Coordinator Agents Configuration - Configuration for all agent types in the system.

This module contains the configuration for all agent types, including their instructions
and server names, as well as functionality to create and manage agents.
"""

import os
import logging
from typing import Dict, Any, Optional, List, Callable
import uuid
import json
from datetime import datetime

from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm import RequestParams
from mcp_agent.workflows.orchestrator.orchestrator import Orchestrator
from mcp_agent.workflows.router.router_llm import LLMRouter
from mcp_agent.workflows.llm.augmented_llm_anthropic import AnthropicAugmentedLLM
from mcp_agent.workflows.router.router_llm_anthropic import AnthropicLLMRouter
from mcp_agent.logging.logger import get_logger

from .coordinator_memory import CoordinatorMemory



# --- ADDED: Custom orchestrator that overrides _get_full_plan to inject strict planning rules ---
from mcp_agent.workflows.orchestrator.orchestrator import Orchestrator
from mcp_agent.workflows.orchestrator.orchestrator_models import Plan

# NOTE: FixedAnthropicAugmentedLLM will be passed as parameter to avoid circular import

class StrictOrchestrator(Orchestrator):
    """Custom orchestrator that patches the planning prompt to prevent premature plan completion."""
    
    def __init__(self, *args, fixed_llm_class=None, **kwargs):
        # Initialize the parent orchestrator
        super().__init__(*args, **kwargs)
        
        # Replace the planner with our fixed version if provided
        if fixed_llm_class and hasattr(self, 'planner') and self.planner:
            # Get the current planner's configuration
            current_config = {
                'agent': getattr(self.planner, 'agent', None),
                'server_names': getattr(self.planner, 'server_names', None),
                'instruction': getattr(self.planner, 'instruction', None),
                'name': getattr(self.planner, 'name', None),
                'default_request_params': getattr(self.planner, 'default_request_params', None),
                'context': getattr(self.planner, 'context', None),
            }
            # Create new fixed planner with same config
            self.planner = fixed_llm_class(**{k: v for k, v in current_config.items() if v is not None})
            logger.info("StrictOrchestrator: Replaced planner with FixedAnthropicAugmentedLLM")
    
    async def _get_full_plan(
        self,
        objective: str,
        plan_result,
        request_params: RequestParams | None = None,
    ) -> Plan:
        """Generate full plan with strict completion logic enforced."""
        params = self.get_request_params(request_params)

        agents = "\n".join(
            [
                f"{idx}. {self._format_agent_info(agent)}"
                for idx, agent in enumerate(self.agents, 1)
            ]
        )

        # FIXED: Use our custom prompt template that includes STRICT_PLANNER_INSTRUCTION
        from mcp_agent.workflows.orchestrator.orchestrator_prompts import PLAN_RESULT_TEMPLATE
        
        # Format the plan result using the same template as the original
        plan_result_str = PLAN_RESULT_TEMPLATE.format(
            plan_objective=plan_result.objective,
            steps_str="\n".join([
                f"Step {i+1}: {step.result}" 
                for i, step in enumerate(plan_result.step_results)
            ]) if plan_result.step_results else "No steps executed yet",
            plan_status="In Progress" if plan_result.step_results else "Starting",
            plan_result=plan_result.result or "None"
        )
        
        # Create our custom prompt with minimal strict completion logic patch
        custom_prompt = f"""You are tasked with orchestrating a plan to complete an objective.
You can analyze results from the previous steps already executed to decide if the objective is complete.
Your plan must be structured in sequential steps, with each step containing independent parallel subtasks.

**EMOJI GUIDELINES:** 📋 Use relevant emojis in your plan descriptions to make them more readable and organized. Examples: 🔍 for research, ✍️ for writing, 📊 for analysis, 🎯 for objectives, ✅ for completion, 📝 for tasks, etc.

CRITICAL COMPLETION LOGIC:
- When you see "No steps executed yet" → ALWAYS set is_complete=false
- When you see "Progress So Far: (empty)" → ALWAYS set is_complete=false  
- ONLY set is_complete=true when you see ACTUAL executed steps with REAL results that achieve the objective

Objective: {objective}

{plan_result_str}

If the previous results achieve the objective, return is_complete=True.
Otherwise, generate remaining steps needed.

You have access to the following MCP Servers (which are collections of tools/functions),
and Agents (which are collections of servers):

Agents:
{agents}

Generate a plan with all remaining steps needed.
Steps are sequential, but each Step can have parallel subtasks.
For each Step, specify a description of the step and independent subtasks that can run in parallel.
For each subtask specify:
    1. Clear description of the task that an LLM can execute  
    2. Name of 1 Agent OR List of MCP server names to use for the task
    
Return your response in the following JSON structure:
    {{
        "steps": [
            {{
                "description": "Description of step 1",
                "tasks": [
                    {{
                        "description": "Description of task 1",
                        "agent": "agent_name"  # For AgentTask
                    }},
                    {{
                        "description": "Description of task 2", 
                        "agent": "agent_name2"
                    }}
                ]
            }}
        ],
        "is_complete": false
    }}

You must respond with valid JSON only, with no triple backticks. No markdown formatting.
No extra text. Do not wrap in ```json code fences."""

        # CRITICAL: Call the planner's generate_structured method to ensure events are emitted
        # This is what triggers the plan events that the frontend can intercept
        plan = await self.planner.generate_structured(
            message=custom_prompt,
            response_model=Plan,
            request_params=params,
        )

        return plan

# --- ADDED: Agent-specific wrapper for shared cache LLM ---
class AgentSpecificWrapper:
    """
    FIXED: Proper wrapper that handles system instructions correctly.
    The base LLM only uses self.instruction or params.systemPrompt for the system parameter.
    This wrapper sets its own instruction property to include agent-specific instructions.
    
    **Logger Strategy:**
    - Module logger: Standard Python logging for internal debugging
    - Agent logger: MCP event logger for WebSocket events to frontend
    - Context injection: Override logger methods to inject agent context
    """
    def __init__(self, base_llm, agent_name: str, agent_instruction: str = ""):
        self.base_llm = base_llm
        self.agent_name = agent_name
        self.agent_instruction = agent_instruction
        
        # ADDED: Cache the agent-specific logger for efficiency
        self._agent_logger = None
        self._agent_namespace = f"mcp_agent.workflows.llm.augmented_llm_anthropic.{self.agent_name}"
        # --- END ADDED ---
        
        # ADDED: Override context agent name if base LLM has context
        if hasattr(self.base_llm, 'context') and self.base_llm.context:
            try:
                # Override the SharedCacheLLMAggregator name with the actual agent name
                if hasattr(self.base_llm.context, 'agent_name'):
                    original_agent_name = getattr(self.base_llm.context, 'agent_name', 'Unknown')
                    self.base_llm.context.agent_name = self.agent_name
                    logger.debug(f"AgentSpecificWrapper: Overrode context agent_name from '{original_agent_name}' to '{self.agent_name}'")
                else:
                    setattr(self.base_llm.context, 'agent_name', self.agent_name)
                    logger.debug(f"AgentSpecificWrapper: Set context agent_name to '{self.agent_name}'")
            except Exception as e:
                logger.warning(f"AgentSpecificWrapper: Failed to override context agent_name for '{self.agent_name}': {e}")
        # --- END ADDED ---
        
        logger.debug(f"AgentSpecificWrapper created for '{agent_name}' with instruction: {agent_instruction[:100]}...")
        
        # FIXED: Set the instruction property that the base LLM will use
        self._combined_instruction = None
        self._update_combined_instruction()
    
    def _get_agent_logger(self):
        """Get or create the cached agent-specific logger for WebSocket events."""
        if self._agent_logger is None:
            self._agent_logger = get_logger(self._agent_namespace)
        return self._agent_logger
    
    # ADDED: Logger wrapper to inject agent context
    def _create_logger_wrapper(self, original_logger):
        """Create a logger wrapper that injects agent context into all log calls."""
        from mcp_agent.logging.events import EventContext
        
        class LoggerWrapper:
            def __init__(self, original_logger, agent_name):
                self._original = original_logger
                self._agent_name = agent_name
                # Copy all attributes from original logger
                for attr in dir(original_logger):
                    if not attr.startswith('_') and not callable(getattr(original_logger, attr)):
                        setattr(self, attr, getattr(original_logger, attr))
            
            def _inject_context(self, context=None, **data):
                """Inject agent context into log call."""
                # Create or enhance context with agent information
                if context is None:
                    context = EventContext()
                
                # Add agent information to context (EventContext supports extra fields)
                context.agent_name = self._agent_name
                context.real_agent = self._agent_name
                
                # Also add to data for backward compatibility (create copy to avoid modifying original)
                enhanced_data = dict(data)
                enhanced_data['agent_name'] = self._agent_name
                enhanced_data['real_agent'] = self._agent_name
                
                return context, enhanced_data
            
            def _override_namespace_temporarily(self, method_name, *args, **kwargs):
                """Helper to temporarily override logger namespace for any method."""
                # Store original namespace if available
                original_namespace = getattr(self._original, 'namespace', None)
                
                # Create agent-specific namespace
                agent_namespace = f"mcp_agent.workflows.llm.augmented_llm_anthropic.{self._agent_name}"
                
                # Override namespace if the logger supports it
                if hasattr(self._original, 'namespace'):
                    self._original.namespace = agent_namespace
                
                try:
                    method = getattr(self._original, method_name)
                    return method(*args, **kwargs)
                finally:
                    # Restore original namespace
                    if original_namespace is not None and hasattr(self._original, 'namespace'):
                        self._original.namespace = original_namespace
            
            def debug(self, message, name=None, context=None, **data):
                context, data = self._inject_context(context, **data)
                return self._override_namespace_temporarily('debug', message, name=name, context=context, **data)
            
            def info(self, message, name=None, context=None, **data):
                context, data = self._inject_context(context, **data)
                return self._override_namespace_temporarily('info', message, name=name, context=context, **data)
            
            def warning(self, message, name=None, context=None, **data):
                context, data = self._inject_context(context, **data)
                return self._override_namespace_temporarily('warning', message, name=name, context=context, **data)
            
            def error(self, message, name=None, context=None, **data):
                context, data = self._inject_context(context, **data)
                return self._override_namespace_temporarily('error', message, name=name, context=context, **data)
            
            def progress(self, message, name=None, percentage=None, context=None, **data):
                context, data = self._inject_context(context, **data)
                return self._override_namespace_temporarily('progress', message, name=name, percentage=percentage, context=context, **data)
            
            def event(self, etype, ename, message, context, data):
                # For direct event calls, also inject context
                if context is None:
                    context = EventContext()
                
                # CRITICAL FIX: Override the namespace to use the actual agent name
                # The original logger's namespace is tied to "SharedCacheLLMAggregator"
                # but we want events to appear with the real agent name
                context.agent_name = self._agent_name
                context.real_agent = self._agent_name
                
                # Create copy of data to avoid modifying original
                enhanced_data = dict(data) if isinstance(data, dict) else {}
                enhanced_data['agent_name'] = self._agent_name
                enhanced_data['real_agent'] = self._agent_name
                
                # HACK: Temporarily override the original logger's namespace
                # Store original namespace if available
                original_namespace = getattr(self._original, 'namespace', None)
                
                # Create agent-specific namespace
                agent_namespace = f"mcp_agent.workflows.llm.augmented_llm_anthropic.{self._agent_name}"
                
                # Override namespace if the logger supports it
                if hasattr(self._original, 'namespace'):
                    self._original.namespace = agent_namespace
                
                try:
                    result = self._original.event(etype, ename, message, context, enhanced_data)
                finally:
                    # Restore original namespace
                    if original_namespace is not None and hasattr(self._original, 'namespace'):
                        self._original.namespace = original_namespace
                
                return result
            
            def __getattr__(self, name):
                """Delegate all other attributes to the original logger."""
                try:
                    return getattr(self._original, name)
                except AttributeError:
                    raise AttributeError(f"LoggerWrapper has no attribute '{name}'")
        
        return LoggerWrapper(original_logger, self.agent_name)
    # --- END ADDED ---
    
    def _update_combined_instruction(self):
        """Update the combined instruction including agent-specific context."""
        # FIXED: Safe base instruction access
        base_instruction = ''
        if hasattr(self, 'base_llm') and self.base_llm is not None:
            base_instruction = getattr(self.base_llm, 'instruction', '') or ''
        # --- END FIXED ---
        
        if base_instruction:
            self._combined_instruction = f"You are {self.agent_name}. {self.agent_instruction}\n\n{base_instruction}"
        else:
            self._combined_instruction = f"You are {self.agent_name}. {self.agent_instruction}"
        logger.debug(f"Combined instruction for '{self.agent_name}': {self._combined_instruction[:200]}...")
    
    @property
    def instruction(self):
        """Return the combined instruction that includes agent-specific context."""
        return self._combined_instruction
    
    @instruction.setter  
    def instruction(self, value):
        """Allow setting the base instruction and update combined instruction."""
        # FIXED: Safe instruction setting
        if hasattr(self, 'base_llm') and self.base_llm is not None:
            self.base_llm.instruction = value
        else:
            logger.warning(f"AgentSpecificWrapper for '{self.agent_name}': Cannot set instruction, base_llm is not available")
        # --- END FIXED ---
        self._update_combined_instruction()
    
    def _prepare_messages_for_agent(self, message):
        """Prepare messages by filtering out any system messages from the messages array."""
        try:
            if not message:
                return message
            
            # Handle string input (most common from orchestrator)
            if isinstance(message, str):
                # Return just the user message - system handled by instruction property
                return [{"role": "user", "content": message}]
            
            # Handle list of messages
            if isinstance(message, list) and message:
                # Filter out any system messages - they should not be in messages array
                filtered_messages = []
                
                for msg in message:
                    if isinstance(msg, dict):
                        # Skip any existing system messages
                        if msg.get('role') == 'system':
                            logger.debug(f"AgentSpecificWrapper: Filtering out system message from messages array for agent '{self.agent_name}'")
                            continue
                        else:
                            filtered_messages.append(msg)
                    else:
                        filtered_messages.append(msg)
                
                return filtered_messages if filtered_messages else [{"role": "user", "content": "Hello"}]
            
            # Handle single message dict
            if isinstance(message, dict):
                # If it's a system message, filter it out and create fallback
                if message.get('role') == 'system':
                    logger.debug(f"AgentSpecificWrapper: Filtering out single system message for agent '{self.agent_name}'")
                    return [{"role": "user", "content": "Hello"}]  # Fallback user message
                else:
                    return [message]
            
            # Fallback: return as-is
            return message
        except Exception as e:
            logger.error(f"Error in _prepare_messages_for_agent for '{self.agent_name}': {e}")
            return message
    
    async def generate_str(self, message, **kwargs):
        """Generate response with agent-specific context via instruction property."""
        try:
            logger.debug(f"AgentSpecificWrapper.generate_str called for '{self.agent_name}' with message type: {type(message)}")
            processed_messages = self._prepare_messages_for_agent(message)
            
            # ADDED: Ensure context agent name is properly set before each call
            if hasattr(self.base_llm, 'context') and self.base_llm.context:
                try:
                    # Re-inject agent name in case context was reset
                    if hasattr(self.base_llm.context, 'agent_name'):
                        self.base_llm.context.agent_name = self.agent_name
                    else:
                        setattr(self.base_llm.context, 'agent_name', self.agent_name)
                    logger.debug(f"AgentSpecificWrapper.generate_str: Ensured context agent_name='{self.agent_name}'")
                except Exception as e:
                    logger.warning(f"AgentSpecificWrapper.generate_str: Failed to set context agent_name for '{self.agent_name}': {e}")
            # --- END ADDED ---
            
            # MODIFIED: Override logger with wrapper that injects context
            original_logger = getattr(self.base_llm, 'logger', None)
            if original_logger:
                self.base_llm.logger = self._create_logger_wrapper(original_logger)
                logger.debug(f"AgentSpecificWrapper: Temporarily set base_llm logger to wrapper with agent context: {self.agent_name}")
            # --- END MODIFIED ---
            
            # FIXED: Safe instruction handling
            original_instruction = None
            if hasattr(self, 'base_llm') and self.base_llm is not None and hasattr(self.base_llm, 'instruction'):
                original_instruction = getattr(self.base_llm, 'instruction', None)
                self.base_llm.instruction = self._combined_instruction # Set combined instruction
            
            try:
                # FIXED: Safe method call with existence check
                if hasattr(self.base_llm, 'generate_str'):
                    result = await self.base_llm.generate_str(processed_messages, **kwargs)
                else:
                    raise AttributeError(f"Base LLM for agent '{self.agent_name}' does not have generate_str method")
                # --- END FIXED ---
            finally:
                # Restore original instruction safely
                if original_instruction is not None and hasattr(self.base_llm, 'instruction'):
                    self.base_llm.instruction = original_instruction
                
                # MODIFIED: Restore original logger
                if original_logger and hasattr(self.base_llm, 'logger'):
                    self.base_llm.logger = original_logger
                    logger.debug(f"AgentSpecificWrapper: Restored original base_llm logger for '{self.agent_name}'")
                # --- END MODIFIED ---
                
            logger.debug(f"AgentSpecificWrapper.generate_str completed for '{self.agent_name}'")
            return result
        except Exception as e:
            logger.error(f"Error in AgentSpecificWrapper.generate_str for agent '{self.agent_name}': {e}")
            # FIXED: Safe fallback with method existence check
            if hasattr(self, 'base_llm') and self.base_llm is not None and hasattr(self.base_llm, 'generate_str'):
                # MODIFIED: Override logger for fallback case too
                original_logger_fallback = getattr(self.base_llm, 'logger', None)
                if original_logger_fallback:
                    self.base_llm.logger = self._create_logger_wrapper(original_logger_fallback)
                # --- END MODIFIED ---
                
                original_instruction_fallback = getattr(self.base_llm, 'instruction', None)
                if hasattr(self.base_llm, 'instruction'):
                    self.base_llm.instruction = self._combined_instruction 
                try:
                    result = await self.base_llm.generate_str(message, **kwargs)
                finally:
                    if original_instruction_fallback is not None and hasattr(self.base_llm, 'instruction'):
                        self.base_llm.instruction = original_instruction_fallback
                    
                    # MODIFIED: Restore logger in fallback case
                    if original_logger_fallback and hasattr(self.base_llm, 'logger'):
                        self.base_llm.logger = original_logger_fallback
                    # --- END MODIFIED ---
                return result
            else:
                raise AttributeError(f"Cannot fallback: base_llm for agent '{self.agent_name}' does not have generate_str method")
            # --- END FIXED ---
    
    async def generate(self, message, **kwargs):
        """Generate response with agent-specific context via instruction property."""
        try:
            logger.debug(f"AgentSpecificWrapper.generate called for '{self.agent_name}'")
            processed_messages = self._prepare_messages_for_agent(message)
            
            # MODIFIED: Override logger with wrapper that injects context
            original_logger = getattr(self.base_llm, 'logger', None)
            if original_logger:
                self.base_llm.logger = self._create_logger_wrapper(original_logger)
                logger.debug(f"AgentSpecificWrapper: Temporarily set base_llm logger to wrapper with agent context: {self.agent_name}")
            # --- END MODIFIED ---
            
            # FIXED: Safe instruction handling
            original_instruction = None
            if hasattr(self, 'base_llm') and self.base_llm is not None and hasattr(self.base_llm, 'instruction'):
                original_instruction = getattr(self.base_llm, 'instruction', '')
                self.base_llm.instruction = self._combined_instruction
            # --- END FIXED ---
            
            try:
                # FIXED: Safe method call with existence check
                if hasattr(self.base_llm, 'generate'):
                    result = await self.base_llm.generate(processed_messages, **kwargs)
                    logger.debug(f"AgentSpecificWrapper.generate completed for '{self.agent_name}'")
                    return result
                else:
                    raise AttributeError(f"Base LLM for agent '{self.agent_name}' does not have generate method")
                # --- END FIXED ---
            finally:
                # Restore original instruction safely
                if original_instruction is not None and hasattr(self.base_llm, 'instruction'):
                    self.base_llm.instruction = original_instruction
                
                # MODIFIED: Restore original logger
                if original_logger and hasattr(self.base_llm, 'logger'):
                    self.base_llm.logger = original_logger
                    logger.debug(f"AgentSpecificWrapper: Restored original base_llm logger for '{self.agent_name}'")
                # --- END MODIFIED ---
                
        except Exception as e:
            logger.error(f"Error in AgentSpecificWrapper.generate for agent '{self.agent_name}': {e}")
            # FIXED: Safe fallback
            if hasattr(self, 'base_llm') and self.base_llm is not None and hasattr(self.base_llm, 'generate'):
                # MODIFIED: Override logger for fallback case too
                original_logger_fallback = getattr(self.base_llm, 'logger', None)
                if original_logger_fallback:
                    self.base_llm.logger = self._create_logger_wrapper(original_logger_fallback)
                # --- END MODIFIED ---
                
                try:
                    result = await self.base_llm.generate(message, **kwargs)
                finally:
                    # MODIFIED: Restore logger in fallback case
                    if original_logger_fallback and hasattr(self.base_llm, 'logger'):
                        self.base_llm.logger = original_logger_fallback
                    # --- END MODIFIED ---
                return result
            else:
                raise AttributeError(f"Cannot fallback: base_llm for agent '{self.agent_name}' does not have generate method")
            # --- END FIXED ---
    
    async def generate_structured(self, message, response_model, **kwargs):
        """Generate structured response with agent-specific context via instruction property."""
        try:
            logger.debug(f"AgentSpecificWrapper.generate_structured called for '{self.agent_name}'")
            processed_messages = self._prepare_messages_for_agent(message)
            
            # ADDED: Ensure context agent name is properly set before each call
            if hasattr(self.base_llm, 'context') and self.base_llm.context:
                try:
                    # Re-inject agent name in case context was reset
                    if hasattr(self.base_llm.context, 'agent_name'):
                        self.base_llm.context.agent_name = self.agent_name
                    else:
                        setattr(self.base_llm.context, 'agent_name', self.agent_name)
                    logger.debug(f"AgentSpecificWrapper.generate_structured: Ensured context agent_name='{self.agent_name}'")
                except Exception as e:
                    logger.warning(f"AgentSpecificWrapper.generate_structured: Failed to set context agent_name for '{self.agent_name}': {e}")
            # --- END ADDED ---
            
            # MODIFIED: Override logger with wrapper that injects context
            original_logger = getattr(self.base_llm, 'logger', None)
            if original_logger:
                self.base_llm.logger = self._create_logger_wrapper(original_logger)
                logger.debug(f"AgentSpecificWrapper: Temporarily set base_llm logger to wrapper with agent context: {self.agent_name}")
            # --- END MODIFIED ---
            
            # FIXED: Safe instruction handling
            original_instruction = None
            if hasattr(self, 'base_llm') and self.base_llm is not None and hasattr(self.base_llm, 'instruction'):
                original_instruction = getattr(self.base_llm, 'instruction', '')
                self.base_llm.instruction = self._combined_instruction
            # --- END FIXED ---
            
            try:
                # FIXED: Safe method call with existence check
                if hasattr(self.base_llm, 'generate_structured'):
                    result = await self.base_llm.generate_structured(processed_messages, response_model, **kwargs)
                    logger.debug(f"AgentSpecificWrapper.generate_structured completed for '{self.agent_name}'")
                    return result
                else:
                    raise AttributeError(f"Base LLM for agent '{self.agent_name}' does not have generate_structured method")
                # --- END FIXED ---
            finally:
                # Restore original instruction safely
                if original_instruction is not None and hasattr(self.base_llm, 'instruction'):
                    self.base_llm.instruction = original_instruction
                
                # MODIFIED: Restore original logger
                if original_logger and hasattr(self.base_llm, 'logger'):
                    self.base_llm.logger = original_logger
                    logger.debug(f"AgentSpecificWrapper: Restored original base_llm logger for '{self.agent_name}'")
                # --- END MODIFIED ---
                
        except Exception as e:
            logger.error(f"Error in AgentSpecificWrapper.generate_structured for agent '{self.agent_name}': {e}")
            # FIXED: Safe fallback
            if hasattr(self, 'base_llm') and self.base_llm is not None and hasattr(self.base_llm, 'generate_structured'):
                # MODIFIED: Override logger for fallback case too
                original_logger_fallback = getattr(self.base_llm, 'logger', None)
                if original_logger_fallback:
                    self.base_llm.logger = self._create_logger_wrapper(original_logger_fallback)
                # --- END MODIFIED ---
                
                try:
                    result = await self.base_llm.generate_structured(message, response_model, **kwargs)
                finally:
                    # MODIFIED: Restore logger in fallback case
                    if original_logger_fallback and hasattr(self.base_llm, 'logger'):
                        self.base_llm.logger = original_logger_fallback
                    # --- END MODIFIED ---
                return result
            else:
                raise AttributeError(f"Cannot fallback: base_llm for agent '{self.agent_name}' does not have generate_structured method")
            # --- END FIXED ---
    
    def __getattr__(self, name):
        """Delegate all other attributes to the base LLM."""
        # FIXED: Safe delegation with AttributeError prevention
        if hasattr(self, 'base_llm') and self.base_llm is not None:
            try:
                return getattr(self.base_llm, name)
            except AttributeError:
                # Re-raise with more specific error message
                raise AttributeError(f"Neither AgentSpecificWrapper nor its base LLM has attribute '{name}'")
        else:
            raise AttributeError(f"AgentSpecificWrapper has no base_llm to delegate '{name}' to")
        # --- END FIXED ---
# --- END ADDED ---

logger = logging.getLogger(__name__)

# Get API keys and settings from environment variables
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")

# Define the list of required agents for the system
REQUIRED_AGENTS = ["decider", "researcher", "creator", "editor"]

class AgentConfiguration:
    """
    Configuration and management for all agent types.
    
    This class handles the creation, configuration, and management of agents,
    orchestrators, and routers for the coordinator.
    """
    
    def __init__(self, websocket_manager=None, memory=None, create_llm_fn: Optional[Callable] = None):
        """
        Initialize the agent configuration.
        
        Args:
            websocket_manager: WebSocket manager for sending updates
            memory: Memory manager for storing knowledge
            create_llm_fn: Function to create LLM instances for agents
        """
        self.websocket_manager = websocket_manager
        self.memory = memory
        self.create_llm_fn = create_llm_fn # Store the LLM creation function
        
        # Entity tracking for different contexts
        self.task_entities = {}
        self.query_entities = {}
        self.session_entities = {}
        
        # Agent configuration dictionary
        self.agent_configs = {
            "decider": {
                "name": "decider",
                "instruction": """You are a decider agent for Denker, which analyzes user queries and conversation history to determine which workflow should be used.

                **EMOJI GUIDELINES:** 🎯 Use relevant emojis in your explanations to make them more readable and engaging. Examples: 🔍 for research, ✍️ for writing, 📊 for data analysis, 🤔 for decision-making, etc.

                **CRITICAL:** Analyze the **entire message history provided, to avoid asking for clarification**.

                **Contextual Keywords:** Pay close attention to user phrasing like "last file", "earlier conversation", "the document", "this summary", etc. These phrases **require** you to use the conversation history to identify the specific item being referenced before making any decision or asking for clarification.

                1. Classify the user's **underlying request** (considering the full history, especially when contextual keywords are used) into:
                    - case 1: (simple) Simple conversations, questions about Denker, or other simple tasks
                    - case 2: (router) Single-focus tasks that can be handled by ONE agent (research only, write only, edit only, etc.)
                    - case 3: (orchestrator) Complex tasks requiring MULTIPLE SEQUENTIAL STEPS with different agents
                    
                **ORCHESTRATOR INDICATORS** (case 3):
                • Tasks requiring research AND writing (e.g., "write a report about X", "create an analysis of Y")
                • Tasks with explicit multi-step language ("research and write", "analyze and summarize", "investigate and report")
                • Content creation requests that need comprehensive research first
                • Tasks requiring both information gathering and document creation
                • Requests for "comprehensive", "detailed", "thorough" content that implies research + writing
                • Any task that would naturally require: research → organize → write → (optionally) edit
                
                **ROUTER INDICATORS** (case 2):
                • Pure research requests ("find information about X", "search for Y")
                • Pure writing requests with provided information ("write this content", "edit this document")
                • Single-tool tasks ("create a chart", "convert this file")
                • Quick lookups or specific information retrieval
                2. If the query is about Denker itself, provide a specific response based on all the denker agents and their capabilities.
                3. **Handling Clarification:**
                   - **Search History First:** Before deciding clarification is needed, actively search the provided message history for information that might resolve potential ambiguities in the user's latest request (e.g., if the user asks about "the file", check history for recently mentioned files).
                   - If the history shows you **previously asked for clarification**, and the **most recent user message appears to answer that clarification**, DO NOT ask for clarification again. Use the provided answer and the full history context to proceed with classifying the original request (usually case 2 or 3).
                   - Only identify a need for clarification (`needs_clarification: true`) if the user's request remains genuinely ambiguous **after considering the entire history** and the history does not contain the necessary clarifying details.
                   - If clarification is truly needed, generate concise and specific questions.
                   - **Constraint:** If you determine `needs_clarification: true`, you **MUST NOT** set `workflow_type: "simple"`. The workflow must be `router` or `orchestrator`.
                4. **IMPORTANT RULE:** Queries marked as originating from the **Intention Agent** (check the input source) **MUST NOT** be classified as `simple`. They **MUST** be classified as either `router` (case 2) or `orchestrator` (case 3).
                5. For queries originally from Main Window, you can choose any workflow type.

                Respond with valid JSON only:
                {
                "case": 1|2|3,
                "workflow_type": "simple|router|orchestrator",
                "explanation": "Briefly explain why this workflow was chosen based on the request and history.",
                "simple_response": "Direct response ONLY for genuinely simple queries (case 1) that don't require further agent work.",
                "needs_clarification": true|false,
                "clarifying_questions": ["Question 1", "Question 2"]
                }""",
                "server_names": [],  # Decider doesn't need external services
                "model": "claude-3-5-haiku-20241022"
            },

            "researcher": {
                "name": "researcher",
                "instruction": """You are a focused research agent for Denker. Your ONLY job is to gather raw information and provide it with proper citations. You do NOT write content, create documents, or format results - you only research.

                **EMOJI GUIDELINES:** 🔍 Use relevant emojis to make your research findings more readable and organized. Examples: 🔍 for search results, 📊 for data, 💡 for insights, 📚 for sources, ⚠️ for limitations, etc.

                **CRITICAL FILE-FIRST RESEARCH PRIORITY:**
                📁 **WHEN FILES ARE ATTACHED - USE QDRANT ONLY, NO WEB SEARCH**
                • If the user has attached files to their message, prioritize searching these files using Qdrant
                • Do NOT use web search when files are attached - focus on user's provided materials
                • Only search within the attached documents and related content in Qdrant
                • The user has provided specific files because they want answers from THOSE files, not general web information
                • If information is not found in attached files, clearly state this limitation rather than searching the web

                **STRICT SCOPE - Research ONLY:**
                • **Web Research:** Search and fetch online information with citations (ONLY when NO files attached)
                  - **SUMMARIZE web search results**: Don't copy entire articles - extract key points, data, and quotes
                  - Provide concise summaries of lengthy web content with proper citations
                • **Local Research:** Find information in user files using Qdrant and filesystem (PRIORITY when files attached)
                • **Information Extraction:** Extract relevant facts, data, and quotes
                • **Citation Provision:** Provide proper source citations for all findings

                **What You DO:**
                ✅ Search for information on requested topics
                ✅ Extract relevant facts, data, quotes, and insights  
                ✅ **SUMMARIZE lengthy web search results** - extract key points instead of copying entire articles
                ✅ Provide proper citations: `[1](url)` or `[1](filepath:/path/to/file)`
                ✅ Note information gaps or limitations
                ✅ Present findings as raw research data
                ✅ **PRIORITIZE Qdrant searches when files are attached**
                ✅ **AVOID web search when user has provided specific files**

                **What You DO NOT Do:**
                ❌ Write articles, reports, or documents
                ❌ Create outlines or structure content
                ❌ Format research into polished presentations
                ❌ Make recommendations or conclusions
                ❌ Use markdown-editor or filesystem for content creation
                ❌ **Web search when files are attached (use Qdrant instead)**

                **Simple Research Output Format:**
                Present your findings as bullet-pointed research data with citations:
                • Key fact/insight from source [1](citation)
                • Another finding from different source [2](citation)
                • Relevant quote: "quote text" [3](citation)

                **Sources:** 
                [1] Source Title - URL/filepath
                [2] Source Title - URL/filepath

                Your role ends when you provide the raw research. Content creation is handled by other agents.""",
                "server_names": ["fetch", "websearch", "qdrant", "filesystem"],
                "model": "claude-3-7-sonnet-20250219"
            },
            "creator": {
                "name": "creator",
                "instruction": """You are a content writer for Denker. Your job is to write content based on provided research or requirements. You focus on writing quality content - no heavy editing, no research gathering.

                **EMOJI GUIDELINES:** ✍️ Use relevant emojis to make your content more engaging and easier to read. Examples: ✍️ for writing, 📝 for documents, 📊 for charts, 🎯 for objectives, ✅ for completed tasks, 📁 for file operations, etc.

                **CRITICAL SECURITY MODEL - WORKSPACE-FIRST APPROACH:**
                🔒 **ALL WORK HAPPENS IN WORKSPACE FIRST** 🔒
                • You can ONLY create/edit files in workspace: `/tmp/dnker_workspace/default/filename.md`
                • NEVER attempt to write directly to user folders (security violation)
                • Use simple filenames in workspace: `report.md`, `analysis.md`
                • Final conversion happens directly to user's desired location

                **MANDATORY WORKFLOW - ALWAYS FOLLOW THIS SEQUENCE:**
                1. **Create content in workspace**: Use markdown-editor to create content in workspace (e.g., report.md)
                2. **🚨 CRITICAL: ALWAYS show live preview FIRST** 🚨: Use `markdown-editor.live_preview` to display the content to user - THIS IS MANDATORY, NEVER SKIP
                3. **Convert directly to user location**: Use `markdown-editor.convert_from_md` with destination path to convert directly to user's preferred format and location
                4. **ALWAYS provide ABSOLUTE PATH**: Always provide the complete absolute path of the final file

                **WORKFLOW EXAMPLE:**
                User: "Write a report.docx and save to Downloads"
                1. Create in the workspace: report.md` using markdown-editor
                2. Work on content in workspace/report.md`
                3. **MANDATORY** - Use `markdown-editor.live_preview` to show results to user
                4. Convert directly: `markdown-editor.convert_from_md(source="/tmp/denker_workspace/default/report.md", output_format="docx", destination="/Users/username/Downloads/report.docx")`
                5. You: **ALWAYS provide ABSOLUTE PATH**: "Final file saved to: `/Users/username/Downloads/report.docx`"

                **STRICT SCOPE - Writing ONLY:**
                • **Content Writing:** Transform research into well-structured written content
                • **Basic Organization:** Create logical document structure and flow
                • **Visual Integration:** Add charts/visuals when specifically requested
                • **Document Creation:** Use markdown-editor to create and preview documents

                **What You DO:**
                ✅ Write articles, reports, documents from scratch IN WORKSPACE
                ✅ Transform research data into readable content
                ✅ Create basic document structure (headers, sections, paragraphs)
                ✅ Incorporate provided citations and sources appropriately
                ✅ Add charts/visuals when explicitly requested by user
                ✅ **🚨 CRITICAL: ALWAYS use markdown-editor.live_preview to show final content to user BEFORE converting** 🚨
                ✅ Use markdown-editor.convert_from_md to convert directly to user's preferred format and location
                ✅ **ALWAYS provide the complete absolute path of the final file**

                **What You DO NOT Do:**
                ❌ Conduct research (use provided research data)
                ❌ Heavy grammar/style editing (basic grammar only)
                ❌ Fact-checking or verification (trust provided research)
                ❌ Format optimization or professional styling
                ❌ Try to edit files outside workspace (security violation)
                ❌ Skip live preview step (🚨 ABSOLUTELY FORBIDDEN - MANDATORY requirement 🚨)
                ❌ Use filesystem.move_file (outdated - convert_from_md handles destination directly)

                **Writing Standards:**
                • Write clearly and engagingly based on provided information
                • Maintain good basic grammar and readability
                • Structure content logically with appropriate headers
                • Include citations from provided research
                • Focus on content creation, not perfection

                **🚨 MANDATORY Final Steps - NEVER SKIP:** 🚨
                1. **🚨 CRITICAL: ALWAYS use `markdown-editor.live_preview`** 🚨 to show your written content to the user
                2. **Then use `markdown-editor.convert_from_md`** with destination path to convert directly to user's preferred format and location
                3. **ALWAYS provide the complete absolute path** of the final file (e.g., `/Users/username/Downloads/report.docx`)""",
                "server_names": ["filesystem", "markdown-editor"],
                "model": "claude-3-7-sonnet-20250219"
            },
            "editor": {
                "name": "editor",
                "instruction": """You are a professional editor for Denker. Your job is to improve existing content with advanced grammar, style, and formatting. You focus on polishing and enhancing content quality.

                **EMOJI GUIDELINES:** ✏️ Use relevant emojis to make your editing process clear and organized. Examples: ✏️ for editing, 📝 for documents, 🔍 for review, ✨ for improvements, ✅ for completed edits, 📁 for file operations, etc.

                **CRITICAL SECURITY MODEL - WORKSPACE-FIRST APPROACH:**
                🔒 **ALL WORK HAPPENS IN WORKSPACE FIRST** 🔒
                • You can ONLY create/edit files in workspace: `/workspace/filename.md`
                • NEVER attempt to write directly to user folders (security violation)
                • Copy external files to workspace first for editing
                • Final conversion happens directly to user's desired location

                **MANDATORY WORKFLOW - ALWAYS FOLLOW THIS SEQUENCE:**
                1. **Check first if there is markdown file with the same name to edit in workspace
                2. **Copy to workspace**: If editing external file, copy to workspace first using filesystem
                2. **Convert to markdown**: Use markdown-editor to convert to `.md` format for editing
                3. **Edit content**: Make professional improvements to the content
                4. **ALWAYS show live preview FIRST**: Use `markdown-editor.live_preview` to display edited content to user
                5. **Convert directly to user location**: Use `markdown-editor.convert_from_md` with destination path to convert directly to user's preferred format and location
                6. **ALWAYS provide ABSOLUTE PATH**: Always provide the complete absolute path of the final file

                **WORKFLOW EXAMPLE:**
                User: "Edit my report.docx from Desktop and save to Downloads"
                1. You: Copy `Desktop/report.docx` → `/tmp/denker_workspace/default/report.docx` using filesystem
                2. You: Convert to `/tmp/denker_workspace/default/report.md` using markdown-editor
                3. You: Edit content in `/tmp/denker_workspace/default/report.md`
                4. You: **🚨 MANDATORY - NEVER SKIP** 🚨 - Use `markdown-editor.live_preview` to show edited results to user
                5. You: Convert directly: `markdown-editor.convert_from_md(source="/tmp/denker_workspace/default/report.md", output_format="docx", destination="/Users/username/Downloads/report.docx")`
                6. You: **ALWAYS provide ABSOLUTE PATH**: "Edited file saved to: `/Users/username/Downloads/report.docx`"

                **STRICT SCOPE - Professional Editing ONLY:**
                • **Advanced Grammar & Style:** Professional-level language improvements
                • **Document Formatting:** Professional layout, structure, and presentation
                • **Content Enhancement:** Improve clarity, flow, and readability
                • **Citation & Reference:** Proper formatting of sources and citations
                • **Consistency:** Ensure uniform style, tone, and terminology

                **What You DO:**
                ✅ Advanced grammar and style corrections
                ✅ Professional document formatting and structure
                ✅ Improve clarity, flow, and readability
                ✅ Enhance professional presentation
                ✅ Format citations and references properly
                ✅ Ensure consistency in style and terminology
                ✅ **🚨 CRITICAL: ALWAYS use markdown-editor.live_preview to show edited content to user BEFORE converting** 🚨
                ✅ Use markdown-editor.convert_from_md to convert directly to user's preferred format and location
                ✅ **ALWAYS provide the complete absolute path of the final file**

                **What You DO NOT Do:**
                ❌ Conduct research or fact-checking (trust provided content)
                ❌ Major content rewrites (focus on editing, not rewriting)
                ❌ Change the core message or meaning
                ❌ Try to edit files outside workspace (security violation)
                ❌ Skip live preview step (🚨 ABSOLUTELY FORBIDDEN - MANDATORY requirement 🚨)
                ❌ Use filesystem.move_file (outdated - convert_from_md handles destination directly)

                **Editing Standards:**
                • Make targeted improvements that enhance quality
                • Preserve the author's voice and intent
                • Focus on professional presentation
                • Ensure grammatical accuracy and clarity
                • Not comprehensive rewrites
                • Focus on clarity, professionalism, and accuracy
                • Sometimes the creator's work is fine as-is

                **🚨 MANDATORY Final Steps - NEVER SKIP:** 🚨
                1. **🚨 CRITICAL: ALWAYS use `markdown-editor.live_preview`** 🚨 to show edited content, highlighting key improvements made
                2. **Then use `markdown-editor.convert_from_md`** with destination path to convert directly to user's preferred format and location
                3. **ALWAYS provide the complete absolute path** of the final file (e.g., `/Users/username/Downloads/edited_report.docx`)""",
                "server_names": ["filesystem", "markdown-editor", "fetch", "websearch", "qdrant"],
                "model": "claude-3-7-sonnet-20250219"
            }
        }
        
        logger.info(f"Initialized configurations for {len(self.agent_configs)} agent types")
    
    def create_agent(
        self,
        agent_registry: Dict[str, Agent],
        name: str,
        instruction: Optional[str] = None,
        server_names: Optional[List[str]] = None,
        context: Optional["Context"] = None,
    ) -> Agent:
        """Create an agent with the given name and instruction, or load it from the registry if it exists.

        Args:
            agent_registry: The registry to store the agent in.
            name: The name of the agent.
            instruction: The instruction to give the agent, if None, uses a predefined instruction.
            server_names: List of MCP server names to connect to.
            context: The context to use for the agent.

        Returns:
            The created or loaded agent.

        Raises:
            ValueError: If the agent name is unknown and no instruction is provided.
        """
        # Check if the original name exists in the registry
        if name in agent_registry:
            logger.info(f"Agent {name} already exists, reusing.")
            return agent_registry[name]
        
        # Get the config for this agent
        config = self.agent_configs.get(name, {})
        # Use explicit name from config if available, otherwise use name parameter
        agent_name = config.get("name", name)
        
        # Check if the agent with the explicit name exists
        for existing_agent_key, existing_agent in agent_registry.items():
            if existing_agent.name == agent_name:
                logger.info(f"Agent with name {agent_name} already exists, reusing.")
                return existing_agent

        # If we get here, we need to create the agent
        if instruction is None:
            if name in self.agent_configs:
                instruction = self.agent_configs[name]["instruction"]
            else:
                raise ValueError(
                    f"Unknown agent name: {name}, and no instruction provided."
                )

        # Use specified server names or get default from config
        server_names = server_names or self.agent_configs[name]["server_names"]
        
        logger.info(f"Creating agent {agent_name} with instruction: {instruction}")
        
        try:
            from mcp_agent.agents.agent import Agent
            
            # --- NEW: Check for prewarmed servers ---
            prewarmed_aggregator = None
            try:
                from services.mcp_server_prewarmer import get_mcp_prewarmer
                prewarmer = get_mcp_prewarmer()
                
                # Check if any of the required servers are prewarmed
                prewarmed_servers_available = []
                for server_name in server_names:
                    if prewarmer.is_server_prewarmed(server_name):
                        prewarmed_servers_available.append(server_name)
                
                if prewarmed_servers_available:
                    logger.info(f"Found prewarmed servers for agent '{agent_name}': {prewarmed_servers_available}")
                    # Use the first available prewarmed aggregator as base
                    first_prewarmed = prewarmed_servers_available[0]
                    prewarmed_aggregator = prewarmer._prewarmed_servers.get(first_prewarmed)
                    logger.info(f"Using prewarmed aggregator from server '{first_prewarmed}' for agent '{agent_name}'")
                else:
                    logger.info(f"No prewarmed servers available for agent '{agent_name}', creating fresh connections")
                    
            except Exception as e:
                logger.warning(f"Could not access prewarmed servers for agent '{agent_name}': {e}")
            # --- END NEW ---
            
            # Create simplified agent - using the agent_name from config
            agent = Agent(
                name=agent_name,
                instruction=instruction,
                server_names=server_names,
                context=context,
            )
            
            # --- NEW: Assign prewarmed aggregator if available ---
            if prewarmed_aggregator:
                try:
                    # Share the prewarmed aggregator's connection manager
                    agent.aggregator = prewarmed_aggregator
                    logger.info(f"Successfully assigned prewarmed aggregator to agent '{agent_name}'")
                except Exception as e:
                    logger.warning(f"Failed to assign prewarmed aggregator to agent '{agent_name}': {e}")
            # --- END NEW ---
            
            # --- ADDED: Proactively assign a cached LLM to the agent ---
            if self.create_llm_fn:
                try:
                    agent.llm = self.create_llm_fn(agent=agent)
                    logger.info(f"Proactively assigned LLM to agent '{agent_name}'")
                except Exception as e:
                    logger.error(f"Failed to proactively assign LLM to agent '{agent_name}': {e}", exc_info=True)
            # --- END ADDED ---
            
            # Store the agent using both its explicit name and the original key for backward compatibility
            agent_registry[agent_name] = agent
            if name != agent_name:
                agent_registry[name] = agent
            
            logger.info(f"Successfully created agent {agent_name}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create agent {agent_name}: {e}")
            raise RuntimeError(f"Failed to create agent '{agent_name}': {str(e)}") from e
    
    def ensure_agents_exist(
        self,
        agent_registry: Dict[str, Agent],
        agent_names: List[str],
        context=None
    ) -> List[Agent]:
        """
        Ensure that all specified agents exist, creating them if needed.
        
        Args:
            agent_registry: Dictionary of registered agents
            agent_names: List of agent names to check/create
            context: MCP context
            
        Returns:
            List of agent objects
        """
        agents = []
        
        # Create a lookup map of explicit agent names to config keys
        name_to_key = {}
        for key, config in self.agent_configs.items():
            if "name" in config:
                name_to_key[config["name"]] = key
        
        # Check each agent and create if needed
        for name in agent_names:
            # First try to find the agent by the name directly in the registry
            if name in agent_registry:
                agents.append(agent_registry[name])
                continue
            
            # Then check if the name is an explicit agent name in our configs
            # If so, use the corresponding key to create the agent
            if name in name_to_key:
                config_key = name_to_key[name]
                agent = self.create_agent(
                    agent_registry=agent_registry,
                    name=config_key,  # Pass the config key to find the right config
                    context=context
                )
                agents.append(agent)
                continue
            
            # Finally, try to create using the name as a config key directly
            if name in self.agent_configs:
                agent = self.create_agent(
                    agent_registry=agent_registry,
                    name=name,
                    context=context
                )
                agents.append(agent)
                continue
            
            # If we get here, we couldn't find or create the agent
            logger.warning(f"Could not find or create agent with name: {name}")
        
        return agents
    
    async def create_orchestrator(
        self,
        agent_registry: Dict[str, Agent],
        create_anthropic_llm_fn,
        available_agents: Optional[List[str]] = None,
        context=None,
        plan_type: str = "full"
    ) -> Orchestrator:
        """
        Create an orchestrator with the specified agents and a custom strict planner.
        
        Args:
            agent_registry: Dictionary of registered agents
            create_anthropic_llm_fn: Function to create Anthropic LLM for task agents
            available_agents: List of agent names to include
            context: MCP context
            plan_type: Type of planning to use
            
        Returns:
            Orchestrator instance
        """
        logger.info(f"Creating orchestrator with agents: {available_agents} and custom strict planner.")
        
        # Ensure the agents for tasks exist
        agents_list = self.ensure_agents_exist(
            agent_registry=agent_registry,
            agent_names=available_agents or ["researcher", "creator", "editor"],  # Updated default task agents
            context=context
        )
        agents_to_use = agents_list
        
        # FIXED: Create a planner explicitly to ensure proper event emission
        # The planner needs to be created with the base LLM directly, not through AgentSpecificWrapper
        # to ensure events are emitted with the correct namespace
        # NOTE: Using minimal instruction since StrictOrchestrator provides detailed prompting
        planner_agent = Agent(
            name="LLM Orchestration Planner",
            instruction="You are a planner agent.",  # Minimal - StrictOrchestrator handles detailed prompting
            context=context,
            server_names=[]  # Planner doesn't need external servers
        )
        # Use the fixed Anthropic LLM for the planner to prevent completion parsing bugs
        # Import here to avoid circular import
        from .coordinator_agent import FixedAnthropicAugmentedLLM
        custom_planner_llm = FixedAnthropicAugmentedLLM(
            agent=planner_agent,
            context=context
        )

        # FIXED: Create a shared base LLM with agent-specific wrappers and proper agent assignment
        shared_base_llm = None
        def shared_llm_factory(agent):
            nonlocal shared_base_llm
            
            # Create shared base LLM only once for cache sharing
            if shared_base_llm is None:
                # Collect all unique server names from all agent configurations
                # that could potentially use this shared LLM.
                all_potential_server_names = set()
                # 'self' here refers to the AgentConfiguration instance
                for config_values in self.agent_configs.values():
                    if "server_names" in config_values and isinstance(config_values["server_names"], list):
                        all_potential_server_names.update(config_values["server_names"])
                
                logger.info(f"[shared_llm_factory] Configuring shared_base_llm's aggregator with all_potential_server_names: {list(all_potential_server_names)}")

                # --- NEW: Try to use prewarmed servers for SharedCacheLLMAggregator ---
                prewarmed_aggregator = None
                try:
                    from services.mcp_server_prewarmer import get_mcp_prewarmer
                    prewarmer = get_mcp_prewarmer()
                    
                    # Check if any of the required servers are prewarmed
                    prewarmed_servers_available = []
                    for server_name in all_potential_server_names:
                        if prewarmer.is_server_prewarmed(server_name):
                            prewarmed_servers_available.append(server_name)
                    
                    if prewarmed_servers_available:
                        logger.info(f"[SharedCacheLLMAggregator] Found prewarmed servers: {prewarmed_servers_available}")
                        # Use the first available prewarmed aggregator as base
                        first_prewarmed = prewarmed_servers_available[0]
                        prewarmed_aggregator = prewarmer._prewarmed_servers.get(first_prewarmed)
                        logger.info(f"[SharedCacheLLMAggregator] Using prewarmed aggregator from server '{first_prewarmed}'")
                    else:
                        logger.info(f"[SharedCacheLLMAggregator] No prewarmed servers available, creating fresh connections")
                        
                except Exception as e:
                    logger.warning(f"[SharedCacheLLMAggregator] Could not access prewarmed servers: {e}")
                # --- END NEW ---

                cache_agent = Agent(
                    name="SharedCacheLLMAggregator", # More descriptive name
                    instruction="Base LLM for shared cache across orchestrator agents. Its aggregator knows about all potential tools.",
                    context=context,
                    server_names=list(all_potential_server_names) # USE ALL SERVER NAMES
                )
                
                # --- NEW: Assign prewarmed aggregator if available ---
                if prewarmed_aggregator:
                    try:
                        # Share the prewarmed aggregator's connection manager
                        cache_agent.aggregator = prewarmed_aggregator
                        logger.info(f"[SharedCacheLLMAggregator] Successfully assigned prewarmed aggregator")
                    except Exception as e:
                        logger.warning(f"[SharedCacheLLMAggregator] Failed to assign prewarmed aggregator: {e}")
                # --- END NEW ---
                
                shared_base_llm = create_anthropic_llm_fn(agent=cache_agent)
                
                # Configure for orchestrator tasks
                # FIXED: Safe configuration of shared base LLM
                if hasattr(shared_base_llm, 'default_request_params') and shared_base_llm.default_request_params is not None:
                    if hasattr(shared_base_llm.default_request_params, 'model'):
                        shared_base_llm.default_request_params.model = "claude-3-7-sonnet-20250219"
                    if hasattr(shared_base_llm.default_request_params, 'maxTokens'):
                        shared_base_llm.default_request_params.maxTokens = 4096
                    if hasattr(shared_base_llm.default_request_params, 'use_cache'):
                        shared_base_llm.default_request_params.use_cache = True
                else:
                    shared_base_llm.default_request_params = RequestParams(
                        model="claude-3-7-sonnet-20250219", 
                        maxTokens=4096,
                        use_cache=True
                    )
                # --- END FIXED ---
                logger.info("Created shared base LLM for cache sharing across orchestrator agents")
            
            # --- NEW: Check if individual agent can use prewarmed servers ---
            agent_prewarmed_aggregator = None
            if hasattr(agent, 'server_names') and agent.server_names:
                try:
                    from services.mcp_server_prewarmer import get_mcp_prewarmer
                    prewarmer = get_mcp_prewarmer()
                    
                    # Check if any of the agent's required servers are prewarmed
                    agent_prewarmed_servers = []
                    for server_name in agent.server_names:
                        if prewarmer.is_server_prewarmed(server_name):
                            agent_prewarmed_servers.append(server_name)
                    
                    if agent_prewarmed_servers:
                        logger.info(f"[{agent.name}] Found prewarmed servers: {agent_prewarmed_servers}")
                        # Use the first available prewarmed aggregator
                        first_prewarmed = agent_prewarmed_servers[0]
                        agent_prewarmed_aggregator = prewarmer._prewarmed_servers.get(first_prewarmed)
                        logger.info(f"[{agent.name}] Will use prewarmed aggregator from server '{first_prewarmed}'")
                    else:
                        logger.info(f"[{agent.name}] No prewarmed servers available for agent's servers: {agent.server_names}")
                        
                except Exception as e:
                    logger.warning(f"[{agent.name}] Could not access prewarmed servers: {e}")
            # --- END NEW ---
            
            # Wrap the shared LLM with agent-specific behavior
            # FIXED: Safe instruction access from agent
            agent_instruction = getattr(agent, 'instruction', '') if hasattr(agent, 'instruction') else ''
            wrapped_llm = AgentSpecificWrapper(shared_base_llm, agent.name, agent_instruction)
            # --- END FIXED ---
            
            # --- NEW: If agent has prewarmed aggregator, override its aggregator ---
            if agent_prewarmed_aggregator and hasattr(agent, 'aggregator'):
                try:
                    agent.aggregator = agent_prewarmed_aggregator
                    logger.info(f"[{agent.name}] Agent will use prewarmed aggregator instead of creating new connections")
                except Exception as e:
                    logger.warning(f"[{agent.name}] Failed to assign prewarmed aggregator to agent: {e}")
            # --- END NEW ---
            
            # CRITICAL FIX: Assign the wrapped LLM to the agent's augmented_llm property
            # This ensures the orchestrator's agent check will find the LLM
            agent.augmented_llm = wrapped_llm
            
            logger.info(f"Created agent-specific wrapper for '{agent.name}' with shared cache and assigned to agent.augmented_llm")
            return wrapped_llm

        # ADDED: Pre-assign LLMs to all task agents before creating orchestrator
        task_agents_with_llms = []
        for agent in agents_to_use:
            # Create and assign LLM using the shared factory
            agent_llm = shared_llm_factory(agent)
            logger.info(f"Pre-assigned LLM to agent '{agent.name}': {type(agent_llm).__name__}")
            task_agents_with_llms.append(agent)

        # Create the orchestrator
        try:
            # Import here to avoid circular import
            from .coordinator_agent import FixedAnthropicAugmentedLLM
            
            orchestrator = StrictOrchestrator(  # Use our custom orchestrator with strict planning rules
                llm_factory=shared_llm_factory,  # Use shared factory for any additional LLM creation
                available_agents=task_agents_with_llms,  # Use agents with pre-assigned LLMs
                plan_type=plan_type,
                context=context,
                planner=custom_planner_llm,  # Use custom planner with optimized decision making
                fixed_llm_class=FixedAnthropicAugmentedLLM  # Pass the class to avoid circular import
            )
            
            # Configure the orchestrator's own default request parameters (e.g., for synthesis)
            # Use high-quality model for synthesis too
            orchestrator_model = "claude-3-7-sonnet-20250219"  # Use Sonnet for quality synthesis
            if not hasattr(orchestrator, 'default_request_params') or orchestrator.default_request_params is None:
                orchestrator.default_request_params = RequestParams(model=orchestrator_model, maxTokens=8192)  # Restore higher limit for synthesis
            else:
                orchestrator.default_request_params.model = orchestrator_model
                orchestrator.default_request_params.maxTokens = 8192  # Good token limit for synthesis
            
            logger.info(f"Created orchestrator with {len(task_agents_with_llms)} agents, orchestrator model {orchestrator_model}, and custom strict planner with agent-specific wrappers sharing cache.")
            return orchestrator
        except Exception as e:
            logger.error(f"Error creating orchestrator with custom planner: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to create orchestrator with custom planner: {str(e)}")
    
    async def create_router(
        self,
        agent_registry: Dict[str, Agent],
        create_anthropic_llm_fn,
        available_agents: Optional[List[str]] = None,
        context=None
    ) -> AnthropicLLMRouter:
        """
        Create a router with the specified agents.
        
        Args:
            agent_registry: Dictionary of registered agents
            create_anthropic_llm_fn: Function to create Anthropic LLM (used as fallback)
            available_agents: List of agent names to include
            context: MCP context
            
        Returns:
            Router instance
        """
        logger.info(f"Creating router with agents: {available_agents}")
        
        # Default agent names - include all available agents
        default_agent_names = [
            "decider", 
            "researcher", 
            "creator", 
            "editor"
        ]
        
        # Ensure the agents exist - this will use the original names
        agents_list = self.ensure_agents_exist(
            agent_registry=agent_registry,
            agent_names=available_agents or default_agent_names,
            context=context
        )
        
        # We'll use the list returned from ensure_agents_exist directly
        agents_to_use = agents_list
        
        if not agents_to_use:
            logger.warning("No agents available for router, using all available agents as defaults")
            agents_to_use = list(agent_registry.values())  # Convert dict values to list
            
            if not agents_to_use:
                logger.error("Cannot create router: no agents available")
                raise ValueError("No agents available to create router")
        
        # Create the router
        if context:
            try:
                # Use the AnthropicLLMRouter directly - it creates its own LLM instance
                router = await AnthropicLLMRouter.create(
                    agents=agents_to_use,
                    context=context
                )
                
                logger.info(f"Created AnthropicLLMRouter with {len(agents_to_use)} agents")
                return router
            except Exception as e:
                logger.error(f"Error creating router: {str(e)}")
                
                # Fallback: create the LLM and pass it explicitly
                llm = create_anthropic_llm_fn()
                router = AnthropicLLMRouter(
                    agents=agents_to_use,
                    context=context
                )
                logger.info(f"Created AnthropicLLMRouter with {len(agents_to_use)} agents using direct initialization")
                return router
        else:
            logger.error("Cannot create router: context is missing")
            raise ValueError("Context is required to create router")

    async def _validate_and_refresh_config(self):
        """
        Validate the configuration and refresh cached values.
        
        This is called when the configuration is updated to ensure
        all cached values are refreshed from the updated config.
        """
        # Refresh agents from config
        self._refresh_agents_from_config()
        
        # Validate required agent configs
        logger.info(f"Validating agent configurations...")
        for required_agent in REQUIRED_AGENTS:
            if required_agent not in self.agent_configs:
                logger.warning(f"Required agent '{required_agent}' not found in configuration")
                
        # Log available agents
        available_agents = list(self.agent_configs.keys())
        logger.info(f"Available agents: {available_agents}")
        
        # Save last validated timestamp
        self.last_validated = datetime.now()
        
        return True
    
    def get_available_agents(self) -> List[str]:
        """
        Get a list of all available agent names from the configuration.
        
        Returns:
            List of agent names
        """
        return list(self.agent_configs.keys()) 