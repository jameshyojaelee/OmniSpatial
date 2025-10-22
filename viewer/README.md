# OmniSpatial Viewer

This Next.js application streams OME-NGFF imagery directly into the browser using [@vivjs/viewer](https://github.com/hms-dbmi/viv). It overlays cell centroids or polygons obtained from the AnnData tables stored alongside the NGFF bundle and provides simple filtering and colour-by controls.

## Getting Started

```bash
pnpm install
pnpm dev
```

Navigate to http://localhost:3000 and paste the HTTP(S) URL of a NGFF Zarr store. A sidebar allows you to toggle feature overlays, colour by any observation column, and download the current view as a PNG.

The `/api/geojson` endpoint loads AnnData observations, converts coordinate columns or WKT polygons to GeoJSON on the fly, and caches responses for subsequent requests.
