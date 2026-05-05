"""
HTTP client for the HDFury VRRoom integration.
Sends GET requests to the VRRoom HTTP API.
"""
import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

from settings import GlobalSettings

_LOG = logging.getLogger(__name__)

# Connection timeout: 5 seconds total per request
_TIMEOUT = aiohttp.ClientTimeout(total=5)


@dataclass
class HttpError:
    """Represents an HTTP error (non-200 response or connection failure)."""
    status_code: int | None  # None for connection errors
    message: str


class HttpClient:
    """
    Sends HTTP GET requests to the VRRoom device.

    Uses a persistent aiohttp session for efficiency.
    Call close() when done (or use open/close lifecycle via driver connect/disconnect).
    """

    def __init__(self, settings: GlobalSettings) -> None:
        self._settings = settings
        self._session: aiohttp.ClientSession | None = None

    def _get_session(self) -> aiohttp.ClientSession:
        """Return existing session or create a new one."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=_TIMEOUT)
        return self._session

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _build_url(self, path: str) -> str:
        """Build the full URL for a given path."""
        return f"http://{self._settings.host}/{path}"

    async def get(self, path: str) -> dict[str, Any] | HttpError:
        """
        Send HTTP GET to http://{host}/{path}.
        Returns parsed JSON dict or HttpError.
        Timeout: 5s. No retry, no auth, no body.
        """
        url = self._build_url(path)
        try:
            session = self._get_session()
            async with session.get(url) as response:
                if response.status != 200:
                    msg = f"HTTP {response.status} from {url}"
                    _LOG.error(msg)
                    return HttpError(status_code=response.status, message=msg)
                # Some VRRoom commands (insel, reboot, hotplug) return an
                # empty body — only parse JSON if there is content.
                text = await response.text()
                if not text.strip():
                    return {}
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    _LOG.warning("Non-JSON response from %s: %r", url, text[:200])
                    return {}
        except asyncio.TimeoutError:
            msg = f"Timeout connecting to {url}"
            _LOG.error(msg)
            return HttpError(status_code=None, message=msg)
        except aiohttp.ClientError as exc:
            msg = f"Connection error to {url}: {exc}"
            _LOG.error(msg)
            return HttpError(status_code=None, message=msg)
