"""
VRRoomRemoteEntity — ucapi Remote-Entity für den HDFury VRRoom.

Empfängt Befehle von Remote Three und delegiert sie an den HttpClient.
Unterstützt Eingangsumschaltung (Read-Modify-Write), Reboot und HotPlug.
"""
import logging
from typing import Any

import ucapi
from ucapi import Remote, StatusCodes
from ucapi import remote

from http_client import HttpClient, HttpError
from status_parser import StatusParser, ParseError

_LOG = logging.getLogger(__name__)

ENTITY_ID = "vrroom_remote"
ENTITY_NAME = "VRRoom"

FEATURES = [
    remote.Features.ON_OFF,
    remote.Features.TOGGLE,
    remote.Features.SEND_CMD,
]

# All 12 simple commands supported by the VRRoom entity
SIMPLE_COMMANDS = [
    "SELECT_TX0_RX0",
    "SELECT_TX0_RX1",
    "SELECT_TX0_RX2",
    "SELECT_TX0_RX3",
    "SELECT_TX0_COPY",
    "SELECT_TX1_RX0",
    "SELECT_TX1_RX1",
    "SELECT_TX1_RX2",
    "SELECT_TX1_RX3",
    "SELECT_TX1_COPY",
    "REBOOT",
    "HOTPLUG",
]

# Mapping: command id → (tx_index, input_value)
# tx_index 0 = TX0, tx_index 1 = TX1
# input_value: 0–3 = RX0–RX3, 4 = COPY
_TX_COMMANDS: dict[str, tuple[int, int]] = {
    "SELECT_TX0_RX0":  (0, 0),
    "SELECT_TX0_RX1":  (0, 1),
    "SELECT_TX0_RX2":  (0, 2),
    "SELECT_TX0_RX3":  (0, 3),
    "SELECT_TX0_COPY": (0, 4),
    "SELECT_TX1_RX0":  (1, 0),
    "SELECT_TX1_RX1":  (1, 1),
    "SELECT_TX1_RX2":  (1, 2),
    "SELECT_TX1_RX3":  (1, 3),
    "SELECT_TX1_COPY": (1, 4),
}

_VALID_INPUT_VALUES = frozenset({0, 1, 2, 3, 4})


class VRRoomRemoteEntity(Remote):
    """
    ucapi Remote-Entity für den HDFury VRRoom HDMI-Matrix-Switch.

    Unterstützt Eingangsumschaltung (Read-Modify-Write), Reboot und HotPlug.
    """

    def __init__(self, http_client: HttpClient) -> None:
        self._http_client = http_client
        self._parser = StatusParser()

        super().__init__(
            identifier=ENTITY_ID,
            name=ENTITY_NAME,
            features=FEATURES,
            attributes={remote.Attributes.STATE: remote.States.UNKNOWN},
            simple_commands=SIMPLE_COMMANDS,
            cmd_handler=self._handle_command,
        )

    async def _handle_command(
        self,
        entity: "VRRoomRemoteEntity",
        cmd_id: str,
        params: dict[str, Any] | None = None,
    ) -> StatusCodes:
        """
        Command handler registered with ucapi.

        Receives commands from Remote 3 and delegates to HttpClient.
        """
        return await self.handle_command(cmd_id, params or {})

    async def handle_command(
        self,
        cmd_id: str,
        params: dict[str, Any] | None = None,
    ) -> StatusCodes:
        """
        Execute a command by cmd_id.

        Mapping:
        - SELECT_TX*_RX* / SELECT_TX*_COPY → Read-Modify-Write insel
        - REBOOT → GET /cmd?reboot
        - HOTPLUG → GET /cmd?hotplug
        - on / off / toggle → REBOOT
        """
        # Map on/off/toggle to REBOOT (Req 5.7)
        if cmd_id in (remote.Commands.ON, remote.Commands.OFF, remote.Commands.TOGGLE):
            cmd_id = "REBOOT"

        # Simple commands: REBOOT and HOTPLUG
        if cmd_id == "REBOOT":
            return await self._simple_get("cmd?reboot")

        if cmd_id == "HOTPLUG":
            return await self._simple_get("cmd?hotplug")

        # TX input selection commands (Read-Modify-Write)
        if cmd_id in _TX_COMMANDS:
            tx_index, new_value = _TX_COMMANDS[cmd_id]

            # Validate input value (Req 3.6, 3.7)
            if new_value not in _VALID_INPUT_VALUES:
                _LOG.error("Invalid input value %d for command %s", new_value, cmd_id)
                return StatusCodes.BAD_REQUEST

            return await self._select_input(tx_index, new_value)

        _LOG.error("Unknown command: %s", cmd_id)
        return StatusCodes.NOT_IMPLEMENTED

    async def _simple_get(self, path: str) -> StatusCodes:
        """Send a simple GET request and return OK or SERVER_ERROR."""
        result = await self._http_client.get(path)
        if isinstance(result, HttpError):
            _LOG.error("Command GET /%s failed: %s", path, result.message)
            return StatusCodes.SERVER_ERROR
        return StatusCodes.OK

    async def _select_input(self, tx_index: int, new_value: int) -> StatusCodes:
        """
        Read-Modify-Write: fetch current status, update one TX, send insel command.

        tx_index: 0 = TX0, 1 = TX1
        new_value: 0–4
        """
        # Step 1: Fetch current status (Req 3.1, 3.2)
        raw = await self._http_client.get("ssi/infopage.ssi")
        if isinstance(raw, HttpError):
            _LOG.error("Status fetch failed: %s", raw.message)
            return StatusCodes.SERVER_ERROR

        status = self._parser.parse(raw)
        if isinstance(status, ParseError):
            _LOG.error("Status parse failed: %s", status.message)
            return StatusCodes.SERVER_ERROR

        # Step 2: Determine new tx0/tx1 values, keeping the other unchanged
        if tx_index == 0:
            tx0 = new_value
            tx1 = status.portseltx1
        else:
            tx0 = status.portseltx0
            tx1 = new_value

        # Step 3: Send insel command (Req 3.3, 3.4)
        path = f"cmd?insel={tx0}%20{tx1}"
        result = await self._http_client.get(path)
        if isinstance(result, HttpError):
            _LOG.error("insel command failed: %s", result.message)
            return StatusCodes.SERVER_ERROR

        return StatusCodes.OK
