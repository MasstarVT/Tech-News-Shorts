import react from "@vitejs/plugin-react";
import {defineConfig} from "vite";

// `npm run dev` serves the app on 5173 and forwards /api to `technews web` (8765).
// `npm run build` writes web/dist, which `technews web` serves itself.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {"/api": "http://127.0.0.1:8765"},
  },
  build: {outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 1200},
});
