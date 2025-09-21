import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backendTarget = env.VITE_BACKEND_URL;

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: backendTarget
      ? {
          proxy: {
            "/api": {
              target: backendTarget,
              changeOrigin: true,
              secure: false,
            },
            "/auth": {
              target: backendTarget,
              changeOrigin: true,
              secure: false,
            },
          },
        }
      : undefined,
  };
});
