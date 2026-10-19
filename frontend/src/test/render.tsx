// Renders a page or component the way App mounts it: inside a router, at a route, beside a probe
// that shows where navigation led. Test support only: nothing the build bundles imports it.
import { render, screen, type RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

function Landed() {
  const { pathname } = useLocation();
  return <output data-testid="landed">{pathname}</output>;
}

// `path` is the pattern the element is mounted under, so useParams reads `route` as App's routes
// would; navigating anywhere else renders the probe in its place.
export function renderAt(element: ReactElement, route = "/", path = route): RenderResult {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path={path} element={element} />
        <Route path="*" element={<Landed />} />
      </Routes>
    </MemoryRouter>,
  );
}

// Where navigation led, or null while the element is still mounted.
export function landedAt(): string | null {
  return screen.queryByTestId("landed")?.textContent ?? null;
}
