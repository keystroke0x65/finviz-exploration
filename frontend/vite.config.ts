import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In Docker Compose, "localhost" inside the frontend container refers to
// the frontend container itself, not the backend service — Compose's
// internal DNS resolves the backend by its service name instead. Running
// vite directly on the host (outside Docker) still needs localhost, so
// this is configurable via an env var Compose sets and bare `vite` doesn't.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": BACKEND_URL,
    },
  },
});
