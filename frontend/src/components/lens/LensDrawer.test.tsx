// @vitest-environment jsdom
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createEventTimer } from "../../api/event_timers";
import { addHandoverNote, getHandoverStory } from "../../api/handover";
import { aManeuver, aStory } from "../../test/handover";
import { held } from "../../test/held";
import { aLens, lensTree, renderWithLens } from "../../test/lens";
import type { HandoverStory } from "../../types";
import LensDrawer from "./LensDrawer";

vi.mock("../../api/handover");
vi.mock("../../api/event_timers");

const NOW = Date.parse("2026-01-06T12:00:00Z");

const H = 3_600_000;
const at = (t: number) => new Date(t).toISOString();

function story(overrides: Partial<HandoverStory> = {}): HandoverStory {
  return aStory({
    window_start: at(NOW - 120 * H),
    generated_at: at(NOW),
    notices: [
      {
        id: "n-1",
        event_key: "EVT-1",
        notice: "7afc_19Oct-1726Z",
        event_class: "RPO / TEST-SAT 1 (90001) vs TEST-SAT 2 (90002) / LEO",
        kind: "RPO",
        status: "OPEN",
        udl_created_at: at(NOW - 30 * H),
        source: "TEST",
        udl_id: "UDL-1",
      },
    ],
    notes: [
      {
        id: "note-1",
        author_id: null,
        author: "test.lead",
        text: "Re-run the conjunction.",
        created_at: at(NOW - 5 * H),
      },
    ],
    timers: [
      { id: "t-0", label: "Past 90001", target_time: at(NOW - H), event_key: "EVT-1" },
      {
        id: "t-1",
        label: "Closest approach 90001 / 90002",
        target_time: at(NOW + 2 * H),
        event_key: "EVT-1",
      },
    ],
    suggestions: [
      {
        thread_id: "p-9",
        event_key: "EVT-1",
        channel_name: "Watch floor",
        reason: "names 90001",
        matching_posts: 1,
        first_post: {
          post_id: "p-9",
          posted_at: at(NOW - 2 * H),
          author: "test.bravo",
          message: "90001 again",
        },
      },
    ],
    ...overrides,
  });
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(NOW);
  vi.mocked(getHandoverStory).mockReset().mockResolvedValue(story());
  vi.mocked(addHandoverNote).mockReset();
  vi.mocked(createEventTimer).mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

async function opened(lens = aLens({ satNo: 90001 })) {
  renderWithLens(<LensDrawer satNo={90001} />, lens);
  await screen.findByText("Closest approach");
  return lens;
}

describe("the lens", () => {
  it("names the object, its partner, urgency and state, and counts down to its next timer", async () => {
    await opened();
    expect(screen.getByRole("dialog", { name: /TEST-SAT 1/ })).toBeTruthy();
    expect(screen.getByText("HIGH")).toBeTruthy();
    expect(screen.getByText("OPEN")).toBeTruthy();
    expect(screen.getByText("LEO")).toBeTruthy();
    const tags = document.querySelector(".lens-tags") as HTMLElement;
    expect(
      within(tags).getByRole("button", { name: "Open the lens on TEST-SAT 2 90002" }),
    ).toBeTruthy();
    expect(screen.getByText("2:00:00")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Close the lens" })).toBe(document.activeElement);
  });

  it("on a first look shows everything Holly holds, with no new marks", async () => {
    await opened();
    expect(screen.getByText("Everything Holly holds")).toBeTruthy();
    expect(screen.queryByText("NEW")).toBeNull();
  });

  it("marks what came in since the analyst last looked", async () => {
    await opened(aLens({ satNo: 90001, lastSeen: () => NOW - 3 * H }));
    expect(screen.getByText("Since you last looked")).toBeTruthy();
    expect(screen.getByText("1 new")).toBeTruthy();
    const fresh = screen.getAllByRole("list")[0];
    expect(within(fresh).getByText("NEW")).toBeTruthy();
    expect(within(fresh).getByText(/test.bravo in #Watch floor/)).toBeTruthy();
    expect(screen.getByText(/┆ you last looked/)).toBeTruthy();
  });

  it("says nothing is new when nothing is", async () => {
    await opened(aLens({ satNo: 90001, lastSeen: () => NOW - H }));
    expect(screen.getByText("Nothing new.")).toBeTruthy();
  });

  it("says when no timer is set, and when the story is cut", async () => {
    vi.mocked(getHandoverStory).mockResolvedValue(story({ timers: [], truncated: true }));
    renderWithLens(<LensDrawer satNo={90001} />, aLens({ satNo: 90001 }));
    expect(await screen.findByText("No timer set on this object.")).toBeTruthy();
    expect(screen.getByText(/part of it is shown/)).toBeTruthy();
  });

  it("says when the story cannot be loaded", async () => {
    vi.mocked(getHandoverStory).mockRejectedValue(new Error("down"));
    renderWithLens(<LensDrawer satNo={90001} />, aLens({ satNo: 90001 }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/could not load/);
  });

  it("pins and unpins through the lens state, and shows its refusal", async () => {
    const lens = await opened(
      aLens({
        satNo: 90001,
        watch: [{ sat_no: 90001, pinned: true, pinned_at: null, last_seen_at: null }],
        watchError: "Holly could not put that on watch.",
      }),
    );
    const pin = screen.getByRole("button", { name: "★ On watch" });
    expect(pin.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(pin);
    expect(lens.toggleWatch).toHaveBeenCalledWith(90001);
    expect(screen.getByRole("alert").textContent).toBe("Holly could not put that on watch.");
  });

  it("adds a note and reloads, then returns focus to the lens", async () => {
    vi.mocked(addHandoverNote).mockResolvedValue({
      id: "n",
      author_id: null,
      author: null,
      text: "x",
      created_at: at(NOW),
    });
    const lens = await opened();
    fireEvent.click(screen.getByRole("button", { name: "Add note" }));
    const box = screen.getByLabelText("Note on this object");
    fireEvent.change(box, { target: { value: "  Watch it.  " } });
    fireEvent.submit(box.closest("form") as HTMLFormElement);
    await waitFor(() => expect(addHandoverNote).toHaveBeenCalledWith(90001, "Watch it."));
    await waitFor(() => expect(lens.changed).toHaveBeenCalled());
    expect(screen.queryByLabelText("Note on this object")).toBeNull();
    expect(screen.getByRole("button", { name: "Close the lens" })).toBe(document.activeElement);
  });

  it("keeps the note and says so when it cannot be saved", async () => {
    vi.mocked(addHandoverNote).mockRejectedValue(new Error("down"));
    await opened();
    fireEvent.click(screen.getByRole("button", { name: "Add note" }));
    const box = screen.getByLabelText<HTMLTextAreaElement>("Note on this object");
    fireEvent.change(box, { target: { value: "Keep me." } });
    fireEvent.submit(box.closest("form") as HTMLFormElement);
    expect((await screen.findByRole("alert")).textContent).toMatch(/could not save/);
    expect(box.value).toBe("Keep me.");
  });

  it("sets a timer on the object's notice, from the form the palette asked for", async () => {
    vi.mocked(createEventTimer).mockResolvedValue({} as never);
    await opened(aLens({ satNo: 90001, form: "timer" }));
    fireEvent.change(screen.getByLabelText("In minutes"), { target: { value: "30" } });
    fireEvent.submit(screen.getByLabelText("Timer").closest("form") as HTMLFormElement);
    await waitFor(() => expect(createEventTimer).toHaveBeenCalled());
    const sent = vi.mocked(createEventTimer).mock.calls[0][0];
    expect(sent).toEqual({
      label: "Check TEST-SAT 1 (90001)",
      target_time: expect.any(String),
      event_key: "EVT-1",
      pre_alert_minutes: 15,
    });
    expect(Math.abs(Date.parse(sent.target_time) - (NOW + 30 * 60_000))).toBeLessThan(10_000);
  });

  it("says when the timer cannot be set", async () => {
    vi.mocked(createEventTimer).mockRejectedValue(new Error("down"));
    await opened();
    fireEvent.click(screen.getByRole("button", { name: "Set timer" }));
    fireEvent.submit(screen.getByLabelText("Timer").closest("form") as HTMLFormElement);
    expect((await screen.findByRole("alert")).textContent).toMatch(/could not save/);
  });

  it("opens the full story on the Handover page and closes", async () => {
    const lens = await opened();
    fireEvent.click(screen.getByRole("button", { name: "Open full story" }));
    expect(lens.close).toHaveBeenCalled();
    expect(screen.getByTestId("landed").textContent).toBe("/handover?sat=90001");
  });

  it("closes on a press outside it, but not inside it, nor while Find is over it", async () => {
    const lens = await opened();
    fireEvent.mouseDown(screen.getByRole("dialog"));
    expect(lens.close).not.toHaveBeenCalled();
    fireEvent.mouseDown(document.querySelector(".lens-scrim") as Element);
    expect(lens.close).toHaveBeenCalledTimes(1);
  });

  it("leaves a press outside to Find while Find is open over it", async () => {
    const lens = await opened(aLens({ satNo: 90001, paletteOpen: true }));
    fireEvent.mouseDown(document.querySelector(".lens-scrim") as Element);
    expect(lens.close).not.toHaveBeenCalled();
  });

  it("keeps what is new as it was when the lens opened, though the mark moves meanwhile", async () => {
    let seen = NOW - 3 * H;
    const lens = aLens({ satNo: 90001, lastSeen: () => seen });
    const { rerender } = renderWithLens(<LensDrawer satNo={90001} />, lens);
    await screen.findByText("Closest approach");
    seen = NOW;
    rerender(lensTree(<LensDrawer satNo={90001} />, { ...lens }));
    expect(screen.getByText("1 new")).toBeTruthy();
  });

  it("keeps the newer story when an older read answers late", async () => {
    const first = held<HandoverStory>();
    vi.mocked(getHandoverStory)
      .mockReset()
      .mockImplementationOnce(() => first.promise)
      .mockResolvedValueOnce(story({ name: "NEWER" }));
    const lens = aLens({ satNo: 90001 });
    const { rerender } = renderWithLens(<LensDrawer satNo={90001} />, lens);
    rerender(lensTree(<LensDrawer satNo={90001} />, { ...lens, version: 1 }));
    expect(await screen.findByRole("heading", { name: /NEWER/ })).toBeTruthy();
    await act(async () => first.resolve(story({ name: "OLDER" })));
    expect(screen.queryByRole("heading", { name: /OLDER/ })).toBeNull();
    expect(screen.getByRole("heading", { name: /NEWER/ })).toBeTruthy();
  });

  it("drops a late failure from an older read", async () => {
    const first = held<HandoverStory>();
    vi.mocked(getHandoverStory)
      .mockReset()
      .mockImplementationOnce(() => first.promise)
      .mockResolvedValueOnce(story());
    const lens = aLens({ satNo: 90001 });
    const { rerender } = renderWithLens(<LensDrawer satNo={90001} />, lens);
    rerender(lensTree(<LensDrawer satNo={90001} />, { ...lens, version: 1 }));
    await screen.findByText("Closest approach");
    await act(async () => first.reject(new Error("late")));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("draws each source on its own lane", async () => {
    vi.mocked(getHandoverStory).mockResolvedValue(
      story({
        maneuvers: [
          aManeuver({ id: "m-a", source: "PROVIDER-A", event_start_time: at(NOW - 40 * H) }),
          aManeuver({ id: "m-b", source: null, event_start_time: null }),
        ],
        threads: [
          {
            thread_id: "t",
            event_keys: ["EVT-1"],
            channel_name: "LEO cell",
            confirmed_at: at(NOW),
            truncated: false,
            posts: [{ post_id: "p", posted_at: at(NOW - 20 * H), author: null, message: "x" }],
          },
        ],
      }),
    );
    renderWithLens(<LensDrawer satNo={90001} />, aLens({ satNo: 90001 }));
    await screen.findByText("Closest approach");
    const strip = document.querySelector(".lens-strip") as HTMLElement;
    expect(strip.querySelectorAll(".lens-mark.tone-maneuver")).toHaveLength(1);
    expect(strip.querySelectorAll(".lens-mark.tone-post")).toHaveLength(1);
    expect(strip.querySelectorAll(".lens-mark.hollow")).toHaveLength(1);
    expect(strip.querySelectorAll(".lens-mark.tone-note")).toHaveLength(3);
  });

  it("refuses a timer with no whole number of minutes", async () => {
    await opened(aLens({ satNo: 90001, form: "timer" }));
    const set = within(document.querySelector(".lens-form") as HTMLElement).getByRole("button");
    fireEvent.change(screen.getByLabelText("In minutes"), { target: { value: "" } });
    expect((set as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("In minutes"), { target: { value: "0" } });
    expect((set as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("In minutes"), { target: { value: "5" } });
    expect((set as HTMLButtonElement).disabled).toBe(false);
  });

  it("will not set a timer without a label", async () => {
    await opened(aLens({ satNo: 90001, form: "timer" }));
    const set = within(document.querySelector(".lens-form") as HTMLElement).getByRole("button");
    expect(set).toHaveProperty("disabled", false);
    fireEvent.change(screen.getByLabelText("Timer"), { target: { value: "   " } });
    expect(set).toHaveProperty("disabled", true);
  });

  it("keeps Tab inside the lens", async () => {
    await opened();
    const dialog = screen.getByRole("dialog");
    const buttons = within(dialog).getAllByRole("button");
    const first = buttons[0];
    const last = buttons.at(-1) as HTMLElement;
    last.focus();
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);
    fireEvent.keyDown(dialog, { key: "a" });
    expect(document.activeElement).toBe(last);
  });

  it("counts down live", async () => {
    await opened();
    await act(async () => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByText("1:59:59")).toBeTruthy();
  });
});
