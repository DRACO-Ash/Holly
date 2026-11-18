// @vitest-environment jsdom
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getActivity } from "../api/activity";
import { getHandoverObjects, getWatch, markSeen, setWatch } from "../api/handover";
import { held } from "../test/held";
import { aNotice, anObject } from "../test/lens";
import type { ActivityOverview } from "../types";
import { useLens } from "./lens";
import { LensProvider } from "./LensContext";

vi.mock("../api/handover");
vi.mock("../api/activity");

function Probe() {
  const lens = useLens();
  return (
    <div>
      <output data-testid="state">
        {JSON.stringify({
          enabled: lens.enabled,
          satNo: lens.satNo,
          form: lens.form,
          palette: lens.paletteOpen,
          objects: [...lens.objects.keys()],
          notsos: [...lens.noticeByNotso.keys()],
          watch: lens.watch.map((r) => [r.sat_no, r.pinned]),
          seen: lens.lastSeen(90001),
          error: lens.watchError,
        })}
      </output>
      <button type="button" onClick={(e) => lens.open(90001, e.currentTarget)}>
        open
      </button>
      <button type="button" onClick={() => lens.open(90002, null, "timer")}>
        timer
      </button>
      <button type="button" onClick={(e) => lens.open(90002, e.currentTarget)}>
        switch
      </button>
      <button type="button" onClick={lens.closePalette}>
        close find
      </button>
      <button type="button" onClick={lens.close}>
        close
      </button>
      <button type="button" onClick={() => lens.toggleWatch(90001)}>
        pin
      </button>
      <button type="button" onClick={lens.changed}>
        changed
      </button>
      <input aria-label="field" />
    </div>
  );
}

const state = () => JSON.parse(screen.getByTestId("state").textContent ?? "{}");

beforeEach(() => {
  vi.mocked(getHandoverObjects)
    .mockReset()
    .mockResolvedValue({
      window_hours: 120,
      window_start: "2026-01-01T00:00:00Z",
      generated_at: "2026-01-06T00:00:00Z",
      objects: [anObject()],
      truncated: false,
    });
  vi.mocked(getActivity)
    .mockReset()
    .mockResolvedValue({
      notices: [aNotice(), aNotice({ id: "n-2", notice: null })],
    } as ActivityOverview);
  vi.mocked(getWatch).mockReset().mockResolvedValue({ items: [], cap: 20 });
  vi.mocked(markSeen)
    .mockReset()
    .mockResolvedValue({ sat_no: 90001, pinned: false, pinned_at: null, last_seen_at: null });
  vi.mocked(setWatch).mockReset();
});

async function mounted(enabled = true) {
  render(
    <LensProvider enabled={enabled}>
      <Probe />
    </LensProvider>,
  );
  if (enabled) await waitFor(() => expect(state().objects).toEqual(["90001"]));
}

