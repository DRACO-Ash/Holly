// Builds the prototype as one page with every script, style, font and image inlined, so it opens
// from a file with no server and no network.
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "./",
  cacheDir: ".vite-proto",
  build: {
    outDir: "dist-proto",
    emptyOutDir: true,
    assetsInlineLimit: 100_000_000,
    cssCodeSplit: false,
    modulePreload: false,
    rollupOptions: { output: { inlineDynamicImports: true } },
  },
});
