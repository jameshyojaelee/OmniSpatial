# Quickstart

## Python CLI

```bash
poetry install
poetry run omnispatial --help
poetry run omnispatial convert sample-data/ input_workspace/
```

## Napari Plugin

```bash
poetry run napari --with omnispatial
```

Inside napari, open the **Plugins → OmniSpatial → Loader** item.

## Web Viewer

```bash
cd viewer
pnpm install
pnpm dev
```

Navigate to http://localhost:3000 and provide an NGFF Zarr URL to explore.
