// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useEventTimers } from "../context/EventTimersContext";
import { aTimer } from "../test/fixtures";
import type { EventTimer } from "../types";
import EventTimersPanel from "./EventTimersPanel";

vi.mock("../context/EventTimersContext", () => ({ useEventTimers: vi.fn() }));

const createTimer = vi.fn();
const dismissTimer = vi.fn();
const deleteTimer = vi.fn();

interface Lists {
  firing?: EventTimer[];
  preAlerting?: EventTimer[];
  upcoming?: EventTimer[];
  dismissed?: EventTimer[];
  error?: string | null;
}

function panel(lists: Lists = {}) {
  vi.mocked(useEventTimers).mockReturnValue({
    firing: [],
    preAlerting: [],
    upcoming: [],
    dismissed: [],
    error: null,
    createTimer,
    dismissTimer,
    deleteTimer,
    ...lists,
  } as unknown as ReturnType<typeof useEventTimers>);
  return render(<EventTimersPanel />);
}

function field(name: string) {
  return screen.getByLabelText(name) as HTMLInputElement;
}

function rowOf(label: string) {
  return screen.getByText(label).closest("li")!;
}

beforeEach(() => {
  localStorage.clear();
  createTimer.mockReset().mockResolvedValue(aTimer(60));
  dismissTimer.mockReset().mockResolvedValue(undefined);
  deleteTimer.mockReset().mockResolvedValue(undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("the event timers panel", () => {
  it("counts the timers in each state, and says when there are none", () => {
    panel();
    expect(screen.getByText(/firing ·/).textContent).toBe("0 firing · 0 pre-alert · 0 upcoming");
    expect(screen.getByText("No timers set.")).toBeTruthy();
  });

  it("folds away and remembers it, and opens folded when last left so", () => {
    const view = panel();
    const toggle = screen.getByRole("button", { name: /Event timers/ });
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByLabelText("Label")).toBeNull();
    expect(localStorage.getItem("holly.event-timers.collapsed")).toBe("1");
    view.unmount();
    panel();
    const again = screen.getByRole("button", { name: /Event timers/ });
    expect(again.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(again);
    expect(localStorage.getItem("holly.event-timers.collapsed")).toBe("0");
    expect(screen.getByLabelText("Label")).toBeTruthy();
  });

  it("shows each timer with its state, recurrence and event, firing first", () => {
    panel({
      firing: [aTimer(-1, { id: "f", label: "Firing one", event_key: "EVT-TEST" })],
      preAlerting: [aTimer(3, { id: "p", label: "Pre one", pre_alert_minutes: 5 })],
      upcoming: [aTimer(60, { id: "u", label: "Upcoming one", recurrence: "daily" })],
      dismissed: [aTimer(-9, { id: "d", label: "Dismissed one" })],
    });
    expect(
      screen.getAllByRole("listitem").map((li) => li.querySelector("strong")?.textContent),
    ).toEqual(["Firing one", "Pre one", "Upcoming one", "Dismissed one"]);
    expect(within(rowOf("Firing one")).getByText("Firing")).toBeTruthy();
    expect(within(rowOf("Firing one")).getByText("event EVT-TEST")).toBeTruthy();
    expect(within(rowOf("Pre one")).getByText("5-min alert")).toBeTruthy();
    expect(within(rowOf("Upcoming one")).getByText("Daily")).toBeTruthy();
    expect(within(rowOf("Dismissed one")).getByText("Dismissed")).toBeTruthy();
    expect(within(rowOf("Firing one")).getByRole("button", { name: "Dismiss" })).toBeTruthy();
    expect(within(rowOf("Upcoming one")).queryByRole("button", { name: "Dismiss" })).toBeNull();
    expect(within(rowOf("Dismissed one")).queryByRole("button", { name: "Dismiss" })).toBeNull();
  });

  it("shows each target in UTC and how far off it is", () => {
    vi.useFakeTimers({ now: new Date("2026-01-01T00:00:00Z") });
    try {
      panel({
        upcoming: [
          aTimer(0, { id: "a", label: "Days", target_time: "2026-01-03T03:00:00Z" }),
          aTimer(0, { id: "b", label: "Hours", target_time: "2026-01-01T01:05:00Z" }),
          aTimer(0, { id: "c", label: "Minutes", target_time: "2026-01-01T00:07:30Z" }),
          aTimer(0, { id: "e", label: "Past", target_time: "2025-12-31T23:00:00Z" }),
        ],
      });
      expect(within(rowOf("Days")).getByText("2026-01-03 03:00:00Z")).toBeTruthy();
      expect(within(rowOf("Days")).getByText("in 2d 3h")).toBeTruthy();
      expect(within(rowOf("Hours")).getByText("in 1h 5m")).toBeTruthy();
      expect(within(rowOf("Minutes")).getByText("in 7m")).toBeTruthy();
      expect(within(rowOf("Past")).getByText("now")).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });

  it("dismisses a timer, holding its buttons meanwhile", async () => {
    let finish: () => void = () => undefined;
    dismissTimer.mockReturnValue(
      new Promise<void>((resolve) => {
        finish = resolve;
      }),
    );
    panel({ preAlerting: [aTimer(3, { id: "p", label: "Pre one" })] });
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(dismissTimer).toHaveBeenCalledWith("p");
    await waitFor(() =>
      expect((screen.getByRole("button", { name: "Delete" }) as HTMLButtonElement).disabled).toBe(
        true,
      ),
    );
    finish();
    await waitFor(() =>
      expect((screen.getByRole("button", { name: "Delete" }) as HTMLButtonElement).disabled).toBe(
        false,
      ),
    );
  });

  it("deletes a timer only once the analyst confirms", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    panel({ upcoming: [aTimer(60, { id: "u", label: "Upcoming one" })] });
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(confirm).toHaveBeenCalledWith("Delete this timer?");
    expect(deleteTimer).not.toHaveBeenCalled();
    confirm.mockReturnValue(true);
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(deleteTimer).toHaveBeenCalledWith("u");
    await waitFor(() =>
      expect((screen.getByRole("button", { name: "Delete" }) as HTMLButtonElement).disabled).toBe(
        false,
      ),
    );
  });

  it("adds a timer from the form, in UTC, then clears the form", async () => {
    panel();
    const add = screen.getByRole("button", { name: "Add timer" }) as HTMLButtonElement;
    expect(add.disabled).toBe(true);
    fireEvent.change(field("Label"), { target: { value: "  Synthetic burn  " } });
    fireEvent.change(field("Event ID (optional)"), { target: { value: "  EVT-TEST " } });
    fireEvent.change(field("Target time (local)"), { target: { value: "2026-01-02T03:04" } });
    fireEvent.change(field("Pre-alert (min)"), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText("Recurrence"), { target: { value: "weekly" } });
    expect(add.disabled).toBe(false);
    fireEvent.click(add);
    await waitFor(() => expect(field("Label").value).toBe(""));
    expect(createTimer).toHaveBeenCalledWith({
      label: "Synthetic burn",
      target_time: new Date("2026-01-02T03:04").toISOString(),
      event_key: "EVT-TEST",
      pre_alert_minutes: 10,
      recurrence: "weekly",
    });
    expect(field("Event ID (optional)").value).toBe("");
    expect(field("Target time (local)").value).toBe("");
    expect(field("Pre-alert (min)").value).toBe("5");
    expect((screen.getByLabelText("Recurrence") as HTMLSelectElement).value).toBe("none");
  });

  it("sends no event and no pre-alert when they are left empty", async () => {
    panel();
    fireEvent.change(field("Label"), { target: { value: "Synthetic" } });
    fireEvent.change(field("Target time (local)"), { target: { value: "2026-01-02T03:04" } });
    fireEvent.change(field("Pre-alert (min)"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Add timer" }));
    await waitFor(() => expect(createTimer).toHaveBeenCalled());
    expect(createTimer.mock.lastCall![0]).toMatchObject({ event_key: null, pre_alert_minutes: 0 });
  });

  it("clamps a negative pre-alert to none where the browser does not hold the form to its minimum", async () => {
    panel();
    fireEvent.change(field("Label"), { target: { value: "Synthetic" } });
    fireEvent.change(field("Target time (local)"), { target: { value: "2026-01-02T03:04" } });
    fireEvent.change(field("Pre-alert (min)"), { target: { value: "-5" } });
    fireEvent.submit(screen.getByRole("button", { name: "Add timer" }).closest("form")!);
    await waitFor(() => expect(createTimer).toHaveBeenCalled());
    expect(createTimer.mock.lastCall![0]).toMatchObject({ pre_alert_minutes: 0 });
  });

  it("refuses to add a timer without a label or a time", () => {
    panel();
    const form = screen.getByRole("button", { name: "Add timer" }).closest("form")!;
    fireEvent.change(field("Label"), { target: { value: "   " } });
    fireEvent.change(field("Target time (local)"), { target: { value: "2026-01-02T03:04" } });
    fireEvent.submit(form);
    fireEvent.change(field("Label"), { target: { value: "Synthetic" } });
    fireEvent.change(field("Target time (local)"), { target: { value: "" } });
    fireEvent.submit(form);
    expect(createTimer).not.toHaveBeenCalled();
  });

  it("shows why a timer could not be added, and keeps what was typed", async () => {
    let fail: (reason: unknown) => void = () => undefined;
    createTimer.mockReturnValue(
      new Promise((_, reject) => {
        fail = reject;
      }),
    );
    panel();
    fireEvent.change(field("Label"), { target: { value: "Synthetic" } });
    fireEvent.change(field("Target time (local)"), { target: { value: "2026-01-02T03:04" } });
    fireEvent.click(screen.getByRole("button", { name: "Add timer" }));
    const busy = (await screen.findByRole("button", { name: "Adding..." })) as HTMLButtonElement;
    expect(busy.disabled).toBe(true);
    fail({ response: { data: { detail: "Target must be in the future" } } });
    expect(await screen.findByText("Target must be in the future")).toBeTruthy();
    expect(field("Label").value).toBe("Synthetic");
  });

  it("shows the timers' own load error when nothing else went wrong", () => {
    panel({ error: "Could not load timers." });
    expect(screen.getByText("Could not load timers.")).toBeTruthy();
  });
});
