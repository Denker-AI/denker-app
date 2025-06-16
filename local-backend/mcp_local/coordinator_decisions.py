"""
Coordinator Decisions - Decision-making logic for Coordinator Agent.

This module contains the decision-making functionality, such as determining
which workflow to use (router, orchestrator, or simple) based on user queries.
"""

import json
import logging
import re
from typing import Dict, Any, Optional, List

from mcp_agent.workflows.llm.augmented_llm import RequestParams

logger = logging.getLogger(__name__)

class DecisionMaker:
    """Handler for making workflow decisions based on user queries."""
    
    def __init__(self, websocket_manager, agents_registry):
        """
        Initialize the decision maker.
        
        Args:
            websocket_manager: WebSocket manager for sending updates
            agents_registry: Registry of available agents
        """
        self.websocket_manager = websocket_manager
        self.agents_registry = agents_registry
    
    async def get_workflow_decision(
        self, 
        query: str, 
        from_intention_agent: bool = False, 
        query_id: str = None,
        create_anthropic_llm_fn=None,
        processed_message: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Use the decider agent to determine the appropriate workflow.
        
        Args:
            query: The user's query text
            from_intention_agent: Whether this request came from the intention agent
            query_id: The query ID for WebSocket updates (optional)
            create_anthropic_llm_fn: Function to create an Anthropic LLM
            processed_message: Pre-processed message ready for LLM use
            
        Returns:
            Dict containing workflow type and response for simple conversations
        """
        # Create the decider agent if it doesn't exist
        if "decider" not in self.agents_registry:
            logger.warning("Decider agent not found in registry, cannot make a workflow decision")
            return self._create_default_decision()
        
        # Get the decider agent
        decider = self.agents_registry["decider"]
        
        try:
            # Create an Anthropic LLM with the decider agent's name
            llm = create_anthropic_llm_fn(agent_name="decider")
            
            # If we have a query_id, send a status update that we're deciding on workflow
            if query_id and self.websocket_manager.is_connected(query_id):
                await self.websocket_manager.send_consolidated_update(
                    query_id=query_id,
                    update_type="status",
                    message="Analyzing your request to determine the best approach...",
                    data={
                        "status": "deciding",
                        "agent": "decider"
                    }
                )
            
            # Check that we have a processed message
            if not processed_message:
                logger.error("No processed_message provided! This is required for the decider agent.")
                return self._create_default_decision(error="Missing processed message")
                
            # Use the provided processed message directly
            message = processed_message
            logger.info(f"Using provided processed message with {len(message['content'])} content blocks")
            logger.debug(f"Decider message content summary: {[block.get('type') for block in message['content']]}")
            
            # Get decision from the decider agent directly using the LLM
            decider_response = await llm.generate_str(
                message=message,
                request_params=RequestParams(
                    temperature=0.2,  # Low temperature for consistent decisions
                    maxTokens=1000
                )
            )
            
            # Log the decider's response
            logger.info(f"Decider agent response: {decider_response}")
            
            try:
                # Clean up the response: strip markdown code block markers if present
                cleaned_response = decider_response
                
                # Check for markdown code block markers (handles various formats)
                if "```" in cleaned_response:
                    # Find the first and last ``` markers
                    start_lines = [line for line in cleaned_response.split("\n") if "```" in line]
                    if start_lines:
                        # Find the content after the first ``` line
                        first_marker_pos = cleaned_response.find(start_lines[0])
                        start_pos = first_marker_pos + len(start_lines[0])
                        
                        # Find the position of the closing ```
                        remaining_text = cleaned_response[start_pos:]
                        end_marker_pos = remaining_text.rfind("```")
                        
                        if end_marker_pos > 0:
                            # Extract the content between the markers
                            cleaned_response = remaining_text[:end_marker_pos].strip()
                            logger.info(f"Stripped markdown code block markers from response")
                
                # Try to parse the JSON response
                decision_data = json.loads(cleaned_response)
                logger.info(f"Successfully parsed decision data: {decision_data}")
                
                # Validate required fields
                if not isinstance(decision_data, dict):
                    raise ValueError("Decision data must be a dictionary")
                
                workflow = decision_data.get("workflow_type")
                explanation = decision_data.get("explanation")
                
                if not workflow or not explanation:
                    raise ValueError("Missing required fields: workflow_type and explanation")
                
                decision = {
                    "workflow_type": workflow,
                    "explanation": explanation,
                    "raw_response": decider_response
                }
                
                # Add additional fields if they exist
                if "simple_response" in decision_data:
                    decision["simple_response"] = decision_data["simple_response"]
                
                if "needs_clarification" in decision_data:
                    decision["needs_clarification"] = decision_data["needs_clarification"]
                    
                    # Include clarifying questions if available
                    if decision_data.get("clarifying_questions"):
                        decision["clarifying_questions"] = decision_data["clarifying_questions"]
                
                # If we have a query_id, send the decision as a consolidated update AND WAIT
                if query_id and self.websocket_manager.is_connected(query_id):
                    logger.info(f"[{query_id}] Sending 'decision' update via WebSocket...")
                    await self.websocket_manager.send_consolidated_update(
                        query_id=query_id,
                        update_type="decision",
                        message=f"Selected {workflow} workflow: {explanation}",
                        data=decision
                    )
                    logger.info(f"[{query_id}] Finished sending 'decision' update.")

                return decision
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse decider response as JSON: {e}")
                logger.error(f"Raw response: {decider_response}")
                decision = self._create_default_decision(error="Failed to parse decision, using default workflow")
            except ValueError as e:
                logger.error(f"Invalid decision data: {e}")
                logger.error(f"Raw response: {decider_response}")
                decision = self._create_default_decision(error=str(e))
            except Exception as e:
                logger.error(f"Unexpected error processing decision: {e}")
                logger.error(f"Raw response: {decider_response}")
                decision = self._create_default_decision(error=f"Unexpected error: {str(e)}")
            
            return decision
            
        except Exception as e:
            logger.error(f"Error getting workflow decision: {str(e)}")
            # Default to router workflow
            decision = self._create_default_decision(error=f"Error in decision process: {str(e)}")
            
            # If we have a query_id, send the error as a consolidated update
            if query_id and self.websocket_manager.is_connected(query_id):
                await self.websocket_manager.send_consolidated_update(
                    query_id=query_id,
                    update_type="error",
                    message=f"Error determining workflow: {str(e)}. Falling back to router.",
                    data=decision
                )
                
            return decision
    
    def _create_default_decision(self, error: str = "Unknown error") -> dict:
        """Create a default decision when error occurs, defaulting to router workflow."""
        return {
            "workflow_type": "router",  # Default to router workflow
            "explanation": f"Error in decision making: {error}. Falling back to router workflow.",
            "raw_response": None
        } 