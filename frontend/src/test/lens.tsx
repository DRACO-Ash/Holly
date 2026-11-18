// A lens state for the Object Lens's component tests: on, with two known objects and one notice,
// every action a spy. Test support only: nothing the build bundles imports it.
import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { vi } from "vitest";
import { LensContext, type LensState } from "../context/lens";
import type { ActivityNotice, HandoverObject } from "../types";

export function anObject(overrides: Partial<HandoverObject> = {}): HandoverObject {
  return {
    sat_no: 90001,
    name: "TEST-SAT 1",
    kinds: ["RPO"],
    latest_at: "2026-01-05T09:00:00Z",
    events: 1,
    maneuvers: 2,
    ...overrides,
  };
}

export function aNotice(overrides: Partial<ActivityNotice> = {}): ActivityNotice {
  return {
    id: "n-1",
    notice: "7afc_19Oct-1726Z",
    event_class: "RPO / TEST-SAT 1 (90001) vs TEST-SAT 2 (90002) / LEO",
    event_type: "other",
    status: "OPEN",
    region: null,
    udl_created_at: "2026-01-05T09:00:00Z",
    sat_ids: ["90001", "90002"],
    urgency: "high",
    top_action: null,
    ...overrides,
  };
}

export function aLens(overrides: Partial<LensState> = {}): LensState {
  const objects = [anObject(), anObject({ sat_no: 90002, name: "TEST-SAT 2", maneuvers: 0 })];
  const notices = [aNotice()];
  return {
    enabled: true,
    satNo: null,
    form: null,
    open: vi.fn(),
    close: vi.fn(),
    paletteOpen: false,
    openPalette: vi.fn(),
    closePalette: vi.fn(),
    objects: new Map(objects.map((o) => [String(o.sat_no), o])),
    notices,
    noticeByNotso: new Map(notices.map((n) => [n.notice as string, n])),
    watch: [],
    watchCap: 20,
    watchError: null,
    toggleWatch: vi.fn(),
    lastSeen: () => null,
    version: 0,
    changed: vi.fn(),
    ...overrides,
  };
}

function Landed() {
  const { pathname, search } = useLocation();
  return <output data-testid="landed">{pathname + search}</output>;
}

export function renderWithLens(element: ReactElement, lens: LensState = aLens()): RenderResult {
  return render(
    <LensContext.Provider value={lens}>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={element} />
          <Route path="*" element={<Landed />} />
        </Routes>
      </MemoryRouter>
    </LensContext.Provider>,
  );
}
