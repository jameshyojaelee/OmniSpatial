"""CLI entrypoint for OmniSpatial."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, Type

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

LOG = logging.getLogger("omnispatial")
LOG_JSON = False


def _configure_logging(verbosity: int, json_logs: bool) -> None:
    global LOG_JSON
    LOG_JSON = json_logs
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(message)s")


def _log(event: str, **payload: object) -> None:
    if LOG_JSON:
        record = {"event": event, **payload}
        console.print_json(data=record)
    else:
        details = " ".join(f"{key}={value}" for key, value in payload.items())
        console.log(f"{event} {details}" if details else event)

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
    verbose: int = typer.Option(0, "--verbose", "-V", count=True, help="Increase log verbosity (repeatable)."),
    log_json: bool = typer.Option(False, "--log-json", help="Emit JSON structured logs."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run detection and validation without writing outputs."),
    image_chunks: Optional[str] = typer.Option(None, help="Image chunk size as comma-separated values, e.g. 1,256,256."),
    label_chunks: Optional[str] = typer.Option(None, help="Label chunk size as comma-separated values, e.g. 256,256."),
    compressor: Optional[str] = typer.Option("zstd", help="Compression codec (zstd, lz4, zlib, snappy, none)."),
    compression_level: int = typer.Option(5, help="Compression level (1-9)."),
) -> None:
    """Convert a spatial assay into NGFF or SpatialData bundles."""
    _configure_logging(verbose, log_json)
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

    _log("adapter.selected", adapter=vendor_key)
    dataset = adapter.read(input_path)
    _log("dataset.loaded", images=len(dataset.images), labels=len(dataset.labels), tables=len(dataset.tables))

    out_format = output_format.lower()
    if out_format not in {"ngff", "spatialdata"}:
        console.print("[bold red]Unsupported format. Choose 'ngff' or 'spatialdata'.[/bold red]")
        raise typer.Exit(code=1)

    if dry_run:
        _log("convert.dry_run", output=str(out), format=out_format)
        return

    def _parse_chunks(value: Optional[str], dims: int) -> Optional[Tuple[int, ...]]:
        if not value:
            return None
        parts = value.split(",")
        if len(parts) != dims:
            raise typer.BadParameter(f"Expected {dims} comma-separated integers, received '{value}'.")
        return tuple(int(part) for part in parts)

    try:
        if out_format == "ngff":
            img_chunks = _parse_chunks(image_chunks, 3)
            lbl_chunks = _parse_chunks(label_chunks, 2)
            target = write_ngff(
                dataset,
                str(out),
                image_chunks=img_chunks,
                label_chunks=lbl_chunks,
                compressor=compressor,
                compression_level=compression_level,
            )
        else:
            target = write_spatialdata(dataset, str(out))
    except Exception as exc:  # pragma: no cover - error path
        _log("convert.error", error=str(exc))
        raise typer.Exit(code=1) from exc

    _log("convert.completed", output=target, format=out_format)


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
