// @vitest-environment jsdom
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { listMattermostMessages } from "../../api/mattermost";
import { aChannel, aChatMessage } from "../../test/fixtures";
import type { MattermostMessage, MattermostMessagePage } from "../../types";
import ChannelConversation from "./ChannelConversation";
import CommsFeed, { FEED_POLL_MS } from "./CommsFeed";
import type { FeedScope } from "./scope";

vi.mock("../../api/mattermost");

const NOW = new Date("2026-01-02T04:00:00Z");
const ops = aChannel({ mm_channel_id: "ops", display_name: "Ops", message_count: 3 });
const idle = aChannel({ mm_channel_id: "idle", display_name: "Idle", following: false });

function pageOf(items: MattermostMessage[], total = items.length): MattermostMessagePage {
  return { items, total, limit: 50, offset: 0 };
}

function calls() {
  return vi.mocked(listMattermostMessages).mock.calls.map(([query]) => query);
}

// The last of a list: Array.prototype.at is outside the dashboard's ES2020 library.
function latest<T>(items: readonly T[]): T | undefined {
  return items[items.length - 1];
}

beforeEach(() => {
  vi.mocked(listMattermostMessages).mockReset().mockResolvedValue(pageOf([]));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("CommsFeed", () => {
  function feed(scope: FeedScope = { kind: "following" }, channels = [ops, idle]) {
    const onScope = vi.fn();
    render(
      <CommsFeed channels={channels} scope={scope} onScope={onScope} lastSeen={null} now={NOW} />,
    );
    return onScope;
  }

  it("shows the followed open channels' messages, newest first", async () => {
    vi.mocked(listMattermostMessages).mockResolvedValue(
      pageOf([aChatMessage({ channel_id: "ops", message: "Synthetic burn report" })]),
    );
    feed();
    expect(await screen.findByText("Synthetic burn report")).toBeTruthy();
    expect(calls()[0]).toEqual({ followed: true, q: undefined, limit: 50, offset: 0 });
    expect(screen.getByText("1 of 1 messages")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Load older" }) as HTMLButtonElement).disabled).toBe(
      true,
    );
  });

  it("asks nothing when no channel is followed, and says how to follow one", () => {
    feed({ kind: "following" }, [idle]);
    expect(screen.getByText(/No channel is followed/)).toBeTruthy();
    expect(listMattermostMessages).not.toHaveBeenCalled();
  });

  it("switches between the followed channels and every channel", async () => {
    const onScope = feed({ kind: "all" });
    await waitFor(() => expect(listMattermostMessages).toHaveBeenCalled());
    expect(calls()[0]?.channel_id).toBeUndefined();
    const followed = screen.getByRole("button", { name: "Followed channels" });
    expect(followed.getAttribute("aria-pressed")).toBe("false");
    expect(screen.getByRole("button", { name: "All channels" }).getAttribute("aria-pressed")).toBe(
      "true",
    );
    fireEvent.click(followed);
    expect(onScope).toHaveBeenCalledWith({ kind: "following" });
    fireEvent.click(screen.getByRole("button", { name: "All channels" }));
    expect(onScope).toHaveBeenLastCalledWith({ kind: "all" });
    expect(await screen.findByText("No messages from these channels yet.")).toBeTruthy();
  });

  it("narrows to the channels chosen, each a chip that takes it out, and widens again", async () => {
    const onScope = feed({ kind: "chosen", ids: ["ops", "gone-channel"] });
    await waitFor(() => expect(listMattermostMessages).toHaveBeenCalled());
    expect(calls()[0]?.channel_id).toEqual(["ops", "gone-channel"]);
    expect(screen.getByText("Showing only")).toBeTruthy();
    const opsChip = screen.getByRole("button", { name: "Stop showing #Ops" });
    expect(opsChip.textContent).toBe("#Opsx");
    fireEvent.click(opsChip);
    expect(onScope).toHaveBeenCalledWith({ kind: "chosen", ids: ["gone-channel"] });
    // A channel Holly no longer lists reads by its id.
    fireEvent.click(screen.getByRole("button", { name: "Stop showing #gone-channel" }));
    expect(onScope).toHaveBeenLastCalledWith({ kind: "chosen", ids: ["ops"] });
    fireEvent.click(screen.getByRole("button", { name: "Show every followed channel" }));
    expect(onScope).toHaveBeenLastCalledWith({ kind: "following" });
  });

  it("opens with the last 24 hours of each followed channel, a lane narrowing the feed", async () => {
    const busy = aChannel({
      mm_channel_id: "busy",
      display_name: "Busy",
      activity: Array.from({ length: 24 }, (_, hour) => (hour === 23 ? 2 : 0)),
    });
    const onScope = feed({ kind: "following" }, [busy, idle]);
    await waitFor(() => expect(listMattermostMessages).toHaveBeenCalled());
    // The unfollowed channel has no lane.
    expect(screen.getAllByRole("button", { name: /messages? in the last 24 hours$/ })).toHaveLength(
      1,
    );
    fireEvent.click(screen.getByRole("button", { name: "Busy, 2 messages in the last 24 hours" }));
    expect(onScope).toHaveBeenCalledWith({ kind: "chosen", ids: ["busy"] });
    expect(screen.getByRole("heading", { name: "Messages" })).toBeTruthy();
  });

  it("searches the messages once typing pauses", async () => {
    feed();
    await waitFor(() => expect(listMattermostMessages).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByLabelText("Search messages"), { target: { value: "  burn " } });
    await waitFor(() => expect(latest(calls())?.q).toBe("burn"));
    expect(await screen.findByText('No message contains "burn".')).toBeTruthy();
  });

  it("says when the messages could not be read", async () => {
    vi.mocked(listMattermostMessages).mockRejectedValue({});
    feed();
    expect((await screen.findByRole("alert")).textContent).toBe("Failed to load messages.");
  });

  it("loads older messages below, once each", async () => {
    const newest = aChatMessage({ id: "n", channel_id: "ops", message: "Newest" });
    const older = aChatMessage({ id: "o", channel_id: "ops", message: "Older" });
    vi.mocked(listMattermostMessages)
      .mockResolvedValueOnce(pageOf([newest], 2))
      .mockResolvedValueOnce(pageOf([newest, older], 2));
    feed();
    expect(await screen.findByText("1 of 2 messages")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Load older" }));
    expect(await screen.findByText("Older")).toBeTruthy();
    expect(latest(calls())?.offset).toBe(1);
    expect(screen.getAllByText("Newest")).toHaveLength(1);
    expect(screen.getByText("2 of 2 messages")).toBeTruthy();
  });

  it("says when older messages could not be read", async () => {
    vi.mocked(listMattermostMessages)
      .mockResolvedValueOnce(pageOf([aChatMessage({ channel_id: "ops" })], 2))
      .mockRejectedValueOnce({});
    feed();
    fireEvent.click(await screen.findByRole("button", { name: "Load older" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Failed to load older messages.");
  });

  it("offers newer messages as they arrive, without moving the list", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const shown = aChatMessage({ id: "a", channel_id: "ops", message: "Shown" });
    const arrived = aChatMessage({
      id: "b",
      channel_id: "ops",
      message: "Arrived",
      posted_at: "2026-01-02T03:59:00Z",
    });
    vi.mocked(listMattermostMessages)
      .mockResolvedValueOnce(pageOf([shown]))
      .mockResolvedValueOnce(pageOf([arrived, shown]))
      .mockRejectedValueOnce(new Error("Network Error"));
    feed();
    expect(await screen.findByText("Shown")).toBeTruthy();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(FEED_POLL_MS);
    });
    expect(latest(calls())?.posted_at_gte).toBe(shown.posted_at);
    expect(screen.queryByText("Arrived")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Show 1 new message" }));
    expect(screen.getByText("Arrived")).toBeTruthy();
    expect(screen.getByText("2 of 2 messages")).toBeTruthy();
    // A poll that fails changes nothing.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(FEED_POLL_MS);
    });
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("drops a poll answered after the scope changed, and stops polling once closed", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const late = aChatMessage({ id: "late", channel_id: "ops", message: "Late" });
    let answer: (page: MattermostMessagePage) => void = () => undefined;
    vi.mocked(listMattermostMessages)
      .mockResolvedValueOnce(pageOf([]))
      .mockImplementationOnce(() => new Promise((resolve) => (answer = resolve)))
      .mockResolvedValue(pageOf([]));
    const onScope = vi.fn();
    const { rerender, unmount } = render(
      <CommsFeed
        channels={[ops]}
        scope={{ kind: "following" }}
        onScope={onScope}
        lastSeen={null}
        now={NOW}
      />,
    );
    await waitFor(() => expect(calls()).toHaveLength(1));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(FEED_POLL_MS);
    });
    expect(calls()).toHaveLength(2);
    rerender(
      <CommsFeed
        channels={[ops]}
        scope={{ kind: "all" }}
        onScope={onScope}
        lastSeen={null}
        now={NOW}
      />,
    );
    await act(async () => {
      answer(pageOf([late]));
      await Promise.resolve();
    });
    expect(screen.queryByRole("button", { name: /new message/ })).toBeNull();
    const asked = calls().length;
    unmount();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(FEED_POLL_MS * 2);
    });
    expect(calls()).toHaveLength(asked);
  });

  function many(count: number, from: number) {
    return Array.from({ length: count }, (_, n) =>
      aChatMessage({
        id: `m${from + n}`,
        channel_id: "ops",
        message: `Message ${from + n}`,
        posted_at: new Date(Date.UTC(2026, 0, 2, 3, 0, 0) + (from + n) * 1000).toISOString(),
      }),
    ).reverse();
  }

  it("reloads the latest page when more arrived than one poll holds, so none is skipped", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const shown = aChatMessage({ id: "a", channel_id: "ops", message: "Shown" });
    vi.mocked(listMattermostMessages)
      .mockResolvedValueOnce(pageOf([shown]))
      .mockResolvedValueOnce(pageOf(many(50, 12), 61))
      .mockResolvedValueOnce(pageOf(many(50, 12), 62));
    feed();
    expect(await screen.findByText("Shown")).toBeTruthy();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(FEED_POLL_MS);
    });
    // 61 in the server's total: the 60 newer, and the newest shown, which the poll asks from.
    fireEvent.click(screen.getByRole("button", { name: "Show 60 new messages" }));
    expect(await screen.findByText("50 of 62 messages")).toBeTruthy();
    // The reload asks for the latest page itself, not for what came after the newest shown.
    expect(latest(calls())).toEqual({ followed: true, q: undefined, limit: 50, offset: 0 });
    expect(screen.queryByText("Shown")).toBeNull();
    expect((screen.getByRole("button", { name: "Load older" }) as HTMLButtonElement).disabled).toBe(
      false,
    );
  });

  it("drops a reload of the latest page answered after the scope changed", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const shown = aChatMessage({ id: "a", channel_id: "ops", message: "Shown" });
    let slow: (page: MattermostMessagePage) => void = () => undefined;
    vi.mocked(listMattermostMessages)
      .mockResolvedValueOnce(pageOf([shown]))
      .mockResolvedValueOnce(pageOf(many(50, 12), 61))
      .mockImplementationOnce(() => new Promise((resolve) => (slow = resolve)))
      .mockResolvedValue(
        pageOf([aChatMessage({ id: "e", channel_id: "ops", message: "Every channel" })]),
      );
    const onScope = vi.fn();
    const props = { channels: [ops], onScope, lastSeen: null, now: NOW };
    const { rerender } = render(<CommsFeed scope={{ kind: "following" }} {...props} />);
    expect(await screen.findByText("Shown")).toBeTruthy();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(FEED_POLL_MS);
    });
    fireEvent.click(screen.getByRole("button", { name: "Show 60 new messages" }));
    rerender(<CommsFeed scope={{ kind: "all" }} {...props} />);
    expect(await screen.findByText("Every channel")).toBeTruthy();
    await act(async () => {
      slow(pageOf(many(50, 12), 62));
      await Promise.resolve();
    });
    expect(screen.queryByText("Message 61")).toBeNull();
    expect(screen.getByText("Every channel")).toBeTruthy();
  });

  it("shows the answer to the latest ask, whatever order the answers come in", async () => {
    let slow: (page: MattermostMessagePage) => void = () => undefined;
    vi.mocked(listMattermostMessages)
      .mockImplementationOnce(() => new Promise((resolve) => (slow = resolve)))
      .mockResolvedValueOnce(
        pageOf([aChatMessage({ id: "n", channel_id: "ops", message: "Newer" })]),
      );
    const onScope = vi.fn();
    const { rerender } = render(
      <CommsFeed
        channels={[ops]}
        scope={{ kind: "following" }}
        onScope={onScope}
        lastSeen={null}
        now={NOW}
      />,
    );
    rerender(
      <CommsFeed
        channels={[ops]}
        scope={{ kind: "all" }}
        onScope={onScope}
        lastSeen={null}
        now={NOW}
      />,
    );
    expect(await screen.findByText("Newer")).toBeTruthy();
    await act(async () => {
      slow(pageOf([aChatMessage({ id: "o", channel_id: "ops", message: "Older ask" })]));
      await Promise.resolve();
    });
    expect(screen.queryByText("Older ask")).toBeNull();
    expect(screen.getByText("Newer")).toBeTruthy();
  });

  it("drops older messages answered after the scope changed", async () => {
    let slow: (page: MattermostMessagePage) => void = () => undefined;
    vi.mocked(listMattermostMessages)
      .mockResolvedValueOnce(
        pageOf([aChatMessage({ id: "f", channel_id: "ops", message: "First" })], 2),
      )
      .mockImplementationOnce(() => new Promise((resolve) => (slow = resolve)))
      .mockResolvedValueOnce(
        pageOf([aChatMessage({ id: "e", channel_id: "ops", message: "Everything" })]),
      );
    const onScope = vi.fn();
    const { rerender } = render(
      <CommsFeed
        channels={[ops]}
        scope={{ kind: "following" }}
        onScope={onScope}
        lastSeen={null}
        now={NOW}
      />,
    );
    fireEvent.click(await screen.findByRole("button", { name: "Load older" }));
    rerender(
      <CommsFeed
        channels={[ops]}
        scope={{ kind: "all" }}
        onScope={onScope}
        lastSeen={null}
        now={NOW}
      />,
    );
    expect(await screen.findByText("Everything")).toBeTruthy();
    await act(async () => {
      slow(pageOf([aChatMessage({ id: "x", channel_id: "ops", message: "Stale older" })], 2));
      await Promise.resolve();
    });
    expect(screen.queryByText("Stale older")).toBeNull();
  });
});

