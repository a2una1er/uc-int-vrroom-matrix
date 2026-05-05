"""
VRRoom Select entities for TX0 and TX1 input selection.

Each entity presents a dropdown of named inputs (RX0–RX3 + Copy).
Selecting an option triggers a Read-Modify-Write insel command.
"""
import logging
from typing import Any

from ucapi import StatusCodes
from ucapi.select import Select, Attributes, States, Commands

from http_client import HttpClient, HttpError
from settings import GlobalSettings
from status_parser import StatusParser, ParseError

_LOG = logging.getLogger(__name__)

ENTITY_ID_TX0 = "vrroom_tx0"
ENTITY_ID_TX1 = "vrroom_tx1"


class VRRoomSelectEntity(Select):
    """
    ucapi Select entity for one VRRoom output (TX0 or TX1).

    Presents a dropdown of named inputs. On selection, performs a
    Read-Modify-Write to set the chosen input while keeping the other
    output unchanged.
    """

    def __init__(
        self,
        tx_index: int,
        settings: GlobalSettings,
        http_client: HttpClient,
    ) -> None:
        self._tx_index = tx_index
        self._settings = settings
        self._http_client = http_client
        self._parser = StatusParser()

        entity_id = ENTITY_ID_TX0 if tx_index == 0 else ENTITY_ID_TX1
        name = "TX0 Input" if tx_index == 0 else "TX1 Input"
        options = settings.input_options()

        super().__init__(
            identifier=entity_id,
            name=name,
            attributes={
                Attributes.STATE: States.ON,
                Attributes.OPTIONS: options,
                Attributes.CURRENT_OPTION: options[0],
            },
            cmd_handler=self._handle_command,
        )

    def update_options(self) -> None:
        """Refresh the options list from current settings (call after setup)."""
        self.attributes[Attributes.OPTIONS] = self._settings.input_options()

    def update_current_option(self, input_value: int) -> None:
        """Update the displayed current option from a raw input value."""
        self.attributes[Attributes.CURRENT_OPTION] = self._settings.input_value_to_option(input_value)

    async def _handle_command(
        self,
        entity: "VRRoomSelectEntity",
        cmd_id: str,
        params: dict[str, Any] | None,
    ) -> StatusCodes:
        """Handle select commands — same signature as SmartThings integration (no websocket param)."""
        options = self._settings.input_options()
        current = entity.attributes.get(Attributes.CURRENT_OPTION, options[0])
        current_idx = options.index(current) if current in options else 0

        # Resolve which option was selected
        if cmd_id == Commands.SELECT_OPTION:
            selected = (params or {}).get("option")
        elif cmd_id == Commands.SELECT_FIRST:
            selected = options[0]
        elif cmd_id == Commands.SELECT_LAST:
            selected = options[-1]
        elif cmd_id == Commands.SELECT_NEXT:
            selected = options[(current_idx + 1) % len(options)]
        elif cmd_id == Commands.SELECT_PREVIOUS:
            selected = options[(current_idx - 1) % len(options)]
        else:
            _LOG.error("Unknown select command: %s", cmd_id)
            return StatusCodes.NOT_IMPLEMENTED

        if not selected:
            return StatusCodes.BAD_REQUEST

        input_value = self._settings.option_to_input_value(selected)
        if input_value is None:
            _LOG.error("Unknown option: %r", selected)
            return StatusCodes.BAD_REQUEST

        result = await self._select_input(input_value)
        if result == StatusCodes.OK:
            entity.attributes[Attributes.CURRENT_OPTION] = selected
        return result

    async def _select_input(self, new_value: int) -> StatusCodes:
        """Read-Modify-Write: fetch status, update this TX, send insel command."""
        raw = await self._http_client.get("ssi/infopage.ssi")
        if isinstance(raw, HttpError):
            _LOG.error("Status fetch failed: %s", raw.message)
            return StatusCodes.SERVER_ERROR

        status = self._parser.parse(raw)
        if isinstance(status, ParseError):
            _LOG.error("Status parse failed: %s", status.message)
            return StatusCodes.SERVER_ERROR

        if self._tx_index == 0:
            tx0, tx1 = new_value, status.portseltx1
        else:
            tx0, tx1 = status.portseltx0, new_value

        path = f"cmd?insel={tx0}%20{tx1}"
        _LOG.info(
            "TX%d → input %d: GET http://%s/%s",
            self._tx_index, new_value, self._settings.host, path,
        )
        result = await self._http_client.get(path)
        if isinstance(result, HttpError):
            _LOG.error("insel command failed: %s", result.message)
            return StatusCodes.SERVER_ERROR

        return StatusCodes.OK
