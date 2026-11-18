// @vitest-environment jsdom
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { listEventTimers } from "../../api/event_timers";
import { listMattermostMessages } from "../../api/mattermost";
import { aLens, renderWithLens } from "../../test/lens";
import type { EventTimer, MattermostMessage } from "../../types";
import Palette from "./Palette";

vi.mock("../../api/event_timers");
vi.mock("../../api/mattermost");

const SOON = new Date(Date.now() + 90 * 60_000).toISOString();

function aTimer(overrides: Partial<EventTimer> = {}): EventTimer {
  return {
    id: "t-1",
    event_key: null,
    label: "Closest approach 90001 / 90002",
    target_time: SOON,
    pre_alert_minutes: 15,
    recurrence: "none",
    pre_alert_fired_at: null,
    dismissed_at: null,
    dismissed_by: null,
    created_by: null,
    shift_date: null,
    created_at: SOON,
    updated_at: SOON,
    ...overrides,
  };
}

function aMessage(overrides: Partial<MattermostMessage> = {}): MattermostMessage {
  return {
    id: "m-1",
    mm_post_id: "p-1",
    channel_id: "c-1",
    channel_name: "Watch floor",
    user_id: "u-1",
    user_display_name: "test.bravo",
    posted_at: "2026-01-05T10:00:00Z",
    message: "Checking 90002 now",
    post_type: null,
    created_at: "2026-01-05T10:00:00Z",
    updated_at: "2026-01-05T10:00:00Z",
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(listEventTimers)
    .mockReset()
    .mockResolvedValue({ items: [aTimer()] });
  vi.mocked(listMattermostMessages)
    .mockReset()
    .mockResolvedValue({ items: [], total: 0, limit: 4, offset: 0 });
});

const box = () => screen.getByRole("searchbox");
const typeIn = (text: string) => fireEvent.change(box(), { target: { value: text } });
const options = () =>
  within(screen.getByRole("list", { name: "Results" })).queryAllByRole("button");

