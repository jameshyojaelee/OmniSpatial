import { Box, Button, Container, Paper, Stack, TextField, Typography } from "@mui/material";
import type { FormEvent } from "react";
import { create } from "zustand";

import { VivCanvas } from "../components/VivCanvas";

type ViewerState = {
  inputUrl: string;
  activeUrl: string;
  overlayText: string;
  setInputUrl: (value: string) => void;
  loadUrl: () => void;
};

const useViewerStore = create<ViewerState>((set, get) => ({
  inputUrl: "",
  activeUrl: "",
  overlayText: "Awaiting dataset",
  setInputUrl: (value: string) => set({ inputUrl: value }),
  loadUrl: () => {
    const { inputUrl } = get();
    set({
      activeUrl: inputUrl.trim(),
      overlayText: inputUrl.trim() ? `Viewing ${inputUrl.trim()}` : "Awaiting dataset"
    });
  }
}));

export default function HomePage(): JSX.Element {
  const { inputUrl, activeUrl, overlayText, setInputUrl, loadUrl } = useViewerStore();

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    loadUrl();
  };

  return (
    <Container maxWidth="lg" sx={{ paddingY: 6 }}>
      <Stack spacing={4}>
        <Box>
          <Typography variant="h3" gutterBottom>
            OmniSpatial Web Viewer
          </Typography>
          <Typography variant="body1" color="rgba(229, 238, 247, 0.75)">
            Paste a public OME-NGFF Zarr URL to load it directly in the browser using @vivjs.
          </Typography>
        </Box>
        <Paper component="form" onSubmit={handleSubmit} sx={{ padding: 3, display: "flex", gap: 2 }}>
          <TextField
            fullWidth
            value={inputUrl}
            label="NGFF Zarr URL"
            onChange={(event) => setInputUrl(event.target.value)}
            placeholder="https://example.org/dataset.zarr"
            InputLabelProps={{ shrink: true }}
          />
          <Button variant="contained" color="primary" type="submit">
            Load
          </Button>
        </Paper>
        <Paper sx={{ padding: 2, minHeight: "620px", backgroundColor: "#0d1117" }}>
          <VivCanvas url={activeUrl} overlayText={overlayText} />
        </Paper>
      </Stack>
    </Container>
  );
}
