import httpx
from typing import Optional, Dict, Any
from config.settings import settings

class CloudMessageRepository:
    def __init__(self, api_base_url: str = None, token: Optional[str] = None):
        if api_base_url is None:
            api_base_url = settings.BACKEND_URL
        self.api_base_url = api_base_url.rstrip("/")
        self.token = token

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def get_by_conversation(self, conversation_id: str, limit: int = 10, before_message_id: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.api_base_url}/api/v1/conversations/{conversation_id}"
        params = {"limit": limit}
        if before_message_id:
            params["before_message_id"] = before_message_id
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def add_message(self, conversation_id: str, content: str, role: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.api_base_url}/api/v1/conversations/{conversation_id}/messages"
        data = {"content": content, "role": role}
        if metadata:
            data["metadata"] = metadata
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=data, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def create(self, conversation_id: str, obj_in: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.api_base_url}/api/v1/conversations/{conversation_id}/messages"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=obj_in, headers=self._headers())
            resp.raise_for_status()
            return resp.json() 