import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
// The theme's three typefaces, bundled into the build: the dashboard's policy allows fonts only
// from Holly itself (font-src 'self'), never from a font service.
import "@fontsource-variable/inter";
import "@fontsource-variable/fira-code";
import "@fontsource/share-tech-mono";
import "./styles/tokens.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
