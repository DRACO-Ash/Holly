// @vitest-environment jsdom
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getActivity } from "../api/activity";
import { getHandoverObjects, getWatch, markSeen, setWatch } from "../api/handover";
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
    vi.mocked(markSeen).mockResolvedValue({
      sat_no: 90001,
      pinned: false,
      pinned_at: null,
      last_seen_at: "2026-01-06T10:00:00Z",
    });
    await mounted();
    const opener = screen.getByText("open");
    fireEvent.click(opener);
    expect(state().satNo).toBe(90001);
    fireEvent.click(screen.getByText("close"));
    expect(markSeen).toHaveBeenCalledWith(90001);
    expect(state().satNo).toBeNull();
    expect(document.activeElement).toBe(opener);
    await waitFor(() => expect(state().seen).toBe(Date.parse("2026-01-06T10:00:00Z")));
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

  it("names the cap when a pin is refused", async () => {
    vi.mocked(setWatch).mockRejectedValue(new Error("full"));
    await mounted();
    fireEvent.click(screen.getByText("pin"));
    await waitFor(() => expect(state().error).toMatch(/At most 20 objects/));
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
