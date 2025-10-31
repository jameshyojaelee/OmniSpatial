#!/usr/bin/env python3
"""Invoke OmniSpatial conversions and validation from workflow engines."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, Sequence, Tuple

from omnispatial import api


def _parse_chunks(value: Optional[str], dims: int) -> Optional[Tuple[int, ...]]:
    if value is None:
        return None
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if len(parts) != dims:
        raise SystemExit(f"Expected {dims} comma-separated values, received '{value}'.")
    return tuple(int(part) for part in parts)


def _resolve_cli_path(flag_value: Optional[Path], positional_value: Optional[Path], label: str) -> Path:
    """Choose between positional and flag-supplied paths, enforcing consistency."""
    if flag_value and positional_value and flag_value != positional_value:
        raise SystemExit(
            f"Conflicting {label} values provided (positional='{positional_value}' vs '--{label}={flag_value}')."
        )
    path = flag_value or positional_value
    if path is None:
        raise SystemExit(f"Missing required {label} path. Provide it positionally or with '--{label}'.")
    return path


def _convert(args: argparse.Namespace) -> None:
    input_path = _resolve_cli_path(getattr(args, "input_flag", None), getattr(args, "input_path", None), "input")
    output_path = _resolve_cli_path(getattr(args, "output_flag", None), getattr(args, "output_path", None), "output")

    # Maintain compatibility for any downstream consumers expecting these attributes.
    args.input = input_path
    args.output = output_path

    result = api.convert(
        input_path,
        output_path,
        vendor=args.vendor,
        output_format=args.format,
        dry_run=args.dry_run,
        image_chunks=_parse_chunks(args.image_chunks, 3),
        label_chunks=_parse_chunks(args.label_chunks, 2),
        compressor=args.compressor,
        compression_level=args.compression_level,
    )

    summary = {
        "adapter": result.adapter,
        "format": result.format,
        "output_path": str(result.output_path) if result.output_path else None,
    }
    if args.emit_json:
        print(json.dumps(summary))

    if args.validate_output:
        target = result.output_path or output_path
        report = api.validate(target, output_format=args.validation_format or result.format)
        if args.report_path:
            Path(args.report_path).write_text(report.model_dump_json(indent=2))
        if args.emit_json:
            summary["validation"] = report.model_dump()
            print(json.dumps(summary))


def _validate(args: argparse.Namespace) -> None:
    report = api.validate(args.bundle, output_format=args.format)
    if args.emit_json:
        print(report.model_dump_json(indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    convert = subparsers.add_parser("convert", help="Convert a dataset to NGFF or SpatialData.")
    convert.add_argument(
        "input_path",
        nargs="?",
        type=Path,
        metavar="input",
        help="Input dataset directory to convert (may also be supplied via '--input').",
    )
    convert.add_argument(
        "output_path",
        nargs="?",
        type=Path,
        metavar="output",
        help="Destination path for the converted bundle (may also be supplied via '--output').",
    )
    convert.add_argument(
        "--input",
        dest="input_flag",
        type=Path,
        help="Input dataset directory to convert (alternative to positional argument).",
    )
    convert.add_argument(
        "--output",
        dest="output_flag",
        type=Path,
        help="Destination path for the converted bundle (alternative to positional argument).",
    )
    convert.add_argument("--vendor", help="Optional adapter name to enforce (auto-detect if omitted).")
    convert.add_argument("--format", default="ngff", choices=["ngff", "spatialdata"], help="Output bundle format.")
    convert.add_argument("--dry-run", action="store_true", help="Run detection without writing outputs.")
    convert.add_argument("--image-chunks", help="Image chunking, e.g. 1,256,256")
    convert.add_argument("--label-chunks", help="Label chunking, e.g. 256,256")
    convert.add_argument("--compressor", default="zstd", help="Compression codec to use for NGFF outputs.")
    convert.add_argument("--compression-level", type=int, default=5, help="Compression level for NGFF outputs.")
    convert.add_argument("--validate-output", action="store_true", help="Run validation after conversion.")
    convert.add_argument("--validation-format", choices=["ngff", "spatialdata"], help="Override validation format if needed.")
    convert.add_argument("--report-path", help="Write validation report JSON to this path.")
    convert.add_argument("--emit-json", action="store_true", help="Emit machine-readable conversion/validation summary.")
    convert.set_defaults(func=_convert)

    validate = subparsers.add_parser("validate", help="Validate an existing bundle.")
    validate.add_argument("bundle", type=Path, help="Path to a NGFF or SpatialData bundle.")
    validate.add_argument("--format", default="ngff", choices=["ngff", "spatialdata"], help="Bundle format.")
    validate.add_argument("--emit-json", action="store_true", help="Emit the validation report as JSON.")
    validate.set_defaults(func=_validate)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
