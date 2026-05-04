"""
Global settings for the HDFury VRRoom integration driver.
"""
from dataclasses import dataclass


@dataclass
class GlobalSettings:
    """Holds global configuration for the VRRoom driver."""
    host: str = "vrroom"  # Fallback hostname (Req 1.2)


# Global settings instance (Req 1.3)
g = GlobalSettings()
