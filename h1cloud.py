"""Client for H1 Panel API. Credentials must be provided via Render environment."""
import logging
from urllib.parse import quote
import aiohttp
from config import config

log = logging.getLogger(__name__)

class H1CloudClient:
    def __init__(self):
        self.base = config.H1CLOUD_API_BASE.rstrip("/")
        self.token = config.H1CLOUD_API_TOKEN

    @property
    def configured(self):
        return bool(self.base and self.token)

    async def request(self, method: str, path: str, payload=None):
        if not self.configured:
            raise RuntimeError("H1 Panel API не настроен: задайте H1CLOUD_API_TOKEN в Render")
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(method, f"{self.base}{path}", headers=headers, json=payload) as resp:
                try: data = await resp.json(content_type=None)
                except Exception: data = {"error": await resp.text()}
                if resp.status >= 400 or data.get("ok") is False:
                    raise RuntimeError(f"H1 API {resp.status}: {data.get('error', 'ошибка запроса')}")
                return data

    async def create_client(self, user_id: int, days: int):
        payload = {"name": f"omniro_{user_id}", "days": max(1, int(days)), "device_limit": max(0, config.H1CLOUD_DEVICE_LIMIT)}
        if config.H1CLOUD_TRAFFIC_LIMIT_GB > 0:
            payload["traffic_limit_gb"] = config.H1CLOUD_TRAFFIC_LIMIT_GB
        data = await self.request("POST", "/create", payload)
        client = data.get("client") or data
        return client.get("subscription_url") or client.get("sub_url") or client.get("link") or ""

    async def extend_client(self, user_id: int, days: int):
        return await self.request("PATCH", f"/clients/{quote(f'omniro_{user_id}', safe='')}", {"days": max(1, int(days))})

    async def get_client(self, user_id: int):
        return await self.request("GET", f"/clients/{quote(f'omniro_{user_id}', safe='')}")

h1cloud_client = H1CloudClient()
