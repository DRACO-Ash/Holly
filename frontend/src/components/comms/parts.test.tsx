// @vitest-environment jsdom
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { aChannel, aChatMessage, aSweep } from "../../test/fixtures";
import type { MattermostChannel } from "../../types";
import { channelHues } from "../../utils/comms";
import ActivityLanes from "./ActivityLanes";
import ActivityTrace from "./ActivityTrace";
import ChannelSwitchboard from "./ChannelSwitchboard";
import FollowSwitch from "./FollowSwitch";
import MessageList from "./MessageList";
import { type FeedScope, MAX_PICKED, scopeQuery, toggled } from "./scope";
import SweepStrip from "./SweepStrip";

const NOW = new Date("2026-01-02T04:00:00Z");

function day(at: Record<number, number>): number[] {
  return Array.from({ length: 24 }, (_, hour) => at[hour] ?? 0);
}

describe("ActivityTrace", () => {
  it("draws one bar an hour on the page's one scale, the current hour last, and reads out the total", () => {
    const { container } = render(<ActivityTrace counts={day({ 0: 2, 23: 4 })} hue={3} peak={8} />);
    const trace = screen.getByRole("img", { name: "6 messages in the last 24 hours" });
    expect(trace.getAttribute("class")).toBe("activity-trace channel-hue-3");
    const bars = container.querySelectorAll("rect");
    expect(bars).toHaveLength(24);
    expect(container.querySelectorAll("rect.trace-on")).toHaveLength(2);
    // Scaled to the page's busiest hour, 8, not this trace's own 4.
    expect(bars[23].getAttribute("height")).toBe("8");
    expect(bars[0].getAttribute("height")).toBe("4");
    expect(bars[1].getAttribute("height")).toBe("1");
    expect(bars[23].getAttribute("class")).toBe("trace-on trace-now");
    expect(container.querySelector("line")).toBeNull();
  });

  it("says one message, and draws a quiet day flat", () => {
    render(<ActivityTrace counts={day({ 5: 1 })} hue={1} peak={1} />);
    expect(screen.getByRole("img", { name: "1 message in the last 24 hours" })).toBeTruthy();
    const { container } = render(<ActivityTrace counts={[]} hue={1} peak={0} />);
    expect(screen.getByRole("img", { name: "0 messages in the last 24 hours" })).toBeTruthy();
    expect(container.querySelectorAll("rect")).toHaveLength(0);
  });

  it("stretches inside a lane, hides itself from the reader there, and marks the last visit", () => {
    const { container } = render(
      <ActivityTrace
        counts={day({ 3: 1 })}
        hue={2}
        peak={1}
        width={240}
        stretch
        seenAt={6}
        decorative
      />,
    );
    const svg = container.querySelector("svg") as SVGElement;
    expect(svg.getAttribute("class")).toBe("activity-trace channel-hue-2 stretch");
    expect(svg.getAttribute("preserveAspectRatio")).toBe("none");
    expect(svg.getAttribute("aria-hidden")).toBe("true");
    expect(svg.getAttribute("role")).toBeNull();
    expect(container.querySelector("line")?.getAttribute("x1")).toBe("60");
  });
});

describe("FollowSwitch", () => {
  it("is a labelled switch that asks for the other state", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <FollowSwitch label="Ops" on={false} describedBy="hint" onChange={onChange} />,
    );
    const control = screen.getByRole("switch", { name: "Follow Ops" });
    expect(control.getAttribute("aria-checked")).toBe("false");
    expect(control.getAttribute("aria-describedby")).toBe("hint");
    expect(control.textContent).toBe("Off");
    fireEvent.click(control);
    expect(onChange).toHaveBeenCalledWith(true);
    rerender(<FollowSwitch label="Ops" on onChange={onChange} />);
    expect(control.getAttribute("aria-checked")).toBe("true");
    expect(control.className).toBe("follow-switch on");
    fireEvent.click(control);
    expect(onChange).toHaveBeenLastCalledWith(false);
  });

  it("keeps its focus while its change saves, and ignores presses meanwhile", () => {
    const onChange = vi.fn();
    render(<FollowSwitch label="Ops" on busy onChange={onChange} />);
    const control = screen.getByRole("switch") as HTMLButtonElement;
    expect(control.disabled).toBe(false);
    expect(control.getAttribute("aria-disabled")).toBe("true");
    control.focus();
    fireEvent.click(control);
    expect(onChange).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(control);
  });
});

