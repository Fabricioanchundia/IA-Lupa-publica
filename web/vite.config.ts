import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

// Content Security Policy for the PUBLISHED site: only our own files, no third parties.
// 'wasm-unsafe-eval' lets the browser run DuckDB's WebAssembly; nothing else is relaxed.
// It is added only to the build, because `npm run dev` injects inline scripts and styles
// (hot reload) that this policy would rightly block.
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'wasm-unsafe-eval'",
  "worker-src 'self' blob:",
  "style-src 'self'",
  "font-src 'self'",
  "img-src 'self' data:",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
].join("; ");

function contentSecurityPolicy(): Plugin {
  return {
    name: "lupa-csp",
    apply: "build",
    transformIndexHtml: () => [
      { tag: "meta", attrs: { "http-equiv": "Content-Security-Policy", content: CSP }, injectTo: "head-prepend" },
    ],
  };
}

// base "./" so the site works under any path (e.g. GitHub Pages /Lupa-publica/).
export default defineConfig({
  base: "./",
  plugins: [react(), contentSecurityPolicy()],
  build: { target: "es2022", chunkSizeWarningLimit: 2000 },
});
