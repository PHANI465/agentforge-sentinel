/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

const DEFAULT_ORIGIN = "http://127.0.0.1:8000";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.SENTINEL_API_ORIGIN || DEFAULT_ORIGIN;
  return {
    plugins: [react()],
    server: {
      proxy: {
        "/v1": { target, changeOrigin: true },
        "/healthz": { target, changeOrigin: true },
      },
    },
    test: {
      environment: "jsdom",
      setupFiles: "./src/test/setup.ts",
      include: ["src/**/*.test.ts", "src/**/*.test.tsx", "e2e/support/**/*.test.ts"],
    },
  };
});
