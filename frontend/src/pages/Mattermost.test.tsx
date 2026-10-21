// @vitest-environment jsdom
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getCurrentUser } from "../api/auth";
import { ACCESS_TOKEN_KEY } from "../api/client";
import {
  listChannels,
  listMattermostMessages,
  reviewAllChannels,
  sweepNow,
  updateChannel,
} from "../api/mattermost";
import { AuthProvider, useAuth } from "../context/AuthContext";
import { aChannel, aChatMessage, aSweep, aUser } from "../test/fixtures";
import { renderAt } from "../test/render";
import type { MattermostChannel, MattermostChannels } from "../types";
import MattermostPage, { CHANNELS_POLL_MS } from "./Mattermost";

vi.mock("../api/auth");
vi.mock("../api/mattermost");

const ops = aChannel({ mm_channel_id: "ops", display_name: "Ops", new_since: 3 });
const fresh = aChannel({
  mm_channel_id: "fresh",
  display_name: "Fresh",
  is_new: true,
  first_seen_at: "2026-01-02T00:00:00Z",
});
const shut = aChannel({
  mm_channel_id: "shut",
  display_name: "Shut",
  status: "closed",
  pulled: false,
  first_seen_at: "2026-01-03T00:00:00Z",
});

function channelsOf(channels: MattermostChannel[], sweep = aSweep()): MattermostChannels {
  return { channels, sweep };
}

const quietSweep = {
  ok: true,
  problem: null,
  found: 3,
  new: 0,
  closed: 0,
  reopened: 0,
  lost: 0,
  channels_polled: 2,
  channels_failed: 0,
  inserted: 5,
};

function shown() {
  localStorage.setItem(ACCESS_TOKEN_KEY, "a-1");
  renderAt(
    <AuthProvider>
      <MattermostPage />
    </AuthProvider>,
    "/mattermost",
  );
}

function latest<T>(items: readonly T[]): T | undefined {
  return items[items.length - 1];
}

function messageQueries() {
  return vi.mocked(listMattermostMessages).mock.calls.map(([query]) => query);
}

function nameButton(name: string) {
  const board = screen.getByRole("complementary", { name: "Channels" });
  return within(board).getByRole("button", { name });
}

async function ready() {
  await screen.findByRole("complementary", { name: "Channels" });
  // The user is known, and the channels were asked for since the last visit.
  await waitFor(() => expect(localStorage.getItem("holly.comms.seen.user-7")).not.toBeNull());
}

