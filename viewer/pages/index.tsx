import {
  Alert,
  Box,
  Button,
  Divider,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Switch,
  TextField,
  Typography
} from "@mui/material";
import { useRouter } from "next/router";
import { useEffect, useMemo, useRef, useState } from "react";

import VivCanvas, { VivCanvasHandle, ViewerFeature } from "../components/VivCanvas";

type FeatureResponse = {
  type: "FeatureCollection";
  features: ViewerFeature[];
  columns: string[];
};

const MAX_FEATURES = 1000;

function hslToHex(h: number, s: number, l: number): string {
  const sNorm = s / 100;
  const lNorm = l / 100;
  const k = (n: number) => (n + h / 30) % 12;
  const a = sNorm * Math.min(lNorm, 1 - lNorm);
  const f = (n: number) => {
    const value = lNorm - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
    return Math.round(255 * value)
      .toString(16)
      .padStart(2, "0");
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

function generateColorMap(values: string[]): Record<string, string> {
  const palette: Record<string, string> = {};
  const unique = Array.from(new Set(values));
  unique.forEach((value, index) => {
    const hue = (index * 137) % 360;
    palette[value] = hslToHex(hue, 70, 55);
  });
  return palette;
}

function normaliseValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "__missing";
  }
  return `${value}`;
}

