"""Napari plugin entry points for OmniSpatial."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
from napari_plugin_engine import napari_hook_implementation

try:  # Optional napari imports
    import napari
    from napari.types import LayerDataTuple
except ImportError:  # pragma: no cover - executed when napari is unavailable
    LayerDataTuple = Any  # type: ignore[assignment]
    napari = None  # type: ignore

try:  # Optional Qt imports for dock widget
    from qtpy.QtWidgets import (  # type: ignore
        QComboBox,
        QFormLayout,
        QLabel,
        QPushButton,
        QWidget,
    )
except ImportError:  # pragma: no cover - executed in headless environments
    QWidget = object  # type: ignore

import anndata as ad
import zarr

if TYPE_CHECKING:  # pragma: no cover
    import napari.layers

LayerDataList = List[LayerDataTuple]


def _coerce_path(path: Any) -> Path:
    if isinstance(path, (list, tuple)):
        path = path[0]
    return Path(path)


def _is_omnispatial_bundle(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        root = zarr.open_group(str(path), mode="r")
    except Exception:
        return False
    return "images" in root or "labels" in root


def _load_table(path: Path) -> Optional[ad.AnnData]:
    tables_dir = path / "tables"
    if not tables_dir.exists():
        return None
    first_table = next((child for child in tables_dir.iterdir() if child.is_dir()), None)
    if first_table is None:
        return None
    return ad.read_zarr(str(first_table))


def _points_layer_from_table(adata: ad.AnnData, name: str) -> Optional[LayerDataTuple]:
    for required in ("x", "y"):
        if required not in adata.obs.columns:
            return None
    coordinates = np.column_stack([adata.obs["y"].to_numpy(dtype=float), adata.obs["x"].to_numpy(dtype=float)])
    properties = {col: adata.obs[col].to_numpy() for col in adata.obs.columns}
    metadata = {"name": f"{name}_points", "properties": properties, "metadata": {"_adata": adata}}
    return (coordinates, metadata, "points")


def _label_layers(path: Path, image_shape: Tuple[int, int]) -> Iterable[LayerDataTuple]:
    labels_dir = zarr.open_group(str(path), mode="r")["labels"] if (path / "labels").exists() else None
    if labels_dir is None:
        return []
    layers: List[LayerDataTuple] = []
    for name in labels_dir.group_keys():
        mask = labels_dir[name]["0"][:]
        metadata = {"name": name}
        if mask.shape != image_shape:
            mask = mask.reshape(image_shape)
        layers.append((mask, metadata, "labels"))
    return layers


def omnispatial_reader(path: Any) -> Optional[LayerDataList]:  # napari reader signature
    bundle_path = _coerce_path(path)
    if not _is_omnispatial_bundle(bundle_path):
        return None

    root = zarr.open_group(str(bundle_path), mode="r")
    images = root.get("images")
    if not images:
        return None

    image_name = next(iter(images.group_keys()))
    image_dataset = images[image_name]["0"]
    image = image_dataset[:]
    if image.ndim == 3 and image.shape[0] == 1:
        image = image[0]
    scale = None
    multiscales = images[image_name].attrs.get("multiscales", [])
    if multiscales:
        scale_transform = multiscales[0]["datasets"][0].get("coordinateTransformations", [])
        for transform in scale_transform:
            if transform.get("type") == "scale":
                scale_values = transform.get("scale", [])
                if len(scale_values) >= 3:
                    scale = scale_values[-2:]
                elif len(scale_values) == 2:
                    scale = scale_values
                break
    metadata = {"name": image_name}
    if scale is not None:
        metadata["scale"] = tuple(scale[::-1])

    layers: LayerDataList = [(image, metadata, "image")]

    label_layers = list(_label_layers(bundle_path, image.shape[-2:]))
    layers.extend(label_layers)

    adata = _load_table(bundle_path)
    if adata is not None:
        points_layer = _points_layer_from_table(adata, image_name)
        if points_layer:
            layers.append(points_layer)

    return layers


class OmniSpatialDock(QWidget):  # type: ignore[misc]
    """Simple dock widget for filtering and colouring points layers."""

    def __init__(self, viewer: "napari.Viewer") -> None:  # type: ignore[name-defined]
        super().__init__()
        self._viewer = viewer
        if QWidget is object:  # pragma: no cover - Qt missing
            return
        self.layer_combo = QComboBox()
        self.property_combo = QComboBox()
        self.value_combo = QComboBox()
        self.color_combo = QComboBox()
        self.apply_button = QPushButton("Apply Filter")
        self.reset_button = QPushButton("Reset")
        self.color_button = QPushButton("Apply Color")

        form = QFormLayout(self)
        form.addRow(QLabel("Points layer"), self.layer_combo)
        form.addRow(QLabel("Property"), self.property_combo)
        form.addRow(QLabel("Value"), self.value_combo)
        form.addRow(QLabel("Color by"), self.color_combo)
        form.addRow(self.apply_button)
        form.addRow(self.reset_button)
        form.addRow(self.color_button)

        self.layer_combo.currentTextChanged.connect(self._on_layer_changed)
        self.property_combo.currentTextChanged.connect(self._on_property_changed)
        self.apply_button.clicked.connect(self._apply_filter)
        self.reset_button.clicked.connect(self._reset_layer)
        self.color_button.clicked.connect(self._apply_color)

        self._viewer.layers.events.inserted.connect(lambda event: self._refresh_layers())
        self._viewer.layers.events.removed.connect(lambda event: self._refresh_layers())
        self._refresh_layers()

    def _points_layers(self) -> List["napari.layers.Points"]:  # type: ignore[name-defined]
        return [layer for layer in self._viewer.layers if layer.__class__.__name__ == "Points"]

    def _refresh_layers(self) -> None:
        if QWidget is object:  # pragma: no cover
            return
        current = self.layer_combo.currentText()
        self.layer_combo.blockSignals(True)
        self.layer_combo.clear()
        for layer in self._points_layers():
            self.layer_combo.addItem(layer.name)
        index = self.layer_combo.findText(current)
        if index >= 0:
            self.layer_combo.setCurrentIndex(index)
        else:
            self._on_layer_changed(self.layer_combo.currentText())
        self.layer_combo.blockSignals(False)

    def _get_selected_layer(self) -> Optional["napari.layers.Points"]:  # type: ignore[name-defined]
        name = self.layer_combo.currentText()
        for layer in self._points_layers():
            if layer.name == name:
                return layer
        return None

    def _ensure_original(self, layer: "napari.layers.Points") -> None:  # type: ignore[name-defined]
        storage = layer.metadata.setdefault("_omni_original", {})
        if "data" not in storage:
            storage["data"] = layer.data.copy()
            storage["properties"] = {key: np.asarray(value).copy() for key, value in layer.properties.items()}

    def _on_layer_changed(self, _: str) -> None:
        if QWidget is object:  # pragma: no cover
            return
        layer = self._get_selected_layer()
        self.property_combo.blockSignals(True)
        self.property_combo.clear()
        self.value_combo.clear()
        self.color_combo.clear()
        if layer is not None and layer.properties:
            for prop_name in layer.properties.keys():
                self.property_combo.addItem(prop_name)
                self.color_combo.addItem(prop_name)
            self._on_property_changed(self.property_combo.currentText())
        self.property_combo.blockSignals(False)

    def _on_property_changed(self, property_name: str) -> None:
        if QWidget is object:  # pragma: no cover
            return
        layer = self._get_selected_layer()
        self.value_combo.clear()
        if layer is None or property_name == "":
            return
        values = np.unique(layer.properties[property_name])
        for value in values:
            self.value_combo.addItem(str(value))

    def _apply_filter(self) -> None:
        layer = self._get_selected_layer()
        if layer is None:
            return
        property_name = self.property_combo.currentText()
        if not property_name:
            return
        value = self.value_combo.currentText()
        self._ensure_original(layer)
        storage = layer.metadata["_omni_original"]
        mask = storage["properties"][property_name].astype(str) == value
        if mask.all():
            return
        layer.data = storage["data"][mask]
        layer.properties = {key: values[mask] for key, values in storage["properties"].items()}

    def _reset_layer(self) -> None:
        layer = self._get_selected_layer()
        if layer is None or "_omni_original" not in layer.metadata:
            return
        storage = layer.metadata["_omni_original"]
        layer.data = storage["data"]
        layer.properties = storage["properties"]

    def _apply_color(self) -> None:
        layer = self._get_selected_layer()
        if layer is None:
            return
        property_name = self.color_combo.currentText()
        if property_name:
            layer.face_color = property_name


@napari_hook_implementation  # type: ignore[misc]
def napari_experimental_provide_dock_widget() -> Iterable[Tuple[Any, Dict[str, Any]]]:
    if napari is None:  # pragma: no cover - napari not installed
        return []
    return [(OmniSpatialDock, {"name": "OmniSpatial Inspector"})]


@napari_hook_implementation  # type: ignore[misc]
def napari_get_reader(path: Any) -> Optional[Any]:
    if _is_omnispatial_bundle(_coerce_path(path)):
        return omnispatial_reader
    return None


def get_manifest_path() -> str:
    return str(Path(__file__).with_name("napari.yaml"))


__all__ = [
    "get_manifest_path",
    "napari_get_reader",
    "napari_experimental_provide_dock_widget",
    "omnispatial_reader",
    "OmniSpatialDock",
]
