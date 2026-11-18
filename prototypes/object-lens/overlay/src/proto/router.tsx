// The prototype routes by hash, so a file opened from disk keeps deep links and the Back button.
// Embedded as a blob (inside the proposal), the page address cannot anchor a URL, so routes are
// kept in memory instead; that copy is for looking around, not for running the test.
import type { ReactNode } from "react";
import { HashRouter, MemoryRouter } from "react-router-dom";

export default function ProtoRouter({ children }: Readonly<{ children: ReactNode }>) {
  return globalThis.location.protocol === "blob:" ? <MemoryRouter>{children}</MemoryRouter> : <HashRouter>{children}</HashRouter>;
}
