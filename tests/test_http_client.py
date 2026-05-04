"""
Tests for HttpClient.

Property-based tests use hypothesis.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

import aiohttp

from http_client import HttpClient, HttpError
from settings import GlobalSettings


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_client(host: str = "vrroom") -> HttpClient:
    return HttpClient(GlobalSettings(host=host))


# ---------------------------------------------------------------------------
# Property 1: URL construction for status fetch
# Feature: hdfury-vrroom-integration, Property 1: URL-Konstruktion für Status-Abruf
# Validates: Requirements 2.1, 7.4
# ---------------------------------------------------------------------------

@given(
    host=st.text(
        min_size=1,
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters=".-_"
        )
    )
)
@h_settings(max_examples=100)
def test_status_url_construction(host):
    """For any valid host, status URL must be http://{host}/ssi/infopage.ssi (Req 2.1, 7.4)."""
    client = make_client(host)
    url = client._build_url("ssi/infopage.ssi")
    assert url == f"http://{host}/ssi/infopage.ssi"


# ---------------------------------------------------------------------------
# Property 2: URL construction for input switching
# Feature: hdfury-vrroom-integration, Property 2: URL-Konstruktion für Eingangsumschaltung
# Validates: Requirements 3.3, 3.4, 7.4
# ---------------------------------------------------------------------------

@given(
    host=st.text(
        min_size=1,
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters=".-_"
        )
    ),
    tx0=st.integers(min_value=0, max_value=4),
    tx1=st.integers(min_value=0, max_value=4),
)
@h_settings(max_examples=100)
def test_insel_url_construction(host, tx0, tx1):
    """For any valid host and tx0/tx1, insel URL must be correct (Req 3.3, 3.4, 7.4)."""
    client = make_client(host)
    url = client._build_url(f"cmd?insel={tx0}%20{tx1}")
    assert url == f"http://{host}/cmd?insel={tx0}%20{tx1}"


# ---------------------------------------------------------------------------
# Property 6: HTTP error handling
# Feature: hdfury-vrroom-integration, Property 6: HTTP-Fehlerbehandlung
# Validates: Requirements 2.6
# ---------------------------------------------------------------------------

@given(status_code=st.integers(min_value=100, max_value=599).filter(lambda x: x != 200))
@h_settings(max_examples=100)
@pytest.mark.asyncio
async def test_non_200_returns_http_error(status_code):
    """For any non-200 status code, get() must return HttpError with that code (Req 2.6)."""
    client = make_client()
    mock_response = AsyncMock()
    mock_response.status = status_code
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("http_client.aiohttp.ClientSession", return_value=mock_session):
        result = await client.get("ssi/infopage.ssi")

    assert isinstance(result, HttpError)
    assert result.status_code == status_code


# ---------------------------------------------------------------------------
# Property 11: No retry
# Feature: hdfury-vrroom-integration, Property 11: Kein Retry bei HTTP-Fehlern
# Validates: Requirements 7.5
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_retry_on_error():
    """On failure, request is attempted exactly once (Req 7.5)."""
    client = make_client()
    call_count = 0

    def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("connection refused"))
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        return mock_cm

    mock_session = AsyncMock()
    mock_session.get = mock_get
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("http_client.aiohttp.ClientSession", return_value=mock_session):
        result = await client.get("ssi/infopage.ssi")

    assert isinstance(result, HttpError)
    assert call_count == 1


# ---------------------------------------------------------------------------
# Unit test: connection error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connection_error_returns_http_error_with_none_status():
    """aiohttp.ClientError → HttpError(status_code=None) (Req 2.7)."""
    client = make_client()

    mock_session = AsyncMock()
    mock_session.get = MagicMock(side_effect=aiohttp.ClientError("refused"))
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("http_client.aiohttp.ClientSession", return_value=mock_session):
        result = await client.get("ssi/infopage.ssi")

    assert isinstance(result, HttpError)
    assert result.status_code is None
