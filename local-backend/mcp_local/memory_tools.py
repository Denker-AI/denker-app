"""
Memory Tools for MCP Agent

This module provides memory tools integration for the MCP Agent, implementing
the interfaces expected by the CoordinatorMemory class.
"""

import logging
from typing import Dict, Any, List, Optional
import json
from datetime import datetime
import uuid
import os
from pathlib import Path

logger = logging.getLogger(__name__)

class MemoryTools:
    """
    Implementation of memory tools for MCP Agent.
    
    This class provides the memory-related functions that can be used
    by CoordinatorMemory to interact with a knowledge graph.
    """
    
    def __init__(self, storage_path: str = None):
        """
        Initialize the memory tools with a knowledge graph.
        
        Args:
            storage_path: Path to store the memory data (default: ./memory_data)
        """
        # Set storage path - use environment variable if provided, otherwise fallback to relative path
        if storage_path:
            self.storage_path = storage_path
        elif os.environ.get('DENKER_MEMORY_DATA_PATH'):
            self.storage_path = os.environ.get('DENKER_MEMORY_DATA_PATH')
        else:
            self.storage_path = os.path.join(os.getcwd(), 'memory_data')
        os.makedirs(self.storage_path, exist_ok=True)
        
        self.entities_file = os.path.join(self.storage_path, 'entities.json')
        self.relations_file = os.path.join(self.storage_path, 'relations.json')
        
        # Load existing data or initialize empty structures
        self.entities = self._load_entities()
        self.relations = self._load_relations()
        
        logger.info(f"Memory tools initialized with {len(self.entities)} entities and {len(self.relations)} relations")
    
    def _load_entities(self) -> Dict[str, Dict[str, Any]]:
        """Load entities from storage."""
        if os.path.exists(self.entities_file):
            try:
                with open(self.entities_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading entities: {e}")
        return {}
    
    def _load_relations(self) -> List[Dict[str, Any]]:
        """Load relations from storage."""
        if os.path.exists(self.relations_file):
            try:
                with open(self.relations_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading relations: {e}")
        return []
    
    def _save_entities(self):
        """Save entities to storage."""
        try:
            with open(self.entities_file, 'w') as f:
                json.dump(self.entities, f)
        except Exception as e:
            logger.error(f"Error saving entities: {e}")
    
    def _save_relations(self):
        """Save relations to storage."""
        try:
            with open(self.relations_file, 'w') as f:
                json.dump(self.relations, f)
        except Exception as e:
            logger.error(f"Error saving relations: {e}")
    
    async def mcp_memory_create_entities(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create new entities in the knowledge graph."""
        for entity in entities:
            name = entity["name"]
            self.entities[name] = {
                "name": name,
                "entityType": entity["entityType"],
                "observations": entity.get("observations", [])
            }
            logger.info(f"Entity created: {name}")
        
        # Save changes to disk
        self._save_entities()
        
        return {"status": "success", "created": len(entities)}
    
    async def mcp_memory_create_relations(self, relations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create new relations between entities in the knowledge graph."""
        created = 0
        
        for relation in relations:
            # Check that both entities exist
            if relation["from"] not in self.entities or relation["to"] not in self.entities:
                logger.warning(f"Cannot create relation, entities not found: {relation}")
                continue
                
            self.relations.append({
                "from": relation["from"],
                "to": relation["to"],
                "relationType": relation["relationType"],
                "id": str(uuid.uuid4())
            })
            created += 1
            logger.info(f"Relation created: {relation['from']} -> {relation['to']}")
        
        # Save changes to disk
        if created > 0:
            self._save_relations()
        
        return {"status": "success", "created": created}
    
    async def mcp_memory_add_observations(self, observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Add observations to existing entities."""
        count = 0
        changes = False
        
        for observation_item in observations:
            entity_name = observation_item["entityName"]
            
            if entity_name not in self.entities:
                logger.warning(f"Entity not found: {entity_name}")
                continue
                
            for content in observation_item["contents"]:
                self.entities[entity_name]["observations"].append(content)
                count += 1
                changes = True
                
            logger.info(f"Added {len(observation_item['contents'])} observations to {entity_name}")
        
        # Save changes to disk
        if changes:
            self._save_entities()
        
        return {"status": "success", "added": count}
    
    async def mcp_memory_delete_entities(self, entityNames: List[str]) -> Dict[str, Any]:
        """Delete entities and their relations from the knowledge graph."""
        count = 0
        relation_count = 0
        entities_changed = False
        relations_changed = False
        
        for name in entityNames:
            if name in self.entities:
                del self.entities[name]
                count += 1
                entities_changed = True
                
                # Delete relations involving this entity
                original_relations_count = len(self.relations)
                self.relations = [r for r in self.relations 
                                 if r["from"] != name and r["to"] != name]
                
                relation_count += original_relations_count - len(self.relations)
                if relation_count > 0:
                    relations_changed = True
                
                logger.info(f"Entity deleted: {name}")
        
        # Save changes to disk
        if entities_changed:
            self._save_entities()
        if relations_changed:
            self._save_relations()
        
        return {"status": "success", "deleted": count, "relations_deleted": relation_count}
    
    async def mcp_memory_delete_observations(self, deletions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Delete specific observations from entities."""
        count = 0
        changes = False
        
        for deletion in deletions:
            entity_name = deletion["entityName"]
            
            if entity_name not in self.entities:
                logger.warning(f"Entity not found: {entity_name}")
                continue
                
            observations_to_delete = set(deletion["observations"])
            original_count = len(self.entities[entity_name]["observations"])
            self.entities[entity_name]["observations"] = [
                obs for obs in self.entities[entity_name]["observations"]
                if obs not in observations_to_delete
            ]
            
            deleted = original_count - len(self.entities[entity_name]["observations"])
            if deleted > 0:
                changes = True
                count += deleted
            
            logger.info(f"Deleted {deleted} observations from {entity_name}")
        
        # Save changes to disk
        if changes:
            self._save_entities()
        
        return {"status": "success", "deleted": count}
    
    async def mcp_memory_delete_relations(self, relations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Delete relations from the knowledge graph."""
        count = 0
        changes = False
        
        for relation in relations:
            # Filter out relations that match the criteria
            original_count = len(self.relations)
            self.relations = [r for r in self.relations 
                             if not (r["from"] == relation["from"] and 
                                    r["to"] == relation["to"] and 
                                    r["relationType"] == relation["relationType"])]
            
            deleted = original_count - len(self.relations)
            if deleted > 0:
                changes = True
                count += deleted
            
            logger.info(f"Deleted {deleted} relations matching: {relation}")
        
        # Save changes to disk
        if changes:
            self._save_relations()
        
        return {"status": "success", "deleted": count}
    
    async def mcp_memory_read_graph(self, random_string: str) -> Dict[str, Any]:
        """Read the entire knowledge graph."""
        return {
            "nodes": [self.entities[name] for name in self.entities],
            "relations": self.relations
        }
    
    async def mcp_memory_search_nodes(self, query: str) -> Dict[str, Any]:
        """Search for nodes in the knowledge graph based on a query."""
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
        count = 0
        changes = False
        
        for entity in entities:
            name = entity["name"]
            
            if name not in self.entities:
                logger.warning(f"Entity not found for update: {name}")
                continue
                
            if "entityType" in entity:
                self.entities[name]["entityType"] = entity["entityType"]
                changes = True
                
            if "observations" in entity:
                self.entities[name]["observations"] = entity["observations"]
                changes = True
                
            count += 1
            logger.info(f"Entity updated: {name}")
        
        # Save changes to disk
        if changes:
            self._save_entities()
        
        return {"status": "success", "updated": count}
    
    async def mcp_memory_update_relations(self, relations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Update existing relations in the knowledge graph."""
        # In this simple implementation, we'll remove and re-create the relations
        to_delete = []
        to_create = []
        
        for relation in relations:
            to_delete.append(relation)
            to_create.append(relation)
            
        await self.mcp_memory_delete_relations(to_delete)
        result = await self.mcp_memory_create_relations(to_create)
        
        # No need to save here as both delete_relations and create_relations already save
        
        return {"status": "success", "updated": result.get("created", 0)}

    async def mcp_memory_health_check(self) -> bool:
        """Check memory backend health via /api/v1/memory/health endpoint."""
        try:
            resp = await self.client.get(f"{self.backend_url}/api/v1/memory/health")
            data = resp.json()
            return data.get("status") == "ok"
        except Exception as e:
            logger.error(f"Memory health check failed: {e}")
            return False

# Initialize the memory tools with persistence
# This ensures that memory is saved to disk and loaded across server restarts
memory_tools = MemoryTools() 