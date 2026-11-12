"""Package version shared by the public SDK and CLI."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("dicehub-python")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0+unknown"
