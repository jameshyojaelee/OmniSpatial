import { Box, CircularProgress, Typography } from "@mui/material";
import { GeoJsonLayer, ScatterplotLayer } from "@deck.gl/layers";
import type { Feature, FeatureCollection } from "geojson";
import dynamic from "next/dynamic";
import {
  ForwardedRef,
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState
} from "react";

const VivViewer = dynamic(async () => {
  const mod = await import("@vivjs/viewer");
  return mod.VivViewer;
}, { ssr: false });

type LoadedViewerState = {
  imageLayer: unknown | null;
  views: unknown[];
  initialViewState: Record<string, unknown>;
  layerConfig: Record<string, unknown>;
  loader: unknown;
};

export type ViewerFeature = Feature & {
  properties: Record<string, unknown>;
};

type VivCanvasProps = {
  url: string;
  overlayText: string;
  features: ViewerFeature[];
  showImage: boolean;
  showFeatures: boolean;
  colorBy: string | null;
  colorMap: Record<string, string>;
};
export type VivCanvasHandle = {
  capturePng: () => string | null;
};

function hexToRgbaTuple(color: string, alpha = 200): [number, number, number, number] {
  const hex = color.replace("#", "");
  const bigint = parseInt(hex, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return [r, g, b, alpha];
}

const VivCanvas = (
  { url, overlayText, features, showImage, showFeatures, colorBy, colorMap }: VivCanvasProps,
  ref: ForwardedRef<VivCanvasHandle>
): JSX.Element => {
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [state, setState] = useState<LoadedViewerState | null>(null);
  const viewerRef = useRef<{ deck?: { canvas?: HTMLCanvasElement; gl?: WebGLRenderingContext } } | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load(): Promise<void> {
      if (!url) {
        setState(null);
        setStatus("idle");
        return;
      }
      setStatus("loading");
      setError(null);
      try {
        const [{ loadOmeroMultiscales }, { MultiscaleImageLayer }, viewer] = await Promise.all([
          import("@vivjs/loaders"),
          import("@vivjs/layers"),
          import("@vivjs/viewer")
        ]);
        const [loader, metadata] = await loadOmeroMultiscales(url);
        const detailView = new viewer.DetailView() as { id: string };
        const views = [detailView];
        const { initialViewState, layerConfig } = viewer.getDefaultInitialViewState(loader);
        const channelLabels = metadata?.omero?.channels?.map((channel: { label?: string }) => channel.label ?? "channel") ?? ["channel"];
        const layer = new MultiscaleImageLayer({
          loader,
          id: "primary",
          selection: { z: 0, t: 0, c: 0 },
          colormap: "viridis",
          channelNames: channelLabels
        });
        if (!cancelled) {
          setState({
            imageLayer: layer,
            views,
            initialViewState: { [detailView.id]: initialViewState },
            layerConfig,
            loader
          });
          setStatus("ready");
        }
      } catch (err) {
        if (!cancelled) {
          setError((err as Error).message);
          setStatus("error");
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [url]);

  const featureLayer = useMemo(() => {
    if (!showFeatures || features.length === 0) {
      return null;
    }
    const collection: FeatureCollection = { type: "FeatureCollection", features };
    if (!colorBy) {
      return new GeoJsonLayer({
        id: "omnispatial-features",
        data: collection,
        filled: false,
        stroked: true,
        getLineColor: [255, 255, 255, 200],
        lineWidthMinPixels: 1,
        pickable: true
      });
    }
    const getColor = (properties: Record<string, unknown>) => {
      const value = properties[colorBy];
      const key = value === undefined || value === null ? "__missing" : String(value);
      const color = colorMap[key] ?? "#4dabf7";
      return hexToRgbaTuple(color, 160);
    };
    const geometries = features.map((feature) => feature.geometry?.type ?? "");
    const onlyPoints = geometries.every((type) => type === "Point");
    if (onlyPoints) {
      return new ScatterplotLayer({
        id: "omnispatial-points",
        data: features,
        getPosition: (d: Feature) => d.geometry?.type === "Point" ? d.geometry.coordinates : [0, 0],
        getFillColor: (d: Feature) => getColor((d.properties as Record<string, unknown>) ?? {}),
        getRadius: 8,
        radiusUnits: "pixels",
        pickable: true,
        stroked: false,
        updateTriggers: {
          getFillColor: [colorBy, colorMap]
        }
      });
    }
    return new GeoJsonLayer({
      id: "omnispatial-polygons",
      data: collection,
      getFillColor: (d: Feature) => getColor((d.properties as Record<string, unknown>) ?? {}),
      getLineColor: [255, 255, 255, 200],
      lineWidthMinPixels: 1,
      pickable: true,
      filled: true,
      stroked: true,
      updateTriggers: {
        getFillColor: [colorBy, colorMap]
      }
    });
  }, [features, showFeatures, colorBy, colorMap]);

  const layers = useMemo(() => {
    const layerList: unknown[] = [];
    if (showImage && state?.imageLayer) {
      layerList.push(state.imageLayer);
    }
    if (featureLayer) {
      layerList.push(featureLayer);
    }
    return layerList;
  }, [showImage, state?.imageLayer, featureLayer]);

  useImperativeHandle(ref, () => ({
    capturePng: () => {
      const canvas = viewerRef.current?.deck?.canvas ?? viewerRef.current?.deck?.gl?.canvas ?? null;
      if (!canvas) {
        return null;
      }
      return canvas.toDataURL("image/png");
    }
  }), []);

  const overlay = useMemo(() => (
    <Box
      sx={{
        position: "absolute",
        top: 16,
        right: 16,
        backgroundColor: "rgba(0, 0, 0, 0.6)",
        color: "white",
        padding: "8px 12px",
        borderRadius: 1,
        fontSize: "0.9rem"
      }}
    >
      {overlayText}
    </Box>
  ), [overlayText]);

  if (!url) {
    return <Typography variant="body1">Enter a public NGFF Zarr URL to begin.</Typography>;
  }

  if (status === "loading") {
    return (
      <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
        <CircularProgress />
        <Typography variant="body2">Loading NGFF pyramid…</Typography>
      </Box>
    );
  }

  if (status === "error") {
    return <Typography color="error">{error ?? "Unable to load dataset."}</Typography>;
  }

  if (!state) {
    return <Typography variant="body1">Viewer is ready.</Typography>;
  }

  return (
    <Box sx={{ position: "relative", width: "100%", height: "600px" }}>
      <VivViewer
        loader={state.loader as never}
        views={state.views as never}
        layers={layers as never}
        layerConfig={state.layerConfig as never}
        initialViewState={state.initialViewState as never}
        viewerRef={viewerRef as never}
      />
      {overlay}
    </Box>
  );
};

const ForwardedVivCanvas = forwardRef(VivCanvas);
ForwardedVivCanvas.displayName = "VivCanvas";

export default ForwardedVivCanvas;
