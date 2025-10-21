"""Detection tests for vendor adapters."""

from __future__ import annotations

import pandas as pd
import pytest

from omnispatial.adapters import get_adapter
from omnispatial.adapters.cosmx import CosMxAdapter
from omnispatial.adapters.merfish import MerfishAdapter
from omnispatial.adapters.xenium import XeniumAdapter


def _write_table(path) -> None:
    df = pd.DataFrame({"cell_id": ["a", "b"], "x": [0.0, 1.0], "y": [0.0, 1.0], "gene_a": [10, 20]})
    df.to_csv(path, index=False)


@pytest.mark.parametrize(
    ("adapter_cls", "filename"),
    [
        (XeniumAdapter, "cells.csv"),
        (CosMxAdapter, "cosmx_spots.csv"),
        (MerfishAdapter, "merfish_transcripts.csv"),
    ],
)
def test_adapter_detects_expected_structure(tmp_path, adapter_cls, filename) -> None:
    """Each adapter should recognise its canonical file layout."""
    file_path = tmp_path / filename
    _write_table(file_path)
    adapter = adapter_cls()
    assert adapter.detect(tmp_path)
    dataset = adapter.read(tmp_path)
    assert dataset.tables[0].cell_count == 2


def test_get_adapter_returns_none_for_unknown(tmp_path) -> None:
    """Unknown paths should not raise errors and return None."""
    assert get_adapter(tmp_path / "missing") is None
