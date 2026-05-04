"""
Tests für VRRoomRemoteEntity.

Enthält Unit-Tests und Property-Based Tests für das Befehlsmapping,
Read-Modify-Write-Verhalten und die Validierung von Input-Werten.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from http_client import HttpClient, HttpError
from settings import GlobalSettings
from status_parser import DeviceStatus
from remote_entity import VRRoomRemoteEntity
from ucapi import StatusCodes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_entity(http_client: HttpClient | None = None) -> VRRoomRemoteEntity:
    """Create a VRRoomRemoteEntity with a mock or real HttpClient."""
    if http_client is None:
        http_client = MagicMock(spec=HttpClient)
    return VRRoomRemoteEntity(http_client)


def make_status_dict(tx0: int = 0, tx1: int = 0) -> dict:
    """Create a minimal valid status dict as returned by the VRRoom API."""
    return {
        "portseltx0": str(tx0),
        "portseltx1": str(tx1),
        "rx0in5v": "0",
        "rx1in5v": "0",
        "rx2in5v": "0",
        "rx3in5v": "0",
    }


def make_mock_client(status_tx0: int = 0, status_tx1: int = 0) -> MagicMock:
    """Create a mock HttpClient that returns a valid status and OK for all GETs."""
    client = MagicMock(spec=HttpClient)

    async def mock_get(path: str):
        if "infopage" in path:
            return make_status_dict(status_tx0, status_tx1)
        return {}  # OK response for insel/reboot/hotplug

    client.get = AsyncMock(side_effect=mock_get)
    return client


# ---------------------------------------------------------------------------
# Property 3: Read-Modify-Write — unveränderte Seite bleibt erhalten
# Feature: hdfury-vrroom-integration, Property 3: Read-Modify-Write
# Validates: Requirements 3.1, 3.2
# ---------------------------------------------------------------------------

@given(
    current_tx0=st.integers(min_value=0, max_value=4),
    current_tx1=st.integers(min_value=0, max_value=4),
    new_tx0=st.integers(min_value=0, max_value=4),
)
@h_settings(max_examples=100)
@pytest.mark.asyncio
async def test_rmw_tx0_preserves_tx1(current_tx0, current_tx1, new_tx0):
    """
    Property 3 (TX0 side): When SELECT_TX0_RX{n} is sent, the insel command
    must contain tx1=current_tx1 unchanged.

    Validates: Requirements 3.1, 3.2
    """
    client = make_mock_client(current_tx0, current_tx1)
    entity = make_entity(client)

    cmd_map = {0: "SELECT_TX0_RX0", 1: "SELECT_TX0_RX1", 2: "SELECT_TX0_RX2",
               3: "SELECT_TX0_RX3", 4: "SELECT_TX0_COPY"}
    cmd_id = cmd_map[new_tx0]

    result = await entity.handle_command(cmd_id)
    assert result == StatusCodes.OK

    insel_calls = [call for call in client.get.call_args_list if "insel" in str(call)]
    assert len(insel_calls) == 1, f"Expected exactly 1 insel call, got {len(insel_calls)}"

    insel_path = insel_calls[0].args[0]
    expected_path = f"cmd?insel={new_tx0}%20{current_tx1}"
    assert insel_path == expected_path, (
        f"Expected '{expected_path}', got '{insel_path}' "
        f"(current_tx0={current_tx0}, current_tx1={current_tx1}, new_tx0={new_tx0})"
    )


@given(
    current_tx0=st.integers(min_value=0, max_value=4),
    current_tx1=st.integers(min_value=0, max_value=4),
    new_tx1=st.integers(min_value=0, max_value=4),
)
@h_settings(max_examples=100)
@pytest.mark.asyncio
async def test_rmw_tx1_preserves_tx0(current_tx0, current_tx1, new_tx1):
    """
    Property 3 (TX1 side): When SELECT_TX1_RX{n} is sent, the insel command
    must contain tx0=current_tx0 unchanged.

    Validates: Requirements 3.1, 3.2
    """
    client = make_mock_client(current_tx0, current_tx1)
    entity = make_entity(client)

    cmd_map = {0: "SELECT_TX1_RX0", 1: "SELECT_TX1_RX1", 2: "SELECT_TX1_RX2",
               3: "SELECT_TX1_RX3", 4: "SELECT_TX1_COPY"}
    cmd_id = cmd_map[new_tx1]

    result = await entity.handle_command(cmd_id)
    assert result == StatusCodes.OK

    insel_calls = [call for call in client.get.call_args_list if "insel" in str(call)]
    assert len(insel_calls) == 1, f"Expected exactly 1 insel call, got {len(insel_calls)}"

    insel_path = insel_calls[0].args[0]
    expected_path = f"cmd?insel={current_tx0}%20{new_tx1}"
    assert insel_path == expected_path, (
        f"Expected '{expected_path}', got '{insel_path}' "
        f"(current_tx0={current_tx0}, current_tx1={current_tx1}, new_tx1={new_tx1})"
    )


# ---------------------------------------------------------------------------
# Property 4: Validierung ungültiger Input-Werte
# Feature: hdfury-vrroom-integration, Property 4: Validierung ungültiger Input-Werte
# Validates: Requirements 3.6, 3.7
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_12_commands_use_valid_input_values():
    """All 12 simple commands map to valid input values (0–4). Validates: Req 3.6, 3.7."""
    from remote_entity import _TX_COMMANDS, _VALID_INPUT_VALUES

    for cmd_id, (tx_index, value) in _TX_COMMANDS.items():
        assert value in _VALID_INPUT_VALUES, (
            f"Command {cmd_id} maps to invalid value {value} (must be in 0–4)"
        )
        assert tx_index in (0, 1), (
            f"Command {cmd_id} has invalid tx_index {tx_index} (must be 0 or 1)"
        )


@pytest.mark.asyncio
async def test_unknown_command_makes_no_http_request():
    """An unknown/invalid command must not trigger any HTTP request. Validates: Req 3.6, 3.7."""
    client = MagicMock(spec=HttpClient)
    client.get = AsyncMock()
    entity = make_entity(client)

    result = await entity.handle_command("INVALID_COMMAND_XYZ")
    assert result == StatusCodes.NOT_IMPLEMENTED
    client.get.assert_not_called()


# ---------------------------------------------------------------------------
# Property 5: Fehlerweiterleitung bei Status-Abruf-Fehler
# Feature: hdfury-vrroom-integration, Property 5: Fehlerweiterleitung
# Validates: Requirements 3.9
# ---------------------------------------------------------------------------

@given(
    cmd_id=st.sampled_from([
        "SELECT_TX0_RX0", "SELECT_TX0_RX1", "SELECT_TX0_RX2", "SELECT_TX0_RX3",
        "SELECT_TX0_COPY", "SELECT_TX1_RX0", "SELECT_TX1_RX1", "SELECT_TX1_RX2",
        "SELECT_TX1_RX3", "SELECT_TX1_COPY",
    ])
)
@h_settings(max_examples=50)
@pytest.mark.asyncio
async def test_failed_status_fetch_prevents_insel_command(cmd_id: str):
    """If the status fetch fails (HttpError), no insel command must be sent. Validates: Req 3.9."""
    client = MagicMock(spec=HttpClient)

    async def mock_get(path: str):
        if "infopage" in path:
            return HttpError(status_code=503, message="Service unavailable")
        return {}

    client.get = AsyncMock(side_effect=mock_get)
    entity = make_entity(client)

    result = await entity.handle_command(cmd_id)
    assert result == StatusCodes.SERVER_ERROR

    insel_calls = [call for call in client.get.call_args_list if "insel" in str(call)]
    assert len(insel_calls) == 0, f"insel command was sent despite status fetch failure: {insel_calls}"


@given(
    cmd_id=st.sampled_from([
        "SELECT_TX0_RX0", "SELECT_TX0_RX1", "SELECT_TX0_RX2", "SELECT_TX0_RX3",
        "SELECT_TX0_COPY", "SELECT_TX1_RX0", "SELECT_TX1_RX1", "SELECT_TX1_RX2",
        "SELECT_TX1_RX3", "SELECT_TX1_COPY",
    ])
)
@h_settings(max_examples=50)
@pytest.mark.asyncio
async def test_parse_error_prevents_insel_command(cmd_id: str):
    """If the status response cannot be parsed, no insel command must be sent. Validates: Req 3.9."""
    client = MagicMock(spec=HttpClient)

    async def mock_get(path: str):
        if "infopage" in path:
            return {}  # Missing required fields → ParseError
        return {}

    client.get = AsyncMock(side_effect=mock_get)
    entity = make_entity(client)

    result = await entity.handle_command(cmd_id)
    assert result == StatusCodes.SERVER_ERROR

    insel_calls = [call for call in client.get.call_args_list if "insel" in str(call)]
    assert len(insel_calls) == 0, f"insel command was sent despite parse error: {insel_calls}"


# ---------------------------------------------------------------------------
# Unit-Test: Copy-Mode-Mapping — Validates: Requirements 4.1
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_select_tx0_copy_uses_input_value_4():
    """SELECT_TX0_COPY must send input value 4 for TX0. Validates: Req 4.1."""
    client = make_mock_client(status_tx0=2, status_tx1=1)
    entity = make_entity(client)

    result = await entity.handle_command("SELECT_TX0_COPY")
    assert result == StatusCodes.OK

    insel_calls = [call for call in client.get.call_args_list if "insel" in str(call)]
    assert len(insel_calls) == 1
    assert insel_calls[0].args[0] == "cmd?insel=4%201"


@pytest.mark.asyncio
async def test_select_tx1_copy_uses_input_value_4():
    """SELECT_TX1_COPY must send input value 4 for TX1. Validates: Req 4.1."""
    client = make_mock_client(status_tx0=3, status_tx1=0)
    entity = make_entity(client)

    result = await entity.handle_command("SELECT_TX1_COPY")
    assert result == StatusCodes.OK

    insel_calls = [call for call in client.get.call_args_list if "insel" in str(call)]
    assert len(insel_calls) == 1
    assert insel_calls[0].args[0] == "cmd?insel=3%204"


# ---------------------------------------------------------------------------
# Additional unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reboot_command():
    """REBOOT command must call GET /cmd?reboot."""
    client = MagicMock(spec=HttpClient)
    client.get = AsyncMock(return_value={})
    entity = make_entity(client)

    result = await entity.handle_command("REBOOT")
    assert result == StatusCodes.OK
    client.get.assert_called_once_with("cmd?reboot")


@pytest.mark.asyncio
async def test_hotplug_command():
    """HOTPLUG command must call GET /cmd?hotplug."""
    client = MagicMock(spec=HttpClient)
    client.get = AsyncMock(return_value={})
    entity = make_entity(client)

    result = await entity.handle_command("HOTPLUG")
    assert result == StatusCodes.OK
    client.get.assert_called_once_with("cmd?hotplug")


@pytest.mark.asyncio
async def test_on_maps_to_reboot():
    """ON command must be mapped to REBOOT."""
    from ucapi import remote as ucapi_remote
    client = MagicMock(spec=HttpClient)
    client.get = AsyncMock(return_value={})
    entity = make_entity(client)

    result = await entity.handle_command(ucapi_remote.Commands.ON)
    assert result == StatusCodes.OK
    client.get.assert_called_once_with("cmd?reboot")


@pytest.mark.asyncio
async def test_off_maps_to_reboot():
    """OFF command must be mapped to REBOOT."""
    from ucapi import remote as ucapi_remote
    client = MagicMock(spec=HttpClient)
    client.get = AsyncMock(return_value={})
    entity = make_entity(client)

    result = await entity.handle_command(ucapi_remote.Commands.OFF)
    assert result == StatusCodes.OK
    client.get.assert_called_once_with("cmd?reboot")


@pytest.mark.asyncio
async def test_toggle_maps_to_reboot():
    """TOGGLE command must be mapped to REBOOT."""
    from ucapi import remote as ucapi_remote
    client = MagicMock(spec=HttpClient)
    client.get = AsyncMock(return_value={})
    entity = make_entity(client)

    result = await entity.handle_command(ucapi_remote.Commands.TOGGLE)
    assert result == StatusCodes.OK
    client.get.assert_called_once_with("cmd?reboot")


@pytest.mark.asyncio
async def test_http_error_on_reboot_returns_server_error():
    """If REBOOT GET fails, SERVER_ERROR must be returned."""
    client = MagicMock(spec=HttpClient)
    client.get = AsyncMock(return_value=HttpError(status_code=500, message="error"))
    entity = make_entity(client)

    result = await entity.handle_command("REBOOT")
    assert result == StatusCodes.SERVER_ERROR


@pytest.mark.asyncio
async def test_http_error_on_insel_returns_server_error():
    """If the insel GET fails after a successful status fetch, SERVER_ERROR must be returned."""
    client = MagicMock(spec=HttpClient)

    async def mock_get(path: str):
        if "infopage" in path:
            return make_status_dict(0, 0)
        return HttpError(status_code=500, message="insel failed")

    client.get = AsyncMock(side_effect=mock_get)
    entity = make_entity(client)

    result = await entity.handle_command("SELECT_TX0_RX1")
    assert result == StatusCodes.SERVER_ERROR
