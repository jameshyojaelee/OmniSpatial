# Developer Guide

This guide outlines how to extend OmniSpatial with a new vendor adapter and integrate it into the tooling.

## 1. Create an adapter class

Adapters inherit from `SpatialAdapter` and implement the `detect`, `read`, and `metadata` methods. Use `register_adapter` so the registry discovers the adapter automatically.

```python
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from omnispatial.adapters import SpatialAdapter, register_adapter
from omnispatial.core.model import SpatialDataset

@register_adapter
class MyAdapter(SpatialAdapter):
    name = "my_vendor"

    def metadata(self) -> Dict[str, Any]:
        return {"vendor": "Example", "modalities": ["transcriptomics"]}

    def detect(self, input_path: Path) -> bool:
        return (input_path / "my_file.csv").exists()

    def read(self, input_path: Path) -> SpatialDataset:
        # Parse files and build ImageLayer, LabelLayer, TableLayer instances
        ...
```

Use the canonical models in `omnispatial.core.model` to assemble the dataset. The `tests/conftest.py` fixtures illustrate minimal image and table construction routines.

## 2. Register in the CLI

Adapters registered with the decorator automatically participate in CLI detection. Users can force a specific adapter via:

```bash
poetry run omnispatial convert data_dir --out bundle.zarr --vendor my_vendor
```

## 3. Add tests

Create property or regression tests under `omnispatial/tests/` to:

- Ensure `detect` recognises valid inputs and rejects others.
- Verify `read` returns consistent shapes, transforms, and tables.
- Exercise the conversion pipeline using `poetry run omnispatial convert` when appropriate.

## 4. Document the adapter

Update `docs/architecture.md` or add a dedicated section describing the new adapter’s expectations (file names, coordinate conventions, etc.). Keep the end-to-end notebook up to date if the adapter introduces additional steps.

## 5. Release

Once tests and documentation pass, push to a feature branch and open a pull request. On merge to `main`:

- CI builds the wheel, validates the docs, and prepares artifacts.
- Tags matching `v*` trigger automatic publishing to PyPI and redeploy the GitHub Pages documentation.

For major updates, bump the version via `poetry version`, run `tools/update_citation.py --version X.Y.Z`, and update `CHANGELOG.md` before tagging.
