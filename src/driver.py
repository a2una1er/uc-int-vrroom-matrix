"""
Einstiegspunkt für den HDFury VRRoom Integration Driver.
"""
import asyncio
import logging
import os

import ucapi
from ucapi import select

from http_client import HttpClient, HttpError
from remote_entity import VRRoomMiscEntity, ENTITY_ID as ENTITY_ID_MISC
from select_entity import VRRoomSelectEntity, ENTITY_ID_TX0, ENTITY_ID_TX1
from settings import GlobalSettings, g
from status_parser import ParseError, StatusParser

_LOG = logging.getLogger(__name__)

_DRIVER_JSON = os.path.join(os.path.dirname(__file__), "..", "driver.json")

loop = asyncio.new_event_loop()
api = ucapi.IntegrationAPI(loop)

_http_client: HttpClient | None = None
_tx0_entity: VRRoomSelectEntity | None = None
_tx1_entity: VRRoomSelectEntity | None = None
_misc_entity: VRRoomMiscEntity | None = None
_poll_task: asyncio.Task | None = None
_connected: bool = False
_consecutive_errors: int = 0
_MAX_ERRORS_BEFORE_BACKOFF = 3
_MAX_BACKOFF_MULTIPLIER = 6  # max 6x poll interval


async def _fetch_and_apply_status() -> bool:
    """Fetch device status and update Select entity current options."""
    global _consecutive_errors

    if _http_client is None:
        return False

    result = await _http_client.get("ssi/infopage.ssi")
    if isinstance(result, HttpError):
        _LOG.error("Status fetch failed: %s", result.message)
        _consecutive_errors += 1
        _set_entities_unavailable()
        return False

    status = StatusParser().parse(result)
    if isinstance(status, ParseError):
        _LOG.error("Status parse failed: %s", status.message)
        _consecutive_errors += 1
        _set_entities_unavailable()
        return False

    # Success — reset error counter and mark entities available
    _consecutive_errors = 0

    changed = False

    if _tx0_entity:
        new_option = g.input_value_to_option(status.portseltx0)
        old_option = _tx0_entity.attributes.get(select.Attributes.CURRENT_OPTION)
        if new_option != old_option:
            _tx0_entity.update_current_option(status.portseltx0)
            changed = True
        api.configured_entities.update_attributes(
            ENTITY_ID_TX0,
            {
                select.Attributes.STATE: select.States.ON,
                select.Attributes.OPTIONS: g.input_options(),
                select.Attributes.CURRENT_OPTION: _tx0_entity.attributes[select.Attributes.CURRENT_OPTION],
            },
        )

    if _tx1_entity:
        new_option = g.input_value_to_option(status.portseltx1)
        old_option = _tx1_entity.attributes.get(select.Attributes.CURRENT_OPTION)
        if new_option != old_option:
            _tx1_entity.update_current_option(status.portseltx1)
            changed = True
        api.configured_entities.update_attributes(
            ENTITY_ID_TX1,
            {
                select.Attributes.STATE: select.States.ON,
                select.Attributes.OPTIONS: g.input_options(),
                select.Attributes.CURRENT_OPTION: _tx1_entity.attributes[select.Attributes.CURRENT_OPTION],
            },
        )

    if changed:
        _LOG.info(
            "Status updated: tx0=%d (%s), tx1=%d (%s)",
            status.portseltx0, g.input_value_to_option(status.portseltx0),
            status.portseltx1, g.input_value_to_option(status.portseltx1),
        )

    # Keep misc entity state in sync
    if _misc_entity:
        from ucapi import remote
        api.configured_entities.update_attributes(
            ENTITY_ID_MISC,
            {remote.Attributes.STATE: remote.States.ON},
        )

    return True


def _set_entities_unavailable() -> None:
    """Mark all entities as UNAVAILABLE when VRRoom is unreachable."""
    if _tx0_entity:
        api.configured_entities.update_attributes(
            ENTITY_ID_TX0,
            {select.Attributes.STATE: select.States.UNAVAILABLE},
        )
    if _tx1_entity:
        api.configured_entities.update_attributes(
            ENTITY_ID_TX1,
            {select.Attributes.STATE: select.States.UNAVAILABLE},
        )
    if _misc_entity:
        from ucapi import remote
        api.configured_entities.update_attributes(
            ENTITY_ID_MISC,
            {remote.Attributes.STATE: remote.States.UNAVAILABLE},
        )


