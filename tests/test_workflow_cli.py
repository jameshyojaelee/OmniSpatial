"""Regression tests for the workflow helper script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "examples" / "workflows" / "scripts" / "run_omnispatial.py"


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Execute the workflow CLI helper and return the completed process."""
    cmd = [sys.executable, str(SCRIPT_PATH), *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def test_convert_and_validate_roundtrip(tmp_path: Path, xenium_synthetic_dataset: Path) -> None:
    """Conversion followed by validation emits JSON summaries and writes bundles."""
    output_bundle = tmp_path / "xenium_bundle.ngff.zarr"

    convert_result = _run_cli(
        [
            "convert",
            "--input",
            str(xenium_synthetic_dataset),
            "--output",
            str(output_bundle),
            "--format",
            "ngff",
            "--vendor",
            "xenium",
            "--emit-json",
        ]
    )

    convert_lines = [line for line in convert_result.stdout.splitlines() if line.strip()]
    assert convert_lines, convert_result.stdout
    convert_payload = json.loads(convert_lines[-1])
    assert convert_payload["adapter"] == "xenium"
    assert convert_payload["format"] == "ngff"
    assert output_bundle.exists() and output_bundle.is_dir()

    validate_result = _run_cli(
        [
            "validate",
            str(output_bundle),
            "--format",
            "ngff",
            "--emit-json",
        ]
    )

    validation_payload = json.loads(validate_result.stdout)
    assert validation_payload["ok"] is True
    assert validation_payload["summary"]["format"] == "ngff"
    assert validation_payload["summary"]["target"].endswith("xenium_bundle.ngff.zarr")
