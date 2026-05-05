"""
HTTP client for the HDFury VRRoom integration.
Sends GET requests to the VRRoom HTTP API.
"""
import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

from settings import GlobalSettings

_LOG = logging.getLogger(__name__)


@dataclass
class HttpError:
    """Represents an HTTP error (non-200 response or connection failure)."""
    status_code: int | None  # None for connection errors
    message: str


class HttpClient:
    """
    Sends HTTP GET requests to the VRRoom device.

    Invariants (Req 7.1–7.5):
    - Only GET method
    - No Authorization header
    - No request body
    - URL always built from g.host
    - No retry on failure
    """

    def __init__(self, settings: GlobalSettings) -> None:
        self._settings = settings

    def _build_url(self, path: str) -> str:
        """Build the full URL for a given path (Req 7.4)."""
        return f"http://{self._settings.host}/{path}"

    async def get(self, path: str) -> dict[str, Any] | HttpError:
        """
        Send HTTP GET to http://{host}/{path}.
        Returns parsed JSON dict or HttpError.
        No retry, no auth, no body (Req 7.1–7.5).
        """
        url = self._build_url(path)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        # Req 2.6, 3.8, 5.3, 6.3
                        msg = f"HTTP {response.status} from {url}"
                        _LOG.error(msg)
                        return HttpError(status_code=response.status, message=msg)
                    # Some VRRoom commands (insel, reboot, hotplug) return an
                    # empty body — only parse JSON if there is content.
                    text = await response.text()
                    if not text.strip():
                        return {}
                    try:
                        import json
                        return json.loads(text)
                    except json.JSONDecodeError as exc:
                        _LOG.warning("Non-JSON response from %s: %r", url, text[:200])
                        return {}
        except aiohttp.ClientError as exc:
            # Req 2.7
            msg = f"Connection error to {url}: {exc}"
            _LOG.error(msg)
            return HttpError(status_code=None, message=msg)
