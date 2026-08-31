import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Backend dev server; overridable with VITE_API_TARGET.
const apiTarget = process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: apiTarget, changeOrigin: true },
    },
  },
});
