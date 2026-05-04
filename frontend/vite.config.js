import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Proxy /chat and /health to the FastAPI backend so the React app uses relative
// URLs and never has to think about CORS or environment-specific hostnames.
//
// Backend target order:
//   1. VITE_BACKEND_URL (set by docker-compose to http://backend:8000)
//   2. http://localhost:8000 (local dev)
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.VITE_BACKEND_URL || "http://localhost:8000";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      host: true,
      proxy: {
        "/chat":   { target, changeOrigin: true },
        "/health": { target, changeOrigin: true },
      },
    },
  };
});
