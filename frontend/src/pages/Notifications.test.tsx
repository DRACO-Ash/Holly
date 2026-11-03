// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getActivity } from "../api/activity";
import { listNotifications, refreshNotificationsNow } from "../api/notifications";
import { aManeuverOf, anElset, aNotice, anOverview } from "../test/activity";
import { landedAt, renderAt } from "../test/render";
import type { ActivityOverview } from "../types";
import NotificationsPage from "./Notifications";

vi.mock("../api/activity");
vi.mock("../api/notifications");

const NOW = Date.parse("2026-11-02T20:00:00Z");

function overview(overrides: Partial<ActivityOverview> = {}): ActivityOverview {
  return anOverview({
    notices: [
      aNotice({
        id: "n-urgent",
        notice: "TEST-NOTICE-A",
        event_class: "Maneuver / TEST-ALPHA (90001) / GEO",
        sat_ids: ["90001", "90009"],
        urgency: "high",
        top_action: "Tell the duty officer.",
        udl_created_at: "2026-11-02T18:00:00Z",
      }),
      aNotice({
        id: "n-photo",
        notice: "TEST-NOTICE-B",
        event_class: "Photometric change / TEST-BRAVO (90002)",
        sat_ids: ["90002"],
        urgency: "medium",
        udl_created_at: "2026-11-01T09:00:00Z",
      }),
      aNotice({
        id: "n-leo",
        notice: "TEST-NOTICE-C",
        event_class: "RPO / TEST-CHARLIE (90003) vs TEST-DELTA (90004) / LEO",
        sat_ids: ["90003", "90004"],
        status: "CLOSED",
        udl_created_at: "2026-10-30T09:00:00Z",
      }),
    ],
    maneuvers: [
      aManeuverOf({
        sat_no: 90001,
        source: "TEST-PROVIDER",
        event_start_time: "2026-11-02T17:30:00Z",
      }),
    ],
    elsets: [anElset(90002, { period: 95 })],
    ...overrides,
  });
}

async function shown(data: ActivityOverview = overview()) {
  vi.mocked(getActivity).mockResolvedValue(data);
  renderAt(<NotificationsPage />, "/notifications");
  await waitFor(() => expect(screen.queryByText("Loading the window...")).toBeNull());
}