describe("SweepStrip", () => {
  function lamp(container: HTMLElement) {
    return container.querySelector(".sweep-lamp")?.className;
  }

  it("says when Holly last swept, as which bot and how often, and lights green", () => {
    const onSweep = vi.fn();
    const { container } = render(
      <SweepStrip sweep={aSweep()} sweeping={false} onSweep={onSweep} now={NOW} />,
    );
    expect(container.textContent).toContain(
      "Channels swept 1 h ago as @synthetic-bot, every minute.",
    );
    expect(screen.getByText("1 h ago").getAttribute("title")).toBe("2026-01-02 03:00:00 UTC");
    expect(lamp(container)).toBe("sweep-lamp ok");
    fireEvent.click(screen.getByRole("button", { name: "Find channels now" }));
    expect(onSweep).toHaveBeenCalled();
  });

  it("says in words when the last sweep failed, and names no bot it never learned", () => {
    const { container } = render(
      <SweepStrip
        sweep={aSweep({ ok: false, bot: null, interval_seconds: 300 })}
        sweeping={false}
        onSweep={vi.fn()}
        now={NOW}
      />,
    );
    expect(lamp(container)).toBe("sweep-lamp failed");
    expect(container.textContent).toContain("The last channel sweep, 1 h ago, failed.");
    expect(container.textContent).not.toContain("@");
  });

  it("says how often in minutes, or in seconds when it is not whole minutes", () => {
    const { container, rerender } = render(
      <SweepStrip
        sweep={aSweep({ interval_seconds: 300 })}
        sweeping={false}
        onSweep={vi.fn()}
        now={NOW}
      />,
    );
    expect(container.textContent).toContain("every 5 minutes.");
    rerender(
      <SweepStrip
        sweep={aSweep({ interval_seconds: 90 })}
        sweeping={false}
        onSweep={vi.fn()}
        now={NOW}
      />,
    );
    expect(container.textContent).toContain("every 90 seconds.");
  });

  it("says no sweep has run yet, and waits, keeping its focus, while one runs", () => {
    const onSweep = vi.fn();
    const { container } = render(
      <SweepStrip
        sweep={aSweep({ last_at: null, ok: null })}
        sweeping
        onSweep={onSweep}
        now={NOW}
      />,
    );
    expect(container.textContent).toContain("No channel sweep has run since Holly last started.");
    expect(lamp(container)).toBe("sweep-lamp busy");
    const button = screen.getByRole("button", { name: "Finding channels..." });
    expect(button.getAttribute("aria-disabled")).toBe("true");
    fireEvent.click(button);
    expect(onSweep).not.toHaveBeenCalled();
  });

  it("shows a plain lamp before any outcome is known", () => {
    const { container } = render(
      <SweepStrip sweep={aSweep({ ok: null })} sweeping={false} onSweep={vi.fn()} now={NOW} />,
    );
    expect(lamp(container)).toBe("sweep-lamp");
  });
});

