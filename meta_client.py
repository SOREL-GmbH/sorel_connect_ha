import aiohttp
import asyncio
import logging
from functools import lru_cache

_LOGGER = logging.getLogger(__name__)

class MetaClient:
    def __init__(self, base_url: str, session: aiohttp.ClientSession):
        self._base = base_url
        self._session = session

    async def get_schema_for_client(self, client_id: str) -> dict:
        url = f"{self._base}/schema?client_id={client_id}"
        async with self._session.get(url, timeout=10) as r:
            r.raise_for_status()
            return await r.json()

    async def get_capabilities(self, client_type: str) -> dict:
        url = f"{self._base}/capabilities?type={client_type}"
        async with self._session.get(url, timeout=10) as r:
            r.raise_for_status()
            return await r.json()
