"""Tests für driver.py und GlobalSettings."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from settings import GlobalSettings, g
from http_client import HttpClient, HttpError
from status_parser import DeviceStatus


# ---------------------------------------------------------------------------
# GlobalSettings tests
# ---------------------------------------------------------------------------

def test_default_host_is_vrroom():
    """Fallback-Host ist 'vrroom' wenn kein Host konfiguriert (Req 1.2)."""
    settings = GlobalSettings()
    assert settings.host == "vrroom"


def test_global_instance_default_host():
    """Globale Instanz g hat Fallback-Host 'vrroom'."""
    assert g.host == "vrroom"


def test_host_can_be_set():
    """Host kann gesetzt werden (Req 1.1)."""
    settings = GlobalSettings(host="192.168.1.100")
    assert settings.host == "192.168.1.100"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_status_dict(tx0: int = 0, tx1: int = 0) -> dict:
    return {
        "portseltx0": str(tx0),
        "portseltx1": str(tx1),
        "rx0in5v": "0",
        "rx1in5v": "0",
        "rx2in5v": "0",
        "rx3in5v": "0",
    }


def make_mock_http_client(success: bool = True, tx0: int = 1, tx1: int = 2) -> MagicMock:
    client = MagicMock(spec=HttpClient)
    if success:
        client.get = AsyncMock(return_value=make_status_dict(tx0, tx1))
    else:
        client.get = AsyncMock(
            return_value=HttpError(status_code=503, message="Service unavailable")
        )
    return client


# ---------------------------------------------------------------------------
# Property 12: Startup-Fetch genau einmal
# Feature: hdfury-vrroom-integration, Property 12: Startup-Fetch genau einmal
# Validates: Requirements 9.4
# ---------------------------------------------------------------------------

@given(
    tx0=st.integers(min_value=0, max_value=4),
    tx1=st.integers(min_value=0, max_value=4),
)
@h_settings(max_examples=100)
@pytest.mark.asyncio
async def test_startup_fetch_called_exactly_once(tx0, tx1):
    """On activation (CONNECT event), the status fetch is executed exactly once. Validates: Req 9.4."""
    import driver as drv

    mock_client = make_mock_http_client(success=True, tx0=tx0, tx1=tx1)

    from remote_entity import VRRoomRemoteEntity
    mock_entity = MagicMock(spec=VRRoomRemoteEntity)
    mock_entity.attributes = {}

    original_client = drv._http_client
    original_entity = drv._entity
    try:
        drv._http_client = mock_client
        drv._entity = mock_entity

        await drv._fetch_and_apply_status()

        assert mock_client.get.call_count == 1
        mock_client.get.assert_called_once_with("ssi/infopage.ssi")
    finally:
        drv._http_client = original_client
        drv._entity = original_entity


# ---------------------------------------------------------------------------
# Unit-Test: Startup-Fetch erfolgreich — Validates: Requirements 9.1, 9.2
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_startup_fetch_success_sets_entity_state():
    """When startup fetch succeeds, entity state is set to ON. Validates: Req 9.1, 9.2."""
    import driver as drv
    from ucapi import remote as ucapi_remote

    mock_client = make_mock_http_client(success=True, tx0=2, tx1=3)

    from remote_entity import VRRoomRemoteEntity
    mock_entity = MagicMock(spec=VRRoomRemoteEntity)
    mock_entity.attributes = {}

    original_client = drv._http_client
    original_entity = drv._entity
    try:
        drv._http_client = mock_client
        drv._entity = mock_entity

        result = await drv._fetch_and_apply_status()

        assert result is True
        assert mock_entity.attributes[ucapi_remote.Attributes.STATE] == ucapi_remote.States.ON
    finally:
        drv._http_client = original_client
        drv._entity = original_entity


# ---------------------------------------------------------------------------
# Unit-Test: Startup-Fetch fehlgeschlagen — Validates: Requirements 9.3
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_startup_fetch_failure_leaves_entity_unavailable():
    """When startup fetch fails, entity state remains UNAVAILABLE. Validates: Req 9.3."""
    import driver as drv
    from ucapi import remote as ucapi_remote

    mock_client = make_mock_http_client(success=False)

    from remote_entity import VRRoomRemoteEntity
    mock_entity = MagicMock(spec=VRRoomRemoteEntity)
    mock_entity.attributes = {ucapi_remote.Attributes.STATE: ucapi_remote.States.UNKNOWN}

    original_client = drv._http_client
    original_entity = drv._entity
    try:
        drv._http_client = mock_client
        drv._entity = mock_entity

        result = await drv._fetch_and_apply_status()

        assert result is False
        assert mock_entity.attributes[ucapi_remote.Attributes.STATE] == ucapi_remote.States.UNKNOWN
    finally:
        drv._http_client = original_client
        drv._entity = original_entity


@pytest.mark.asyncio
async def test_startup_fetch_parse_error_leaves_entity_unavailable():
    """When startup fetch returns unparseable data, entity remains uninitialized. Validates: Req 9.3."""
    import driver as drv
    from ucapi import remote as ucapi_remote

    from remote_entity import VRRoomRemoteEntity
    mock_entity = MagicMock(spec=VRRoomRemoteEntity)
    mock_entity.attributes = {ucapi_remote.Attributes.STATE: ucapi_remote.States.UNKNOWN}

    mock_client = MagicMock(spec=HttpClient)
    mock_client.get = AsyncMock(return_value={"some_field": "value"})

    original_client = drv._http_client
    original_entity = drv._entity
    try:
        drv._http_client = mock_client
        drv._entity = mock_entity

        result = await drv._fetch_and_apply_status()

        assert result is False
        assert mock_entity.attributes[ucapi_remote.Attributes.STATE] == ucapi_remote.States.UNKNOWN
    finally:
        drv._http_client = original_client
        drv._entity = original_entity


# ---------------------------------------------------------------------------
# Unit-Test: Remote-3-Verbindung löst Status-Abruf aus — Validates: Requirements 10.5
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connect_event_triggers_status_fetch():
    """When Remote Three connects (CONNECT event), a status fetch is triggered. Validates: Req 10.5."""
    import driver as drv

    mock_client = make_mock_http_client(success=True, tx0=0, tx1=1)

    from remote_entity import VRRoomRemoteEntity
    mock_entity = MagicMock(spec=VRRoomRemoteEntity)
    mock_entity.attributes = {}

    original_client = drv._http_client
    original_entity = drv._entity
    try:
        drv._http_client = mock_client
        drv._entity = mock_entity

        await drv.on_connect()

        mock_client.get.assert_called_once_with("ssi/infopage.ssi")
    finally:
        drv._http_client = original_client
        drv._entity = original_entity
