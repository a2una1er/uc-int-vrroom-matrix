"""
Status parser for the HDFury VRRoom integration.

Parses the JSON response from /ssi/infopage.ssi into a typed DeviceStatus object.

The VRRoom API returns all fields as strings. Only portseltx0/portseltx1 are
converted to int — everything else is passed through unchanged in extra.
"""
import logging
from dataclasses import dataclass, field
from typing import Any

_LOG = logging.getLogger(__name__)

VALID_INPUT_VALUES = frozenset({0, 1, 2, 3, 4})
REQUIRED_FIELDS = ("portseltx0", "portseltx1")


@dataclass
class DeviceStatus:
    """Typed representation of the VRRoom device status."""
    portseltx0: int          # Active input for TX0 (0–4)
    portseltx1: int          # Active input for TX1 (0–4)
    extra: dict[str, Any] = field(default_factory=dict)  # All other fields, unchanged


@dataclass
class ParseError:
    """Represents a parse error when processing VRRoom JSON response."""
    message: str


class StatusParser:
    """
    Parses VRRoom /ssi/infopage.ssi JSON response into DeviceStatus.

    Only portseltx0/portseltx1 are converted (str → int, range 0–4).
    All other fields are kept as-is in the extra dict.
    """

    def parse(self, data: dict[str, Any]) -> "DeviceStatus | ParseError":
        """
        Parse a JSON dict into a DeviceStatus object.

        Returns ParseError if:
        - portseltx0 or portseltx1 are missing
        - portseltx0/portseltx1 cannot be converted to int in range 0–4
        """
        # Check required fields
        for field_name in REQUIRED_FIELDS:
            if field_name not in data:
                return ParseError(message=f"Missing required field: {field_name}")

        # Parse portseltx0 (str → int, range 0–4)
        try:
            tx0 = int(data["portseltx0"])
        except (ValueError, TypeError):
            return ParseError(message=f"Invalid value for portseltx0: {data['portseltx0']!r}")
        if tx0 not in VALID_INPUT_VALUES:
            return ParseError(message=f"portseltx0 value {tx0} out of range 0–4")

        # Parse portseltx1 (str → int, range 0–4)
        try:
            tx1 = int(data["portseltx1"])
        except (ValueError, TypeError):
            return ParseError(message=f"Invalid value for portseltx1: {data['portseltx1']!r}")
        if tx1 not in VALID_INPUT_VALUES:
            return ParseError(message=f"portseltx1 value {tx1} out of range 0–4")

        # Everything else goes into extra unchanged
        extra = {k: v for k, v in data.items() if k not in REQUIRED_FIELDS}

        return DeviceStatus(portseltx0=tx0, portseltx1=tx1, extra=extra)

    def serialize(self, status: DeviceStatus) -> dict[str, Any]:
        """
        Serialize a DeviceStatus back to a string dict (round-trip).
        """
        result: dict[str, Any] = {
            "portseltx0": str(status.portseltx0),
            "portseltx1": str(status.portseltx1),
        }
        result.update(status.extra)
        return result
