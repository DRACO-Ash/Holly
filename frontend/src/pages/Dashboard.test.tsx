// @vitest-environment jsdom
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getFeed } from "../api/assistant";
import { aFeedItem, aNotification, anEvaluation } from "../test/fixtures";
import { landedAt, renderAt } from "../test/render";
import type { AssistantFeed, AssistantFeedItem } from "../types";
import Dashboard from "./Dashboard";

vi.mock("../api/assistant");

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

// The figure beside a label in the roll-up across the top.
function count(label: string) {
  const rollup = document.querySelector<HTMLElement>(".dashboard-rollup")!;
  return within(rollup).getByText(label).previousElementSibling?.textContent;
}

beforeEach(() => {
  vi.mocked(getFeed).mockReset().mockResolvedValue(feed([]));
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
    expect(screen.getByText(/Last refreshed \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/)).toBeTruthy();
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
    expect(count("Pending")).toBe("1");
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
    const groups = screen.getAllByRole("heading", { level: 2 });
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
    expect(within(first).getByText("2026-01-02 03:04:05")).toBeTruthy();
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
    expect(within(bare).getByText("n/a")).toBeTruthy();
    expect(bare.querySelector(".action-feed-class")).toBeNull();
    expect(bare.querySelector(".action-feed-summary")).toBeNull();
    expect(bare.querySelector(".action-feed-action")).toBeNull();
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

  it("refreshes on request, saying so meanwhile, and shows why a refresh failed", async () => {
    await shown();
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
    expect(screen.getByText(/\(refreshing\.\.\.\)/)).toBeTruthy();
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
