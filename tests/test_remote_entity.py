"""
Tests für VRRoomMiscEntity (Remote entity for REBOOT and HOTPLUG commands).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from http_client import HttpClient, HttpError
from remote_entity import VRRoomMiscEntity, ENTITY_ID
from ucapi import StatusCodes, remote


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_entity(http_client: HttpClient | None = None) -> VRRoomMiscEntity:
    """Create a VRRoomMiscEntity with a mock HttpClient."""
    if http_client is None:
        http_client = MagicMock(spec=HttpClient)
        http_client.get = AsyncMock(return_value={})
        http_client._settings = MagicMock()
        http_client._settings.host = "192.168.178.76"
    return VRRoomMiscEntity(http_client)


# ---------------------------------------------------------------------------
# REBOOT command tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reboot_command():
    """REBOOT simple command calls GET /cmd?reboot."""
    client = MagicMock(spec=HttpClient)
    client.get = AsyncMock(return_value={})
    client._settings = MagicMock()
    client._settings.host = "192.168.178.76"
    entity = make_entity(client)

    result = await entity._handle_command(entity, remote.Commands.SEND_CMD, {"command": "REBOOT"})
    assert result == StatusCodes.OK
    client.get.assert_called_once_with("cmd?reboot")


@pytest.mark.asyncio
async def test_hotplug_command():
    """HOTPLUG simple command calls GET /cmd?hotplug= (with trailing =)."""
    client = MagicMock(spec=HttpClient)
    client.get = AsyncMock(return_value={})
    client._settings = MagicMock()
    client._settings.host = "192.168.178.76"
    entity = make_entity(client)

    result = await entity._handle_command(entity, remote.Commands.SEND_CMD, {"command": "HOTPLUG"})
    assert result == StatusCodes.OK
    client.get.assert_called_once_with("cmd?hotplug=")


@pytest.mark.asyncio
async def test_unknown_command_returns_not_implemented():
    """Unknown command returns NOT_IMPLEMENTED."""
    client = MagicMock(spec=HttpClient)
    client.get = AsyncMock(return_value={})
    client._settings = MagicMock()
    client._settings.host = "192.168.178.76"
    entity = make_entity(client)

    result = await entity._handle_command(entity, remote.Commands.SEND_CMD, {"command": "INVALID"})
    assert result == StatusCodes.NOT_IMPLEMENTED
    client.get.assert_not_called()


@pytest.mark.asyncio
async def test_empty_command_returns_bad_request():
    """Empty command string returns BAD_REQUEST."""
    client = MagicMock(spec=HttpClient)
    client.get = AsyncMock(return_value={})
    client._settings = MagicMock()
    client._settings.host = "192.168.178.76"
    entity = make_entity(client)

    result = await entity._handle_command(entity, remote.Commands.SEND_CMD, {"command": ""})
    assert result == StatusCodes.BAD_REQUEST


@pytest.mark.asyncio
async def test_http_error_returns_server_error():
    """If the HTTP GET fails, SERVER_ERROR is returned."""
    client = MagicMock(spec=HttpClient)
    client.get = AsyncMock(return_value=HttpError(status_code=500, message="error"))
    client._settings = MagicMock()
    client._settings.host = "192.168.178.76"
    entity = make_entity(client)

    result = await entity._handle_command(entity, remote.Commands.SEND_CMD, {"command": "REBOOT"})
    assert result == StatusCodes.SERVER_ERROR
