import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { bundledLicences } from "./bundled-licences.mjs";

export default defineConfig({
  plugins: [react(), bundledLicences()],
  server: {
    // Loopback only, as the API under `python -m app`: neither is reachable from the network.
    host: "127.0.0.1",
    port: 3000,
    strictPort: true,
    // The Holly server in development: `python -m app` listens on PORT or 8080.
    proxy: {
      "/api": "http://127.0.0.1:8080",
    },
  },
  test: {
    // Node by default; a test of the page opts into a browser with @vitest-environment jsdom.
    environment: "node",
    include: ["src/**/*.test.{ts,tsx}"],
    // Testing Library unmounts what each test rendered when it finds a global afterEach. A setup
    // file could register that instead, but Vitest leaves setup files out of every coverage
    // report, and the gate scores a file it cannot find at 0%.
    globals: true,
    coverage: {
      provider: "v8",
      // The App Store's node job runs the tests at the upload's root and its Code Quality gate
      // reads coverage/lcov.info there, so the report is written there too, naming each file
      // from the root (frontend/src/...): a file the gate cannot find scores 0%.
      reporter: ["text", ["lcov", { projectRoot: ".." }]],
      reportsDirectory: "../coverage",
      include: ["src/**/*.{ts,tsx}"],
      // The floor the gate holds the upload to, held here for the dashboard on its own.
      thresholds: { lines: 80, branches: 80, functions: 80, statements: 80 },
    },
  },
});
