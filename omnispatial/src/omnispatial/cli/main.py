"""CLI entrypoint for OmniSpatial."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from omnispatial import __version__
from omnispatial.validate.core import ValidationReport

console = Console()
app = typer.Typer(help="Convert, validate, and view spatial omics assets with OmniSpatial.")
view_app = typer.Typer(help="Viewer utilities for Napari and the web experience.")


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
    input_path: Path = typer.Argument(..., help="Input dataset or folder."),
    output_path: Path = typer.Argument(..., help="Output workspace for NGFF and SpatialData."),
    metadata: Optional[Path] = typer.Option(None, "--metadata", help="Optional metadata recipe in YAML."),
) -> None:
    """Convert a spatial assay into OME-NGFF Zarr and SpatialData outputs."""
    console.print("[bold green]Starting conversion pipeline[/bold green]")
    console.log(f"Input path: {input_path}")
    console.log(f"Output path: {output_path}")
    if metadata:
        console.log(f"Metadata recipe: {metadata}")
    console.print(
        "Conversion is not yet implemented. This placeholder ensures the CLI wiring is functional.",
        style="yellow",
    )


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