describe("Find", () => {
  it("opens focused on the box and offers the pages first", () => {
    renderWithLens(<Palette />);
    expect(box()).toBe(document.activeElement);
    expect(options()[0].textContent).toMatch(/Dashboard/);
  });

  it("puts the matching objects first with why they matter, then notices and a timer action", async () => {
    renderWithLens(<Palette />);
    typeIn("9000");
    await waitFor(() => expect(options()[0].textContent).toMatch(/timer in 1 h 30 min/));
    const first = options()[0].textContent;
    expect(first).toMatch(/TEST-SAT 1 #90001/);
    expect(first).toMatch(/1 open NOTSO \(HIGH\)/);
    expect(first).toMatch(/2 provider records/);
    expect(options()[1].textContent).toMatch(/TEST-SAT 2 #90002.*0 provider records/);
    expect(options()[0].getAttribute("aria-current")).toBe("true");
    expect(options().at(-1)?.textContent).toMatch(/Set a timer on TEST-SAT 1 #90001/);
  });

  it("gives an object only the timers that name its number whole", async () => {
    vi.mocked(listEventTimers).mockResolvedValue({
      items: [
        aTimer({ label: "Pass 900010" }),
        aTimer({ id: "t-2", label: "Old 90001", target_time: "2020-01-01T00:00:00Z" }),
      ],
    });
    renderWithLens(<Palette />);
    typeIn("90001");
    await waitFor(() => expect(listEventTimers).toHaveBeenCalled());
    await act(async () => undefined);
    expect(options()[0].textContent).not.toMatch(/timer in/);
  });

  it("opens the lens on Enter and pins on Shift and Enter, staying open", () => {
    const lens = aLens();
    renderWithLens(<Palette />, lens);
    typeIn("90002");
    fireEvent.keyDown(box(), { key: "Enter", shiftKey: true });
    expect(lens.toggleWatch).toHaveBeenCalledWith(90002);
    expect(lens.closePalette).not.toHaveBeenCalled();
    fireEvent.keyDown(box(), { key: "Enter" });
    expect(lens.closePalette).toHaveBeenCalled();
    expect(lens.open).toHaveBeenCalledWith(90002, null);
  });

  it("moves with the arrow keys, within the list", () => {
    renderWithLens(<Palette />);
    fireEvent.keyDown(box(), { key: "ArrowUp" });
    expect(options()[0].getAttribute("aria-current")).toBe("true");
    fireEvent.keyDown(box(), { key: "ArrowDown" });
    expect(options()[1].getAttribute("aria-current")).toBe("true");
    expect(screen.getByText(/results\. Enter opens Notifications\./)).toBeTruthy();
    for (let i = 0; i < 20; i++) fireEvent.keyDown(box(), { key: "ArrowDown" });
    expect(options().at(-1)?.getAttribute("aria-current")).toBe("true");
    fireEvent.keyDown(box(), { key: "x" });
  });

  it("selects only with a moving pointer, and runs what is clicked", () => {
    const lens = aLens();
    renderWithLens(<Palette />, lens);
    fireEvent.mouseMove(options()[3]);
    expect(options()[3].getAttribute("aria-current")).toBe("true");
    fireEvent.mouseMove(options()[3]);
    fireEvent.click(options()[3]);
    expect(lens.closePalette).toHaveBeenCalled();
    expect(screen.getByTestId("landed").textContent).toBe("/comms");
  });

  it("finds a notice by NOTSO number and opens it", () => {
    renderWithLens(<Palette />);
    typeIn("7afc");
    fireEvent.click(screen.getByRole("button", { name: /7afc_19Oct-1726Z/ }));
    expect(screen.getByTestId("landed").textContent).toBe("/notifications/n-1");
  });

  it("searches followed chat from 3 characters and opens the lens on the object a message names", async () => {
    vi.mocked(listMattermostMessages).mockResolvedValue({
      items: [aMessage(), aMessage({ id: "m-2", message: "Nothing named", channel_name: null })],
      total: 2,
      limit: 4,
      offset: 0,
    });
    const lens = aLens();
    renderWithLens(<Palette />, lens);
    typeIn("ch");
    await act(async () => {
      await new Promise((r) => setTimeout(r, 250));
    });
    expect(listMattermostMessages).not.toHaveBeenCalled();
    typeIn("checking");
    const hit = await screen.findByRole("button", { name: /Checking 90002 now/ });
    expect(listMattermostMessages).toHaveBeenCalledWith({
      q: "checking",
      followed: true,
      limit: 4,
    });
    fireEvent.click(hit);
    expect(lens.open).toHaveBeenCalledWith(90002, null);
    fireEvent.click(screen.getByRole("button", { name: /Nothing named/ }));
    expect(screen.getByTestId("landed").textContent).toBe("/comms");
  });

  it("says when nothing matches, and keeps working when its lookups fail", async () => {
    vi.mocked(listEventTimers).mockRejectedValue(new Error("down"));
    vi.mocked(listMattermostMessages).mockRejectedValue(new Error("down"));
    renderWithLens(<Palette />);
    typeIn("zzzz");
    expect(await screen.findByText("Nothing in the window matches.")).toBeTruthy();
    await act(async () => {
      await new Promise((r) => setTimeout(r, 250));
    });
    expect(options()).toHaveLength(0);
  });

  it.each(["", "zzzz"])("keeps Tab inside Find, with or without results (%j)", (query) => {
    renderWithLens(<Palette />);
    typeIn(query);
    expect(options().length > 0).toBe(query === "");
    const dialog = screen.getByRole("dialog");
    for (const shiftKey of [false, true]) {
      box().focus();
      expect(fireEvent.keyDown(box(), { key: "Tab", shiftKey })).toBe(false);
      expect(document.activeElement).toBe(box());
    }
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it("closes from the backdrop, and runs the timer action through the lens", () => {
    const lens = aLens();
    renderWithLens(<Palette />, lens);
    typeIn("90001");
    fireEvent.click(screen.getByRole("button", { name: /Set a timer/ }));
    expect(lens.open).toHaveBeenCalledWith(90001, null, "timer");
    fireEvent.mouseDown(document.querySelector(".lens-scrim") as Element);
    expect(lens.closePalette).toHaveBeenCalledTimes(2);
  });
});