describe("ChannelConversation", () => {
  function conversation(channel = ops, lastSeen: string | null = null) {
    const onFollow = vi.fn();
    render(
      <ChannelConversation
        channel={channel}
        channels={[ops, idle]}
        busy={false}
        onFollow={onFollow}
        lastSeen={lastSeen}
        now={NOW}
      />,
    );
    return onFollow;
  }

  function scrolledUp() {
    // jsdom lays nothing out: give the scroll box a height the reader is far above the end of.
    const box = document.querySelector(".conversation-scroll") as HTMLElement;
    Object.defineProperty(box, "scrollHeight", { configurable: true, value: 2000 });
    Object.defineProperty(box, "clientHeight", { configurable: true, value: 400 });
    box.scrollTop = 0;
    return box;
  }

  const first = aChatMessage({ id: "1", message: "First", posted_at: "2026-01-02T01:00:00Z" });
  const arrived = aChatMessage({ id: "2", message: "Arrived", posted_at: "2026-01-02T03:59:00Z" });

  it("adds a message that arrives at the bottom for a reader already there", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(listMattermostMessages)
      .mockResolvedValueOnce(pageOf([first]))
      .mockResolvedValueOnce(pageOf([arrived, first]))
      .mockRejectedValueOnce(new Error("Network Error"));
    conversation(ops, "2026-01-02T02:00:00Z");
    expect(await screen.findByText("First")).toBeTruthy();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(FEED_POLL_MS);
    });
    expect(latest(calls())).toEqual({
      channel_id: "ops",
      limit: 50,
      offset: 0,
      posted_at_gte: first.posted_at,
    });
    const bodies = [...document.querySelectorAll(".comms-body")].map((b) => b.textContent);
    expect(bodies).toEqual(["First", "Arrived"]);
    expect(screen.getByText("New since your last visit")).toBeTruthy();
    // A poll that fails changes nothing.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(FEED_POLL_MS);
    });
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("holds a message that arrives below a reader who has scrolled up, until asked", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(listMattermostMessages)
      .mockResolvedValueOnce(pageOf([first]))
      .mockResolvedValueOnce(pageOf([arrived, first]))
      .mockResolvedValue(pageOf([first]));
    conversation();
    expect(await screen.findByText("First")).toBeTruthy();
    scrolledUp();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(FEED_POLL_MS);
    });
    expect(screen.queryByText("Arrived")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "1 new message below" }));
    expect(screen.getByText("Arrived")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /new message/ })).toBeNull();
    // Nothing newer: nothing waits.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(FEED_POLL_MS);
    });
    expect(screen.queryByRole("button", { name: /new message/ })).toBeNull();
  });

  it("reloads the latest page when more arrived than one poll holds, at the bottom or below", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const burst = Array.from({ length: 50 }, (_, n) =>
      aChatMessage({
        id: `b${n}`,
        message: `Burst ${n}`,
        posted_at: `2026-01-02T03:${String(10 + n).padStart(2, "0")}:00Z`,
      }),
    ).reverse();
    vi.mocked(listMattermostMessages)
      .mockResolvedValueOnce(pageOf([first]))
      .mockResolvedValueOnce(pageOf(burst, 70))
      .mockResolvedValueOnce(pageOf(burst, 71));
    conversation();
    expect(await screen.findByText("First")).toBeTruthy();
    // At the bottom: the latest page at once.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(FEED_POLL_MS);
    });
    await waitFor(() => expect(screen.queryByText("First")).toBeNull());
    expect(calls()[2]).toEqual({ channel_id: "ops", limit: 50, offset: 0 });
    // Scrolled up: offered, then the latest page on request.
    scrolledUp();
    // 60 arrived after the newest shown; the server's total counts that one too, as it asks
    // from its time on.
    const later = Array.from({ length: 50 }, (_, n) =>
      aChatMessage({
        id: `l${n}`,
        message: `Later ${n}`,
        posted_at: new Date(Date.UTC(2026, 0, 2, 4, 0, n)).toISOString(),
      }),
    ).reverse();
    vi.mocked(listMattermostMessages).mockResolvedValueOnce(pageOf(later, 61));
    vi.mocked(listMattermostMessages).mockResolvedValueOnce(pageOf(later, 111));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(FEED_POLL_MS);
    });
    fireEvent.click(screen.getByRole("button", { name: "60 new messages below" }));
    await waitFor(() =>
      expect(latest(calls())).toEqual({ channel_id: "ops", limit: 50, offset: 0 }),
    );
  });

  it("drops the answer for a channel no longer shown", async () => {
    let slow: (page: MattermostMessagePage) => void = () => undefined;
    vi.mocked(listMattermostMessages)
      .mockImplementationOnce(() => new Promise((resolve) => (slow = resolve)))
      .mockResolvedValueOnce(pageOf([aChatMessage({ id: "i", message: "Idle's own" })]));
    const props = {
      channels: [ops, idle],
      busy: false,
      onFollow: vi.fn(),
      lastSeen: null,
      now: NOW,
    };
    const { rerender } = render(<ChannelConversation channel={ops} {...props} />);
    rerender(<ChannelConversation channel={idle} {...props} />);
    expect(await screen.findByText("Idle's own")).toBeTruthy();
    await act(async () => {
      slow(pageOf([aChatMessage({ id: "o", message: "Ops, late" })]));
      await Promise.resolve();
    });
    expect(screen.queryByText("Ops, late")).toBeNull();
  });

  it("drops a poll with more than a page answered for a channel no longer shown", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let slow: (page: MattermostMessagePage) => void = () => undefined;
    vi.mocked(listMattermostMessages)
      .mockResolvedValueOnce(pageOf([first]))
      .mockImplementationOnce(() => new Promise((resolve) => (slow = resolve)))
      .mockResolvedValue(pageOf([aChatMessage({ id: "i", message: "Idle's own" })]));
    const props = {
      channels: [ops, idle],
      busy: false,
      onFollow: vi.fn(),
      lastSeen: null,
      now: NOW,
    };
    const { rerender } = render(<ChannelConversation channel={ops} {...props} />);
    expect(await screen.findByText("First")).toBeTruthy();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(FEED_POLL_MS);
    });
    rerender(<ChannelConversation channel={idle} {...props} />);
    expect(await screen.findByText("Idle's own")).toBeTruthy();
    const asked = calls().length;
    await act(async () => {
      slow(pageOf([arrived], 70));
      await Promise.resolve();
    });
    // No reload of the channel no longer shown, and the one shown stays.
    expect(
      calls()
        .slice(asked)
        .filter((query) => query?.channel_id === "ops"),
    ).toEqual([]);
    expect(screen.getByText("Idle's own")).toBeTruthy();
  });

  it("stops polling once closed, and drops an answer that lands after", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let slow: (page: MattermostMessagePage) => void = () => undefined;
    vi.mocked(listMattermostMessages)
      .mockImplementationOnce(() => new Promise((resolve) => (slow = resolve)))
      .mockResolvedValue(pageOf([]));
    const { unmount } = render(
      <ChannelConversation
        channel={ops}
        channels={[ops]}
        busy={false}
        onFollow={vi.fn()}
        lastSeen={null}
        now={NOW}
      />,
    );
    unmount();
    await act(async () => {
      slow(pageOf([first]));
      await vi.advanceTimersByTimeAsync(FEED_POLL_MS * 2);
    });
    expect(calls()).toHaveLength(1);
  });

  it("counts several messages waiting below, and polls from nothing in an empty channel", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const third = aChatMessage({ id: "3", message: "Third", posted_at: "2026-01-02T03:59:30Z" });
    vi.mocked(listMattermostMessages)
      .mockResolvedValueOnce(pageOf([]))
      .mockResolvedValueOnce(pageOf([third, arrived]));
    conversation();
    expect(await screen.findByText("Holly holds no message from this channel yet.")).toBeTruthy();
    scrolledUp();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(FEED_POLL_MS);
    });
    expect(latest(calls())?.posted_at_gte).toBeUndefined();
    expect(screen.getByRole("button", { name: "2 new messages below" })).toBeTruthy();
  });

  it("reads one channel oldest first, with its team, kind and count", async () => {
    vi.mocked(listMattermostMessages).mockResolvedValue(
      pageOf([
        aChatMessage({ id: "2", message: "Second", posted_at: "2026-01-02T02:00:00Z" }),
        aChatMessage({ id: "1", message: "First", posted_at: "2026-01-02T01:00:00Z" }),
      ]),
    );
    const onFollow = conversation();
    expect(await screen.findByText("Second")).toBeTruthy();
    const bodies = [...document.querySelectorAll(".comms-body")].map((b) => b.textContent);
    expect(bodies).toEqual(["First", "Second"]);
    expect(calls()[0]).toEqual({ channel_id: "ops", limit: 50, offset: 0 });
    expect(screen.getByRole("heading", { name: "#Ops" })).toBeTruthy();
    expect(screen.getByText(/Synthetic Team · Public channel · 3 messages held/)).toBeTruthy();
    fireEvent.click(screen.getByRole("switch", { name: "Follow Ops" }));
    expect(onFollow).toHaveBeenCalledWith(ops, false);
  });

  it("says a closed channel is closed, and offers no switch", async () => {
    conversation(
      aChannel({
        display_name: "Done",
        status: "closed",
        closed_at: "2026-01-01T00:00:00Z",
        team_name: null,
        channel_type: "P",
        message_count: 1,
      }),
    );
    expect(
      await screen.findByText(
        /This channel has been closed since .*: its name carries the word CLOSED, so Holly treats it as closed\. Take the word out of its name in Mattermost and the next sweep opens it again\. Holly keeps the messages it pulled and pulls nothing more\./,
      ),
    ).toBeTruthy();
    expect(screen.getByText("Closed by name")).toBeTruthy();
    // The channel's own name, not the headings' capitals.
    expect(screen.getByRole("heading", { name: "#Done" }).className).toBe("record-value");
    expect(screen.queryByRole("switch")).toBeNull();
    expect(screen.getByText("Private channel · 1 message held")).toBeTruthy();
    expect(await screen.findByText("Holly holds no message from this channel yet.")).toBeTruthy();
  });

  it("names an archived channel and one closed at a time unknown", async () => {
    conversation(aChannel({ display_name: "Shelved", status: "closed", archived: true }));
    expect(await screen.findByText("Archived")).toBeTruthy();
    expect(
      screen.getByText(
        "This channel has been archived in Mattermost. Holly keeps the messages it pulled and pulls nothing more.",
      ),
    ).toBeTruthy();
  });

  it("says when the bot can no longer read it, or when it is not followed", async () => {
    conversation(aChannel({ accessible: false }));
    expect(await screen.findByText(/The bot can no longer read this channel/)).toBeTruthy();
    conversation(idle);
    expect(await screen.findByText(/Not followed: Holly pulls nothing/)).toBeTruthy();
  });

  it("loads earlier messages above", async () => {
    vi.mocked(listMattermostMessages)
      .mockResolvedValueOnce(pageOf([aChatMessage({ id: "2", message: "Latest" })], 2))
      .mockResolvedValueOnce(
        pageOf(
          [aChatMessage({ id: "1", message: "Before", posted_at: "2026-01-02T01:00:00Z" })],
          2,
        ),
      );
    conversation();
    fireEvent.click(await screen.findByRole("button", { name: "Load earlier messages" }));
    expect(await screen.findByText("Before")).toBeTruthy();
    expect(latest(calls())?.offset).toBe(1);
    const bodies = [...document.querySelectorAll(".comms-body")].map((b) => b.textContent);
    expect(bodies).toEqual(["Before", "Latest"]);
    expect(screen.queryByRole("button", { name: "Load earlier messages" })).toBeNull();
  });

  it("says when the channel, or its earlier messages, could not be read", async () => {
    vi.mocked(listMattermostMessages).mockRejectedValueOnce({});
    conversation();
    expect((await screen.findByRole("alert")).textContent).toBe("Failed to load this channel.");
  });

  it("says when earlier messages could not be read", async () => {
    vi.mocked(listMattermostMessages)
      .mockResolvedValueOnce(pageOf([aChatMessage()], 3))
      .mockRejectedValueOnce({});
    conversation();
    fireEvent.click(await screen.findByRole("button", { name: "Load earlier messages" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Failed to load earlier messages.");
  });
});
