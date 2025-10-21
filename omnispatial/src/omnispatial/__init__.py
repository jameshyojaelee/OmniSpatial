"""OmniSpatial Python package."""

from importlib import metadata


def _load_version() -> str:
    """Return the installed package version, falling back to the source version."""
    try:
        return metadata.version("omnispatial")
    except metadata.PackageNotFoundError:
        return "0.1.0"


__all__ = ["__version__"]
__version__ = _load_version()
