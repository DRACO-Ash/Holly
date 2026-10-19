// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { listMattermostMessages } from "../api/mattermost";
import { renderAt } from "../test/render";
import type { MattermostMessage, MattermostMessagePage } from "../types";
import MattermostPage from "./Mattermost";

vi.mock("../api/mattermost");

function aMessage(overrides: Partial<MattermostMessage> = {}): MattermostMessage {
  return {
    id: "mm-1",
    mm_post_id: "post-test-1",
    channel_id: "channel-test-1",
    channel_name: "test-channel",
    user_id: "user-test-1",
    user_display_name: "Synthetic poster",
    posted_at: "2026-01-02T03:04:05Z",
    message: "Synthetic message",
    post_type: null,
    created_at: "2026-01-02T03:05:00Z",
    updated_at: "2026-01-02T03:05:00Z",
    ...overrides,
  };
}

function pageOf(items: MattermostMessage[], total = items.length): MattermostMessagePage {
  return { items, total, limit: 100, offset: 0 };
}

function lastQuery() {
  return vi.mocked(listMattermostMessages).mock.lastCall?.[0];
}

// A promise the test settles itself, to hold the page while it waits.
function deferred<T>() {
  let resolve: (value: T) => void = () => undefined;
  const promise = new Promise<T>((settle) => {
    resolve = settle;
  });
  return { promise, resolve };
}

function pager(): string | null {
  return screen.getByText(/ total · page /).textContent;
}

function button(name: string): HTMLButtonElement {
  return screen.getByRole("button", { name }) as HTMLButtonElement;
}

function filterBy(value: string) {
  fireEvent.change(screen.getByLabelText("Channel ID (filter)"), { target: { value } });
  fireEvent.click(button("Apply"));
}

async function shown() {
  renderAt(<MattermostPage />, "/comms");
  await waitFor(() => expect(screen.queryByText("Loading...")).toBeNull());
}

beforeEach(() => {
  vi.mocked(listMattermostMessages)
    .mockReset()
    .mockResolvedValue(pageOf([aMessage()]));
});

