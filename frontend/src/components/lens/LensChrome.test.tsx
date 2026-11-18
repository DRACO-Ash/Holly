// @vitest-environment jsdom
import { act, fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { listEventTimers } from "../../api/event_timers";
import { getHandoverStory } from "../../api/handover";
import { aStory } from "../../test/handover";
import { held } from "../../test/held";
import type { HandoverStory } from "../../types";
import { aLens, lensTree, renderWithLens } from "../../test/lens";
import { FindButton, LensLayer, WatchStrip } from "./LensChrome";

vi.mock("../../api/handover");
vi.mock("../../api/event_timers");
vi.mock("../../api/mattermost");

const H = 3_600_000;
const at = (t: number) => new Date(t).toISOString();
const pinned = (sat: number, seen: number | null = null) => ({
  sat_no: sat,
  pinned: true,
  pinned_at: null,
  last_seen_at: seen === null ? null : at(seen),
});

beforeEach(() => {
  vi.mocked(listEventTimers).mockResolvedValue({ items: [] });
  const now = Date.now();
  vi.mocked(getHandoverStory)
    .mockReset()
    .mockImplementation(async (satNo) =>
      satNo === 90001
        ? aStory({
            notes: [{ id: "n", author_id: null, author: "a", text: "x", created_at: at(now - H) }],
            timers: [
              { id: "t", label: "Pass", target_time: at(now + 50 * 60_000), event_key: null },
            ],
          })
        : aStory({ sat_no: 90002, name: "TEST-SAT 2" }),
    );
});

describe("the lens in Holly's frame", () => {
  it("offers Find only while the lens is on", () => {
    const lens = aLens();
    const { unmount } = renderWithLens(<FindButton />, lens);
    fireEvent.click(screen.getByRole("button", { name: /Find/ }));
    expect(lens.openPalette).toHaveBeenCalled();
    unmount();
    renderWithLens(<FindButton />, aLens({ enabled: false }));
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("shows each pinned object with what is new and its next timer, or that it is quiet", async () => {
    const now = Date.now();
    const lens = aLens({
      watch: [pinned(90001), pinned(90002), { ...pinned(90003), pinned: false }],
      lastSeen: (sat) => (sat === 90001 ? now - 2 * H : now),
    });
    renderWithLens(<WatchStrip />, lens);
    const strip = screen.getByRole("region", { name: "Objects on watch" });
    expect(await screen.findByText(/1 new/)).toBeTruthy();
    expect(strip.textContent).toMatch(/⏱ 0:50/);
    expect(await screen.findByText(/quiet/)).toBeTruthy();
    expect(strip.textContent).not.toMatch(/90003/);
    fireEvent.click(screen.getByRole("button", { name: /90002 TEST-SAT 2/ }));
    expect(lens.open).toHaveBeenCalledWith(90002, expect.any(HTMLButtonElement));
    fireEvent.click(screen.getByRole("button", { name: "Stop watching 90001" }));
    expect(lens.toggleWatch).toHaveBeenCalledWith(90001);
  });

  it("shows nothing with nothing pinned, with the lens off, or for a story that fails", async () => {
    vi.mocked(getHandoverStory).mockRejectedValue(new Error("down"));
    const { unmount } = renderWithLens(<WatchStrip />, aLens());
    expect(screen.queryByRole("region")).toBeNull();
    unmount();
    renderWithLens(<WatchStrip />, aLens({ enabled: false, watch: [pinned(90001)] }));
    expect(screen.queryByRole("region")).toBeNull();
  });

  it("never shows a slow story under another object's lens", async () => {
    const slow = held<HandoverStory>();
    vi.mocked(getHandoverStory)
      .mockReset()
      .mockImplementationOnce(() => slow.promise)
      .mockResolvedValueOnce(aStory({ sat_no: 90002, name: "TEST-SAT 2" }));
    // 90001 has never been looked at; 90002 was, an hour ago: the lens must take each one's own.
    const lastSeen = (sat: number) => (sat === 90002 ? Date.now() - H : null);
    const { rerender } = renderWithLens(<LensLayer />, aLens({ satNo: 90001, lastSeen }));
    rerender(lensTree(<LensLayer />, aLens({ satNo: 90002, lastSeen })));
    expect(await screen.findByRole("heading", { name: /TEST-SAT 2/ })).toBeTruthy();
    expect(screen.getByText("Since you last looked")).toBeTruthy();
    await act(async () => slow.resolve(aStory({ name: "SLOW ONE", notes: [] })));
    expect(screen.queryByText(/SLOW ONE/)).toBeNull();
    expect(screen.getByRole("heading", { name: /TEST-SAT 2/ })).toBeTruthy();
  });

  it("holds the open lens or Find, and nothing with the lens off", async () => {
    const { unmount } = renderWithLens(<LensLayer />, aLens({ satNo: 90001 }));
    expect(await screen.findByRole("dialog", { name: /TEST-SAT 1/ })).toBeTruthy();
    unmount();
    const second = renderWithLens(<LensLayer />, aLens({ paletteOpen: true }));
    expect(screen.getByRole("dialog", { name: "Find anything" })).toBeTruthy();
    second.unmount();
    renderWithLens(<LensLayer />, aLens({ enabled: false, satNo: 90001, paletteOpen: true }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
