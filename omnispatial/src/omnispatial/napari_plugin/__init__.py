"""Napari plugin entry points for OmniSpatial."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, List, Tuple

from napari_plugin_engine import napari_hook_implementation
from rich.console import Console

console = Console()


def _load_ngff(path: Path = Path(".")) -> None:
    """Placeholder dock widget callable that logs the requested path."""
    console.print(f"Requested NGFF bundle: {path}", style="magenta")
    console.print("Loading is not yet implemented.", style="yellow")


@napari_hook_implementation
def napari_experimental_provide_dock_widget() -> Iterable[Tuple[Callable[..., None], dict]]:
    """Expose the OmniSpatial loader dock widget to napari."""
    return [(_load_ngff, {"name": "OmniSpatial Loader"})]


__all__ = ["napari_experimental_provide_dock_widget"]
