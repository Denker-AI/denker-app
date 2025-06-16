import httpx
from typing import Optional, Dict, Any, List
from config.settings import settings

class CloudAgentRepository:
    def __init__(self, api_base_url: str = None, token: Optional[str] = None):
        if api_base_url is None:
            api_base_url = settings.BACKEND_URL
        self.api_base_url = api_base_url.rstrip("/")
        self.token = token

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def create(self, obj_in: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.api_base_url}/api/v1/agents/logs"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=obj_in, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def get(self, id: str) -> Dict[str, Any]:
        url = f"{self.api_base_url}/api/v1/agents/logs/{id}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def get_by_query_id(self, query_id: str) -> List[Dict[str, Any]]:
        url = f"{self.api_base_url}/api/v1/agents/logs/query/{query_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def update(self, id: str, obj_in: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.api_base_url}/api/v1/agents/logs/{id}"
        async with httpx.AsyncClient() as client:
            resp = await client.put(url, json=obj_in, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def delete(self, id: str) -> Dict[str, Any]:
        url = f"{self.api_base_url}/api/v1/agents/logs/{id}"
        async with httpx.AsyncClient() as client:
            resp = await client.delete(url, headers=self._headers())
            resp.raise_for_status()
            return resp.json() 