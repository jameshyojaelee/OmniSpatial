"""CLI entrypoint for OmniSpatial."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Type

import typer
from rich.console import Console
from rich.table import Table

from omnispatial import __version__
from omnispatial.adapters import SpatialAdapter, get_adapter
from omnispatial.adapters.cosmx import CosMxAdapter
from omnispatial.adapters.merfish import MerfishAdapter
from omnispatial.adapters.xenium import XeniumAdapter
from omnispatial.ngff import write_ngff, write_spatialdata
from omnispatial.validate.core import ValidationReport

console = Console()
app = typer.Typer(help="Convert, validate, and view spatial omics assets with OmniSpatial.")
view_app = typer.Typer(help="Viewer utilities for Napari and the web experience.")

VENDOR_MAP: Dict[str, Type[SpatialAdapter]] = {
    "xenium": XeniumAdapter,
    "cosmx": CosMxAdapter,
    "merfish": MerfishAdapter,
}


def _version_callback(value: bool) -> None:
    """Print the package version and exit when requested."""
    if value:
        console.print(f"OmniSpatial [bold cyan]{__version__}[/bold cyan]")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the OmniSpatial version and exit.",
    ),
) -> None:
    """Initialize the CLI before command dispatch."""
    return None


@app.command()
def convert(
    input_path: Path = typer.Argument(..., exists=True, help="Input dataset directory."),
    out: Path = typer.Option(..., "--out", "-o", help="Output Zarr store path."),
    vendor: Optional[str] = typer.Option(None, "--vendor", "-v", help="Vendor adapter to use."),
    output_format: str = typer.Option(
        "ngff",
        "--format",
        "-f",
        case_sensitive=False,
        help="Output format: 'ngff' or 'spatialdata'.",
    ),
) -> None:
    """Convert a spatial assay into NGFF or SpatialData bundles."""
    vendor_key: Optional[str] = vendor.lower() if vendor else None
    if vendor_key and vendor_key not in VENDOR_MAP:
        console.print(f"[bold red]Unknown vendor '{vendor}'.[/bold red]")
        raise typer.Exit(code=1)

    adapter: SpatialAdapter
    if vendor_key:
        adapter = VENDOR_MAP[vendor_key]()
    else:
        detected = get_adapter(input_path)
        if detected is None:
            console.print("[bold red]Could not detect a compatible adapter for the input directory.[/bold red]")
            raise typer.Exit(code=1)
        adapter = detected
        vendor_key = adapter.name

    console.print(f"[bold green]Using adapter:[/bold green] {vendor_key}")
    dataset = adapter.read(input_path)

    out_format = output_format.lower()
    if out_format not in {"ngff", "spatialdata"}:
        console.print("[bold red]Unsupported format. Choose 'ngff' or 'spatialdata'.[/bold red]")
        raise typer.Exit(code=1)

    try:
        if out_format == "ngff":
            target = write_ngff(dataset, str(out))
        else:
            target = write_spatialdata(dataset, str(out))
    except Exception as exc:  # pragma: no cover - error path
        console.print(f"[bold red]Conversion failed:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"[bold cyan]Wrote output:[/bold cyan] {target}")


@app.command()
def validate(
    bundle: Path = typer.Argument(..., help="Path to a SpatialData or NGFF bundle."),
    schema: Optional[Path] = typer.Option(None, help="Custom validation schema in JSON Schema format."),
) -> None:
    """Validate a bundle and display a structured report."""
    report: ValidationReport = ValidationReport.example(bundle=bundle, schema_path=schema)
    table = Table(title="Validation Summary")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Details")
    for item in report.items:
        table.add_row(item.name, item.status, item.detail)
    console.print(table)


@view_app.command("napari")
def view_napari(entry_point: str = typer.Option("omnispatial", help="Plugin entry identifier.")) -> None:
    """Display instructions for launching the OmniSpatial napari plugin."""
    console.print(
        "Launch napari and pick '[bold]Plugins → OmniSpatial → Loader[/bold]' to open the dock widget.",
    )
    console.print("Use `napari --plugin {entry_point}` to preload the plugin.", style="cyan")


@view_app.command("web")
def view_web() -> None:
    """Describe how to launch the web viewer for NGFF datasets."""
    console.print("Start the Next.js dev server with [bold]pnpm dev[/bold] inside the viewer directory.")
    console.print(
        "Once running, open http://localhost:3000 and provide an HTTPS URL to an NGFF Zarr store.",
    )


app.add_typer(view_app, name="view")
