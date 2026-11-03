// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { aManeuverOf, aNotice } from "../../test/activity";
import type { ActivityManeuver, ActivityNotice } from "../../types";
import type { ManeuverGroup, Satellite } from "../../utils/ops";
import ManeuverRow, { FactList } from "./ManeuverRow";

const NOW = Date.parse("2026-11-02T20:00:00Z");

function draw(
  maneuver: ActivityManeuver,
  {
    copies = 1,
    satellite,
    notices = [],
    open = false,
  }: {
    copies?: number;
    satellite?: Satellite;
    notices?: ActivityNotice[];
    open?: boolean;
  } = {},
) {
  const group: ManeuverGroup = { maneuver, copies, ids: [maneuver.id] };
  const onToggle = vi.fn();
  const view = render(
    <ul>
      <ManeuverRow
        group={group}
        satellite={satellite}
        slot={2}
        notices={notices}
        now={NOW}
        open={open}
        onToggle={onToggle}
      >
        <p>The record</p>
      </ManeuverRow>
    </ul>,
  );
  return { ...view, onToggle, button: view.container.querySelector("button") as HTMLElement };
}

describe("ManeuverRow", () => {
  it("shows a numbered satellite, its source, its time and nothing it does not have", () => {
    const { button } = draw(aManeuverOf({ id: "m-1", sat_no: 90007, source: "SRC" }));
    expect(button.className).toBe("event-row source-2");
    expect(button.getAttribute("aria-expanded")).toBe("false");
    expect(button.getAttribute("aria-controls")).toBe("maneuver-m-1");
    expect(button.querySelector(".event-title")?.textContent).toBe("#90007");
    expect(screen.getByText("SRC").className).toBe("source-badge source-2");
    expect(screen.getByText("3 h ago")).toBeTruthy();
    expect(screen.getByText("17:00:00Z")).toBeTruthy();
    expect(button.querySelector(".status-pill")).toBeNull();
    expect(button.querySelector(".copies-badge")).toBeNull();
    expect(button.querySelector(".fact-list")).toBeNull();
    expect(button.querySelector(".event-links")).toBeNull();
    expect(screen.queryByText("The record")).toBeNull();
  });

  it("names the satellite, its regime, status, characterization, UCT, copies and facts", () => {
    const { button } = draw(
      aManeuverOf({
        sat_no: 90001,
        maneuver_status: "COLUMN-STATUS",
        mnvr_type: "COLUMN-TYPE",
        facts: {
          status: "POSSIBLE",
          characterization: "Station keeping",
          uct: true,
          delta_pos_km: 2,
        },
      }),
      {
        copies: 3,
        satellite: {
          id: "90001",
          name: "TEST-SAT",
          regime: "GEO",
          regimeFrom: "notice",
          elset: null,
        },
      },
    );
    expect(button.querySelector(".event-title")?.textContent).toBe("TEST-SAT#90001Station keeping");
    expect(screen.getByText("POSSIBLE")).toBeTruthy();
    expect(screen.queryByText("COLUMN-STATUS")).toBeNull();
    expect(screen.getByText("UCT")).toBeTruthy();
    expect(screen.getByText("×3 records")).toBeTruthy();
    expect(screen.getByTitle("GEO, as the notice states")).toBeTruthy();
    expect(button.querySelector(".fact-list")?.textContent).toBe("Δpos 2 km");
  });

  it("falls back to the typed status and type, and names an unidentified object", () => {
    const { button } = draw(
      aManeuverOf({
        sat_no: null,
        source: null,
        event_start_time: null,
        maneuver_status: "COLUMN-STATUS",
        mnvr_type: "COLUMN-TYPE",
      }),
    );
    expect(button.querySelector(".event-title")?.textContent).toBe(
      "Unidentified objectCOLUMN-TYPE",
    );
    expect(screen.getByText("COLUMN-STATUS")).toBeTruthy();
    expect(screen.getByText("Unknown")).toBeTruthy();
    expect(screen.getByText("time unknown")).toBeTruthy();
  });

  it("lists the notices naming it, counting any beyond three", () => {
    const notices = [
      aNotice({ notice: "N-1" }),
      aNotice({ notice: null }),
      aNotice({ notice: "N-3" }),
      aNotice({ notice: "N-4" }),
    ];
    const { button } = draw(aManeuverOf(), { notices });
    const links = button.querySelector(".event-links") as HTMLElement;
    expect([...links.querySelectorAll(".link-chip")].map((c) => c.textContent)).toEqual([
      "N-1",
      "a notice",
      "N-3",
    ]);
    expect(links.textContent).toContain("and 1 more");
  });

  it("toggles, and shows its drawer when open", () => {
    const { button, onToggle, container } = draw(aManeuverOf({ id: "m-2" }), { open: true });
    expect(button.getAttribute("aria-expanded")).toBe("true");
    expect(container.querySelector("#maneuver-m-2")?.textContent).toBe("The record");
    fireEvent.click(button);
    expect(onToggle).toHaveBeenCalledOnce();
  });
});

describe("FactList", () => {
  it("shows nothing without facts, and each fact with its title", () => {
    const { container, rerender } = render(<FactList facts={[]} />);
    expect(container.innerHTML).toBe("");
    rerender(<FactList facts={[{ label: "Δv", value: "1 m/s", title: "From deltaVel" }]} />);
    expect(screen.getByTitle("From deltaVel").textContent).toBe("Δv1 m/s");
  });
});
