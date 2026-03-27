"""DBC Inventory Analytics – private tool for DivineBeadCraft."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("dbc-inventory-analytics")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = ["__version__"]
