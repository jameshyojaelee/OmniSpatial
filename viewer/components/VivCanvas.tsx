import { Box, CircularProgress, Typography } from "@mui/material";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";

const VivViewer = dynamic(async () => {
  const mod = await import("@vivjs/viewer");
  return mod.VivViewer;
}, { ssr: false });

type LoadedViewerState = {
  layers: unknown[];
  views: unknown[];
  initialViewState: Record<string, unknown>;
  layerConfig: Record<string, unknown>;
  loader: unknown;
};

type VivCanvasProps = {
  url: string;
  overlayText: string;
};

export function VivCanvas({ url, overlayText }: VivCanvasProps): JSX.Element {
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [state, setState] = useState<LoadedViewerState | null>(null);

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
            layers: [layer],
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
        layers={state.layers as never}
        layerConfig={state.layerConfig as never}
        initialViewState={state.initialViewState as never}
      />
      {overlay}
    </Box>
  );
}
