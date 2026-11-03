// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getActivity } from "../api/activity";
import { getManeuver, listManeuvers } from "../api/maneuvers";
import { NO_FACTS, aManeuverOf, aNotice, anElset, anOverview } from "../test/activity";
import { landedAt, renderAt } from "../test/render";
import type { ActivityOverview, Maneuver, ManeuverDetail, ManeuverPage } from "../types";
import ManeuversPage from "./Maneuvers";

vi.mock("../api/activity");
vi.mock("../api/maneuvers");

const NOW = Date.parse("2026-11-02T20:00:00Z");

// Synthetic records: every value is made up for the tests.
const alpha = aManeuverOf({
  id: "m-alpha",
  sat_no: 90001,
  source: "PROVIDER-A",
  event_start_time: "2026-11-02T18:00:00Z",
  facts: { status: "POSSIBLE", delta_vel_kms: 0.0015, post_geo_longitude_deg: 100.5 },
});
const alphaCopy = { ...alpha, id: "m-alpha-copy" };
const beta = aManeuverOf({
  id: "m-beta",
  sat_no: 90002,
  source: "PROVIDER-B",
  event_start_time: "2026-11-01T10:00:00Z",
  facts: { characterization: "TEST-STATION-KEEPING" },
});
const gamma = aManeuverOf({
  id: "m-gamma",
  sat_no: 90002,
  source: "PROVIDER-B",
  event_start_time: "2026-10-30T08:00:00Z",
});
const notice = aNotice({
  id: "n-1",
  notice: "TEST-NOTICE-1",
  event_class: "Maneuver / TEST-SAT ONE (90001) / GEO",
  sat_ids: ["90001"],
});

function overview(overrides: Partial<ActivityOverview> = {}): ActivityOverview {
  return anOverview({
    maneuvers: [alpha, alphaCopy, beta, gamma],
    notices: [notice],
    elsets: [anElset(90002, { period: 95 })],
    ...overrides,
  });
}

function detailOf(id: string, overrides: Partial<ManeuverDetail> = {}): ManeuverDetail {
  return {
    id,
    udl_id: `udl-${id}`,
    data_mode: "TEST",
    source: "PROVIDER-A",
    classification_marking: "U",
    created_by: null,
    orig_network: null,
    origin: null,
    udl_created_at: null,
    sat_no: 90001,
    event_start_time: "2026-11-02T18:00:00Z",
    event_stop_time: null,
    mnvr_type: null,
    description: null,
    delta_v: null,
    thrust_magnitude: null,
    thrust_duration: null,
    propulsion_type: null,
    maneuver_status: null,
    responsible_nation: null,
    created_at: "2026-11-02T18:05:00Z",
    updated_at: "2026-11-02T18:05:00Z",
    facts: { ...NO_FACTS, status: "POSSIBLE", report_time: "2026-11-02T18:30:00Z", uct: false },
    raw: { status: "POSSIBLE", testField: "TEST-VALUE" },
    ...overrides,
  };
}

function rows() {
  return screen
    .queryAllByRole("button", { expanded: false })
    .concat(screen.queryAllByRole("button", { expanded: true }));
}

function rowFor(text: string) {
  const row = rows().find((r) => r.textContent?.includes(text));
  if (!row) throw new Error(`no row for ${text}`);
  return row;
}

function shownCount() {
  return screen.getByText(/^Showing \d+ of/).textContent;
}

