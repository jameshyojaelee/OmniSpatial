"""CLI entrypoint for OmniSpatial."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Type

import typer
from rich.console import Console

from omnispatial import __version__
from omnispatial.adapters import SpatialAdapter, get_adapter
from omnispatial.adapters.cosmx import CosMxAdapter
from omnispatial.adapters.merfish import MerfishAdapter
from omnispatial.adapters.xenium import XeniumAdapter
from omnispatial.ngff import write_ngff, write_spatialdata
from omnispatial.validate import (
    Severity,
    ValidationIOError,
    ValidationReport as ValidationResult,
    validate_bundle,
)

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
    output_format: str = typer.Option(
        "ngff",
        "--format",
        "-f",
        case_sensitive=False,
        help="Bundle format: 'ngff' or 'spatialdata'.",
    ),
    json_report: Optional[Path] = typer.Option(None, "--json", help="Write machine-readable report to a JSON file."),
) -> None:
    """Validate a bundle and emit a machine-readable report."""
    fmt = output_format.lower()
    if fmt not in {"ngff", "spatialdata"}:
        console.print(f"[bold red]Unsupported format '{output_format}'.[/bold red]")
        raise typer.Exit(code=2)

    try:
        report: ValidationResult = validate_bundle(bundle, fmt)
    except ValidationIOError as exc:
        console.print(f"[bold red]Unable to read bundle:[/bold red] {exc}")
        raise typer.Exit(code=2) from exc
    except Exception as exc:  # pragma: no cover - unexpected failure
        console.print(f"[bold red]Validation failed unexpectedly:[/bold red] {exc}")
        raise typer.Exit(code=2) from exc

    if json_report is not None:
        json_report.parent.mkdir(parents=True, exist_ok=True)
        json_report.write_text(report.model_dump_json(indent=2))

    severity_style = {
        Severity.INFO: "cyan",
        Severity.WARNING: "yellow",
        Severity.ERROR: "red",
    }

    if report.issues:
        console.print("[bold]Validation Issues:[/bold]")
        for issue in report.issues:
            style = severity_style.get(issue.severity, "white")
            console.print(
                f"{issue.severity.value.upper()} {issue.code}: {issue.message} ({issue.path})",
                style=style,
            )
    else:
        console.print("[bold green]No issues detected.[/bold green]")

    summary_parts = ", ".join(f"{key}={value}" for key, value in report.summary.items())
    console.print(f"[bold cyan]Summary:[/bold cyan] {summary_parts}")

    if report.ok:
        console.print("[bold green]Validation passed.[/bold green]")
        raise typer.Exit(code=0)

    console.print("[bold red]Validation completed with errors.[/bold red]")
    raise typer.Exit(code=1)


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
