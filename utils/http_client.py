"""
Reusable HTTP client utilities using httpx.

This module provides a centralized HTTP client for making API requests
across the application with consistent error handling and configuration.
"""

import httpx
from typing import Optional, Dict, Any
from pathlib import Path
import asyncio
from functools import wraps


def async_retry(max_attempts=3, backoff_base=2, exceptions=(httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError)):
    """
    Decorator for retrying async functions with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        backoff_base: Base for exponential backoff (seconds)
        exceptions: Tuple of exception types to catch and retry
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts - 1:
                        raise
                    wait_time = backoff_base ** attempt
                    print(f"Request failed with {type(e).__name__}, retrying in {wait_time}s (attempt {attempt + 1}/{max_attempts})...")
                    await asyncio.sleep(wait_time)
            return None
        return wrapper
    return decorator


class HTTPClient:
    """Async HTTP client wrapper for making API requests."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 90.0,
    ):
        """
        Initialize HTTP client.

        Args:
            base_url: Base URL for all requests
            headers: Default headers to include in all requests
            timeout: Request timeout in seconds (default: 90.0)
        """
        self.base_url = base_url
        self.default_headers = headers or {}
        self.timeout = timeout

    @async_retry(max_attempts=3)
    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> httpx.Response:
        """
        Make a GET request.

        Args:
            url: URL endpoint (appended to base_url if base_url is set)
            params: Query parameters
            headers: Additional headers (merged with default headers)
            **kwargs: Additional arguments passed to httpx.get

        Returns:
            httpx.Response object

        Raises:
            httpx.HTTPStatusError: If response status is 4xx or 5xx
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            full_url = self._build_url(url)
            merged_headers = {**self.default_headers, **(headers or {})}

            response = await client.get(
                full_url, params=params, headers=merged_headers, **kwargs
            )
            response.raise_for_status()
            return response

    async def post(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> httpx.Response:
        """
        Make a POST request.

        Args:
            url: URL endpoint (appended to base_url if base_url is set)
            data: Form data to send
            json: JSON data to send
            headers: Additional headers (merged with default headers)
            **kwargs: Additional arguments passed to httpx.post

        Returns:
            httpx.Response object

        Raises:
            httpx.HTTPStatusError: If response status is 4xx or 5xx
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            full_url = self._build_url(url)
            merged_headers = {**self.default_headers, **(headers or {})}

            response = await client.post(
                full_url, data=data, json=json, headers=merged_headers, **kwargs
            )
            response.raise_for_status()
            return response

    async def download_file(
        self,
        url: str,
        file_path: Path | str,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Path:
        """
        Download a file from a URL and save it to disk.

        Args:
            url: URL to download from
            file_path: Local path to save the file
            headers: Additional headers (merged with default headers)
            **kwargs: Additional arguments passed to httpx.get

        Returns:
            Path object of the saved file

        Raises:
            httpx.HTTPStatusError: If response status is 4xx or 5xx
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            full_url = self._build_url(url)
            merged_headers = {**self.default_headers, **(headers or {})}

            response = await client.get(full_url, headers=merged_headers, **kwargs)
            response.raise_for_status()

            # Ensure file_path is a Path object
            file_path = Path(file_path) if isinstance(file_path, str) else file_path

            # Create parent directories if they don't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            with open(file_path, "wb") as f:
                f.write(response.content)

            return file_path

    async def get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Make a GET request and return JSON response.

        Args:
            url: URL endpoint (appended to base_url if base_url is set)
            params: Query parameters
            headers: Additional headers (merged with default headers)
            **kwargs: Additional arguments passed to httpx.get

        Returns:
            Parsed JSON response as dictionary

        Raises:
            httpx.HTTPStatusError: If response status is 4xx or 5xx
        """
        response = await self.get(url, params=params, headers=headers, **kwargs)
        return response.json()

    def _build_url(self, url: str) -> str:
        """
        Build full URL from base_url and endpoint.

        Args:
            url: URL endpoint or full URL

        Returns:
            Complete URL string
        """
        if not self.base_url:
            return url

        # If URL is already absolute, return as-is
        if url.startswith(("http://", "https://")):
            return url

        # Remove trailing slash from base_url and leading slash from url
        base = self.base_url.rstrip("/")
        endpoint = url.lstrip("/")

        return f"{base}/{endpoint}"


class PexelsClient(HTTPClient):
    """Specialized HTTP client for Pexels API."""

    PHOTOS_BASE = "https://api.pexels.com/v1"
    VIDEOS_BASE = "https://api.pexels.com/videos"

    def __init__(self, api_key: str):
        """
        Initialize Pexels client.

        Args:
            api_key: Pexels API key
        """
        super().__init__(headers={"Authorization": api_key}, timeout=120.0)
        self.api_key = api_key

    async def search_photos(
        self,
        query: str,
        orientation: str = "portrait",
        per_page: int = 1,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        Search for photos on Pexels.

        Args:
            query: Search query
            orientation: Image orientation (landscape, portrait, square)
            per_page: Number of results per page (max 80)
            page: Page number

        Returns:
            JSON response with search results
        """
        self.base_url = self.PHOTOS_BASE
        return await self.get_json(
            "/search",
            params={
                "query": query,
                "orientation": orientation,
                "per_page": per_page,
                "page": page,
            },
        )

    async def get_photo(self, photo_id: int) -> Dict[str, Any]:
        """
        Get a specific photo by ID.

        Args:
            photo_id: Pexels photo ID

        Returns:
            JSON response with photo details
        """
        self.base_url = self.PHOTOS_BASE
        return await self.get_json(f"/photos/{photo_id}")

    async def search_videos(
        self,
        query: str,
        orientation: str = "portrait",
        per_page: int = 1,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        Search for videos on Pexels.

        Args:
            query: Search query
            orientation: Video orientation (landscape, portrait, square)
            per_page: Number of results per page (max 80)
            page: Page number

        Returns:
            JSON response with search results
        """
        self.base_url = self.VIDEOS_BASE
        return await self.get_json(
            "/search",
            params={
                "query": query,
                "orientation": orientation,
                "per_page": per_page,
                "page": page,
            },
        )

    async def get_video(self, video_id: int) -> Dict[str, Any]:
        """
        Get a specific video by ID.

        Args:
            video_id: Pexels video ID

        Returns:
            JSON response with video details
        """
        self.base_url = self.VIDEOS_BASE
        return await self.get_json(f"/videos/{video_id}")