async function renderLive(data = overview()) {
  vi.mocked(getActivity).mockResolvedValue(data);
  renderAt(<ManeuversPage />, "/maneuvers");
  await screen.findByText(/^Showing/);
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.spyOn(Date, "now").mockReturnValue(NOW);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("the live window", () => {
  it("counts maneuvers with copies folded, satellites, the last day and the notices", async () => {
    await renderLive();
    const band = document.querySelector(".console-band") as HTMLElement;
    const tile = (label: string) =>
      within(band)
        .getByText(label, { selector: ".stat-label" })
        .closest(".stat-tile") as HTMLElement;
    expect(within(tile("Maneuvers")).getByText("3")).toBeTruthy();
    expect(tile("Maneuvers").textContent).toContain("1 duplicate record folded");
    expect(within(tile("Satellites")).getByText("2")).toBeTruthy();
    expect(within(tile("Last 24 h")).getByText("1")).toBeTruthy();
    expect(within(tile("Named in a notice")).getByText("1")).toBeTruthy();
    expect(within(tile("PROVIDER-B")).getByText("2")).toBeTruthy();
    expect(shownCount()).toBe("Showing 3 of 3 maneuvers");
    expect(rowFor("TEST-SAT ONE").textContent).toContain("×2 records");
    expect(screen.getByText("Today")).toBeTruthy();
    expect(screen.getByText("Yesterday")).toBeTruthy();
  });

  it("shows no fold note when nothing was folded, and an empty list", async () => {
    await renderLive(overview({ maneuvers: [], notices: [] }));
    expect(document.querySelector(".stat-detail")).toBeNull();
    expect(screen.getByText(/No maneuvers match/)).toBeTruthy();
  });

  it("filters by source, and clears with the chip", async () => {
    await renderLive();
    fireEvent.click(screen.getByRole("button", { name: /PROVIDER-B/, pressed: false }));
    expect(shownCount()).toBe("Showing 2 of 3 maneuvers");
    fireEvent.click(screen.getByRole("button", { name: /Source: PROVIDER-B/ }));
    expect(shownCount()).toBe("Showing 3 of 3 maneuvers");
  });

  it("keeps only maneuvers on satellites a notice names, and clears all filters at once", async () => {
    await renderLive();
    fireEvent.click(screen.getByRole("button", { name: /Named in a notice/ }));
    expect(shownCount()).toBe("Showing 1 of 3 maneuvers");
    fireEvent.click(screen.getByRole("button", { name: /PROVIDER-A/, pressed: false }));
    fireEvent.click(screen.getByRole("button", { name: "Clear all" }));
    expect(shownCount()).toBe("Showing 3 of 3 maneuvers");
    fireEvent.click(screen.getByRole("button", { name: /Named in a notice/ }));
    fireEvent.click(screen.getByRole("button", { name: /Named in a notice: remove/ }));
    expect(shownCount()).toBe("Showing 3 of 3 maneuvers");
  });

  it("searches by number, name, source and characterisation", async () => {
    await renderLive();
    const search = screen.getByLabelText("Search maneuvers");
    fireEvent.change(search, { target: { value: "test-sat one" } });
    expect(shownCount()).toBe("Showing 1 of 3 maneuvers");
    fireEvent.change(search, { target: { value: "station-keeping" } });
    expect(shownCount()).toBe("Showing 1 of 3 maneuvers");
    fireEvent.change(search, { target: { value: "90002" } });
    expect(shownCount()).toBe("Showing 2 of 3 maneuvers");
    fireEvent.change(search, { target: { value: "nothing like this" } });
    expect(shownCount()).toBe("Showing 0 of 3 maneuvers");
  });

  it("narrows to a time range by button and by dragging the timeline", async () => {
    await renderLive();
    fireEvent.click(screen.getByRole("button", { name: "Last 24 h" }));
    expect(shownCount()).toBe("Showing 1 of 3 maneuvers");
    fireEvent.click(screen.getByRole("button", { name: /Time range: remove/ }));
    expect(shownCount()).toBe("Showing 3 of 3 maneuvers");

    const svg = document.querySelector(".activity-timeline") as SVGSVGElement;
    svg.getBoundingClientRect = () => ({ left: 0, width: 1000 }) as DOMRect;
    const brush = document.querySelector(".timeline-brush") as SVGRectElement;
    // The window runs 28 Oct 20:00 to 2 Nov 20:00 across view x 128 to 984: the drag spans the
    // last 18 hours or so.
    fireEvent.pointerDown(brush, { clientX: 850, pointerId: 1 });
    fireEvent.pointerMove(brush, { clientX: 984, pointerId: 1 });
    fireEvent.pointerUp(brush, { clientX: 984, pointerId: 1 });
    expect(shownCount()).toBe("Showing 1 of 3 maneuvers");
    expect(screen.getByRole("button", { name: "Dragged range: clear" })).toBeTruthy();
    // A click without a drag clears it.
    fireEvent.pointerDown(brush, { clientX: 500, pointerId: 1 });
    fireEvent.pointerUp(brush, { clientX: 500, pointerId: 1 });
    expect(shownCount()).toBe("Showing 3 of 3 maneuvers");
  });

  it("filters to a satellite chosen on the board, and back", async () => {
    await renderLive();
    const board = screen.getByRole("region", { name: "Most manoeuvring satellites" });
    const first = within(board).getAllByRole("button")[0];
    expect(first.textContent).toContain("#90002");
    expect(first.textContent).toContain("2 maneuvers");
    fireEvent.click(first);
    expect(shownCount()).toBe("Showing 2 of 3 maneuvers");
    expect(screen.getByRole("button", { name: /Satellite: #90002/ })).toBeTruthy();
    fireEvent.click(first);
    expect(shownCount()).toBe("Showing 3 of 3 maneuvers");
  });

  it("draws the GEO belt only when a record gives a longitude", async () => {
    await renderLive();
    const belt = screen.getByRole("img", { name: /GEO belt: 1 maneuver by longitude/ });
    expect(belt.querySelectorAll(".timeline-mark")).toHaveLength(1);
  });

  it("leaves the GEO belt out when no record gives a longitude, and draws a drift", async () => {
    await renderLive(overview({ maneuvers: [beta] }));
    expect(screen.queryByRole("img", { name: /GEO belt/ })).toBeNull();
    const drifting = aManeuverOf({
      facts: { post_geo_longitude_deg: -75, post_drift_rate_deg_day: -0.05 },
    });
    vi.mocked(getActivity).mockResolvedValue(overview({ maneuvers: [drifting] }));
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await screen.findByRole("img", { name: /GEO belt/ });
    expect(document.querySelector(".geo-belt-drift")).toBeTruthy();
  });

  it("says when the overview could not load", async () => {
    vi.mocked(getActivity).mockRejectedValue({});
    renderAt(<ManeuversPage />, "/maneuvers");
    expect((await screen.findByRole("alert")).textContent).toBe(
      "Failed to load the activity overview.",
    );
  });
});

describe("a maneuver opened in place", () => {
  it("loads the record, shows its facts, copies, notices and raw payload", async () => {
    vi.mocked(getManeuver).mockResolvedValue(detailOf("m-alpha"));
    await renderLive();
    const row = rowFor("TEST-SAT ONE");
    fireEvent.click(row);
    expect(row.getAttribute("aria-expanded")).toBe("true");
    expect(getManeuver).toHaveBeenCalledWith("m-alpha");
    const drawer = document.getElementById("maneuver-m-alpha") as HTMLElement;
    await within(drawer).findByText("Raw UDL record");
    expect(within(drawer).getByText("2026-11-02 18:30:00Z")).toBeTruthy();
    expect(within(drawer).getByText("Uncorrelated track")).toBeTruthy();
    expect(drawer.textContent).toContain("Folded from 2 records");
    expect(drawer.textContent).toContain("TEST-VALUE");
    expect(drawer.textContent).toContain("TBC, re-verify");
    fireEvent.click(within(drawer).getByRole("link", { name: "TEST-NOTICE-1" }));
    expect(landedAt()).toBe("/notifications/n-1");
  });

  it("says when the record could not load, and closes again", async () => {
    vi.mocked(getManeuver).mockRejectedValue({});
    await renderLive();
    const row = rowFor("#90002");
    fireEvent.click(row);
    const drawer = document.getElementById(
      `maneuver-${row.getAttribute("aria-controls")?.slice(9)}`,
    );
    expect(drawer).toBeTruthy();
    expect((await screen.findByRole("alert")).textContent).toBe(
      "Failed to load the maneuver record.",
    );
    fireEvent.click(row);
    expect(row.getAttribute("aria-expanded")).toBe("false");
  });

  it("says when a record carries no fact beyond its start", async () => {
    vi.mocked(getManeuver).mockResolvedValue(
      detailOf("m-gamma", { facts: { ...NO_FACTS }, raw: {} }),
    );
    await renderLive(overview({ maneuvers: [gamma] }));
    fireEvent.click(rowFor("#90002"));
    await screen.findByText("Raw UDL record");
    expect(screen.getByText(/carries none of the fields/)).toBeTruthy();
  });

  it("opens from its mark on the timeline", async () => {
    vi.mocked(getManeuver).mockResolvedValue(detailOf("m-beta"));
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    await renderLive();
    const mark = [...document.querySelectorAll(".activity-timeline .timeline-mark")].find((m) =>
      m.textContent?.includes("PROVIDER-B, 01 Nov"),
    ) as Element;
    fireEvent.click(mark);
    await waitFor(() => expect(getManeuver).toHaveBeenCalledWith("m-beta"));
    expect(scroll).toHaveBeenCalled();
  });
});

describe("the full archive", () => {
  function anArchived(overrides: Partial<Maneuver> = {}): Maneuver {
    const detail: Partial<ManeuverDetail> = { ...detailOf("a-1") };
    delete detail.raw;
    return { ...(detail as Maneuver), ...overrides };
  }

  function pageOf(items: Maneuver[], total = items.length): ManeuverPage {
    return { items, total, limit: 50, offset: 0 };
  }

  async function renderArchive(page: ManeuverPage) {
    vi.mocked(getActivity).mockResolvedValue(overview());
    vi.mocked(listManeuvers).mockResolvedValue(page);
    renderAt(<ManeuversPage />, "/maneuvers");
    fireEvent.click(screen.getByRole("button", { name: "Full archive" }));
    await screen.findByText(/total/);
  }

  const cells = (index: number) =>
    within(screen.getAllByRole("row")[index])
      .getAllByRole("cell")
      .map((c) => c.textContent);

  it("lists every record with its end, status, delta-v and source", async () => {
    await renderArchive(
      pageOf([
        anArchived({
          facts: {
            ...NO_FACTS,
            status: "POSSIBLE",
            delta_vel_kms: 0.0012,
            event_end_time: "2026-11-02T18:10:00Z",
          },
        }),
        anArchived({
          id: "a-2",
          sat_no: null,
          source: null,
          event_start_time: null,
          maneuver_status: "TEST-STATUS",
          delta_v: 2.5,
          facts: { ...NO_FACTS },
        }),
        anArchived({ id: "a-3", facts: { ...NO_FACTS } }),
      ]),
    );
    expect(cells(1)).toEqual([
      "90001",
      "2026-11-02 18:00:00Z",
      "2026-11-02 18:10:00Z",
      "POSSIBLE",
      "1.200",
      "PROVIDER-A",
    ]);
    expect(cells(2)).toEqual(["n/a", "n/a", "n/a", "TEST-STATUS", "2.500", "n/a"]);
    expect(cells(3)[3]).toBe("n/a");
    expect(cells(3)[4]).toBe("n/a");
    expect(screen.getByText(/3 total · page 1 of 1/)).toBeTruthy();
  });

  it("sorts, filters by satellite, pages and refreshes on the server", async () => {
    await renderArchive(pageOf([anArchived()], 120));
    const last = () => vi.mocked(listManeuvers).mock.lastCall?.[0];
    fireEvent.click(screen.getByRole("button", { name: /Start/ }));
    await waitFor(() => expect(last()?.sort_dir).toBe("asc"));
    fireEvent.click(screen.getByRole("button", { name: /Sat No/ }));
    await waitFor(() => expect(last()).toMatchObject({ sort_by: "sat_no", sort_dir: "desc" }));

    const field = screen.getByLabelText("Satellite number") as HTMLInputElement;
    fireEvent.change(field, { target: { value: "2.5" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(screen.getByRole("alert").textContent).toBe("Satellite number must be a whole number.");
    fireEvent.change(field, { target: { value: "90001" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(last()?.sat_no).toBe(90001));
    fireEvent.change(field, { target: { value: " " } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(last()?.sat_no).toBeUndefined());

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(last()?.offset).toBe(50));
    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    await waitFor(() => expect(last()?.offset).toBe(0));
    const before = vi.mocked(listManeuvers).mock.calls.length;
    fireEvent.click(
      within(document.querySelector(".card") as HTMLElement).getByRole("button", {
        name: "Refresh",
      }),
    );
    await waitFor(() => expect(vi.mocked(listManeuvers).mock.calls.length).toBe(before + 1));
    fireEvent.change(field, { target: { value: "90001" } });
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(field.value).toBe("");
  });

  it("says when there is nothing to show, or the archive could not load", async () => {
    await renderArchive(pageOf([]));
    expect(screen.getByText("No maneuvers to show.")).toBeTruthy();
    vi.mocked(listManeuvers).mockRejectedValue({});
    fireEvent.click(screen.getByRole("button", { name: /Start/ }));
    expect((await screen.findByRole("alert")).textContent).toBe("Failed to load maneuvers.");
    fireEvent.click(screen.getByRole("button", { name: "Live window" }));
    await screen.findByText(/^Showing/);
  });
});