export default function HomePage(): JSX.Element {
  const router = useRouter();
  const initialUrl = typeof router.query.url === "string" ? router.query.url : "";
  const [inputUrl, setInputUrl] = useState(initialUrl);
  const [activeUrl, setActiveUrl] = useState(initialUrl);
  const [overlayText, setOverlayText] = useState(initialUrl ? `Viewing ${initialUrl}` : "Awaiting dataset");
  const [loading, setLoading] = useState(false);
  const [features, setFeatures] = useState<ViewerFeature[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [colorBy, setColorBy] = useState<string | null>(null);
  const [colorMap, setColorMap] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [showImage, setShowImage] = useState(true);
  const [showFeatures, setShowFeatures] = useState(true);
  const canvasRef = useRef<VivCanvasHandle>(null);

  const legendValues = useMemo(() => {
    if (!colorBy || !features.length) {
      return [] as Array<{ value: string; color: string }>;
    }
    const values = Array.from(new Set(features.map((feature) => normaliseValue(feature.properties[colorBy]))));
    return values.map((value) => ({ value, color: colorMap[value] ?? "#4dabf7" }));
  }, [colorBy, features, colorMap]);

  useEffect(() => {
    const loadFeatures = async () => {
      if (!activeUrl) {
        setFeatures([]);
        setColumns([]);
        setColorBy(null);
        setColorMap({});
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(
          `/api/geojson?url=${encodeURIComponent(activeUrl)}&limit=${MAX_FEATURES}`
        );
        if (!response.ok) {
          throw new Error(`Failed to load features (${response.status})`);
        }
        const data: FeatureResponse = await response.json();
        setFeatures(data.features);
        setColumns(data.columns);
        const defaultColumn = data.columns.includes("gene") ? "gene" : data.columns[0] ?? null;
        setColorBy(defaultColumn);
        if (defaultColumn) {
          const values = data.features.map((feature) => normaliseValue(feature.properties[defaultColumn]));
          setColorMap(generateColorMap(values));
        } else {
          setColorMap({});
        }
      } catch (err) {
        setError((err as Error).message);
        setFeatures([]);
        setColumns([]);
        setColorBy(null);
        setColorMap({});
      } finally {
        setLoading(false);
      }
    };
    void loadFeatures();
  }, [activeUrl]);

  useEffect(() => {
    if (colorBy) {
      const values = features.map((feature) => normaliseValue(feature.properties[colorBy]));
      setColorMap(generateColorMap(values));
    }
  }, [colorBy, features]);

  const handleLoad = () => {
    const trimmed = inputUrl.trim();
    setActiveUrl(trimmed);
    setOverlayText(trimmed ? `Viewing ${trimmed}` : "Awaiting dataset");
    if (trimmed) {
      void router.replace({ pathname: router.pathname, query: { url: trimmed } }, undefined, { shallow: true });
    }
  };

  const handleDownload = () => {
    const dataUrl = canvasRef.current?.capturePng();
    if (!dataUrl) {
      return;
    }
    const link = document.createElement("a");
    link.href = dataUrl;
    link.download = "omnispatial-view.png";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", backgroundColor: "#101418", color: "#e5eef7" }}>
      <Box
        component="aside"
        sx={{
          width: 340,
          padding: 3,
          borderRight: "1px solid rgba(229, 238, 247, 0.08)",
          display: "flex",
          flexDirection: "column",
          gap: 2
        }}
      >
        <Box>
          <Typography variant="h5" gutterBottom>
            OmniSpatial Web Viewer
          </Typography>
          <Typography variant="body2" color="rgba(229, 238, 247, 0.65)">
            Paste an HTTP(S) NGFF Zarr URL and click load to explore the image and per-cell features.
          </Typography>
        </Box>
        <Paper component="form" onSubmit={(event) => { event.preventDefault(); handleLoad(); }} sx={{ padding: 2, backgroundColor: "#12192b" }}>
          <TextField
            fullWidth
            value={inputUrl}
            label="NGFF Zarr URL"
            onChange={(event) => setInputUrl(event.target.value)}
            placeholder="http://localhost:8000/xenium_ngff.zarr"
            InputLabelProps={{ shrink: true }}
            sx={{ mb: 2 }}
          />
          <Button variant="contained" color="primary" fullWidth type="submit">
            Load dataset
          </Button>
        </Paper>
        {error ? <Alert severity="error">{error}</Alert> : null}
        <FormControlLabel
          control={<Switch checked={showImage} onChange={(event) => setShowImage(event.target.checked)} />}
          label="Show image"
        />
        <FormControlLabel
          control={<Switch checked={showFeatures} onChange={(event) => setShowFeatures(event.target.checked)} />}
          label="Show features"
        />
        <FormControl fullWidth size="small" disabled={!columns.length}>
          <InputLabel id="color-by-label">Color by</InputLabel>
          <Select
            labelId="color-by-label"
            value={colorBy ?? ""}
            label="Color by"
            onChange={(event) => setColorBy(event.target.value || null)}
          >
            {columns.map((column) => (
              <MenuItem key={column} value={column}>
                {column}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Button variant="outlined" onClick={handleDownload} disabled={!activeUrl}>
          Download PNG
        </Button>
        <Divider sx={{ my: 2 }} />
        <Box sx={{ flexGrow: 1, overflowY: "auto" }}>
          <Typography variant="subtitle1" gutterBottom>
            Legend
          </Typography>
          {legendValues.length === 0 ? (
            <Typography variant="body2" color="rgba(229, 238, 247, 0.65)">
              Select a column to color-code features.
            </Typography>
          ) : (
            legendValues.map(({ value, color }) => (
              <Box key={value} sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
                <Box sx={{ width: 16, height: 16, borderRadius: 0.5, backgroundColor: color }} />
                <Typography variant="body2">{value === "__missing" ? "(missing)" : value}</Typography>
              </Box>
            ))
          )}
        </Box>
        {loading ? <Typography variant="body2">Loading features…</Typography> : null}
      </Box>
      <Box component="main" sx={{ flexGrow: 1, padding: 3 }}>
        <Paper sx={{ height: "100%", backgroundColor: "#0d1117", position: "relative" }}>
          <VivCanvas
            ref={canvasRef}
            url={activeUrl}
            overlayText={overlayText}
            features={showFeatures ? features : []}
            showImage={showImage}
            showFeatures={showFeatures}
            colorBy={colorBy}
            colorMap={colorMap}
          />
        </Paper>
      </Box>
    </Box>
  );
}