describe("the comms page", () => {
  it("asks for the first 100 messages from every channel, and shows each one in UTC", async () => {
    vi.mocked(listMattermostMessages).mockResolvedValue(
      pageOf([
        aMessage(),
        aMessage({
          id: "mm-2",
          mm_post_id: "post-test-2",
          channel_name: "test-channel-two",
          user_display_name: "Second synthetic poster",
          posted_at: "2026-01-03T05:06:07+01:00",
          message: "Second synthetic message",
        }),
      ]),
    );
    await shown();
    expect(listMattermostMessages).toHaveBeenCalledTimes(1);
    expect(lastQuery()).toEqual({ channel_id: undefined, limit: 100, offset: 0 });
    const [first, other] = screen.getAllByRole("listitem");
    expect(within(first).getByText("#test-channel")).toBeTruthy();
    expect(within(first).getByText("@Synthetic poster")).toBeTruthy();
    expect(within(first).getByText("2026-01-02 03:04:05")).toBeTruthy();
    expect(within(first).getByText("Synthetic message")).toBeTruthy();
    expect(within(other).getByText("#test-channel-two")).toBeTruthy();
    expect(within(other).getByText("@Second synthetic poster")).toBeTruthy();
    expect(within(other).getByText("2026-01-03 04:06:07")).toBeTruthy();
    expect(within(other).getByText("Second synthetic message")).toBeTruthy();
    expect(pager()).toBe("2 total · page 1 of 1");
    expect(button("Previous").disabled).toBe(true);
    expect(button("Next").disabled).toBe(true);
    expect(screen.queryByText(/No messages yet/)).toBeNull();
  });

  it("names the channel and the author by ID when they have no display name", async () => {
    vi.mocked(listMattermostMessages).mockResolvedValue(
      pageOf([aMessage({ channel_name: null, user_display_name: null })]),
    );
    await shown();
    const item = screen.getByRole("listitem");
    expect(within(item).getByText("#channel-test-1")).toBeTruthy();
    expect(within(item).getByText("@user-test-1")).toBeTruthy();
  });

  it("says what to set up when there are no messages, but not while they load", async () => {
    const answer = deferred<MattermostMessagePage>();
    vi.mocked(listMattermostMessages).mockReturnValueOnce(answer.promise);
    renderAt(<MattermostPage />, "/comms");
    expect(screen.getByText("Loading...")).toBeTruthy();
    expect(screen.queryByText(/No messages yet/)).toBeNull();
    answer.resolve(pageOf([]));
    const empty = await screen.findByText(/No messages yet/);
    expect(empty.textContent).toBe(
      "No messages yet. Set MATTERMOST_CHANNEL_IDS in Holly's environment settings and make " +
        "sure the bot account is a member of those channels.",
    );
    expect(screen.queryByText("Loading...")).toBeNull();
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
    expect(pager()).toBe("0 total · page 1 of 1");
    expect(button("Previous").disabled).toBe(true);
    expect(button("Next").disabled).toBe(true);
  });

  it("shows the server's reason when messages cannot load, or a general one, until they do", async () => {
    vi.mocked(listMattermostMessages).mockRejectedValueOnce({
      response: { data: { detail: "No access" } },
    });
    await shown();
    expect(screen.getByText("No access")).toBeTruthy();
    vi.mocked(listMattermostMessages).mockRejectedValueOnce({});
    fireEvent.click(button("Refresh"));
    expect(await screen.findByText("Failed to load Mattermost messages.")).toBeTruthy();
    expect(screen.queryByText("No access")).toBeNull();
    fireEvent.click(button("Refresh"));
    expect(await screen.findByText("Synthetic message")).toBeTruthy();
    expect(screen.queryByText("Failed to load Mattermost messages.")).toBeNull();
  });

  it("filters by channel ID, trimmed, from the first page, and clears the filter", async () => {
    vi.mocked(listMattermostMessages).mockResolvedValue(pageOf([aMessage()], 250));
    await shown();
    fireEvent.click(button("Next"));
    await waitFor(() => expect(lastQuery()?.offset).toBe(100));
    expect(pager()).toBe("250 total · page 2 of 3");
    filterBy("  channel-test-2  ");
    await waitFor(() =>
      expect(lastQuery()).toEqual({ channel_id: "channel-test-2", limit: 100, offset: 0 }),
    );
    expect(pager()).toBe("250 total · page 1 of 3");
    filterBy("   ");
    await waitFor(() =>
      expect(lastQuery()).toEqual({ channel_id: undefined, limit: 100, offset: 0 }),
    );
    filterBy("channel-test-3");
    await waitFor(() => expect(lastQuery()?.channel_id).toBe("channel-test-3"));
    fireEvent.click(button("Clear"));
    await waitFor(() =>
      expect(lastQuery()).toEqual({ channel_id: undefined, limit: 100, offset: 0 }),
    );
    expect((screen.getByLabelText("Channel ID (filter)") as HTMLInputElement).value).toBe("");
    expect(listMattermostMessages).toHaveBeenCalledTimes(6);
  });

  it("asks again for the same page and channel on Refresh", async () => {
    vi.mocked(listMattermostMessages).mockResolvedValue(pageOf([aMessage()], 250));
    await shown();
    filterBy("channel-test-1");
    await waitFor(() => expect(lastQuery()?.channel_id).toBe("channel-test-1"));
    fireEvent.click(button("Next"));
    await waitFor(() => expect(lastQuery()?.offset).toBe(100));
    fireEvent.click(button("Refresh"));
    await waitFor(() => expect(listMattermostMessages).toHaveBeenCalledTimes(4));
    expect(lastQuery()).toEqual({ channel_id: "channel-test-1", limit: 100, offset: 100 });
  });

  it("pages through the messages 100 at a time, and stops at the last page", async () => {
    vi.mocked(listMattermostMessages).mockResolvedValue(pageOf([aMessage()], 300));
    await shown();
    expect(pager()).toBe("300 total · page 1 of 3");
    expect(button("Previous").disabled).toBe(true);
    fireEvent.click(button("Next"));
    await waitFor(() => expect(lastQuery()?.offset).toBe(100));
    expect(pager()).toBe("300 total · page 2 of 3");
    expect(button("Previous").disabled).toBe(false);
    fireEvent.click(button("Next"));
    await waitFor(() => expect(lastQuery()?.offset).toBe(200));
    expect(pager()).toBe("300 total · page 3 of 3");
    expect(button("Next").disabled).toBe(true);
    fireEvent.click(button("Previous"));
    await waitFor(() => expect(lastQuery()?.offset).toBe(100));
    expect(pager()).toBe("300 total · page 2 of 3");
    expect(listMattermostMessages).toHaveBeenCalledTimes(4);
  });
});
