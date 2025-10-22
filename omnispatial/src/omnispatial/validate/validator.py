"""Validation routines for NGFF and SpatialData bundles."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import anndata as ad
import numpy as np
import zarr
from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Severity levels for validation issues."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ValidationIssue(BaseModel):
    """Single validation issue description."""

    code: str
    message: str
    path: str = Field(default="/")
    severity: Severity = Field(default=Severity.ERROR)


class ValidationReport(BaseModel):
    """Aggregate validation report with summary metadata."""

    ok: bool
    issues: List[ValidationIssue] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def example(cls, bundle: Optional[Path] = None, schema_path: Optional[Path] = None) -> "ValidationReport":
        """Create an example report for documentation/tests."""
        issues = [
            ValidationIssue(
                code="EXAMPLE",
                message="Example validation executed.",
                path=str(bundle) if bundle else "/",
                severity=Severity.INFO,
            )
        ]
        summary = {"target": str(bundle) if bundle else "", "schema": str(schema_path) if schema_path else None}
        return cls(ok=True, issues=issues, summary=summary)


class ValidationIOError(RuntimeError):
    """Raised when validation cannot operate due to IO errors."""


def _add_issue(issues: List[ValidationIssue], code: str, message: str, path: str, severity: Severity) -> None:
    issues.append(ValidationIssue(code=code, message=message, path=path, severity=severity))


def _validate_multiscales(
    group: zarr.hierarchy.Group,
    group_path: str,
    issues: List[ValidationIssue],
    expect_channel_axis: bool,
) -> List[float]:
    multiscales = group.attrs.get("multiscales")
    if not multiscales:
        _add_issue(issues, "NGFF_METADATA_MISSING", "Missing multiscales metadata.", group_path, Severity.ERROR)
        return []
    entry = multiscales[0]
    axes = entry.get("axes", [])
    prev_scale: Optional[List[float]] = None
    reported_scale: List[float] = []
    for axis_index, axis in enumerate(axes):
        if axis.get("type") == "space" and "unit" not in axis:
            _add_issue(
                issues,
                "NGFF_AXIS_UNIT_MISSING",
                f"Axis '{axis.get('name', axis_index)}' is missing a unit.",
                group_path,
                Severity.ERROR,
            )
    for dataset in entry.get("datasets", []):
        path = dataset.get("path")
        if path is None or path not in group:
            _add_issue(
                issues,
                "NGFF_DATASET_MISSING",
                "Dataset entry does not exist in Zarr group.",
                f"{group_path}/{path or ''}",
                Severity.ERROR,
            )
            continue
        transforms = dataset.get("coordinateTransformations", [])
        scale_transform = next((t for t in transforms if t.get("type") == "scale"), None)
        translation_transform = next((t for t in transforms if t.get("type") == "translation"), None)
        if scale_transform is None:
            _add_issue(
                issues,
                "NGFF_SCALE_MISSING",
                "Scale transform missing for dataset.",
                f"{group_path}/{path}",
                Severity.ERROR,
            )
            continue
        scale = [float(value) for value in scale_transform.get("scale", [])]
        if expect_channel_axis and len(scale) < 3:
            _add_issue(
                issues,
                "NGFF_SCALE_DIMENSION_MISMATCH",
                "Scale vector expected to include channel axis.",
                f"{group_path}/{path}",
                Severity.ERROR,
            )
        if any(value <= 0 for value in scale):
            _add_issue(
                issues,
                "NGFF_SCALE_NON_POSITIVE",
                "Scale factors must be positive.",
                f"{group_path}/{path}",
                Severity.ERROR,
            )
        spatial_scale = scale[1:] if expect_channel_axis and len(scale) > 1 else scale
        if prev_scale is not None and any(curr < prev for curr, prev in zip(spatial_scale, prev_scale)):
            _add_issue(
                issues,
                "NGFF_SCALE_NON_MONOTONIC",
                "Scale factors must be monotonically increasing across pyramid levels.",
                f"{group_path}/{path}",
                Severity.ERROR,
            )
        prev_scale = spatial_scale
        reported_scale = scale
        if translation_transform is not None:
            translation = translation_transform.get("translation", [])
            if len(translation) != len(scale):
                _add_issue(
                    issues,
                    "NGFF_TRANSLATION_DIMENSION_MISMATCH",
                    "Translation vector length must match scale vector length.",
                    f"{group_path}/{path}",
                    Severity.ERROR,
                )
    return reported_scale


def validate_ngff(path: Path) -> ValidationReport:
    """Validate an NGFF Zarr bundle."""
    try:
        root = zarr.open_group(str(path), mode="r")
    except Exception as exc:  # pragma: no cover - IO failure path
        raise ValidationIOError(str(exc)) from exc

    issues: List[ValidationIssue] = []
    summary: Dict[str, Any] = {"target": str(path), "format": "ngff"}

    images = root.get("images")
    if images is None:
        _add_issue(issues, "NGFF_IMAGES_MISSING", "Images group not found.", "/images", Severity.ERROR)
        image_groups = {}
    else:
        image_groups = {name: images[name] for name in images.group_keys()}
    summary["images"] = len(image_groups)

    image_shapes: Dict[str, Tuple[int, int]] = {}
    image_scales: Dict[str, List[float]] = {}

    for name, group in image_groups.items():
        dataset = group.get("0")
        if dataset is None:
            _add_issue(issues, "NGFF_DATASET_MISSING", "Level '0' not found for image.", f"/images/{name}", Severity.ERROR)
        else:
            data = dataset[:]
            if data.ndim >= 2:
                image_shapes[name] = data.shape[-2:]
        scales = _validate_multiscales(group, f"/images/{name}", issues, expect_channel_axis=True)
        image_scales[name] = scales

    labels = root.get("labels")
    if labels is None:
        label_groups: Dict[str, zarr.hierarchy.Group] = {}
    else:
        label_groups = {name: labels[name] for name in labels.group_keys()}
    summary["labels"] = len(label_groups)

    label_counts: List[int] = []
    for name, group in label_groups.items():
        attrs = group.attrs
        if "image-label" not in attrs:
            _add_issue(
                issues,
                "NGFF_LABEL_METADATA_MISSING",
                "Label group missing image-label metadata.",
                f"/labels/{name}",
                Severity.ERROR,
            )
        mask_dataset = group.get("0")
        if mask_dataset is None:
            _add_issue(issues, "NGFF_DATASET_MISSING", "Level '0' not found for label.", f"/labels/{name}", Severity.ERROR)
            continue
        mask = mask_dataset[:]
        mask_shape = mask.shape[-2:]
        label_counts.append(int(len(np.unique(mask)) - (1 if 0 in mask else 0)))
        linked_image_name = next(iter(image_shapes), None)
        if linked_image_name:
            expected_shape = image_shapes[linked_image_name]
            if mask_shape != expected_shape:
                _add_issue(
                    issues,
                    "NGFF_LABEL_SHAPE_MISMATCH",
                    "Label mask shape does not match image shape.",
                    f"/labels/{name}",
                    Severity.ERROR,
                )
            coords = np.argwhere(mask > 0)
            if coords.size:
                max_y, max_x = coords.max(axis=0)
                if max_y >= expected_shape[0] or max_x >= expected_shape[1]:
                    _add_issue(
                        issues,
                        "NGFF_LABEL_BOUNDARY",
                        "Label geometry extends beyond image bounds.",
                        f"/labels/{name}",
                        Severity.ERROR,
                    )
        _validate_multiscales(group, f"/labels/{name}", issues, expect_channel_axis=False)

    tables = root.get("tables")
    if tables is None:
        table_groups: Dict[str, zarr.hierarchy.Group] = {}
    else:
        table_groups = {name: tables[name] for name in tables.group_keys()}
    summary["tables"] = len(table_groups)

    table_counts: List[int] = []
    for name in table_groups:
        adata_path = path / "tables" / name
        try:
            adata = ad.read_zarr(str(adata_path))
        except Exception as exc:
            _add_issue(
                issues,
                "NGFF_TABLE_READ_ERROR",
                f"Failed to read AnnData table: {exc}.",
                f"/tables/{name}",
                Severity.ERROR,
            )
            continue
        table_counts.append(int(adata.n_obs))
        if adata.obs.index.has_duplicates:
            _add_issue(
                issues,
                "NGFF_TABLE_DUPLICATE_INDEX",
                "AnnData observation index contains duplicates.",
                f"/tables/{name}",
                Severity.ERROR,
            )

    if label_counts and table_counts:
        if sum(label_counts) != sum(table_counts):
            _add_issue(
                issues,
                "NGFF_TABLE_LABEL_MISMATCH",
                "Sum of label indices does not match table observations.",
                "/tables",
                Severity.ERROR,
            )

    # Coordinate transform invertibility check.
    for name, scales in image_scales.items():
        if scales and any(value <= 0 for value in scales):
            _add_issue(
                issues,
                "NGFF_TRANSFORM_NON_INVERTIBLE",
                "Image scale contains non-positive values, making transform non-invertible.",
                f"/images/{name}",
                Severity.ERROR,
            )

    ok = not any(issue.severity == Severity.ERROR for issue in issues)
    return ValidationReport(ok=ok, issues=issues, summary=summary)


def validate_spatialdata(path: Path) -> ValidationReport:
    """Validate a SpatialData Zarr bundle."""
    report = validate_ngff(path)
    report.summary["format"] = "spatialdata"
    return report


def validate_bundle(path: Path, fmt: str) -> ValidationReport:
    """Dispatch validation based on bundle format."""
    if fmt.lower() == "ngff":
        return validate_ngff(path)
    if fmt.lower() == "spatialdata":
        return validate_spatialdata(path)
    raise ValueError(f"Unsupported format '{fmt}'.")


__all__ = [
    "Severity",
    "ValidationIssue",
    "ValidationReport",
    "ValidationIOError",
    "validate_ngff",
    "validate_spatialdata",
    "validate_bundle",
]
