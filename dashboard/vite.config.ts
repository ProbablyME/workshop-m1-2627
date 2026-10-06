import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// En dev, le serveur Vite proxifie /api et /ws vers l'API FastAPI et injecte la clé API
// côté serveur : la clé ne transite jamais dans le code du navigateur.
// Les variables (API_PORT, API_KEY) sont lues dans le .env à la racine du dépôt.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, "..", "");
  const apiPort = env.API_PORT || "8000";
  const target = env.VITE_PROXY_TARGET || `http://localhost:${apiPort}`;
  const headers: Record<string, string> = env.API_KEY ? { "X-API-Key": env.API_KEY } : {};
  return {
    plugins: [react()],
    server: {
      port: Number(env.DASHBOARD_DEV_PORT || 5173),
      strictPort: true,
      proxy: {
        "/api": { target, changeOrigin: true, headers },
        "/ws": { target: target.replace(/^http/, "ws"), ws: true },
      },
    },
  };
});