beforeEach(() => {
  localStorage.clear();
  vi.mocked(getCurrentUser)
    .mockReset()
    .mockResolvedValue(aUser({ id: "user-7" }));
  vi.mocked(listChannels)
    .mockReset()
    .mockResolvedValue(channelsOf([ops, fresh, shut]));
  vi.mocked(listMattermostMessages)
    .mockReset()
    .mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
  vi.mocked(updateChannel).mockReset();
  vi.mocked(reviewAllChannels).mockReset().mockResolvedValue(1);
  vi.mocked(sweepNow).mockReset().mockResolvedValue(quietSweep);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("the Comms console", () => {
  it("shows the switchboard beside the feed of every followed channel, under their lanes", async () => {
    shown();
    await ready();
    expect(screen.getByRole("region", { name: "Feed" })).toBeTruthy();
    expect(screen.getByText(/Channels swept/)).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Last 24 hours" })).toBeTruthy();
    // The followed channels go by the server's follow list, never as a list of ids.
    await waitFor(() => expect(messageQueries()[0]).toMatchObject({ followed: true }));
    expect(messageQueries()[0]?.channel_id).toBeUndefined();
  });

  it("asks how much is new since this user's last visit, and records this one", async () => {
    localStorage.setItem("holly.comms.seen.user-7", "2026-01-02T02:00:00.000Z");
    vi.mocked(listMattermostMessages).mockResolvedValue({
      items: [aChatMessage({ channel_id: "ops", posted_at: "2026-01-02T03:00:00Z" })],
      total: 1,
      limit: 50,
      offset: 0,
    });
    shown();
    await waitFor(() =>
      expect(latest(vi.mocked(listChannels).mock.calls)?.[0]).toBe("2026-01-02T02:00:00.000Z"),
    );
    expect(await screen.findByText("New since your last visit")).toBeTruthy();
    expect(within(nameButton("Ops").closest("li") as HTMLElement).getByText("3 new")).toBeTruthy();
    await waitFor(() =>
      expect(localStorage.getItem("holly.comms.seen.user-7")).not.toBe("2026-01-02T02:00:00.000Z"),
    );
  });

  it("asks for the channels once when the user is already known", async () => {
    // As after a move within the dashboard: the page mounts once the user is known.
    function WhenKnown() {
      const { user } = useAuth();
      return user ? <MattermostPage /> : null;
    }
    localStorage.setItem("holly.comms.seen.user-7", "2026-01-02T02:00:00.000Z");
    localStorage.setItem(ACCESS_TOKEN_KEY, "a-1");
    renderAt(
      <AuthProvider>
        <WhenKnown />
      </AuthProvider>,
      "/mattermost",
    );
    await screen.findByRole("complementary", { name: "Channels" });
    expect(vi.mocked(listChannels).mock.calls).toEqual([["2026-01-02T02:00:00.000Z"]]);
  });

  it("says it is loading, then why the channels could not be read", async () => {
    vi.mocked(listChannels).mockRejectedValue({});
    shown();
    expect(screen.getByText("Loading channels...")).toBeTruthy();
    expect((await screen.findByRole("alert")).textContent).toBe("Failed to load the channels.");
  });

  it("switches to one channel as a conversation, the first open one, and remembers it", async () => {
    shown();
    await ready();
    const layout = screen.getByRole("group", { name: "Layout" });
    fireEvent.click(within(layout).getByRole("button", { name: "Channels" }));
    expect(await screen.findByRole("heading", { name: "#Ops" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Conversation" })).toBeTruthy();
    expect(localStorage.getItem("holly.comms.view")).toBe("channels");
    expect(nameButton("Ops").getAttribute("aria-current")).toBe("true");
    // The conversation's own switch follows for everyone too.
    vi.mocked(updateChannel).mockResolvedValueOnce({ ...ops, following: false });
    const stage = screen.getByRole("region", { name: "Conversation" });
    fireEvent.click(within(stage).getByRole("switch", { name: "Follow Ops" }));
    expect(updateChannel).toHaveBeenCalledWith("ops", { following: false });
    expect(await screen.findByText(/No longer following #Ops, for everyone/)).toBeTruthy();
    fireEvent.click(nameButton("Shut"));
    expect(await screen.findByRole("heading", { name: "#Shut" })).toBeTruthy();
    expect(nameButton("Shut").getAttribute("aria-current")).toBe("true");
    fireEvent.click(within(layout).getByRole("button", { name: "Feed" }));
    expect(localStorage.getItem("holly.comms.view")).toBe("feed");
    // The conversation's channel is not a filter on the feed.
    expect(nameButton("Shut").getAttribute("aria-pressed")).toBe("false");
    expect(nameButton("Shut").getAttribute("aria-current")).toBeNull();
  });

  it("opens in the layout this browser last chose, and says when there is no channel", async () => {
    localStorage.setItem("holly.comms.view", "channels");
    vi.mocked(listChannels).mockResolvedValue(channelsOf([]));
    shown();
    expect(await screen.findByText(/No channel yet/)).toBeTruthy();
  });

  it("narrows the feed to the channels picked on the switchboard, and back again", async () => {
    shown();
    await ready();
    fireEvent.click(nameButton("Ops"));
    await waitFor(() => expect(latest(messageQueries())?.channel_id).toEqual(["ops"]));
    expect(nameButton("Ops").getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Stop showing #Ops" })).toBeTruthy();
    fireEvent.click(nameButton("Fresh"));
    await waitFor(() => expect(latest(messageQueries())?.channel_id).toEqual(["ops", "fresh"]));
    fireEvent.click(nameButton("Ops"));
    await waitFor(() => expect(latest(messageQueries())?.channel_id).toEqual(["fresh"]));
    expect(nameButton("Ops").getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(nameButton("Fresh"));
    // None picked: the followed channels again.
    await waitFor(() => expect(screen.queryByText("Showing only")).toBeNull());
    expect(latest(messageQueries())).toMatchObject({ followed: true });
    fireEvent.click(nameButton("Shut"));
    fireEvent.click(screen.getByRole("button", { name: "All channels" }));
    await waitFor(() => expect(latest(messageQueries())?.channel_id).toBeUndefined());
    expect(nameButton("Shut").getAttribute("aria-pressed")).toBe("false");
  });

  it("brings the stage into view after a pick on a narrow screen, at once if asked for less motion", async () => {
    const scrolls: unknown[] = [];
    window.HTMLElement.prototype.scrollIntoView = function (options?: unknown) {
      scrolls.push(options);
    };
    vi.stubGlobal(
      "matchMedia",
      vi.fn((query: string) => ({ matches: query !== "(min-width: 9999px)" })),
    );
    shown();
    await ready();
    fireEvent.click(nameButton("Ops"));
    expect(scrolls).toEqual([{ behavior: "auto", block: "start" }]);
    vi.stubGlobal(
      "matchMedia",
      vi.fn((query: string) => ({ matches: !query.includes("reduce") })),
    );
    fireEvent.click(nameButton("Fresh"));
    expect(scrolls[1]).toEqual({ behavior: "smooth", block: "start" });
    vi.stubGlobal(
      "matchMedia",
      vi.fn(() => ({ matches: false })),
    );
    fireEvent.click(nameButton("Shut"));
    expect(scrolls).toHaveLength(2);
  });

  it("follows and unfollows a channel for everyone, says so, and can undo it", async () => {
    vi.mocked(updateChannel).mockResolvedValueOnce({ ...ops, following: false, new_since: null });
    shown();
    await ready();
    fireEvent.click(screen.getByRole("switch", { name: "Follow Ops" }));
    expect(updateChannel).toHaveBeenCalledWith("ops", { following: false });
    expect(
      await screen.findByText(
        "No longer following #Ops, for everyone. Holly keeps what it pulled.",
      ),
    ).toBeTruthy();
    expect(screen.getByRole("switch", { name: "Follow Ops" }).getAttribute("aria-checked")).toBe(
      "false",
    );
    // The change answered with the channel alone: its count since the last visit stays.
    expect(within(nameButton("Ops").closest("li") as HTMLElement).getByText("3 new")).toBeTruthy();
    vi.mocked(updateChannel).mockResolvedValueOnce({ ...ops, following: true });
    fireEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(updateChannel).toHaveBeenLastCalledWith("ops", { following: true });
    expect(
      await screen.findByText(
        "Following #Ops for everyone. Holly pulls its messages from the next cycle.",
      ),
    ).toBeTruthy();
  });

  it("says why a follow change was refused, and offers no undo", async () => {
    vi.mocked(updateChannel).mockRejectedValue({
      response: {
        status: 409,
        data: { detail: "This channel is closed: Holly pulls nothing more from it." },
      },
    });
    shown();
    await ready();
    fireEvent.click(screen.getByRole("switch", { name: "Follow Ops" }));
    expect((await screen.findByRole("alert")).textContent).toBe(
      "This channel is closed: Holly pulls nothing more from it.",
    );
    expect(screen.queryByRole("button", { name: "Undo" })).toBeNull();
  });

  it("names the new channels it found and followed, until someone marks them reviewed", async () => {
    shown();
    await ready();
    expect(
      screen.getByText(/A new channel was found and followed: #Fresh\. Switch off/),
    ).toBeTruthy();
    vi.mocked(listChannels).mockResolvedValue(channelsOf([ops, { ...fresh, is_new: false }, shut]));
    fireEvent.click(screen.getByRole("button", { name: "Mark reviewed" }));
    expect(await screen.findByText("Marked 1 channel reviewed.")).toBeTruthy();
    expect(screen.queryByText(/found and followed/)).toBeNull();
    // The banner went: the keyboard is left on the news, not at the top of the page.
    expect(document.activeElement?.textContent).toBe("Marked 1 channel reviewed.");
  });

  it("counts several new channels, waits while marking, and says when marking failed", async () => {
    vi.mocked(listChannels).mockResolvedValue(channelsOf([fresh, { ...ops, is_new: true }]));
    let settle: (value: number) => void = () => undefined;
    vi.mocked(reviewAllChannels).mockReturnValueOnce(
      new Promise((resolve) => {
        settle = resolve;
      }),
    );
    shown();
    await ready();
    expect(screen.getByText(/2 new channels were found and followed/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Mark reviewed" }));
    const busy = await screen.findByRole("button", { name: "Marking..." });
    expect(busy.getAttribute("aria-disabled")).toBe("true");
    fireEvent.click(busy);
    expect(reviewAllChannels).toHaveBeenCalledTimes(1);
    await act(async () => settle(2));
    vi.mocked(reviewAllChannels).mockRejectedValueOnce({});
    fireEvent.click(await screen.findByRole("button", { name: "Mark reviewed" }));
    expect((await screen.findByRole("alert")).textContent).toBe(
      "The channels could not be marked reviewed.",
    );
  });

  it("sweeps on demand and says what it found", async () => {
    shown();
    await ready();
    const before = vi.mocked(listChannels).mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "Find channels now" }));
    expect(
      await screen.findByText("Found 3 channels. Pulled 5 new messages from 2 channels."),
    ).toBeTruthy();
    expect(sweepNow).toHaveBeenCalled();
    expect(vi.mocked(listChannels).mock.calls.length).toBe(before + 1);
  });

  it("shows a failed sweep once, in the strip and the warning under it", async () => {
    shown();
    await ready();
    vi.mocked(sweepNow).mockResolvedValueOnce({ ...quietSweep, ok: false, problem: "Down." });
    vi.mocked(listChannels).mockResolvedValue(
      channelsOf([ops], aSweep({ ok: false, problem: "Down." })),
    );
    fireEvent.click(screen.getByRole("button", { name: "Find channels now" }));
    const alerts = await screen.findAllByRole("alert");
    expect(alerts.map((a) => a.textContent)).toEqual([
      "The last channel sweep failed: Down. Holly keeps pulling the channels it already knows.",
    ]);
    expect(screen.getByText(/The last channel sweep, .*, failed\./)).toBeTruthy();
    expect(screen.queryByText(/^Found /)).toBeNull();
  });

  it("says Holly pulls nothing while Mattermost is not configured", async () => {
    const problem = "Mattermost is not configured (MATTERMOST_URL / MATTERMOST_BOT_TOKEN).";
    vi.mocked(listChannels).mockResolvedValue(
      channelsOf([], aSweep({ configured: false, ok: false, problem })),
    );
    shown();
    expect((await screen.findByRole("alert")).textContent).toBe(
      `The last channel sweep failed: ${problem} Holly pulls nothing until both are set.`,
    );
  });

  it("clears a failed read of the channels once a later one succeeds", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(listChannels).mockRejectedValueOnce({});
    shown();
    expect((await screen.findByRole("alert")).textContent).toBe("Failed to load the channels.");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(CHANNELS_POLL_MS);
    });
    await screen.findByRole("complementary", { name: "Channels" });
    expect(screen.queryByText("Failed to load the channels.")).toBeNull();
  });

  it("says why a sweep could not run", async () => {
    vi.mocked(sweepNow).mockRejectedValueOnce({
      response: { status: 429, data: { detail: "Too many requests." } },
    });
    shown();
    await ready();
    fireEvent.click(screen.getByRole("button", { name: "Find channels now" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Too many requests.");
  });

  it("keeps the latest read of the channels when an earlier one answers late", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let slow: (value: MattermostChannels) => void = () => undefined;
    vi.mocked(listChannels)
      .mockImplementationOnce(() => new Promise((resolve) => (slow = resolve)))
      .mockResolvedValue(channelsOf([ops]));
    shown();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(CHANNELS_POLL_MS);
    });
    expect(await screen.findByRole("button", { name: "Ops" })).toBeTruthy();
    await act(async () => {
      slow(channelsOf([shut]));
      await Promise.resolve();
    });
    expect(screen.queryByRole("button", { name: "Shut" })).toBeNull();
    expect(screen.getByRole("button", { name: "Ops" })).toBeTruthy();
  });

  it("reads the channels again every minute", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    shown();
    await ready();
    const before = vi.mocked(listChannels).mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(CHANNELS_POLL_MS);
    });
    expect(vi.mocked(listChannels).mock.calls.length).toBe(before + 1);
  });
});
