"""Tests für driver.py und GlobalSettings."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from settings import GlobalSettings
from http_client import HttpClient, HttpError
from status_parser import DeviceStatus


# ---------------------------------------------------------------------------
# GlobalSettings tests
# ---------------------------------------------------------------------------

def test_default_host_is_ip():
    """Default-Host ist die konfigurierte IP-Adresse."""
    settings = GlobalSettings()
    assert settings.host == "192.168.178.76"


def test_host_can_be_set():
    """Host kann gesetzt werden."""
    settings = GlobalSettings(host="192.168.1.100")
    assert settings.host == "192.168.1.100"


def test_input_options_returns_five_entries():
    """input_options() returns exactly 5 entries (RX0-RX3 + Copy)."""
    settings = GlobalSettings()
    options = settings.input_options()
    assert len(options) == 5


def test_option_to_input_value_roundtrip():
    """option_to_input_value and input_value_to_option are inverse operations."""
    settings = GlobalSettings(rx0_name="PC", rx1_name="PS5", rx2_name="Switch",
                              rx3_name="Xbox", copy_name="Copy")
    for i in range(5):
        option = settings.input_value_to_option(i)
        assert settings.option_to_input_value(option) == i


def test_option_to_input_value_unknown_returns_none():
    """Unknown option returns None."""
    settings = GlobalSettings()
    assert settings.option_to_input_value("UNKNOWN") is None


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
    client._settings = MagicMock()
    client._settings.host = "192.168.178.76"
    client.close = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# _fetch_and_apply_status tests
# ---------------------------------------------------------------------------

@given(
    tx0=st.integers(min_value=0, max_value=4),
    tx1=st.integers(min_value=0, max_value=4),
)
@h_settings(max_examples=50)
@pytest.mark.asyncio
async def test_fetch_status_calls_infopage_once(tx0, tx1):
    """_fetch_and_apply_status calls GET ssi/infopage.ssi exactly once."""
    import driver as drv

    mock_client = make_mock_http_client(success=True, tx0=tx0, tx1=tx1)

    original_client = drv._http_client
    original_tx0 = drv._tx0_entity
    original_tx1 = drv._tx1_entity
    original_misc = drv._misc_entity
    try:
        drv._http_client = mock_client
        # Set entities to None to avoid update_attributes calls on mock api
        drv._tx0_entity = None
        drv._tx1_entity = None
        drv._misc_entity = None

        result = await drv._fetch_and_apply_status()

        assert result is True
        mock_client.get.assert_called_once_with("ssi/infopage.ssi")
    finally:
        drv._http_client = original_client
        drv._tx0_entity = original_tx0
        drv._tx1_entity = original_tx1
        drv._misc_entity = original_misc


@pytest.mark.asyncio
async def test_fetch_status_failure_returns_false():
    """When HTTP fetch fails, _fetch_and_apply_status returns False."""
    import driver as drv

    mock_client = make_mock_http_client(success=False)

    original_client = drv._http_client
    original_tx0 = drv._tx0_entity
    original_tx1 = drv._tx1_entity
    original_misc = drv._misc_entity
    original_errors = drv._consecutive_errors
    try:
        drv._http_client = mock_client
        drv._tx0_entity = None
        drv._tx1_entity = None
        drv._misc_entity = None
        drv._consecutive_errors = 0

        result = await drv._fetch_and_apply_status()

        assert result is False
        assert drv._consecutive_errors == 1
    finally:
        drv._http_client = original_client
        drv._tx0_entity = original_tx0
        drv._tx1_entity = original_tx1
        drv._misc_entity = original_misc
        drv._consecutive_errors = original_errors


@pytest.mark.asyncio
async def test_fetch_status_parse_error_returns_false():
    """When status response is unparseable, _fetch_and_apply_status returns False."""
    import driver as drv

    mock_client = MagicMock(spec=HttpClient)
    mock_client.get = AsyncMock(return_value={"some_field": "value"})  # Missing required fields
    mock_client._settings = MagicMock()
    mock_client._settings.host = "192.168.178.76"
    mock_client.close = AsyncMock()

    original_client = drv._http_client
    original_tx0 = drv._tx0_entity
    original_tx1 = drv._tx1_entity
    original_misc = drv._misc_entity
    original_errors = drv._consecutive_errors
    try:
        drv._http_client = mock_client
        drv._tx0_entity = None
        drv._tx1_entity = None
        drv._misc_entity = None
        drv._consecutive_errors = 0

        result = await drv._fetch_and_apply_status()

        assert result is False
        assert drv._consecutive_errors == 1
    finally:
        drv._http_client = original_client
        drv._tx0_entity = original_tx0
        drv._tx1_entity = original_tx1
        drv._misc_entity = original_misc
        drv._consecutive_errors = original_errors


@pytest.mark.asyncio
async def test_consecutive_errors_reset_on_success():
    """Successful fetch resets _consecutive_errors to 0."""
    import driver as drv

    mock_client = make_mock_http_client(success=True, tx0=0, tx1=1)

    original_client = drv._http_client
    original_tx0 = drv._tx0_entity
    original_tx1 = drv._tx1_entity
    original_misc = drv._misc_entity
    original_errors = drv._consecutive_errors
    try:
        drv._http_client = mock_client
        drv._tx0_entity = None
        drv._tx1_entity = None
        drv._misc_entity = None
        drv._consecutive_errors = 5  # simulate previous errors

        result = await drv._fetch_and_apply_status()

        assert result is True
        assert drv._consecutive_errors == 0
    finally:
        drv._http_client = original_client
        drv._tx0_entity = original_tx0
        drv._tx1_entity = original_tx1
        drv._misc_entity = original_misc
        drv._consecutive_errors = original_errors
