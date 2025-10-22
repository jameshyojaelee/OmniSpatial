# OmniSpatial Visium HD Adapter

This namespace package adds Visium HD support to OmniSpatial. It discovers Space Ranger–style outputs, loads the expression matrix via Scanpy, and emits GeoJSON-ready polygons for spot annotations so the standard conversion pipeline can produce NGFF or SpatialData bundles.

Install the adapter alongside OmniSpatial (Scanpy is required):

```bash
pip install omnispatial omnispatial-adapter-visium-hd
```

Invoke the adapter explicitly from the CLI when working with Space Ranger outputs:

```bash
omnispatial convert outs --vendor visium_hd --out sample.zarr
```

Refer to the OmniSpatial documentation for validation, visualization, and downstream workflow guidance.