describe("the lens's state", () => {
  it("is off with no provider, and loads nothing when switched off", async () => {
    render(<Probe />);
    expect(state().enabled).toBe(false);
    fireEvent.click(screen.getByText("open"));
    expect(state().satNo).toBeNull();
    await mounted(false);
    expect(getHandoverObjects).not.toHaveBeenCalled();
  });

  it("loads the objects, the held NOTSO numbers and the analyst's watch list", async () => {
    vi.mocked(getWatch).mockResolvedValue({
      items: [
        { sat_no: 90001, pinned: true, pinned_at: null, last_seen_at: "2026-01-05T10:00:00Z" },
      ],
      cap: 20,
    });
    await mounted();
    await waitFor(() => expect(state().watch).toEqual([[90001, true]]));
    expect(state().notsos).toEqual(["7afc_19Oct-1726Z"]);
    expect(state().seen).toBe(Date.parse("2026-01-05T10:00:00Z"));
  });

  it("opens the lens, and on closing marks the look and returns focus", async () => {
    // The server's clock a minute ahead of this browser's: its answer is the later look, so it holds.
    const server = new Date(Date.now() + 60_000).toISOString();
    vi.mocked(markSeen).mockResolvedValue({
      sat_no: 90001,
      pinned: false,
      pinned_at: null,
      last_seen_at: server,
    });
    await mounted();
    const opener = screen.getByText("open");
    fireEvent.click(opener);
    expect(state().satNo).toBe(90001);
    fireEvent.click(screen.getByText("close"));
    expect(markSeen).toHaveBeenCalledWith(90001);
    expect(state().satNo).toBeNull();
    expect(document.activeElement).toBe(opener);
    await waitFor(() => expect(state().seen).toBe(Date.parse(server)));
  });

  it("opens with a form when asked", async () => {
    await mounted();
    fireEvent.click(screen.getByText("timer"));
    expect(state()).toMatchObject({ satNo: 90002, form: "timer" });
  });

  it("opens Find on Ctrl K or /, never from a field, and Esc closes Find, then the lens", async () => {
    await mounted();
    fireEvent.keyDown(screen.getByLabelText("field"), { key: "/" });
    expect(state().palette).toBe(false);
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    expect(state().palette).toBe(true);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(state().palette).toBe(false);
    fireEvent.keyDown(document.body, { key: "/" });
    expect(state().palette).toBe(true);
    fireEvent.click(screen.getByText("open"));
    expect(state()).toMatchObject({ palette: false, satNo: 90001 });
    fireEvent.keyDown(window, { key: "Escape" });
    expect(state().satNo).toBeNull();
    fireEvent.keyDown(window, { key: "Escape" });
    fireEvent.keyDown(window, { key: "K", metaKey: true });
    expect(state().palette).toBe(true);
  });

  it("pins and unpins, and says why a pin was refused", async () => {
    vi.mocked(setWatch).mockResolvedValueOnce({
      sat_no: 90001,
      pinned: true,
      pinned_at: null,
      last_seen_at: null,
    });
    await mounted();
    fireEvent.click(screen.getByText("pin"));
    expect(setWatch).toHaveBeenLastCalledWith(90001, true);
    await waitFor(() => expect(state().watch).toEqual([[90001, true]]));
    vi.mocked(setWatch).mockRejectedValueOnce(new Error("down"));
    fireEvent.click(screen.getByText("pin"));
    expect(setWatch).toHaveBeenLastCalledWith(90001, false);
    await waitFor(() => expect(state().error).toMatch(/could not take that off watch/));
  });

  it("names the cap only when the server refuses on it", async () => {
    vi.mocked(setWatch).mockRejectedValueOnce(
      Object.assign(new Error("full"), { isAxiosError: true, response: { status: 409 } }),
    );
    await mounted();
    fireEvent.click(screen.getByText("pin"));
    await waitFor(() => expect(state().error).toMatch(/at most 20 objects can be on watch/));
    vi.mocked(setWatch).mockRejectedValueOnce(
      Object.assign(new Error("broken"), { isAxiosError: true, response: { status: 500 } }),
    );
    fireEvent.click(screen.getByText("pin"));
    await waitFor(() =>
      expect(state().error).toBe("Holly could not put that on watch. Try again in a moment."),
    );
  });

  it("marks the object left behind when the lens moves to another, and returns focus home", async () => {
    await mounted();
    const home = screen.getByText("open");
    fireEvent.click(home);
    fireEvent.click(screen.getByText("switch"));
    expect(markSeen).toHaveBeenCalledWith(90001);
    expect(state().satNo).toBe(90002);
    fireEvent.click(screen.getByText("switch"));
    expect(markSeen).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(vi.mocked(markSeen).mock.calls).toEqual([[90001], [90002]]);
    expect(document.activeElement).toBe(home);
  });

  it("returns focus to where Find was opened when Find opens the lens", async () => {
    await mounted();
    const home = screen.getByText("open");
    home.focus();
    fireEvent.keyDown(home, { key: "k", ctrlKey: true });
    // Focus has moved into Find by the time a result is chosen.
    const inFind = screen.getByText("timer");
    inFind.focus();
    fireEvent.click(inFind);
    expect(state()).toMatchObject({ palette: false, satNo: 90002 });
    fireEvent.keyDown(window, { key: "Escape" });
    expect(document.activeElement).toBe(home);
  });

  it("with Find over the lens, Esc returns to the lens, then home", async () => {
    await mounted();
    const home = screen.getByText("open");
    fireEvent.click(home);
    const inLens = screen.getByText("changed");
    inLens.focus();
    fireEvent.keyDown(inLens, { key: "k", ctrlKey: true });
    // Asking for Find again from inside Find keeps where it was first opened.
    screen.getByText("pin").focus();
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    fireEvent.keyDown(window, { key: "Escape" });
    expect(state()).toMatchObject({ palette: false, satNo: 90001 });
    expect(document.activeElement).toBe(inLens);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(document.activeElement).toBe(home);
  });

  it("returns focus to where Find was opened when Find closes", async () => {
    await mounted();
    const home = screen.getByText("pin");
    home.focus();
    fireEvent.keyDown(home, { key: "/" });
    screen.getByText("open").focus();
    fireEvent.click(screen.getByText("close find"));
    expect(state().palette).toBe(false);
    expect(document.activeElement).toBe(home);
  });

  it("remembers a look at once, before the server answers, and keeps the pin", async () => {
    vi.mocked(getWatch).mockResolvedValue({
      items: [
        { sat_no: 90001, pinned: true, pinned_at: null, last_seen_at: "2026-01-05T10:00:00Z" },
      ],
      cap: 20,
    });
    vi.mocked(markSeen).mockReturnValue(new Promise(() => undefined));
    await mounted();
    await waitFor(() => expect(state().watch).toEqual([[90001, true]]));
    const before = Date.now();
    fireEvent.click(screen.getByText("open"));
    fireEvent.click(screen.getByText("close"));
    expect(state().seen).toBeGreaterThanOrEqual(before);
    expect(state().watch).toEqual([[90001, true]]);
  });

  it("holds a look until the server answers that look, whatever arrives before", async () => {
    type Row = { sat_no: number; pinned: boolean; pinned_at: null; last_seen_at: string };
    const firstAnswer = held<Row>();
    const secondAnswer = held<Row>();
    vi.mocked(getWatch).mockResolvedValue({
      items: [{ sat_no: 90001, pinned: true, pinned_at: null, last_seen_at: null }],
      cap: 20,
    });
    vi.mocked(markSeen)
      .mockReturnValueOnce(firstAnswer.promise)
      .mockReturnValueOnce(secondAnswer.promise);
    await mounted();
    await waitFor(() => expect(state().watch).toEqual([[90001, true]]));
    fireEvent.click(screen.getByText("open"));
    fireEvent.click(screen.getByText("close"));
    const before = Date.now();
    fireEvent.click(screen.getByText("open"));
    fireEvent.click(screen.getByText("close"));
    const local = state().seen;
    expect(local).toBeGreaterThanOrEqual(before);
    // The answer to the first look is older than the second: the second still stands.
    const old = "2026-01-05T10:00:00Z";
    await act(async () =>
      firstAnswer.resolve({ sat_no: 90001, pinned: true, pinned_at: null, last_seen_at: old }),
    );
    expect(state().seen).toBe(local);
    // A refresh from before any look was stored: the look still stands.
    await act(async () => {
      fireEvent.click(screen.getByText("changed"));
    });
    await waitFor(() => expect(getWatch).toHaveBeenCalledTimes(2));
    expect(state().seen).toBe(local);
    // The answer to the newest look replaces it, even when the server's clock is behind this one.
    const server = new Date(before - 5 * 60_000).toISOString();
    await act(async () =>
      secondAnswer.resolve({ sat_no: 90001, pinned: true, pinned_at: null, last_seen_at: server }),
    );
    expect(state().seen).toBe(Date.parse(server));
  });

  it("keeps the look for the session when the server cannot record it", async () => {
    vi.mocked(markSeen).mockRejectedValue(new Error("down"));
    await mounted();
    const before = Date.now();
    fireEvent.click(screen.getByText("open"));
    fireEvent.click(screen.getByText("close"));
    await act(async () => undefined);
    expect(state().seen).toBeGreaterThanOrEqual(before);
  });

  it("remembers a first look at an object not on watch", async () => {
    vi.mocked(markSeen).mockReturnValue(new Promise(() => undefined));
    await mounted();
    fireEvent.click(screen.getByText("open"));
    fireEvent.click(screen.getByText("close"));
    expect(state().watch).toEqual([]);
    expect(state().seen).not.toBeNull();
  });

  it("marks nothing when closed with no lens open", async () => {
    await mounted();
    fireEvent.click(screen.getByText("close"));
    expect(markSeen).not.toHaveBeenCalled();
  });

  it("takes a watch list that answers after it is gone without failing", async () => {
    const late = held<{ items: []; cap: number }>();
    vi.mocked(getWatch).mockReturnValue(late.promise);
    const { unmount } = render(
      <LensProvider enabled>
        <Probe />
      </LensProvider>,
    );
    unmount();
    await act(async () => late.resolve({ items: [], cap: 20 }));
    expect(getWatch).toHaveBeenCalledTimes(1);
  });

  it("reloads when told something changed, and keeps working when the loads fail", async () => {
    await mounted();
    vi.mocked(getHandoverObjects).mockRejectedValue(new Error("down"));
    vi.mocked(getActivity).mockRejectedValue(new Error("down"));
    vi.mocked(getWatch).mockRejectedValue(new Error("down"));
    await act(async () => {
      fireEvent.click(screen.getByText("changed"));
    });
    expect(getHandoverObjects).toHaveBeenCalledTimes(2);
    expect(state().objects).toEqual(["90001"]);
  });
});
