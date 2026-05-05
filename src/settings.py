"""
Global settings for the HDFury VRRoom integration driver.
"""
import json
import logging
import os
from dataclasses import dataclass, asdict

_LOG = logging.getLogger(__name__)

# Config file path — uses UC_CONFIG_HOME if available (on-device), else current dir
_CONFIG_DIR = os.environ.get("UC_CONFIG_HOME", os.getcwd())
_CONFIG_FILE = os.path.join(_CONFIG_DIR, "vrroom_config.json")


@dataclass
class GlobalSettings:
    """Holds global configuration for the VRRoom driver."""
    host: str = "192.168.178.76"  # Default IP
    rx0_name: str = "RX0"         # Display name for input 0
    rx1_name: str = "RX1"         # Display name for input 1
    rx2_name: str = "RX2"         # Display name for input 2
    rx3_name: str = "RX3"         # Display name for input 3
    copy_name: str = "Copy"       # Display name for copy mode (input 4)
    poll_interval_ms: int = 5000  # Polling interval in milliseconds (0 = disabled)

    def input_options(self) -> list[str]:
        """Return the ordered list of option labels for the Select entities."""
        return [
            self.rx0_name,
            self.rx1_name,
            self.rx2_name,
            self.rx3_name,
            self.copy_name,
        ]

    def option_to_input_value(self, option: str) -> int | None:
        """Map a display name back to its input value (0–4), or None if unknown."""
        options = self.input_options()
        try:
            return options.index(option)
        except ValueError:
            return None

    def input_value_to_option(self, value: int) -> str:
        """Map an input value (0–4) to its display name."""
        options = self.input_options()
        if 0 <= value < len(options):
            return options[value]
        return str(value)

    def save(self) -> None:
        """Persist settings to config file."""
        try:
            os.makedirs(os.path.dirname(_CONFIG_FILE), exist_ok=True)
            with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2)
            _LOG.info("Settings saved to %s", _CONFIG_FILE)
        except OSError as exc:
            _LOG.error("Failed to save settings: %s", exc)

    def load(self) -> None:
        """Load settings from config file if it exists."""
        if not os.path.exists(_CONFIG_FILE):
            _LOG.info("No config file found at %s, using defaults", _CONFIG_FILE)
            return
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.host = data.get("host", self.host)
            self.rx0_name = data.get("rx0_name", self.rx0_name)
            self.rx1_name = data.get("rx1_name", self.rx1_name)
            self.rx2_name = data.get("rx2_name", self.rx2_name)
            self.rx3_name = data.get("rx3_name", self.rx3_name)
            self.copy_name = data.get("copy_name", self.copy_name)
            self.poll_interval_ms = data.get("poll_interval_ms", self.poll_interval_ms)
            _LOG.info("Settings loaded from %s: host=%s", _CONFIG_FILE, self.host)
        except (OSError, json.JSONDecodeError) as exc:
            _LOG.error("Failed to load settings: %s", exc)


# Global settings instance (Req 1.3)
g = GlobalSettings()
g.load()  # Load persisted settings on import
