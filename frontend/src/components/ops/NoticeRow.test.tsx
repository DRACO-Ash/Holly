// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { aManeuverOf, aNotice } from "../../test/activity";
import type { ActivityManeuver, ActivityNotice } from "../../types";
import { type Satellite, parseEventClass } from "../../utils/ops";
import NoticeRow from "./NoticeRow";

const NOW = Date.parse("2026-11-02T20:00:00Z");

const satellite = (id: string, fields: Partial<Satellite> = {}): Satellite => ({
  id,
  name: null,
  regime: null,
  regimeFrom: null,
  elset: null,
  ...fields,
});

function row(
  notice: ActivityNotice,
  {
    directory = new Map<string, Satellite>(),
    maneuvers = new Map<string, ActivityManeuver[]>(),
  }: {
    directory?: Map<string, Satellite>;
    maneuvers?: Map<string, ActivityManeuver[]>;
  } = {},
) {
  const view = render(
    <MemoryRouter>
      <NoticeRow
        notice={notice}
        parsed={parseEventClass(notice.event_class)}
        directory={directory}
        maneuversBySat={maneuvers}
        now={NOW}
      />
    </MemoryRouter>,
  );
  return { ...view, link: view.container.querySelector("a") as HTMLAnchorElement };
}

describe("NoticeRow", () => {
  it("links to the notice and shows its kind, regime, objects, time and number", () => {
    const notice = aNotice({
      id: "n-9",
      event_class: "Maneuver / TEST-SAT (90001) / GEO",
      notice: "TEST-NOTICE-9",
      udl_created_at: "2026-11-02T17:00:00Z",
    });
    const { link } = row(notice);
    expect(link.getAttribute("href")).toBe("/notifications/n-9");
    expect(link.className).toBe("event-row kind-maneuver urgency-none");
    expect(screen.getByText("Maneuver").closest(".kind-badge")).toBeTruthy();
    expect(screen.getByTitle("GEO, as the notice states")).toBeTruthy();
    expect(screen.getByRole("heading", { level: 3 }).textContent).toBe("TEST-SAT #90001");
    expect(screen.getByText("3 h ago")).toBeTruthy();
    expect(screen.getByText("TEST-NOTICE-9")).toBeTruthy();
    // An open notice carries no status badge; urgency info only carries none either.
    expect(link.querySelector(".status-pill")).toBeNull();
    expect(link.querySelector(".urgency-pill")).toBeNull();
  });

  it("shows two objects with vs, the urgency, the next action and a status that is not open", () => {
    const { link } = row(
      aNotice({
        event_class: "RPO / TEST-A (90001) vs TEST-B (90002) / LEO",
        sat_ids: ["90001", "90002"],
        urgency: "high",
        top_action: "Notify the duty officer",
        status: "CLOSED",
        notice: null,
      }),
    );
    expect(link.className).toContain("urgency-high");
    expect(screen.getByRole("heading", { level: 3 }).textContent).toBe(
      "TEST-A #90001vs TEST-B #90002",
    );
    expect(screen.getByText("High")).toBeTruthy();
    expect(screen.getByText("CLOSED")).toBeTruthy();
    expect(link.querySelector(".event-action")?.textContent).toBe("Next: Notify the duty officer");
    expect(screen.queryByText(/Also names/)).toBeNull();
  });

  it("names the other satellites, by name where known, and counts any beyond four", () => {
    const { link } = row(
      aNotice({
        event_class: "Photometric change / TEST-SAT (90001)",
        sat_ids: ["90001", "2", "3", "4", "5", "6"],
      }),
      { directory: new Map([["2", satellite("2", { name: "TEST-TWO" })]]) },
    );
    const also = link.querySelector(".event-links") as HTMLElement;
    expect(also.textContent).toContain("Also names");
    expect([...also.querySelectorAll(".link-chip")].map((c) => c.textContent)).toEqual([
      "TEST-TWO #2",
      "#3",
      "#4",
      "#5",
    ]);
    expect(also.textContent).toContain("and 1 more");
  });

  it("takes the regime from the satellite when the notice gives none", () => {
    row(aNotice({ event_class: "Photometric change / TEST-SAT (90001)" }), {
      directory: new Map([["90001", satellite("90001", { regime: "LEO", regimeFrom: "elset" })]]),
    });
    expect(
      screen.getByTitle("LEO, from the latest element set's period and eccentricity"),
    ).toBeTruthy();
  });

  it("shows the class as written when it cannot be read, and a word when there is none", () => {
    const { unmount } = row(aNotice({ event_class: "Odd", sat_ids: [] }));
    expect(screen.getByRole("heading", { level: 3 }).textContent).toBe("Odd");
    unmount();
    row(aNotice({ event_class: null, notice: "N-1", sat_ids: [] }));
    expect(screen.getByRole("heading", { level: 3 }).textContent).toBe("N-1");
    expect(screen.getByText("Other")).toBeTruthy();
  });

  it("falls back to a word, and hides a number that is the name", () => {
    const { unmount } = row(aNotice({ event_class: null, notice: null, sat_ids: [] }));
    expect(screen.getByRole("heading", { level: 3 }).textContent).toBe("Notice");
    unmount();
    row(aNotice({ event_class: "Maneuver / (90001)" }));
    expect(screen.getByRole("heading", { level: 3 }).textContent).toBe("90001");
  });

  it("lists the maneuvers on its satellites, newest first, and counts the rest", () => {
    const at = (h: number) => `2026-11-02T${String(h).padStart(2, "0")}:15:00Z`;
    const maneuvers = new Map([
      [
        "90001",
        [
          aManeuverOf({ sat_no: 90001, event_start_time: at(10), source: "SRC-A" }),
          aManeuverOf({ sat_no: 90001, event_start_time: at(12), source: "SRC-B" }),
          aManeuverOf({ sat_no: 90001, event_start_time: at(11), source: null }),
          aManeuverOf({ sat_no: 90001, event_start_time: null, source: "SRC-C" }),
        ],
      ],
    ]);
    const { link } = row(aNotice(), { maneuvers });
    const all = link.querySelectorAll(".event-links");
    const links = all[all.length - 1] as HTMLElement;
    expect(links.textContent).toContain("4 maneuvers on these satellites");
    expect([...links.querySelectorAll(".link-chip")].map((c) => c.textContent?.trim())).toEqual([
      "#90001 12:15Z SRC-B",
      "#90001 11:15Z",
      "#90001 10:15Z SRC-A",
    ]);
    expect(links.textContent).toContain("and 1 more");
  });

  it("says one maneuver in the singular", () => {
    const { link } = row(aNotice(), {
      maneuvers: new Map([["90001", [aManeuverOf({ event_start_time: null })]]]),
    });
    expect(link.textContent).toContain("1 maneuver on these satellites");
    expect(link.textContent).not.toContain("more");
  });
});
