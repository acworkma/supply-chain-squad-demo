import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api/events/stream": {
        target: "http://localhost:8000",
        changeOrigin: true,
        headers: { Accept: "text/event-stream" },
      },
      "/api/agent-messages/stream": {
        target: "http://localhost:8000",
        changeOrigin: true,
        headers: { Accept: "text/event-stream" },
      },
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
