"""Tests for the OmniSpatial validator CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import zarr
from typer.testing import CliRunner

from omnispatial.adapters.xenium import XeniumAdapter
from omnispatial.cli import app

runner = CliRunner()


def _convert_dataset(adapter, input_dir: Path, out_path: Path, fmt: str) -> None:
    args = ["convert", str(input_dir), "--out", str(out_path), "--format", fmt, "--vendor", adapter.name]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.stdout


def _run_validate(bundle: Path, fmt: str, json_path: Path) -> tuple[int, dict]:
    args = ["validate", str(bundle), "--format", fmt, "--json", str(json_path)]
    result = runner.invoke(app, args)
    assert json_path.exists(), "JSON report was not written"
    data = json.loads(json_path.read_text())
    return result.exit_code, data


@pytest.mark.parametrize("fmt", ["ngff", "spatialdata"])
def test_validator_ok(xenium_synthetic_dataset: Path, tmp_path: Path, fmt: str) -> None:
    adapter = XeniumAdapter()
    out_path = tmp_path / f"bundle.{fmt}.zarr"
    _convert_dataset(adapter, xenium_synthetic_dataset, out_path, fmt)
    json_path = tmp_path / f"report_{fmt}.json"

    exit_code, data = _run_validate(out_path, fmt, json_path)
    assert exit_code == 0
    assert data["ok"] is True
    assert data["summary"]["format"] == fmt
    assert data["summary"]["images"] >= 1


def test_validator_detects_missing_metadata(xenium_synthetic_dataset: Path, tmp_path: Path) -> None:
    adapter = XeniumAdapter()
    out_path = tmp_path / "bundle_ngff.zarr"
    _convert_dataset(adapter, xenium_synthetic_dataset, out_path, "ngff")

    store = zarr.open_group(str(out_path), mode="r+")
    image_group_name = next(iter(store["images"].group_keys()))
    del store["images"][image_group_name].attrs["multiscales"]

    json_path = tmp_path / "broken_report.json"
    exit_code, data = _run_validate(out_path, "ngff", json_path)
    assert exit_code == 1
    codes = {issue["code"] for issue in data["issues"]}
    assert "NGFF_METADATA_MISSING" in codes
    severities = {issue["severity"] for issue in data["issues"]}
    assert "error" in severities
