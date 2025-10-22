# OmniSpatial CosMx Public Adapter

This namespace package extends OmniSpatial with an adapter tailored to the NanoString CosMx public release datasets. It discovers raw CSV exports, normalises polygon annotations, and emits NGFF-ready bundles via the shared conversion pipeline.

Install alongside OmniSpatial:

```bash
pip install omnispatial omnispatial-adapter-cosmx-public
```

The adapter registers itself through the `omnispatial.adapters` entry-point group and can be invoked from the CLI with:

```bash
omnispatial convert /path/to/cosmx-public --vendor cosmx-public --out output.zarr
```

Refer to the main OmniSpatial documentation for end-to-end conversion and validation instructions.
