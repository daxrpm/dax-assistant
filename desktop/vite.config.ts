import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

// Tauri drives this dev server; it must be on a fixed port and must not try to
// open a browser. `TAURI_DEV_HOST` is set by the CLI for mobile/LAN targets.
const host = process.env.TAURI_DEV_HOST;

export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 5273,
    strictPort: true,
    host: host || false,
    hmr: host ? { protocol: "ws", host, port: 5274 } : undefined,
    watch: { ignored: ["**/src-tauri/**"] },
    // Proxy the backend so browser-based development is same-origin. The
    // packaged app talks to the backend directly from `tauri://localhost`
    // (allowed in CORS by the server), but a plain browser on the dev port is
    // not an allowed origin — without this proxy every request fails and the
    // app renders "Backend unreachable" against a perfectly healthy backend.
    proxy: {
      "/api": { target: "http://127.0.0.1:8420", changeOrigin: true },
      "/ws": { target: "ws://127.0.0.1:8420", ws: true, changeOrigin: true },
    },
  },
  // Tauri targets a known WebKitGTK/WebView2 version, so we can skip legacy
  // transpilation entirely.
  build: {
    target: "es2022",
    // Vite 8 bundles with rolldown; leaving `minify` at its default uses the
    // built-in oxc minifier. Naming "esbuild" here would require the optional
    // esbuild package, which is no longer installed.
    minify: !process.env.TAURI_ENV_DEBUG,
    sourcemap: !!process.env.TAURI_ENV_DEBUG,
    rolldownOptions: {
      output: {
        // Stable package boundaries keep framework caching independent from
        // route code while leaving markdown/highlighting lazy with Chat.
        codeSplitting: {
          groups: [
            {
              name: "react-vendor",
              test: /node_modules\/(?:react|react-dom|scheduler)\//,
            },
            {
              name: "markdown-vendor",
              test: /node_modules\/(?:highlight\.js|react-markdown|rehype-highlight|remark-gfm)\//,
            },
          ],
        },
      },
    },
  },
});
