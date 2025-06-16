import httpx
from typing import Optional, Dict, Any
from config.settings import settings

class CloudFileRepository:
    def __init__(self, api_base_url: str = None, token: Optional[str] = None):
        if api_base_url is None:
            api_base_url = settings.BACKEND_URL
        self.api_base_url = api_base_url.rstrip("/")
        self.token = token
        self.client = httpx.AsyncClient(timeout=30.0)

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def get(self, file_id: str):
        url = f"{self.api_base_url}/api/v1/files/{file_id}"
        resp = await self.client.get(url, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def list_by_user(self):
        url = f"{self.api_base_url}/api/v1/files/list"
        resp = await self.client.get(url, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def upload(self, file_path: str, query_id: Optional[str] = None, message_id: Optional[str] = None):
        url = f"{self.api_base_url}/api/v1/files/upload"
        files = {'file': open(file_path, 'rb')}
        data: Dict[str, Any] = {}
        if query_id: data['query_id'] = query_id
        if message_id: data['message_id'] = message_id
        resp = await self.client.post(url, files=files, data=data, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def delete(self, file_id: str):
        url = f"{self.api_base_url}/api/v1/files/{file_id}"
        resp = await self.client.delete(url, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def exists(self, file_hash: str, user_id: str):
        url = f"{self.api_base_url}/api/v1/files/exists"
        params = {"hash": file_hash, "user_id": user_id}
        resp = await self.client.get(url, params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def create_metadata(self, metadata: dict):
        url = f"{self.api_base_url}/api/v1/files/metadata"
        payload = {"metadata": metadata}
        resp = await self.client.post(url, json=payload, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def update_metadata(self, file_id: str, updates: dict):
        url = f"{self.api_base_url}/api/v1/files/{file_id}/update"
        payload = {"meta_data": updates.get("meta_data", updates)}
        resp = await self.client.post(url, json=payload, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def attach_to_message(self, file_id: str, message_id: str):
        url = f"{self.api_base_url}/api/v1/files/attach-to-message"
        payload = {"file_id": file_id, "message_id": message_id}
        resp = await self.client.post(url, json=payload, headers=self._headers())
        resp.raise_for_status()
        return resp.json() 

    async def close_client(self):
        await self.client.aclose() 