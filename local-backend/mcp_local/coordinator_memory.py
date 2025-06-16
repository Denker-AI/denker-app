"""
Coordinator Memory Manager

This module handles memory management for the MCP Agent coordinator using the memory
knowledge graph tools provided by MCP.
"""

import logging
import os
from typing import Dict, Any, List, Optional
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class CoordinatorMemory:
    """
    Memory manager for the MCP Agent coordinator.
    
    Handles storing user interactions, agent tasks, and results in the knowledge graph.
    """
    
    def __init__(self, memory_tools):
        """
        Initialize the memory manager.
        
        Args:
            memory_tools: The memory tools instance
        """
        self.memory_tools = memory_tools
        self.graph = None
    
    async def initialize(self):
        """Initialize the memory system and check connectivity with a fast health check."""
        try:
            # Ensure the memory tools are initialized first (only needed for PG version)
            if hasattr(self.memory_tools, 'initialize'):
                await self.memory_tools.initialize()

            # Check if memory health check should be skipped for faster startup
            skip_health_check = os.getenv("DENKER_SKIP_MEMORY_HEALTH_CHECK", "false").lower() == "true"
            
            if skip_health_check:
                logger.info("Memory health check skipped (DENKER_SKIP_MEMORY_HEALTH_CHECK=true)")
            else:
                # Fast health check: call the /api/v1/memory/health endpoint
                if hasattr(self.memory_tools, 'mcp_memory_health_check'):
                    ok = await self.memory_tools.mcp_memory_health_check()
                    if ok:
                        logger.info("Memory health check succeeded: backend is reachable.")
                    else:
                        logger.error("Memory health check failed: backend is not reachable.")
                else:
                    logger.warning("No memory health check method implemented in memory_tools.")

            # await self._ensure_core_entities()  # Only do health check at startup

        except Exception as e:
            logger.error(f"Error initializing memory: {str(e)}")
            raise
    
    async def _ensure_core_entities(self):
        """Ensure core entity types exist in the graph."""
        # Check if we have the Denker App entity
        app_entities = await self.memory_tools.mcp_memory_search_nodes(query="Denker App")
        if not app_entities or not app_entities.get("nodes", []):
            # Create the Denker App entity
            await self.memory_tools.mcp_memory_create_entities(entities=[
                {
                    "name": "Denker App",
                    "entityType": "Application",
                    "observations": [
                        "Main application that integrates MCP Agent coordination",
                        "Created on " + datetime.now().isoformat()
                    ]
                }
            ])
            logger.info("Created Denker App entity")
            
        # Check if we have the MCP Agent entity
        mcp_entities = await self.memory_tools.mcp_memory_search_nodes(query="MCP Agent Framework")
        if not mcp_entities or not mcp_entities.get("nodes", []):
            # Create the MCP Agent entity
            await self.memory_tools.mcp_memory_create_entities(entities=[
                {
                    "name": "MCP Agent Framework",
                    "entityType": "Framework",
                    "observations": [
                        "Multi-agent coordination framework integrated with Denker",
                        "Provides orchestration and routing of specialized agents",
                        "Used for complex task decomposition and execution"
                    ]
                }
            ])
            logger.info("Created MCP Agent Framework entity")
            
            # Create the relationship
            await self.memory_tools.mcp_memory_create_relations(relations=[
                {
                    "from": "Denker App",
                    "to": "MCP Agent Framework",
                    "relationType": "uses"
                }
            ])
    
    async def create_entity_if_not_exists(self, entity_name: str, entity_type: str):
        """
        Create an entity if it doesn't already exist.
        
        Args:
            entity_name: The name of the entity
            entity_type: The type of the entity
        """
        # Check if entity already exists
        result = await self.memory_tools.mcp_memory_search_nodes(query=entity_name)
        if not result or not result.get("nodes", []) or not any(node["name"] == entity_name for node in result.get("nodes", [])):
            # Create new entity
            await self.memory_tools.mcp_memory_create_entities(entities=[
                {
                    "name": entity_name,
                    "entityType": entity_type,
                    "observations": [
                        f"Created on {datetime.now().isoformat()}"
                    ]
                }
            ])
            logger.info(f"Created {entity_type} entity: {entity_name}")
        else:
            logger.debug(f"{entity_type} entity already exists: {entity_name}")
    
    async def create_relation(self, from_entity: str, relation_type: str, to_entity: str):
        """
        Create a relation between two entities.
        
        Args:
            from_entity: The source entity
            relation_type: The type of relation
            to_entity: The target entity
        """
        # Create the relation
        await self.memory_tools.mcp_memory_create_relations(relations=[
            {
                "from": from_entity,
                "to": to_entity,
                "relationType": relation_type
            }
        ])
        logger.info(f"Created relation: {from_entity} -> {relation_type} -> {to_entity}")
    
    async def add_observation(self, entity_name: str, observation: str):
        """
        Add an observation to an entity.
        
        Args:
            entity_name: The entity to add the observation to
            observation: The observation text
        """
        # Add the observation
        await self.memory_tools.mcp_memory_add_observations(observations=[
            {
                "entityName": entity_name,
                "contents": [observation]
            }
        ])
        logger.info(f"Added observation to {entity_name}")
    
    async def store_conversation_reference(
        self, 
        entity_name: str, 
        conversation_id: str, 
        message_id: str = None,
        snippet: str = None
    ):
        """
        Store a reference to a conversation in an entity.
        
        Args:
            entity_name: The entity to store the reference in
            conversation_id: The ID of the conversation
            message_id: Optional ID of the specific message
            snippet: Optional snippet of the content for quick reference
        """
        # Get the entity
        result = await self.memory_tools.mcp_memory_open_nodes(names=[entity_name])
        if not result or not result.get("nodes", []):
            logger.warning(f"Entity not found for conversation reference: {entity_name}")
            return
            
        # Extract the entity
        entity = result["nodes"][0]
        
        # Add conversation reference as metadata
        metadata = entity.get("meta_data", {})
        if not metadata:
            metadata = {}
            
        metadata["conversation_id"] = conversation_id
        if message_id:
            metadata["message_id"] = message_id
        if snippet:
            metadata["snippet"] = snippet
        
        # Update the entity with the metadata
        await self.memory_tools.mcp_memory_update_entities(entities=[
            {
                "name": entity_name,
                "meta_data": metadata
            }
        ])
        
        logger.info(f"Stored conversation reference in {entity_name}: {conversation_id}")
    
    async def get_entity_conversation_reference(self, entity_name: str) -> Dict[str, Any]:
        """
        Get conversation references from an entity.
        
        Args:
            entity_name: The entity to get references from
            
        Returns:
            Dict with conversation_id, message_id, and snippet if available
        """
        # Get the entity
        result = await self.memory_tools.mcp_memory_open_nodes(names=[entity_name])
        if not result or not result.get("nodes", []):
            logger.warning(f"Entity not found for getting conversation reference: {entity_name}")
            return {}
            
        # Extract the entity
        entity = result["nodes"][0]
        
        # Extract conversation reference from metadata
        metadata = entity.get("meta_data", {})
        if not metadata:
            return {}
            
        return {
            "conversation_id": metadata.get("conversation_id"),
            "message_id": metadata.get("message_id"),
            "snippet": metadata.get("snippet")
        }
    
    async def search_knowledge(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search the knowledge graph for entities matching the query.
        
        Args:
            query: The search query
            limit: Maximum number of results to return
            
        Returns:
            List of matching entities
        """
        result = await self.memory_tools.mcp_memory_search_nodes(query=query)
        nodes = result.get("nodes", [])
        
        # Sort by relevance and limit results
        # For now, simple substring matching for relevance
        nodes = sorted(nodes, key=lambda x: -sum(query.lower() in obs.lower() for obs in x.get("observations", [])))
        
        return nodes[:limit]

    async def store_user_session(self, session_id: str, user_id: Optional[str] = None):
        """
        Store a new user session in the knowledge graph.
        
        Args:
            session_id: The session ID
            user_id: Optional user ID
        """
        # Use the session_id as the entity name if no user_id provided
        entity_name = f"Session-{session_id}"
        if user_id:
            entity_name = f"User-{user_id}-Session-{session_id}"
        
        # Create the session entity
        await self.memory_tools.mcp_memory_create_entities(entities=[
            {
                "name": entity_name,
                "entityType": "Session",
                "observations": [
                    f"Session started on {datetime.now().isoformat()}",
                    f"Session ID: {session_id}"
                ]
            }
        ])
        
        # Create relationship to the Denker App
        await self.memory_tools.mcp_memory_create_relations(relations=[
            {
                "from": entity_name,
                "to": "Denker App",
                "relationType": "interacts with"
            }
        ])
        
        logger.info(f"Stored user session {session_id}")
        return entity_name
    
    async def store_user_query(self, session_entity: str, query_id: str, query_text: str, workflow_type: str):
        """
        Store a user query in the knowledge graph.
        
        Args:
            session_entity: The session entity name
            query_id: The query ID
            query_text: The query text
            workflow_type: The workflow type used (e.g., orchestrator, router)
        """
        # Create a unique entity name for the query
        query_entity = f"Query-{query_id}"
        
        # Create the query entity
        await self.memory_tools.mcp_memory_create_entities(entities=[
            {
                "name": query_entity,
                "entityType": "Query",
                "observations": [
                    f"Query: {query_text}",
                    f"Workflow type: {workflow_type}",
                    f"Timestamp: {datetime.now().isoformat()}"
                ]
            }
        ])
        
        # Create relationship to the session
        await self.memory_tools.mcp_memory_create_relations(relations=[
            {
                "from": session_entity,
                "to": query_entity,
                "relationType": "submits"
            }
        ])
        
        logger.info(f"Stored user query {query_id}")
        return query_entity
    
    async def store_agent_task(self, query_entity: str, agent_name: str, task_id: str, task_description: str):
        """
        Store an agent task in the knowledge graph.
        
        Args:
            query_entity: The query entity name
            agent_name: The agent name
            task_id: The task ID
            task_description: The task description
        """
        # Create a unique entity name for the task
        task_entity = f"Task-{task_id}"
        
        # Create the task entity
        await self.memory_tools.mcp_memory_create_entities(entities=[
            {
                "name": task_entity,
                "entityType": "Task",
                "observations": [
                    f"Agent: {agent_name}",
                    f"Description: {task_description}",
                    f"Timestamp: {datetime.now().isoformat()}",
                    f"Status: started"
                ]
            }
        ])
        
        # Create relationship to the query
        await self.memory_tools.mcp_memory_create_relations(relations=[
            {
                "from": query_entity,
                "to": task_entity,
                "relationType": "requires"
            }
        ])
        
        # Check if we have an entity for this agent
        agent_entities = await self.memory_tools.mcp_memory_search_nodes(query=f"Agent-{agent_name}")
        
        if not agent_entities or not agent_entities.get("nodes", []):
            # Create the agent entity
            await self.memory_tools.mcp_memory_create_entities(entities=[
                {
                    "name": f"Agent-{agent_name}",
                    "entityType": "Agent",
                    "observations": [
                        f"Specialized agent for {agent_name} tasks",
                        f"Part of the MCP Agent Framework"
                    ]
                }
            ])
            
            # Create relationship to the MCP Agent Framework
            await self.memory_tools.mcp_memory_create_relations(relations=[
                {
                    "from": "MCP Agent Framework",
                    "to": f"Agent-{agent_name}",
                    "relationType": "provides"
                }
            ])
        
        # Create relationship from the agent to the task
        await self.memory_tools.mcp_memory_create_relations(relations=[
            {
                "from": f"Agent-{agent_name}",
                "to": task_entity,
                "relationType": "performs"
            }
        ])
        
        logger.info(f"Stored agent task {task_id} for agent {agent_name}")
        return task_entity
    
    async def update_task_status(self, task_entity: str, status: str, result: Optional[str] = None):
        """
        Update the status of a task.
        
        Args:
            task_entity: The task entity name
            status: The new status
            result: Optional result text
        """
        # Get the existing task
        task_data = await self.memory_tools.mcp_memory_open_nodes(names=[task_entity])
        
        if not task_data or not task_data.get("nodes", []):
            logger.warning(f"Task {task_entity} not found")
            return
        
        task = task_data["nodes"][0]
        
        # Update observations
        observations = task.get("observations", [])
        observations.append(f"Status: {status}")
        
        if result:
            # Limit result size to avoid overwhelming the graph
            result_summary = result[:500] + "..." if len(result) > 500 else result
            observations.append(f"Result: {result_summary}")
        
        observations.append(f"Updated: {datetime.now().isoformat()}")
        
        # Update the task entity
        await self.memory_tools.mcp_memory_update_entities(entities=[
            {
                "name": task_entity,
                "observations": observations
            }
        ])
        
        logger.info(f"Updated task {task_entity} status to {status}")
    
    async def store_result(self, query_entity: str, result_text: str, completion_time: float):
        """
        Store a query result in the knowledge graph.
        
        Args:
            query_entity: The query entity name
            result_text: The result text
            completion_time: The completion time in seconds
        """
        # Generate a unique result ID
        result_id = f"result-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        result_entity = f"Result-{result_id}"
        
        # Limit result size for storage
        result_summary = result_text[:1000] + "..." if len(result_text) > 1000 else result_text
        
        # Create the result entity
        await self.memory_tools.mcp_memory_create_entities(entities=[
            {
                "name": result_entity,
                "entityType": "Result",
                "observations": [
                    f"Result: {result_summary}",
                    f"Completion time: {completion_time} seconds",
                    f"Timestamp: {datetime.now().isoformat()}"
                ]
            }
        ])
        
        # Create relationship to the query
        await self.memory_tools.mcp_memory_create_relations(relations=[
            {
                "from": query_entity,
                "to": result_entity,
                "relationType": "produces"
            }
        ])
        
        logger.info(f"Stored result {result_id}")
        return result_entity
    
    async def record_agent_interaction(self, agent_name: str, message: str):
        """
        Record an agent interaction as a progress update.
        
        Args:
            agent_name: The agent name
            message: The interaction message
        """
        # Check if we have an entity for this agent
        agent_entities = await self.memory_tools.mcp_memory_search_nodes(query=f"Agent-{agent_name}")
        
        if not agent_entities or not agent_entities.get("nodes", []):
            # Skip if the agent entity doesn't exist
            return
        
        agent_entity = f"Agent-{agent_name}"
        
        # Add the interaction as an observation
        await self.memory_tools.mcp_memory_add_observations(observations=[
            {
                "entityName": agent_entity,
                "contents": [
                    f"[{datetime.now().isoformat()}] {message}"
                ]
            }
        ])
    
    async def get_session_history(self, session_entity: str):
        """
        Get the history of a session from the knowledge graph.
        
        Args:
            session_entity: The session entity name
            
        Returns:
            Dict containing session information and history
        """
        try:
            # Get the session entity
            session_data = await self.memory_tools.mcp_memory_open_nodes(names=[session_entity])
            
            if not session_data or not session_data.get("nodes", []):
                logger.warning(f"Session {session_entity} not found")
                return None
            
            session = session_data["nodes"][0]
            
            # Find all queries for this session
            # This would ideally use a more sophisticated approach to follow the graph relationships
            # For now, we'll search for all Query entities and filter
            all_queries = await self.memory_tools.mcp_memory_search_nodes(query="entityType:Query")
            
            if not all_queries or not all_queries.get("nodes", []):
                return {
                    "session": session,
                    "history": []
                }
            
            # Build up the history by examining relationships
            history = []
            
            for query_node in all_queries["nodes"]:
                # Check if this query is related to our session
                query_relations = await self.memory_tools.mcp_memory_open_nodes(names=[query_node["name"]])
                
                if not query_relations or not query_relations.get("nodes", []):
                    continue
                
                query = query_relations["nodes"][0]
                
                # Check for incoming relations from our session
                is_related = False
                for relation in query.get("incomingRelations", []):
                    if relation["from"] == session_entity and relation["relationType"] == "submits":
                        is_related = True
                        break
                
                if not is_related:
                    continue
                
                # Find the results for this query
                results = []
                for relation in query.get("outgoingRelations", []):
                    if relation["relationType"] == "produces":
                        result_data = await self.memory_tools.mcp_memory_open_nodes(names=[relation["to"]])
                        if result_data and result_data.get("nodes", []):
                            results.append(result_data["nodes"][0])
                
                # Add to history
                history.append({
                    "query": query,
                    "results": results
                })
            
            return {
                "session": session,
                "history": history
            }
            
        except Exception as e:
            logger.error(f"Error getting session history: {str(e)}")
            return None 