import httpx
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class ConnectorHttpClient:
    """
    A base HTTP client for connectors with built-in retry logic 
    and common patterns for API interaction.
    """

    def __init__(
        self, 
        base_url: str = "", 
        headers: Optional[Dict[str, str]] = None, 
        timeout: int = 30
    ):
        self.base_url = base_url.rstrip('/')
        self.headers = headers or {
            "User-Agent": "agent-os-connectors/1.0.0",
            "Content-Type": "application/json"
        }
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """
        Lazily initialize the AsyncClient.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url, 
                headers=self.headers, 
                timeout=self.timeout
            )
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True
    )
    async def request(
        self, 
        method: str, 
        url: str, 
        **kwargs
    ) -> httpx.Response:
        """
        Makes a request with retry logic for network errors and 5xx statuses.
        """
        response = await self.client.request(method, url, **kwargs)
        # Raise for 4xx/5xx status codes so retry logic can catch 5xx
        if response.status_code >= 500:
            response.raise_for_status()
        return response

    async def get(self, url: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> httpx.Response:
        return await self.request("GET", url, params=params, **kwargs)

    async def post(self, url: str, json: Optional[Dict[str, Any]] = None, **kwargs) -> httpx.Response:
        return await self.request("POST", url, json=json, **kwargs)

    async def put(self, url: str, json: Optional[Dict[str, Any]] = None, **kwargs) -> httpx.Response:
        return await self.request("PUT", url, json=json, **kwargs)

    async def delete(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("DELETE", url, **kwargs)

    async def close(self):
        """
        Closes the underlying HTTP client.
        """
        if self._client:
            await self._client.aclose()
            self._client = None
