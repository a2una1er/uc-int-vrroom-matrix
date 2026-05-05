"""
VRRoomMiscEntity — ucapi Remote-Entity für REBOOT und HOTPLUG.
"""
import logging
from typing import Any

import ucapi
from ucapi import Remote, StatusCodes
from ucapi import remote

from http_client import HttpClient, HttpError

_LOG = logging.getLogger(__name__)

ENTITY_ID = "vrroom_misc"
ENTITY_NAME = "VRRoom Misc"

FEATURES = [remote.Features.SEND_CMD]

SIMPLE_COMMANDS = ["REBOOT", "HOTPLUG"]


class VRRoomMiscEntity(Remote):
    """Remote entity for VRRoom utility commands: REBOOT and HOTPLUG."""

    def __init__(self, http_client: HttpClient) -> None:
        self._http_client = http_client

        super().__init__(
            identifier=ENTITY_ID,
            name=ENTITY_NAME,
            features=FEATURES,
            attributes={remote.Attributes.STATE: remote.States.ON},
            simple_commands=SIMPLE_COMMANDS,
            cmd_handler=self._handle_command,
        )

    async def _handle_command(
        self,
        entity: "VRRoomMiscEntity",
        cmd_id: str,
        params: dict[str, Any] | None = None,
        websocket: Any | None = None,
    ) -> StatusCodes:
        # Unwrap send_cmd
        if cmd_id == remote.Commands.SEND_CMD:
            cmd_id = (params or {}).get("command", "")
            if not cmd_id:
                return StatusCodes.BAD_REQUEST

        if cmd_id == "REBOOT":
            return await self._simple_get("cmd?reboot")
        if cmd_id == "HOTPLUG":
            return await self._simple_get("cmd?hotplug=")

        _LOG.error("Unknown misc command: %s", cmd_id)
        return StatusCodes.NOT_IMPLEMENTED

    async def _simple_get(self, path: str) -> StatusCodes:
        _LOG.info("Misc command: GET http://%s/%s", "vrroom", path)
        result = await self._http_client.get(path)
        if isinstance(result, HttpError):
            _LOG.error("Command GET /%s failed: %s", path, result.message)
            return StatusCodes.SERVER_ERROR
        return StatusCodes.OK
