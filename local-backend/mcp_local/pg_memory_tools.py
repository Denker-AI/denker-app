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
import httpx

# Attempt to import LocalUserStore
# This might need adjustment based on actual file structure and potential circular dependencies
from core.user_store import LocalUserStore

logger = logging.getLogger(__name__)

class CloudMemoryTools:
    def __init__(self, backend_url: str = None):
        if backend_url is None:
            backend_url = settings.BACKEND_URL
        self.backend_url = backend_url.rstrip("/")
        # self.client is initialized on demand in _get_client()

    async def _get_client(self) -> httpx.AsyncClient:
        user_info = LocalUserStore.get_user() # Get user_info from the store
        token = None
        if user_info and isinstance(user_info, dict):
            token = user_info.get("token")
            
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        else:
            logger.warning("CloudMemoryTools: No token found in LocalUserStore. Calls to protected memory endpoints will likely fail.")
        # Increase timeout to 30 seconds
        return httpx.AsyncClient(headers=headers, timeout=30.0)
    
    async def mcp_memory_create_entities(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        async with await self._get_client() as client:
            resp = await client.post(f"{self.backend_url}/api/v1/memory/entities", json={"entities": entities})
        resp.raise_for_status()
        return resp.json()
    
    async def mcp_memory_create_relations(self, relations: List[Dict[str, Any]]) -> Dict[str, Any]:
        async with await self._get_client() as client:
            resp = await client.post(f"{self.backend_url}/api/v1/memory/relations", json={"relations": relations})
        resp.raise_for_status()
        return resp.json()
    
    async def mcp_memory_add_observations(self, observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        async with await self._get_client() as client:
            resp = await client.post(f"{self.backend_url}/api/v1/memory/observations", json={"observations": observations})
        resp.raise_for_status()
        return resp.json()
    
    async def mcp_memory_delete_entities(self, entityNames: List[str]) -> Dict[str, Any]:
        async with await self._get_client() as client:
            resp = await client.request("DELETE", f"{self.backend_url}/api/v1/memory/entities", json={"entityNames": entityNames})
        resp.raise_for_status()
        return resp.json()
    
    async def mcp_memory_delete_observations(self, deletions: List[Dict[str, Any]]) -> Dict[str, Any]:
        async with await self._get_client() as client:
            resp = await client.request("DELETE", f"{self.backend_url}/api/v1/memory/observations", json={"deletions": deletions})
        resp.raise_for_status()
        return resp.json()
    
    async def mcp_memory_delete_relations(self, relations: List[Dict[str, Any]]) -> Dict[str, Any]:
        async with await self._get_client() as client:
            resp = await client.request("DELETE", f"{self.backend_url}/api/v1/memory/relations", json={"relations": relations})
        resp.raise_for_status()
        return resp.json()
    
    async def mcp_memory_read_graph(self, random_string: str) -> Dict[str, Any]:
        async with await self._get_client() as client:
            resp = await client.get(f"{self.backend_url}/api/v1/memory/graph")
        resp.raise_for_status()
        return resp.json()
    
    async def mcp_memory_search_nodes(self, query: str) -> Dict[str, Any]:
        async with await self._get_client() as client:
            resp = await client.get(f"{self.backend_url}/api/v1/memory/search", params={"query": query})
        resp.raise_for_status()
        return resp.json()
    
    async def mcp_memory_open_nodes(self, names: List[str]) -> Dict[str, Any]:
        async with await self._get_client() as client:
            resp = await client.post(f"{self.backend_url}/api/v1/memory/open", json={"names": names})
        resp.raise_for_status()
        return resp.json()
    
    async def mcp_memory_update_entities(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        async with await self._get_client() as client:
            resp = await client.put(f"{self.backend_url}/api/v1/memory/entities", json={"entities": entities})
        resp.raise_for_status()
        return resp.json()
    
    async def mcp_memory_update_relations(self, relations: List[Dict[str, Any]]) -> Dict[str, Any]:
        async with await self._get_client() as client:
            resp = await client.put(f"{self.backend_url}/api/v1/memory/relations", json={"relations": relations})
        resp.raise_for_status()
        return resp.json()

    async def mcp_memory_health_check(self) -> bool:
        """Check memory backend health via /api/v1/memory/health endpoint."""
        try:
            async with await self._get_client() as client:
                resp = await client.get(f"{self.backend_url}/api/v1/memory/health")
            data = resp.json()
            ok = data.get("status") == "ok"
            if ok:
                logger.info("Memory health check succeeded: backend is reachable.")
            else:
                logger.error(f"Memory health check failed: {data}")
            return ok
        except Exception as e:
            logger.error(f"Memory health check failed: {e}")
            return False

# Global instance is now fine, as it gets token dynamically
memory_tools = CloudMemoryTools() 