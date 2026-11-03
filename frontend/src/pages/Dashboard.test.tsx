// @vitest-environment jsdom
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getActivity } from "../api/activity";
import { getFeed } from "../api/assistant";
import { aManeuverOf, aNotice, anElset, anOverview } from "../test/activity";
import { aFeedItem, aNotification, anEvaluation } from "../test/fixtures";
import { landedAt, renderAt } from "../test/render";
import type { AssistantFeed, AssistantFeedItem } from "../types";
import Dashboard from "./Dashboard";

vi.mock("../api/assistant");
vi.mock("../api/activity");

function feed(items: AssistantFeedItem[], window_hours = 120): AssistantFeed {
  return { items, window_hours };
}

function item(id: string, urgency: string, overrides: Partial<AssistantFeedItem> = {}) {
  return aFeedItem({
    notification: aNotification({ id, notso_identifier: `NOTSO-${id}` }),
    urgency,
    ...overrides,
  });
}

async function shown() {
  renderAt(<Dashboard />, "/");
  await screen.findByRole("heading", { name: "What needs your attention" });
}

function band() {
  return document.querySelector<HTMLElement>(".console-band")!;
}

// The figure beside a label in the band across the top.
function count(label: string) {
  return within(band()).getByText(label).previousElementSibling?.textContent;
}

function theFeed() {
  return screen.getByRole("region", { name: "Assistant feed" });
}

beforeEach(() => {
  vi.mocked(getFeed).mockReset().mockResolvedValue(feed([]));
  vi.mocked(getActivity).mockReset().mockResolvedValue(anOverview());
});

afterEach(() => {
  vi.useRealTimers();
});