describe("ChannelSwitchboard", () => {
  const ops = aChannel({
    mm_channel_id: "ops",
    display_name: "Ops",
    last_message_at: "2026-01-02T03:56:00Z",
    message_count: 3,
    activity: day({ 22: 2, 23: 1 }),
    new_since: 2,
    first_seen_at: "2026-01-01T00:00:00Z",
  });
  const quiet = aChannel({
    mm_channel_id: "quiet",
    display_name: "Quiet",
    following: false,
    pulled: false,
    is_new: true,
    channel_type: "P",
    last_message_at: "2026-01-01T04:00:00Z",
    first_seen_at: "2026-01-01T01:00:00Z",
  });
  const gone = aChannel({
    mm_channel_id: "gone",
    display_name: "Gone",
    accessible: false,
    pulled: false,
    first_seen_at: "2026-01-01T02:00:00Z",
  });
  const fresh = aChannel({
    mm_channel_id: "fresh",
    display_name: "Fresh",
    activity: day({ 23: 4 }),
    first_seen_at: "2026-01-01T03:00:00Z",
  });
  const done = aChannel({
    mm_channel_id: "done",
    display_name: "CLOSED Done",
    status: "closed",
    following: false,
    pulled: false,
    message_count: 1,
    closed_at: "2026-01-01T04:00:00Z",
  });
  const shelved = aChannel({
    mm_channel_id: "shelved",
    display_name: "Shelved",
    status: "closed",
    archived: true,
    pulled: false,
    message_count: 5,
  });

  function board(overrides: Partial<Parameters<typeof ChannelSwitchboard>[0]> = {}) {
    const props = {
      channels: [ops, quiet, gone, fresh, done, shelved] as MattermostChannel[],
      selectedIds: [] as string[],
      picking: true,
      busyId: null,
      onSelect: vi.fn(),
      onFollow: vi.fn(),
      now: NOW,
      ...overrides,
    };
    render(<ChannelSwitchboard {...props} />);
    return props;
  }

  function row(name: string) {
    return screen.getByRole("button", { name }).closest("li") as HTMLElement;
  }

  it("lists the open channels with a shared switch each, and how many are followed", () => {
    board();
    const open = screen.getAllByRole("list")[0];
    expect(within(open).getAllByRole("listitem")).toHaveLength(4);
    expect(screen.getByRole("heading", { name: "Channels 3 of 4 followed" })).toBeTruthy();
    const opsSwitch = screen.getByRole("switch", { name: "Follow Ops" });
    expect(opsSwitch.getAttribute("aria-checked")).toBe("true");
    expect(
      document.getElementById(opsSwitch.getAttribute("aria-describedby")!)?.textContent,
    ).toMatch(
      /^The switches are shared: switching a channel off stops Holly pulling it for everyone\./,
    );
    expect(screen.getByRole("switch", { name: "Follow Quiet" }).getAttribute("aria-checked")).toBe(
      "false",
    );
    expect(within(row("Ops")).getByText("4 min ago")).toBeTruthy();
    expect(within(row("Fresh")).getByText("No messages yet")).toBeTruthy();
  });

  it("draws every pulled channel's day on one scale, with its total in words", () => {
    board();
    const opsTrace = within(row("Ops")).getByRole("img");
    // The busiest hour on the board is Fresh's 4, so Ops's 2 is half height.
    expect(opsTrace.querySelectorAll("rect")[22].getAttribute("height")).toBe("8");
    expect(within(row("Ops")).getByText("3 in 24 h")).toBeTruthy();
    expect(within(row("Fresh")).getByText("4 in 24 h")).toBeTruthy();
  });

  it("says a channel Holly does not pull is not pulled, rather than drawing it quiet", () => {
    board();
    expect(within(row("Quiet")).queryByRole("img")).toBeNull();
    expect(within(row("Quiet")).getByText("Not pulled")).toBeTruthy();
    expect(row("Quiet").textContent).toContain("last pulled 1 d ago");
    expect(within(row("Gone")).getByText("Not pulled")).toBeTruthy();
    expect(within(row("Gone")).queryByText("No messages yet")).toBeNull();
  });

  it("counts what is new since the last visit, and tags a new, a private and a lost channel", () => {
    board();
    expect(within(row("Ops")).getByText("2 new")).toBeTruthy();
    expect(within(row("Fresh")).queryByText(/ new$/)).toBeNull();
    expect(within(row("Quiet")).getByText("New")).toBeTruthy();
    expect(within(row("Quiet")).getByText("Private")).toBeTruthy();
    expect(within(row("Gone")).getByText("Bot removed")).toBeTruthy();
  });

  it("gives the first channels found different hues", () => {
    board();
    const dots = ["Ops", "Quiet", "Gone", "Fresh"].map(
      (name) => row(name).querySelector(".hue-dot")?.className,
    );
    expect(new Set(dots).size).toBe(4);
  });

  it("folds the closed channels away, each with why it closed and what Holly kept", () => {
    board();
    expect(screen.getByText("Closed (2)")).toBeTruthy();
    expect(within(row("CLOSED Done")).getByText("Closed by name")).toBeTruthy();
    expect(within(row("CLOSED Done")).getByText("1 message kept")).toBeTruthy();
    expect(row("CLOSED Done").textContent).toContain("closed 1 d ago");
    expect(within(row("Shelved")).getByText("Archived")).toBeTruthy();
    expect(within(row("Shelved")).getByText("5 messages kept")).toBeTruthy();
    expect(within(row("Shelved")).queryByRole("switch")).toBeNull();
    expect(screen.getByText(/opens again when CLOSED leaves its name/)).toBeTruthy();
  });

  it("in the feed, presses the names picked and picks another", () => {
    const props = board({ selectedIds: ["ops", "done"] });
    expect(screen.getByRole("button", { name: "Ops" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Fresh" }).getAttribute("aria-pressed")).toBe(
      "false",
    );
    expect(screen.getByRole("button", { name: "Ops" }).getAttribute("aria-current")).toBeNull();
    expect(row("CLOSED Done").className).toBe("switchboard-row closed selected");
    expect(screen.getByText(/Select a name to show that channel in the feed/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Fresh" }));
    expect(props.onSelect).toHaveBeenCalledWith("fresh");
    fireEvent.click(screen.getByRole("switch", { name: "Follow Quiet" }));
    expect(props.onFollow).toHaveBeenCalledWith(quiet, true);
  });

  it("in the conversation layout, marks the open channel current, and holds a saving switch", () => {
    board({ selectedIds: ["ops"], picking: false, busyId: "quiet" });
    const name = screen.getByRole("button", { name: "Ops" });
    expect(name.getAttribute("aria-current")).toBe("true");
    expect(name.getAttribute("aria-pressed")).toBeNull();
    expect(row("Ops").className).toBe("switchboard-row selected");
    expect(screen.queryByText(/Select a name/)).toBeNull();
    expect(screen.getByRole("switch", { name: "Follow Quiet" }).getAttribute("aria-disabled")).toBe(
      "true",
    );
  });

  it("says how to add a channel when there is none", () => {
    board({ channels: [] });
    expect(screen.getByText(/No open channel yet/)).toBeTruthy();
    expect(screen.queryByText(/Closed \(/)).toBeNull();
  });
});

describe("ActivityLanes", () => {
  const ops = aChannel({
    mm_channel_id: "ops",
    display_name: "Ops",
    activity: day({ 20: 3, 23: 1 }),
    first_seen_at: "2026-01-01T00:00:00Z",
  });
  const desk = aChannel({
    mm_channel_id: "desk",
    display_name: "Desk",
    activity: day({ 23: 6 }),
    first_seen_at: "2026-01-01T01:00:00Z",
  });
  const unread = aChannel({ mm_channel_id: "unread", display_name: "Unread", pulled: false });

  function lanes(lastSeen: string | null, chosen: string[] = []) {
    const onToggle = vi.fn();
    const channels = [ops, desk, unread];
    render(
      <ActivityLanes
        channels={channels}
        hues={channelHues(channels)}
        chosen={chosen}
        onToggle={onToggle}
        lastSeen={lastSeen}
        now={NOW}
      />,
    );
    return onToggle;
  }

  it("gives each pulled channel a lane on one scale, and none to a channel Holly does not read", () => {
    const onToggle = lanes("2026-01-02T01:30:00Z", ["desk"]);
    expect(screen.getByRole("heading", { name: "Last 24 hours" })).toBeTruthy();
    expect(
      screen.getByText(
        "10 messages across 2 channels, the busiest hour 6. The line marks your last visit.",
      ),
    ).toBeTruthy();
    const opsLane = screen.getByRole("button", { name: "Ops, 4 messages in the last 24 hours" });
    const deskLane = screen.getByRole("button", { name: "Desk, 6 messages in the last 24 hours" });
    expect(opsLane.getAttribute("aria-pressed")).toBe("false");
    expect(deskLane.getAttribute("aria-pressed")).toBe("true");
    expect(screen.queryByRole("button", { name: /^Unread/ })).toBeNull();
    // 3 of the busiest 6: half the lane's height.
    expect(opsLane.querySelectorAll("rect")[20].getAttribute("height")).toBe("8");
    // The left edge is 05:00 the day before, so the last visit, 01:30, is 20.5 hours along.
    expect(opsLane.querySelector("line")?.getAttribute("x1")).toBe("205");
    fireEvent.click(opsLane);
    expect(onToggle).toHaveBeenCalledWith("ops");
  });

  it("draws no line for a first visit, or one longer ago than the lanes reach", () => {
    lanes(null);
    expect(document.querySelector("line")).toBeNull();
    expect(screen.queryByText(/The line marks/)).toBeNull();
  });

  it("draws nothing when no channel is pulled", () => {
    const { container } = render(
      <ActivityLanes
        channels={[unread]}
        hues={new Map()}
        chosen={[]}
        onToggle={vi.fn()}
        lastSeen={null}
        now={NOW}
      />,
    );
    expect(container.innerHTML).toBe("");
  });
});

describe("MessageList", () => {
  const channels = new Map([["ops", aChannel({ mm_channel_id: "ops", display_name: "Ops" })]]);
  const later = aChatMessage({
    id: "m3",
    channel_id: "ops",
    posted_at: "2026-01-02T03:30:00Z",
    message: "Burn confirmed; burn again at 05:00",
  });
  const earlier = aChatMessage({
    id: "m2",
    channel_id: "ops",
    posted_at: "2026-01-02T01:00:00Z",
    user_display_name: null,
    user_id: "poster-2",
  });
  const yesterday = aChatMessage({
    id: "m1",
    channel_id: "unknown",
    channel_name: null,
    posted_at: "2026-01-01T22:00:00Z",
  });

  it("heads each day, marks where the visit's new messages end, and marks the search", () => {
    const { container } = render(
      <MessageList
        messages={[later, earlier, yesterday]}
        channels={channels}
        showChannel
        search="burn"
        lastSeen="2026-01-02T02:00:00Z"
        now={NOW}
      />,
    );
    expect(screen.getAllByRole("heading").map((h) => h.textContent)).toEqual([
      "Today",
      "Yesterday",
    ]);
    // Newest first: the new messages open under one marker and end at the other.
    const markers = [...container.querySelectorAll(".comms-since")];
    expect(markers.map((m) => m.textContent)).toEqual(["New since your last visit", "Earlier"]);
    expect(markers[1].previousElementSibling?.textContent).toContain("Burn confirmed");
    const items = container.querySelectorAll(".comms-item");
    expect(items[0].className).toMatch(/^comms-item channel-hue-\d fresh$/);
    expect(items[1].className).toMatch(/^comms-item channel-hue-\d$/);
    expect([...container.querySelectorAll("mark")].map((m) => m.textContent)).toEqual([
      "Burn",
      "burn",
    ]);
    expect(items[0].textContent).toContain("#Ops");
    // The channel's dot sits before its name, in the same hue as the message's edge.
    const hue = items[0].className.match(/channel-hue-\d/)?.[0];
    expect(items[0].querySelector(".comms-channel .hue-dot")?.className).toBe(`hue-dot ${hue}`);
    expect(items[1].textContent).toContain("@poster-2");
    // A channel Holly does not know reads by its id.
    expect(items[2].textContent).toContain("#unknown");
    expect(screen.getByText("03:30").getAttribute("title")).toBe("2026-01-02 03:30:00 UTC");
  });

  it("reads oldest first as a conversation, naming no channel", () => {
    const { container } = render(
      <MessageList
        messages={[earlier, later]}
        channels={channels}
        showChannel={false}
        lastSeen="2026-01-02T02:00:00Z"
        now={NOW}
      />,
    );
    expect(container.querySelector(".comms-since")?.textContent).toBe("New since your last visit");
    expect(container.querySelector(".comms-channel")).toBeNull();
  });

  it("marks nothing new on a first visit, and names a channel by its stored name", () => {
    const named = aChatMessage({ channel_id: "elsewhere", channel_name: "elsewhere-chat" });
    const { container } = render(
      <MessageList messages={[named]} channels={channels} showChannel lastSeen={null} now={NOW} />,
    );
    expect(container.querySelector(".comms-since")).toBeNull();
    expect(container.querySelector(".fresh")).toBeNull();
    expect(container.textContent).toContain("#elsewhere-chat");
  });
});

describe("the feed's scope", () => {
  const followed = aChannel({ mm_channel_id: "a" });
  const unfollowed = aChannel({ mm_channel_id: "b", following: false });
  const closed = aChannel({ mm_channel_id: "c", status: "closed" });

  it("asks for every channel, the ones chosen, or the followed open ones by the follow list", () => {
    const all = [followed, unfollowed, closed];
    expect(scopeQuery({ kind: "all" }, all)).toEqual({});
    expect(scopeQuery({ kind: "chosen", ids: ["b", "c"] }, all)).toEqual({
      channel_id: ["b", "c"],
    });
    expect(scopeQuery({ kind: "following" }, all)).toEqual({ followed: true });
    expect(scopeQuery({ kind: "following" }, [unfollowed, closed])).toBeNull();
  });

  it("asks for everything before the first sweep, when Holly knows no channel", () => {
    expect(scopeQuery({ kind: "following" }, [])).toEqual({});
  });

  it("takes at most the 200 channels the server reads in one ask, and still takes one out", () => {
    const ids = Array.from({ length: MAX_PICKED }, (_, n) => `c${n}`);
    const full: FeedScope = { kind: "chosen", ids };
    expect(toggled(full, "one-more")).toBe(full);
    expect(toggled(full, "c0")).toEqual({ kind: "chosen", ids: ids.slice(1) });
  });

  it("adds a channel picked, takes one picked again out, and widens when none is left", () => {
    expect(toggled({ kind: "following" }, "a")).toEqual({ kind: "chosen", ids: ["a"] });
    expect(toggled({ kind: "all" }, "a")).toEqual({ kind: "chosen", ids: ["a"] });
    expect(toggled({ kind: "chosen", ids: ["a"] }, "b")).toEqual({
      kind: "chosen",
      ids: ["a", "b"],
    });
    expect(toggled({ kind: "chosen", ids: ["a", "b"] }, "a")).toEqual({
      kind: "chosen",
      ids: ["b"],
    });
    expect(toggled({ kind: "chosen", ids: ["a"] }, "a")).toEqual({ kind: "following" });
  });
});
