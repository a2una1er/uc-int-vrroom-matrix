"""
Einstiegspunkt für den HDFury VRRoom Integration Driver.

Initialisiert die ucapi IntegrationAPI, registriert die VRRoomRemoteEntity
und verwaltet den Verbindungslebenszyklus mit Remote Three.
"""
import asyncio
import logging
import os

import ucapi
from ucapi import remote

from http_client import HttpClient, HttpError
from remote_entity import VRRoomRemoteEntity
from settings import GlobalSettings, g
from status_parser import ParseError, StatusParser

_LOG = logging.getLogger(__name__)

# Path to driver.json relative to this file's location (../driver.json)
_DRIVER_JSON = os.path.join(os.path.dirname(__file__), "..", "driver.json")

# Module-level references so event handlers can access them
api = ucapi.IntegrationAPI()
_http_client: HttpClient | None = None
_entity: VRRoomRemoteEntity | None = None


async def _fetch_and_apply_status() -> bool:
    """
    Fetch device status from VRRoom and update entity state.

    Returns True on success, False on failure.
    Req 9.1, 9.2, 9.3, 10.5
    """
    if _http_client is None or _entity is None:
        _LOG.error("Driver not initialized: http_client or entity is None")
        return False

    result = await _http_client.get("ssi/infopage.ssi")
    if isinstance(result, HttpError):
        # Req 9.3: log error, remain UNAVAILABLE
        _LOG.error("Startup status fetch failed: %s", result.message)
        return False

    status = StatusParser().parse(result)
    if isinstance(status, ParseError):
        _LOG.error("Startup status parse failed: %s", status.message)
        return False

    # Update entity state to ON (Req 9.2)
    _entity.attributes[remote.Attributes.STATE] = remote.States.ON
    _LOG.info(
        "Status fetched: tx0=%d, tx1=%d", status.portseltx0, status.portseltx1
    )
    return True


@api.listens_to(ucapi.Events.CONNECT)
async def on_connect() -> None:
    """
    Handle Remote Three connection event.

    Fetches device status on connection (Req 9.1, 10.5).
    """
    _LOG.info("Remote Three connected — fetching device status")
    await _fetch_and_apply_status()


async def _setup_handler(msg: ucapi.SetupDriver) -> ucapi.SetupAction:
    """
    Handle driver setup flow.

    Extracts host from setup data and stores it in GlobalSettings (Req 1.1).
    """
    if isinstance(msg, ucapi.DriverSetupRequest):
        host = msg.setup_data.get("host", "vrroom")
        if host:
            g.host = host
            if _http_client is not None:
                _http_client._settings.host = host
            _LOG.info("Setup: host set to '%s'", host)
        return ucapi.SetupComplete()

    _LOG.warning("Unexpected setup message type: %s", type(msg))
    return ucapi.SetupError()


async def main() -> None:
    """
    Main entry point for the VRRoom integration driver.

    Initializes all components and starts the ucapi integration API.
    """
    global _http_client, _entity

    settings = GlobalSettings()
    # Keep global g in sync (g is the module-level instance used by HttpClient)
    g.host = settings.host

    _http_client = HttpClient(g)
    _entity = VRRoomRemoteEntity(_http_client)

    # Register entity (Req 10.2, 10.3)
    api.available_entities.add(_entity)

    # Start the integration API WebSocket server (Req 10.3)
    await api.init(_DRIVER_JSON, setup_handler=_setup_handler)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
