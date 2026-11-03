// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { aManeuverOf, aNotice } from "../../test/activity";
import { type ObjectActivity, type Satellite, foldDuplicates } from "../../utils/ops";
import ObjectBoard from "./ObjectBoard";

const satellite = (id: string, name: string | null): Satellite => ({
  id,
  name,
  regime: name ? "GEO" : null,
  regimeFrom: name ? "notice" : null,
  elset: null,
});

describe("ObjectBoard", () => {
  it("says so when nothing is active", () => {
    render(
      <ObjectBoard
        title="Most active"
        entries={[]}
        directory={new Map()}
        start={0}
        end={1}
        selected={null}
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByRole("region", { name: "Most active" })).toBeTruthy();
    expect(screen.getByText("No satellite has activity in the window.")).toBeTruthy();
  });

  it("ranks the satellites, named or numbered, and selects and deselects one", () => {
    const entries: ObjectActivity[] = [
      {
        id: "1",
        notices: [aNotice()],
        maneuvers: foldDuplicates([aManeuverOf(), aManeuverOf({ source: "OTHER" })]),
        times: [5],
      },
      { id: "2", notices: [aNotice(), aNotice()], maneuvers: [], times: [] },
      { id: "3", notices: [], maneuvers: foldDuplicates([aManeuverOf()]), times: [] },
    ];
    const onSelect = vi.fn();
    const { rerender } = render(
      <ObjectBoard
        title="Most active"
        entries={entries}
        directory={new Map([["1", satellite("1", "TEST-SAT")]])}
        start={0}
        end={10}
        selected={null}
        onSelect={onSelect}
      />,
    );
    const rows = screen.getAllByRole("button");
    expect(rows[0].textContent).toContain("TEST-SAT#1");
    expect(rows[0].textContent).toContain("1 notice");
    expect(rows[0].textContent).toContain("2 maneuvers");
    expect(rows[0].querySelector(".regime-badge")?.textContent).toBe("GEO");
    expect(rows[1].textContent).toContain("#2");
    expect(rows[1].textContent).toContain("2 notices");
    expect(rows[1].textContent).not.toContain("maneuver");
    expect(rows[2].textContent).toContain("1 maneuver");
    expect(rows[2].textContent).not.toContain("notice");
    fireEvent.click(rows[1]);
    expect(onSelect).toHaveBeenCalledWith("2");
    rerender(
      <ObjectBoard
        title="Most active"
        entries={entries}
        directory={new Map()}
        start={0}
        end={10}
        selected="2"
        onSelect={onSelect}
      />,
    );
    const on = screen.getAllByRole("button")[1];
    expect(on.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(on);
    expect(onSelect).toHaveBeenLastCalledWith(null);
  });
});
