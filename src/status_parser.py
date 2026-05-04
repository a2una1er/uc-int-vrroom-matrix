"""
Status parser for the HDFury VRRoom integration.

Parses the JSON response from /ssi/infopage.ssi into a typed DeviceStatus object.

IMPORTANT: The VRRoom API returns ALL fields as strings, not native JSON types.
- portseltx0/portseltx1: string "0"–"4" → must be converted to int
- rx0in5v–rx3in5v: string "0" or "1" → must be converted to bool
"""
import logging
from dataclasses import dataclass, field
from typing import Any

_LOG = logging.getLogger(__name__)

VALID_INPUT_VALUES = frozenset({0, 1, 2, 3, 4})
SIGNAL_FIELDS = ("rx0in5v", "rx1in5v", "rx2in5v", "rx3in5v")
REQUIRED_FIELDS = ("portseltx0", "portseltx1")


@dataclass
class DeviceStatus:
    """Typed representation of the VRRoom device status."""
    # Required fields (Req 2.3, 8.3) — converted from string
    portseltx0: int          # Active input for TX0 (0–4), converted from string "0"–"4"
    portseltx1: int          # Active input for TX1 (0–4), converted from string "0"–"4"

    # Signal status (Req 2.4) — converted from string "0"/"1"
    rx0in5v: bool            # "1" → True, "0" → False
    rx1in5v: bool
    rx2in5v: bool
    rx3in5v: bool

    # All remaining fields (Req 2.5, 8.1) — unchanged strings
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParseError:
    """Represents a parse error when processing VRRoom JSON response."""
    message: str


class StatusParser:
    """
    Parses VRRoom /ssi/infopage.ssi JSON response into DeviceStatus.

    All VRRoom API fields are strings. This parser converts:
    - portseltx0/portseltx1: str → int (valid range 0–4)
    - rx0in5v–rx3in5v: str → bool ("1"→True, "0"→False)
    - All other fields: kept as-is in extra dict
    """

    def parse(self, data: dict[str, Any]) -> "DeviceStatus | ParseError":
        """
        Parse a JSON dict (all values as strings) into a DeviceStatus object.

        Returns ParseError if:
        - portseltx0 or portseltx1 are missing (Req 2.8)
        - portseltx0/portseltx1 are not numeric strings or value outside 0–4 (Req 8.3, 8.4)
        - rx*in5v are not "0" or "1" (Req 8.4)
        """
        # Check required fields (Req 2.8)
        for field_name in REQUIRED_FIELDS:
            if field_name not in data:
                return ParseError(message=f"Missing required field: {field_name}")

        # Parse portseltx0 and portseltx1 (str → int, range 0–4)
        try:
            tx0 = int(data["portseltx0"])
        except (ValueError, TypeError):
            return ParseError(message=f"Invalid value for portseltx0: {data['portseltx0']!r}")
        if tx0 not in VALID_INPUT_VALUES:
            return ParseError(message=f"portseltx0 value {tx0} out of range 0–4")

        try:
            tx1 = int(data["portseltx1"])
        except (ValueError, TypeError):
            return ParseError(message=f"Invalid value for portseltx1: {data['portseltx1']!r}")
        if tx1 not in VALID_INPUT_VALUES:
            return ParseError(message=f"portseltx1 value {tx1} out of range 0–4")

        # Parse signal fields (str → bool, only "0" or "1" accepted)
        signal_values: dict[str, bool] = {}
        for sig_field in SIGNAL_FIELDS:
            raw = data.get(sig_field, "0")  # default to "0" if missing
            if raw == "1":
                signal_values[sig_field] = True
            elif raw == "0":
                signal_values[sig_field] = False
            else:
                return ParseError(message=f"Invalid value for {sig_field}: {raw!r} (expected '0' or '1')")

        # Collect extra fields (all fields not in REQUIRED_FIELDS or SIGNAL_FIELDS)
        known_fields = set(REQUIRED_FIELDS) | set(SIGNAL_FIELDS)
        extra = {k: v for k, v in data.items() if k not in known_fields}

        return DeviceStatus(
            portseltx0=tx0,
            portseltx1=tx1,
            rx0in5v=signal_values["rx0in5v"],
            rx1in5v=signal_values["rx1in5v"],
            rx2in5v=signal_values["rx2in5v"],
            rx3in5v=signal_values["rx3in5v"],
            extra=extra,
        )

    def serialize(self, status: DeviceStatus) -> dict[str, Any]:
        """
        Serialize a DeviceStatus back to a JSON-compatible dict with string values.

        Conversions:
        - int → str(value)  (e.g. 2 → "2")
        - True → "1", False → "0"
        - extra fields: unchanged

        Round-trip: serialize(parse(data)) == data (Req 8.2)
        """
        result: dict[str, Any] = {
            "portseltx0": str(status.portseltx0),
            "portseltx1": str(status.portseltx1),
            "rx0in5v": "1" if status.rx0in5v else "0",
            "rx1in5v": "1" if status.rx1in5v else "0",
            "rx2in5v": "1" if status.rx2in5v else "0",
            "rx3in5v": "1" if status.rx3in5v else "0",
        }
        result.update(status.extra)
        return result
