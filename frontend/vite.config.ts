import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Backend target for the dev proxy; overridable with VITE_API_TARGET
// (docker-compose sets it to http://backend:8000).
const apiTarget = process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000";

// Poll the filesystem for changes when running in a container (bind mounts in
// the Docker VM don't emit inotify events reliably).
const usePolling = process.env.CHOKIDAR_USEPOLLING === "true";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": { target: apiTarget, changeOrigin: true },
    },
    watch: usePolling ? { usePolling: true, interval: 300 } : undefined,
  },
});
