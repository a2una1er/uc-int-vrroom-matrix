"""
Global settings for the HDFury VRRoom integration driver.
"""
from dataclasses import dataclass, field


@dataclass
class GlobalSettings:
    """Holds global configuration for the VRRoom driver."""
    host: str = "vrroom"          # Fallback hostname (Req 1.2)
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


# Global settings instance (Req 1.3)
g = GlobalSettings()