describe("the dashboard", () => {
  it("says it is loading until the feed arrives, asking for the server's own window", async () => {
    let answer: (value: AssistantFeed) => void = () => undefined;
    vi.mocked(getFeed).mockReturnValue(
      new Promise((resolve) => {
        answer = resolve;
      }),
    );
    renderAt(<Dashboard />, "/");
    expect(screen.getByText("Loading assistant feed...")).toBeTruthy();
    expect(getFeed).toHaveBeenCalledWith();
    answer(feed([]));
    expect(await screen.findByText(/No NOTSOs in the last 5 days/)).toBeTruthy();
    expect(screen.getByText(/Live · updated just now/)).toBeTruthy();
    expect(screen.getByText("Watch floor")).toBeTruthy();
  });

  it("names the window in days or hours", async () => {
    for (const [hours, words] of [
      [24, "1 day"],
      [1, "1 hour"],
      [36, "36 hours"],
      [0, "0 hours"],
    ] as const) {
      vi.mocked(getFeed).mockResolvedValue(feed([], hours));
      const view = renderAt(<Dashboard />, "/");
      expect(
        await screen.findByText(`No NOTSOs in the last ${words}.`, { exact: false }),
      ).toBeTruthy();
      view.unmount();
    }
  });

  it("counts the notices by urgency, an unknown one as information", async () => {
    vi.mocked(getFeed).mockResolvedValue(
      feed([
        item("h1", "high"),
        item("h2", "high"),
        item("m1", "medium"),
        item("l1", "low"),
        item("p1", "pending"),
        item("n1", "none"),
        item("x1", "unknown-urgency"),
      ]),
    );
    await shown();
    expect(count("High")).toBe("2");
    expect(count("Medium")).toBe("1");
    expect(count("Low")).toBe("1");
    expect(count("Awaiting analysis")).toBe("1");
    expect(count("Info only")).toBe("2");
  });

  it("groups the notices most urgent first, each group named and counted", async () => {
    vi.mocked(getFeed).mockResolvedValue(
      feed([
        item("n1", "none"),
        item("p1", "pending"),
        item("l1", "low"),
        item("h1", "high"),
        item("m1", "medium"),
      ]),
    );
    await shown();
    const groups = within(theFeed()).getAllByRole("heading", { level: 2 });
    expect(groups.map((g) => g.firstElementChild?.textContent)).toEqual([
      "High",
      "Medium",
      "Low",
      "Awaiting analysis",
      "Informational",
    ]);
    expect(groups.map((g) => g.firstElementChild?.className)).toEqual([
      "urgency-pill urgency-high",
      "urgency-pill urgency-medium",
      "urgency-pill urgency-low",
      "urgency-pill urgency-pending",
      "urgency-pill",
    ]);
    expect(groups.map((g) => g.lastElementChild?.textContent)).toEqual(["1", "1", "1", "1", "1"]);
  });

  it("shows each notice's evolution, summary and next action, and opens it by its link", async () => {
    vi.mocked(getFeed).mockResolvedValue(
      feed([
        item("h1", "high", {
          event_summary: "Synthetic evolution",
          event_publication_count: 3,
          evaluation: anEvaluation({ summary: "Synthetic evaluation summary" }),
          top_action: "Synthetic next step",
        }),
        item("h2", "high", { event_summary: "Single publication", event_publication_count: 1 }),
        item("h3", "high", { event_summary: "No count", event_publication_count: null }),
      ]),
    );
    await shown();
    const first = screen.getByText("NOTSO-h1").closest("li")!;
    expect(within(first).getByText(/3 publications/)).toBeTruthy();
    expect(within(first).getByText("Synthetic evolution")).toBeTruthy();
    expect(within(first).getByText("Synthetic evaluation summary")).toBeTruthy();
    expect(within(first).getByText("Synthetic next step")).toBeTruthy();
    expect(within(first).getByText("Test event class")).toBeTruthy();
    expect(first.querySelector("time")?.getAttribute("title")).toBe("2026-01-02 03:04:05Z");
    const second = screen.getByText("NOTSO-h2").closest("li")!;
    expect(within(second).queryByText(/publications/)).toBeNull();
    const third = screen.getByText("NOTSO-h3").closest("li")!;
    expect(within(third).queryByText(/publications/)).toBeNull();
    const link = within(first).getByRole("link", { name: /NOTSO-h1/ });
    expect(link.getAttribute("href")).toBe("/notifications/h1");
    fireEvent.click(link);
    expect(landedAt()).toBe("/notifications/h1");
  });

  it("falls back to the notice id, then a plain label, and leaves out what a notice lacks", async () => {
    vi.mocked(getFeed).mockResolvedValue(
      feed([
        aFeedItem({
          notification: aNotification({
            id: "a",
            notso_identifier: null,
            notice_id: "NOTICE-ONLY",
          }),
        }),
        aFeedItem({
          notification: aNotification({
            id: "b",
            notso_identifier: null,
            notice_id: null,
            event_class: null,
            udl_created_at: null,
          }),
        }),
      ]),
    );
    await shown();
    expect(screen.getByText("NOTICE-ONLY")).toBeTruthy();
    const bare = screen.getByText("Notification").closest("li")!;
    expect(within(bare).getByText("time unknown")).toBeTruthy();
    expect(bare.querySelector(".kind-badge")).toBeNull();
    expect(bare.querySelector(".action-feed-summary")).toBeNull();
    expect(bare.querySelector(".action-feed-action")).toBeNull();
  });

  it("titles a notice by the objects its event class names, with kind and regime", async () => {
    vi.mocked(getFeed).mockResolvedValue(
      feed([
        item("r1", "low", {
          notification: aNotification({
            id: "r1",
            event_class: "RPO / TEST-A (90001) vs TEST-B (90002) / LEO",
          }),
        }),
      ]),
    );
    await shown();
    const row = within(theFeed()).getByRole("link");
    expect(row.className).toContain("kind-rpo");
    expect(within(row).getByText("TEST-A")).toBeTruthy();
    expect(within(row).getByText("#90001")).toBeTruthy();
    expect(within(row).getByText("TEST-B")).toBeTruthy();
    expect(within(row).getByText("LEO").getAttribute("title")).toBe("LEO, as the notice states");
  });

  it("says why a pending notice has no analysis yet", async () => {
    vi.mocked(getFeed).mockResolvedValue(
      feed([
        item("p1", "pending", { assistant_cleared: true }),
        item("p2", "pending", { assistant_cleared: false }),
      ]),
    );
    await shown();
    expect(screen.getByText("Awaiting assistant analysis...")).toBeTruthy();
    expect(
      screen.getByText("Not sent to the assistant: its classification marking is not cleared."),
    ).toBeTruthy();
  });

  it("refreshes the feed and the activity on request, and shows why a refresh failed", async () => {
    await shown();
    await waitFor(() => expect(getActivity).toHaveBeenCalledTimes(1));
    let fail: (reason: unknown) => void = () => undefined;
    vi.mocked(getFeed).mockReturnValueOnce(
      new Promise((_, reject) => {
        fail = reject;
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    const busy = (await screen.findByRole("button", {
      name: "Refreshing...",
    })) as HTMLButtonElement;
    expect(busy.disabled).toBe(true);
    expect(screen.getByText(/· refreshing/)).toBeTruthy();
    await waitFor(() => expect(getActivity).toHaveBeenCalledTimes(2));
    fail({ response: { data: { detail: "Feed unavailable" } } });
    expect(await screen.findByText("Feed unavailable")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Refresh" })).toBeTruthy();
  });

  it("says the feed failed to load when the failure gives no reason", async () => {
    vi.mocked(getFeed).mockRejectedValue("unexpected");
    renderAt(<Dashboard />, "/");
    expect(await screen.findByText("Failed to load the assistant feed.")).toBeTruthy();
  });

  it("refreshes by itself every minute, and stops when it is gone", async () => {
    vi.useFakeTimers();
    const view = renderAt(<Dashboard />, "/");
    await act(async () => {
      await Promise.resolve();
    });
    expect(getFeed).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(getFeed).toHaveBeenCalledTimes(2);
    view.unmount();
    await vi.advanceTimersByTimeAsync(120_000);
    expect(getFeed).toHaveBeenCalledTimes(2);
  });
});

describe("the dashboard's refresh", () => {
  it("keeps the notices while it refreshes", async () => {
    vi.mocked(getFeed).mockResolvedValue(feed([item("h1", "high")]));
    await shown();
    vi.mocked(getFeed).mockReturnValueOnce(new Promise(() => undefined));
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await screen.findByRole("button", { name: "Refreshing..." });
    expect(screen.getByText("NOTSO-h1")).toBeTruthy();
    await waitFor(() => expect(getFeed).toHaveBeenCalledTimes(2));
  });
});

describe("the dashboard's console", () => {
  const recent = new Date(Date.now() - 2 * 3_600_000).toISOString();
  const old = new Date(Date.now() - 50 * 3_600_000).toISOString();

  function withActivity() {
    vi.mocked(getActivity).mockResolvedValue(
      anOverview({
        window_start: new Date(Date.now() - 120 * 3_600_000).toISOString(),
        generated_at: new Date().toISOString(),
        notices: [
          aNotice({
            id: "h1",
            urgency: "high",
            udl_created_at: recent,
            sat_ids: ["90001", "90002"],
            event_class: "Maneuver / TEST-SAT (90001) / GEO",
          }),
          aNotice({ id: "l1", urgency: "low", udl_created_at: old, sat_ids: ["90003"] }),
        ],
        maneuvers: [
          aManeuverOf({ id: "m1", sat_no: 90002, event_start_time: recent }),
          aManeuverOf({ id: "m1b", sat_no: 90002, event_start_time: recent }),
          aManeuverOf({ id: "m2", sat_no: 90001, event_start_time: old }),
        ],
        elsets: [anElset(90002, { period: 95 })],
      }),
    );
    vi.mocked(getFeed).mockResolvedValue(
      feed([
        item("h1", "high", {
          notification: aNotification({
            id: "h1",
            notso_identifier: "NOTSO-h1",
            udl_created_at: recent,
            sat_ids: ["90001", "90002"],
            event_class: "Maneuver / TEST-SAT (90001) / GEO",
          }),
        }),
        item("l1", "low", {
          notification: aNotification({
            id: "l1",
            notso_identifier: "NOTSO-l1",
            udl_created_at: old,
            sat_ids: null,
            sat_no: 90003,
          }),
        }),
      ]),
    );
  }

  it("counts the last day's notices, folded maneuvers and the satellites active", async () => {
    withActivity();
    await shown();
    await screen.findByText("Notices in 24 h");
    expect(count("Notices in 24 h")).toBe("1");
    expect(count("Maneuvers in 24 h")).toBe("1");
    expect(count("Satellites active")).toBe("3");
  });

  it("draws the window's notices by urgency and its maneuvers on a timeline", async () => {
    withActivity();
    await shown();
    const timeline = await screen.findByRole("img", { name: /^Last 5 days: / });
    expect(timeline.getAttribute("aria-label")).toBe(
      "Last 5 days: 4 events in 3 lanes, High 1, Low 1, Maneuvers 2.",
    );
    const maneuver = [...timeline.querySelectorAll("title")].find((t) =>
      t.textContent?.startsWith("Maneuver: #90002"),
    );
    fireEvent.click(maneuver!.parentElement!);
    expect(landedAt()).toBe("/maneuvers");
  });

  it("opens a notice from its mark on the timeline", async () => {
    withActivity();
    await shown();
    const timeline = await screen.findByRole("img", { name: /^Last 5 days: / });
    fireEvent.click(timeline.querySelector(".mark-emphasis")!);
    expect(landedAt()).toBe("/notifications/h1");
  });

  it("filters the feed by urgency from the band, and clears it from its chip", async () => {
    withActivity();
    await shown();
    fireEvent.click(within(band()).getByRole("button", { name: /Low/ }));
    expect(within(theFeed()).queryByText("NOTSO-h1")).toBeNull();
    expect(within(theFeed()).getByText("NOTSO-l1")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Low: remove this filter/ }));
    expect(within(theFeed()).getByText("NOTSO-h1")).toBeTruthy();
  });

  it("filters the feed to the last hours, and says when nothing matches", async () => {
    withActivity();
    await shown();
    await screen.findByRole("img", { name: /^Last 5 days: / });
    fireEvent.click(screen.getByRole("button", { name: "Last 24 h" }));
    expect(within(theFeed()).getByText("NOTSO-h1")).toBeTruthy();
    expect(within(theFeed()).queryByText("NOTSO-l1")).toBeNull();
    fireEvent.click(within(band()).getByRole("button", { name: /Low/ }));
    expect(screen.getByText("No notice in the feed matches these filters.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Clear all" }));
    expect(within(theFeed()).getByText("NOTSO-l1")).toBeTruthy();
  });

  it("filters the feed to a satellite chosen on the board", async () => {
    withActivity();
    await shown();
    const board = await screen.findByRole("region", { name: "Most active satellites" });
    const rows = within(board).getAllByRole("button");
    expect(rows[0].textContent).toContain("TEST-SAT");
    expect(rows[0].textContent).toContain("1 notice");
    expect(rows[0].textContent).toContain("1 maneuver");
    fireEvent.click(within(board).getByRole("button", { name: /#90003/ }));
    expect(within(theFeed()).queryByText("NOTSO-h1")).toBeNull();
    expect(within(theFeed()).getByText("NOTSO-l1")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /#90003: remove this filter/ }));
    expect(within(theFeed()).getByText("NOTSO-h1")).toBeTruthy();
    fireEvent.click(within(board).getByRole("button", { name: /TEST-SAT/ }));
    expect(screen.getByRole("button", { name: /TEST-SAT: remove this filter/ })).toBeTruthy();
  });

  it("says how many maneuvers are on the satellites a notice names", async () => {
    withActivity();
    await shown();
    const first = await waitFor(() => {
      const row = within(theFeed()).getByText("NOTSO-h1").closest("li")!;
      expect(within(row).getByText("3 maneuvers on these satellites")).toBeTruthy();
      return row;
    });
    expect(within(first).getByText("GEO")).toBeTruthy();
    const second = within(theFeed()).getByText("NOTSO-l1").closest("li")!;
    expect(within(second).queryByText(/on these satellites/)).toBeNull();
  });

  it("keeps the feed when the activity overview fails, and says so", async () => {
    vi.mocked(getActivity).mockRejectedValue({ response: { data: { detail: "Overview down" } } });
    vi.mocked(getFeed).mockResolvedValue(feed([item("h1", "high")]));
    await shown();
    expect(await screen.findByText(/The activity overview could not be loaded/)).toBeTruthy();
    expect(screen.getByText(/Overview down/)).toBeTruthy();
    expect(screen.getByText("NOTSO-h1")).toBeTruthy();
    expect(screen.queryByText("Notices in 24 h")).toBeNull();
    expect(screen.queryByRole("img", { name: /Last 5 days/ })).toBeNull();
  });

  it("says when the overview carries only the newest part of the window", async () => {
    vi.mocked(getActivity).mockResolvedValue(
      anOverview({ truncated: { notices: true, maneuvers: false, elsets: false } }),
    );
    await shown();
    expect(await screen.findByText(/holds more notices than this view carries/)).toBeTruthy();
  });
});
