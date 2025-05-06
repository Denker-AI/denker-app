"""
PostgreSQL Memory Tools for MCP Agent

This module provides a PostgreSQL-backed memory tools implementation for the MCP Agent,
implementing the interfaces expected by the CoordinatorMemory class.
"""

import logging
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncpg
from config.settings import settings

logger = logging.getLogger(__name__)

class PGMemoryTools:
    """
    PostgreSQL implementation of memory tools for MCP Agent.
    
    This class provides the memory-related functions backed by PostgreSQL storage
    while maintaining an in-memory cache for fast access.
    """
    
    def __init__(self):
        """Initialize the memory tools with connection to PostgreSQL."""
        self.entities = {}  # In-memory cache
        self.relations = []  # In-memory cache
        self.db_pool = None
        self.initialized = False
        logger.info("PostgreSQL memory tools initialized")
    
    async def initialize(self):
        """Initialize the database connection and load data into memory."""
        if self.initialized:
            return
            
        # Create connection pool
        try:
            self.db_pool = await asyncpg.create_pool(
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD,
                database=settings.POSTGRES_DB,
                host=settings.POSTGRES_HOST,
                port=settings.POSTGRES_PORT,
                min_size=1,
                max_size=10
            )
            logger.info("Connected to PostgreSQL database")
            
            # Load data into memory
            await self._load_from_database()
            self.initialized = True
            
        except Exception as e:
            logger.error(f"Error connecting to PostgreSQL: {e}")
            # Fall back to in-memory only
            self.initialized = True
    
    async def _load_from_database(self):
        """Load all entities and relations from database into memory."""
        try:
            async with self.db_pool.acquire() as conn:
                # Load entities
                entities = await conn.fetch("SELECT * FROM memory_entities")
                for entity in entities:
                    # Load observations for this entity
                    observations = await conn.fetch(
                        "SELECT content FROM memory_observations WHERE entity_name = $1 ORDER BY created_at",
                        entity["entity_name"]
                    )
                    
                    self.entities[entity["entity_name"]] = {
                        "name": entity["entity_name"],
                        "entityType": entity["entity_type"],
                        "observations": [obs["content"] for obs in observations],
                        "conversation_id": entity["conversation_ref"],
                        "message_id": entity["message_ref"],
                        "metadata": entity["metadata"]
                    }
                
                # Load relations
                relations = await conn.fetch("SELECT * FROM memory_relations")
                for relation in relations:
                    self.relations.append({
                        "from": relation["from_entity"],
                        "to": relation["to_entity"],
                        "relationType": relation["relation_type"],
                        "id": relation["id"]
                    })
                
                logger.info(f"Loaded {len(self.entities)} entities and {len(self.relations)} relations from database")
                
        except Exception as e:
            logger.error(f"Error loading from database: {e}")
            # Continue with empty cache
    
    async def _persist_entity(self, entity_name: str):
        """Save a single entity to the database."""
        if not self.db_pool:
            logger.warning("Database connection not available, skipping persistence")
            return
            
        try:
            entity = self.entities[entity_name]
            
            async with self.db_pool.acquire() as conn:
                async with conn.transaction():
                    # Insert or update entity
                    await conn.execute(
                        """
                        INSERT INTO memory_entities 
                            (entity_name, entity_type, conversation_ref, message_ref, metadata, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (entity_name) 
                        DO UPDATE SET 
                            entity_type = $2, 
                            conversation_ref = $3, 
                            message_ref = $4, 
                            metadata = $5,
                            updated_at = $6
                        """,
                        entity_name, 
                        entity["entityType"],
                        entity.get("conversation_id"), 
                        entity.get("message_id"),
                        json.dumps(entity.get("metadata", {})),
                        datetime.now()
                    )
                    
                    # Delete existing observations and insert new ones
                    await conn.execute(
                        "DELETE FROM memory_observations WHERE entity_name = $1",
                        entity_name
                    )
                    
                    # Batch insert observations
                    if entity["observations"]:
                        await conn.executemany(
                            "INSERT INTO memory_observations (entity_name, content) VALUES ($1, $2)",
                            [(entity_name, obs) for obs in entity["observations"]]
                        )
        
        except Exception as e:
            logger.error(f"Error persisting entity {entity_name}: {e}")
    
    async def _persist_relation(self, relation):
        """Save a single relation to the database."""
        if not self.db_pool:
            logger.warning("Database connection not available, skipping persistence")
            return
            
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO memory_relations (id, from_entity, to_entity, relation_type)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (from_entity, to_entity, relation_type) 
                    DO UPDATE SET id = $1
                    """,
                    relation["id"], 
                    relation["from"], 
                    relation["to"], 
                    relation["relationType"]
                )
        
        except Exception as e:
            logger.error(f"Error persisting relation: {e}")
    
    async def _delete_entity_from_db(self, entity_name: str):
        """Delete an entity from the database."""
        if not self.db_pool:
            return
            
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM memory_entities WHERE entity_name = $1",
                    entity_name
                )
        except Exception as e:
            logger.error(f"Error deleting entity {entity_name}: {e}")
    
    async def _delete_relation_from_db(self, relation):
        """Delete a relation from the database."""
        if not self.db_pool:
            return
            
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    DELETE FROM memory_relations 
                    WHERE from_entity = $1 AND to_entity = $2 AND relation_type = $3
                    """,
                    relation["from"], relation["to"], relation["relationType"]
                )
        except Exception as e:
            logger.error(f"Error deleting relation: {e}")
    
    # Interface methods for CoordinatorMemory
    
    async def mcp_memory_create_entities(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create new entities in the knowledge graph."""
        await self.initialize()  # Ensure initialized
        
        for entity in entities:
            name = entity["name"]
            self.entities[name] = {
                "name": name,
                "entityType": entity["entityType"],
                "observations": entity.get("observations", []),
                "metadata": entity.get("metadata", {})
            }
            
            # Add any additional properties
            for key, value in entity.items():
                if key not in ["name", "entityType", "observations", "metadata"]:
                    self.entities[name][key] = value
                    
            logger.info(f"Entity created in memory: {name}")
            
            # Persist to database asynchronously
            await self._persist_entity(name)
        
        return {"status": "success", "created": len(entities)}
    
    async def mcp_memory_create_relations(self, relations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create new relations between entities in the knowledge graph."""
        await self.initialize()  # Ensure initialized
        
        created = 0
        
        for relation in relations:
            # Check that both entities exist
            if relation["from"] not in self.entities or relation["to"] not in self.entities:
                logger.warning(f"Cannot create relation, entities not found: {relation}")
                continue
                
            relation_with_id = {
                "from": relation["from"],
                "to": relation["to"],
                "relationType": relation["relationType"],
                "id": str(uuid.uuid4())
            }
            
            self.relations.append(relation_with_id)
            created += 1
            logger.info(f"Relation created in memory: {relation['from']} -> {relation['to']}")
            
            # Persist to database asynchronously
            await self._persist_relation(relation_with_id)
        
        return {"status": "success", "created": created}
    
    async def mcp_memory_add_observations(self, observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Add observations to existing entities."""
        await self.initialize()  # Ensure initialized
        
        count = 0
        changes = []
        
        for observation_item in observations:
            entity_name = observation_item["entityName"]
            
            if entity_name not in self.entities:
                logger.warning(f"Entity not found for observation: {entity_name}")
                continue
                
            for content in observation_item["contents"]:
                self.entities[entity_name]["observations"].append(content)
                count += 1
                
            changes.append(entity_name)
            logger.info(f"Added {len(observation_item['contents'])} observations to {entity_name}")
        
        # Persist changes to database asynchronously
        for entity_name in changes:
            await self._persist_entity(entity_name)
        
        return {"status": "success", "added": count}
    
    async def mcp_memory_delete_entities(self, entityNames: List[str]) -> Dict[str, Any]:
        """Delete entities and their relations from the knowledge graph."""
        await self.initialize()  # Ensure initialized
        
        count = 0
        relation_count = 0
        
        for name in entityNames:
            if name in self.entities:
                # Delete from memory
                del self.entities[name]
                count += 1
                
                # Delete relations involving this entity
                original_relations_count = len(self.relations)
                self.relations = [r for r in self.relations 
                                 if r["from"] != name and r["to"] != name]
                
                relation_count += original_relations_count - len(self.relations)
                
                logger.info(f"Entity deleted from memory: {name}")
                
                # Delete from database asynchronously
                await self._delete_entity_from_db(name)
        
        return {"status": "success", "deleted": count, "relations_deleted": relation_count}
    
    async def mcp_memory_delete_observations(self, deletions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Delete specific observations from entities."""
        await self.initialize()  # Ensure initialized
        
        count = 0
        changes = []
        
        for deletion in deletions:
            entity_name = deletion["entityName"]
            
            if entity_name not in self.entities:
                logger.warning(f"Entity not found for deletion: {entity_name}")
                continue
                
            observations_to_delete = set(deletion["observations"])
            original_count = len(self.entities[entity_name]["observations"])
            self.entities[entity_name]["observations"] = [
                obs for obs in self.entities[entity_name]["observations"]
                if obs not in observations_to_delete
            ]
            
            deleted = original_count - len(self.entities[entity_name]["observations"])
            if deleted > 0:
                changes.append(entity_name)
                count += deleted
            
            logger.info(f"Deleted {deleted} observations from {entity_name}")
        
        # Persist changes to database asynchronously
        for entity_name in changes:
            await self._persist_entity(entity_name)
        
        return {"status": "success", "deleted": count}
    
    async def mcp_memory_delete_relations(self, relations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Delete relations from the knowledge graph."""
        await self.initialize()  # Ensure initialized
        
        count = 0
        
        for relation in relations:
            # Filter out relations that match the criteria
            original_count = len(self.relations)
            relations_to_delete = [r for r in self.relations 
                                 if (r["from"] == relation["from"] and 
                                    r["to"] == relation["to"] and 
                                    r["relationType"] == relation["relationType"])]
            
            self.relations = [r for r in self.relations 
                             if not (r["from"] == relation["from"] and 
                                    r["to"] == relation["to"] and 
                                    r["relationType"] == relation["relationType"])]
            
            deleted = original_count - len(self.relations)
            count += deleted
            
            logger.info(f"Deleted {deleted} relations matching: {relation}")
            
            # Delete from database asynchronously
            for rel in relations_to_delete:
                await self._delete_relation_from_db(rel)
        
        return {"status": "success", "deleted": count}
    
    async def mcp_memory_read_graph(self, random_string: str) -> Dict[str, Any]:
        """Read the entire knowledge graph."""
        await self.initialize()  # Ensure initialized
        
        return {
            "nodes": [self.entities[name] for name in self.entities],
            "relations": self.relations
        }
    
    async def mcp_memory_search_nodes(self, query: str) -> Dict[str, Any]:
        """Search for nodes in the knowledge graph based on a query."""
        await self.initialize()  # Ensure initialized
        
        query = query.lower()
        matching_nodes = []
        
        for name, entity in self.entities.items():
            if (query in name.lower() or 
                query in entity["entityType"].lower() or
                any(query in obs.lower() for obs in entity["observations"])):
                matching_nodes.append(entity)
        
        return {
            "nodes": matching_nodes
        }
    
    async def mcp_memory_open_nodes(self, names: List[str]) -> Dict[str, Any]:
        """Retrieve specific nodes by their names."""
        await self.initialize()  # Ensure initialized
        
        matching_nodes = []
        related_relations = []
        
        for name in names:
            if name in self.entities:
                matching_nodes.append(self.entities[name])
                
                # Find relations involving this entity
                for relation in self.relations:
                    if relation["from"] == name or relation["to"] == name:
                        related_relations.append(relation)
        
        return {
            "nodes": matching_nodes,
            "relations": related_relations
        }
    
    async def mcp_memory_update_entities(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Update existing entities in the knowledge graph."""
        await self.initialize()  # Ensure initialized
        
        count = 0
        changes = []
        
        for entity in entities:
            name = entity["name"]
            
            if name not in self.entities:
                logger.warning(f"Entity not found for update: {name}")
                continue
            
            # Update fields
            if "entityType" in entity:
                self.entities[name]["entityType"] = entity["entityType"]
            
            if "observations" in entity:
                self.entities[name]["observations"] = entity["observations"]
            
            # Update additional fields
            for key, value in entity.items():
                if key not in ["name", "entityType", "observations"]:
                    self.entities[name][key] = value
            
            changes.append(name)
            count += 1
            logger.info(f"Entity updated in memory: {name}")
        
        # Persist changes to database asynchronously
        for entity_name in changes:
            await self._persist_entity(entity_name)
        
        return {"status": "success", "updated": count}
    
    async def mcp_memory_update_relations(self, relations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Update existing relations in the knowledge graph."""
        await self.initialize()  # Ensure initialized
        
        # In this implementation, we'll remove and re-create the relations
        to_delete = []
        to_create = []
        
        for relation in relations:
            to_delete.append(relation)
            to_create.append(relation)
            
        await self.mcp_memory_delete_relations(to_delete)
        result = await self.mcp_memory_create_relations(to_create)
        
        return {"status": "success", "updated": result.get("created", 0)}

# Initialize memory tools (lazy initialization - will connect when first used)
memory_tools = PGMemoryTools() 