const count = () => screen.getByText(/^Showing \d+ of \d+ notices$/).textContent;
const tile = (label: string) =>
  screen.getByText(label, { selector: ".stat-label" }).closest("button")!;

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  vi.mocked(getActivity).mockReset();
  vi.mocked(refreshNotificationsNow).mockReset().mockResolvedValue();
  vi.mocked(listNotifications)
    .mockReset()
    .mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("the live notifications console", () => {
  it("shows the window in counts and as a list grouped by day", async () => {
    await shown();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Notifications");
    expect(screen.getByText(/The last 5 days of TACREP_NOTSOs/)).toBeTruthy();
    const inWindow = screen.getByText("In window").closest(".stat-tile")!;
    expect(within(inWindow as HTMLElement).getByText("3")).toBeTruthy();
    expect(within(inWindow as HTMLElement).getByText("+1 in last 24 h")).toBeTruthy();
    expect(within(tile("High urgency")).getByText("1")).toBeTruthy();
    expect(within(tile("GEO")).getByText("1")).toBeTruthy();
    // The photometric notice states no regime: its satellite's element set gives LEO.
    expect(within(tile("LEO")).getByText("2")).toBeTruthy();
    expect(count()).toBe("Showing 3 of 3 notices");

    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(expect.arrayContaining(["Today1", "Yesterday1", "Fri 30 Oct1"]));
    const urgent = screen.getByText("TEST-NOTICE-A").closest("a")!;
    expect(urgent.getAttribute("href")).toBe("/notifications/n-urgent");
    expect(within(urgent).getByText("Tell the duty officer.")).toBeTruthy();
    expect(within(urgent).getByText("1 maneuver on these satellites")).toBeTruthy();
    expect(within(urgent).getByText("#90009")).toBeTruthy();
    expect(
      within(screen.getByText("TEST-NOTICE-C").closest("a")!).getByText("CLOSED"),
    ).toBeTruthy();
  });

  it("filters by an urgency, a kind or a regime tile, each removable as a chip", async () => {
    await shown();
    fireEvent.click(tile("High urgency"));
    expect(tile("High urgency").getAttribute("aria-pressed")).toBe("true");
    expect(count()).toBe("Showing 1 of 3 notices");
    fireEvent.click(screen.getByRole("button", { name: /High urgency: remove this filter/ }));
    expect(count()).toBe("Showing 3 of 3 notices");

    fireEvent.click(tile("Photometric change"));
    expect(count()).toBe("Showing 1 of 3 notices");
    fireEvent.click(tile("LEO"));
    expect(count()).toBe("Showing 1 of 3 notices");
    fireEvent.click(screen.getByRole("button", { name: "Clear all" }));
    expect(count()).toBe("Showing 3 of 3 notices");

    fireEvent.click(tile("RPO"));
    fireEvent.click(screen.getByRole("button", { name: /^RPO: remove this filter/ }));
    fireEvent.click(tile("LEO"));
    fireEvent.click(screen.getByRole("button", { name: /^LEO: remove this filter/ }));
    expect(count()).toBe("Showing 3 of 3 notices");
  });

  it("searches by name, number and notice", async () => {
    await shown();
    const search = screen.getByLabelText("Search notices");
    fireEvent.change(search, { target: { value: "bravo" } });
    expect(count()).toBe("Showing 1 of 3 notices");
    fireEvent.change(search, { target: { value: "90004" } });
    expect(count()).toBe("Showing 1 of 3 notices");
    fireEvent.click(screen.getByRole("button", { name: /“90004”: remove this filter/ }));
    expect((search as HTMLInputElement).value).toBe("");
  });

  it("filters to the last hours by the range buttons", async () => {
    await shown();
    fireEvent.click(screen.getByRole("button", { name: "Last 6 h" }));
    expect(count()).toBe("Showing 1 of 3 notices");
    fireEvent.click(screen.getByRole("button", { name: /Last 6 h: remove this filter/ }));
    expect(screen.getByRole("button", { name: "Whole window" }).getAttribute("aria-pressed")).toBe(
      "true",
    );
  });

  it("filters to a range dragged across the timeline", async () => {
    await shown();
    const svg = document.querySelector("svg.activity-timeline")!;
    vi.spyOn(svg, "getBoundingClientRect").mockReturnValue({
      left: 0,
      width: 1000,
      top: 0,
      height: 100,
      right: 1000,
      bottom: 100,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });
    const brush = document.querySelector(".timeline-brush")!;
    fireEvent.pointerDown(brush, { clientX: 800, pointerId: 1 });
    fireEvent.pointerMove(brush, { clientX: 1000, pointerId: 1 });
    fireEvent.pointerUp(brush, { clientX: 1000, pointerId: 1 });
    expect(screen.getByRole("button", { name: /Dragged time range: remove/ })).toBeTruthy();
    expect(count()).toBe("Showing 1 of 3 notices");
    fireEvent.click(screen.getByRole("button", { name: "Dragged range: clear" }));
    expect(count()).toBe("Showing 3 of 3 notices");
  });

  it("opens a notice from its mark on the timeline", async () => {
    await shown();
    fireEvent.click(document.querySelector(".timeline-mark.tone-photometric")!);
    expect(landedAt()).toBe("/notifications/n-photo");
  });

  it("filters to a satellite chosen on the board, and back", async () => {
    await shown();
    const board = screen
      .getByRole("heading", { name: "Most active satellites" })
      .closest("section")!;
    const alpha = within(board).getByText("TEST-ALPHA").closest("button")!;
    fireEvent.click(alpha);
    expect(alpha.getAttribute("aria-pressed")).toBe("true");
    expect(count()).toBe("Showing 1 of 3 notices");
    expect(
      screen.getByRole("button", { name: /TEST-ALPHA #90001: remove this filter/ }),
    ).toBeTruthy();
    fireEvent.click(alpha);
    expect(count()).toBe("Showing 3 of 3 notices");
    fireEvent.click(within(board).getByText("#90009").closest("button")!);
    expect(screen.getByRole("button", { name: /^#90009: remove this filter/ })).toBeTruthy();
  });

  it("says when filters hide every notice, and clears them", async () => {
    await shown();
    fireEvent.click(tile("High urgency"));
    fireEvent.click(tile("Medium urgency"));
    fireEvent.change(screen.getByLabelText("Search notices"), { target: { value: "nothing" } });
    expect(screen.getByText("No notice in the window matches these filters.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(count()).toBe("Showing 3 of 3 notices");
  });

  it("says when the window holds no notices", async () => {
    await shown(anOverview({ window_hours: 30 }));
    expect(screen.getByText(/No notices in the window/)).toBeTruthy();
    expect(screen.getByText(/The last 30 hours of TACREP_NOTSOs/)).toBeTruthy();
  });

  it("names a one-day window and a time-unknown group", async () => {
    await shown(
      anOverview({
        window_hours: 24,
        notices: [aNotice({ udl_created_at: null, event_class: null, notice: null })],
      }),
    );
    expect(screen.getByText(/The last day of TACREP_NOTSOs/)).toBeTruthy();
    expect(screen.getByText("Time unknown")).toBeTruthy();
  });

  it("says what failed when the window cannot load", async () => {
    vi.mocked(getActivity).mockRejectedValue({});
    renderAt(<NotificationsPage />, "/notifications");
    expect((await screen.findByRole("alert")).textContent).toBe(
      "Failed to load the activity overview.",
    );
  });

  it("says when the overview carries only part of the window", async () => {
    await shown(overview({ truncated: { notices: true, maneuvers: false, elsets: false } }));
    expect(screen.getByText(/holds more notices than this view carries/)).toBeTruthy();
  });

  it("pulls from UDL and reloads, or says why the pull failed", async () => {
    await shown();
    fireEvent.click(screen.getByRole("button", { name: "Pull from UDL" }));
    await waitFor(() => expect(getActivity).toHaveBeenCalledTimes(2));
    expect(refreshNotificationsNow).toHaveBeenCalledTimes(1);

    vi.mocked(refreshNotificationsNow).mockRejectedValueOnce({
      response: { data: { detail: "UDL is not configured." } },
    });
    fireEvent.click(screen.getByRole("button", { name: "Pull from UDL" }));
    expect((await screen.findByRole("alert")).textContent).toBe("UDL is not configured.");

    vi.mocked(refreshNotificationsNow).mockRejectedValueOnce(new Error("network"));
    fireEvent.click(screen.getByRole("button", { name: "Pull from UDL" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe("UDL pull failed."));
  });

  it("reloads the window on Refresh", async () => {
    await shown();
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(getActivity).toHaveBeenCalledTimes(2));
  });
});

describe("the notifications page's views", () => {
  it("opens the archive, a page at a time, and returns to the live window", async () => {
    await shown();
    fireEvent.click(screen.getByRole("button", { name: "Full archive" }));
    expect(await screen.findByRole("heading", { name: "Notification archive" })).toBeTruthy();
    await waitFor(() => expect(listNotifications).toHaveBeenCalled());
    expect(screen.getByRole("button", { name: "Full archive" }).getAttribute("aria-pressed")).toBe(
      "true",
    );
    fireEvent.click(screen.getByRole("button", { name: "Live window" }));
    expect(await screen.findByRole("heading", { name: "Notifications" })).toBeTruthy();
  });
});
