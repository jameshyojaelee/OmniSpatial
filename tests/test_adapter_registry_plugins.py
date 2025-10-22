from __future__ import annotations

from pathlib import Path
from typing import Iterator, Type

import pytest

from omnispatial.adapters.base import SpatialAdapter
from omnispatial.adapters import registry


class _DummyEntryPoint:
    group = "omnispatial.adapters"

    def __init__(self, name: str, target) -> None:
        self.name = name
        self._target = target

    def load(self):
        return self._target


class _EntryPointCollection(list):
    def select(self, *, group: str) -> Iterator[_DummyEntryPoint]:  # type: ignore[override]
        return (entry for entry in self if entry.group == group)


class _PluginAdapter(SpatialAdapter):
    name = "dummy-plugin"

    def metadata(self) -> dict:
        return {"vendor": "dummy", "modalities": ["test"]}

    def detect(self, input_path: Path) -> bool:
        return False

    def read(self, input_path: Path):
        raise NotImplementedError("Plugin adapters are not exercised in discovery tests.")


@pytest.fixture
def reset_registry(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(registry, "_REGISTERED_ADAPTERS", {})
    monkeypatch.setattr(registry, "_ENTRYPOINTS_LOADED", False)
    yield


def test_load_adapter_plugins_registers_entry_points(monkeypatch: pytest.MonkeyPatch, reset_registry) -> None:
    monkeypatch.setattr(
        registry.metadata,
        "entry_points",
        lambda: _EntryPointCollection([_DummyEntryPoint("dummy", _PluginAdapter)]),
    )

    registry.load_adapter_plugins(force=True)
    adapters = registry.available_adapters()
    assert "dummy-plugin" in adapters


def test_load_adapter_plugins_accepts_factory(monkeypatch: pytest.MonkeyPatch, reset_registry) -> None:
    def factory() -> Type[SpatialAdapter]:
        return _PluginAdapter

    monkeypatch.setattr(
        registry.metadata,
        "entry_points",
        lambda: _EntryPointCollection([_DummyEntryPoint("dummy", factory)]),
    )

    registry.load_adapter_plugins(force=True)
    names = [adapter_cls.name for adapter_cls in registry.iter_adapters()]
    assert "dummy-plugin" in names