async def _poll_loop() -> None:
    """Background polling task with exponential backoff on errors."""
    _LOG.info("Polling started (interval: %d ms)", g.poll_interval_ms)
    while True:
        # Calculate sleep with backoff
        if _consecutive_errors >= _MAX_ERRORS_BEFORE_BACKOFF:
            multiplier = min(
                2 ** (_consecutive_errors - _MAX_ERRORS_BEFORE_BACKOFF),
                _MAX_BACKOFF_MULTIPLIER,
            )
            sleep_ms = g.poll_interval_ms * multiplier
            _LOG.debug("Backoff active: sleeping %d ms (errors: %d)", sleep_ms, _consecutive_errors)
        else:
            sleep_ms = g.poll_interval_ms

        await asyncio.sleep(sleep_ms / 1000.0)
        if not _connected:
            continue
        try:
            await _fetch_and_apply_status()
        except Exception as exc:
            _LOG.error("Polling error: %s", exc)


def _start_polling() -> None:
    """Start the polling task if interval > 0 and not already running."""
    global _poll_task
    if _poll_task is not None and not _poll_task.done():
        return  # already running
    if g.poll_interval_ms <= 0:
        _LOG.info("Polling disabled (interval = 0)")
        return
    _poll_task = asyncio.ensure_future(_poll_loop(), loop=loop)


def _stop_polling() -> None:
    """Stop the polling task."""
    global _poll_task
    if _poll_task is not None and not _poll_task.done():
        _poll_task.cancel()
        _poll_task = None
        _LOG.info("Polling stopped")


@api.listens_to(ucapi.Events.CONNECT)
async def on_connect() -> None:
    global _connected, _consecutive_errors
    _connected = True
    _consecutive_errors = 0
    _LOG.info("Remote Three connected — fetching device status")
    await api.set_device_state(ucapi.DeviceStates.CONNECTED)
    await _fetch_and_apply_status()
    _start_polling()


@api.listens_to(ucapi.Events.DISCONNECT)
async def on_disconnect() -> None:
    global _connected
    _connected = False
    _LOG.info("Remote Three disconnected — stopping polling")
    _stop_polling()
    if _http_client:
        await _http_client.close()


async def _setup_handler(msg: ucapi.SetupDriver) -> ucapi.SetupAction:
    if isinstance(msg, ucapi.DriverSetupRequest):
        data = msg.setup_data

        # Host
        host = data.get("host", "vrroom").strip() or "vrroom"
        g.host = host
        if _http_client is not None:
            _http_client._settings.host = host

        # Input names
        g.rx0_name = data.get("rx0_name", "").strip() or "RX0"
        g.rx1_name = data.get("rx1_name", "").strip() or "RX1"
        g.rx2_name = data.get("rx2_name", "").strip() or "RX2"
        g.rx3_name = data.get("rx3_name", "").strip() or "RX3"
        g.copy_name = data.get("copy_name", "").strip() or "Copy"

        # Polling interval
        try:
            g.poll_interval_ms = int(data.get("poll_interval_ms", 5000))
        except (ValueError, TypeError):
            g.poll_interval_ms = 5000

        # Refresh options on entities
        options = g.input_options()
        if _tx0_entity:
            _tx0_entity.update_options()
            api.configured_entities.update_attributes(
                ENTITY_ID_TX0, {select.Attributes.OPTIONS: options}
            )
        if _tx1_entity:
            _tx1_entity.update_options()
            api.configured_entities.update_attributes(
                ENTITY_ID_TX1, {select.Attributes.OPTIONS: options}
            )

        # Restart polling with new interval
        _stop_polling()
        if _connected:
            _start_polling()

        # Persist settings
        g.save()

        _LOG.info(
            "Setup: host=%s, inputs=%s, poll=%dms", host, options, g.poll_interval_ms
        )
        return ucapi.SetupComplete()

    _LOG.warning("Unexpected setup message: %s", type(msg))
    return ucapi.SetupError()


async def main() -> None:
    global _http_client, _tx0_entity, _tx1_entity, _misc_entity

    _http_client = HttpClient(g)
    _tx0_entity = VRRoomSelectEntity(tx_index=0, settings=g, http_client=_http_client)
    _tx1_entity = VRRoomSelectEntity(tx_index=1, settings=g, http_client=_http_client)
    _misc_entity = VRRoomMiscEntity(_http_client)

    # Set device_id on all entities so they can be added to activities
    _tx0_entity.device_id = "vrroom"
    _tx1_entity.device_id = "vrroom"
    _misc_entity.device_id = "vrroom"

    api.available_entities.add(_tx0_entity)
    api.available_entities.add(_tx1_entity)
    api.available_entities.add(_misc_entity)

    await api.init(_DRIVER_JSON, setup_handler=_setup_handler)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    loop.run_until_complete(main())
    loop.run_forever()
