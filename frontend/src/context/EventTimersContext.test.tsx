// @vitest-environment jsdom
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  acknowledgePreAlert,
  createEventTimer,
  deleteEventTimer,
  dismissEventTimer,
  listEventTimers,
} from "../api/event_timers";
import { aTimer } from "../test/fixtures";
import type { EventTimer, EventTimerList } from "../types";
import { playFiring, playPreAlert, unlockAudio } from "../utils/timerSound";
import { EventTimersProvider, useEventTimers } from "./EventTimersContext";

vi.mock("../api/event_timers");
vi.mock("../utils/timerSound");

// The browser's Notification API, as a class that records what it shows.
class FakeNotification {
  static permission: NotificationPermission = "default";
  static requestPermission = vi.fn(async (): Promise<NotificationPermission> => "granted");
  static shown: { title: string; options: NotificationOptions | undefined }[] = [];

  constructor(title: string, options?: NotificationOptions) {
    FakeNotification.shown.push({ title, options });
  }
}

let context: ReturnType<typeof useEventTimers>;

function Probe() {
  context = useEventTimers();
  const ids = (list: EventTimer[]) => list.map((t) => t.id).join(",") || "-";
  return (
    <output data-testid="timers">
      {context.loading ? "loading" : "loaded"} firing={ids(context.firing)} pre=
      {ids(context.preAlerting)} upcoming={ids(context.upcoming)} dismissed=
      {ids(context.dismissed)} error={context.error ?? "-"} audio=
      {context.audioEnabled ? "on" : "off"} permission={context.notificationPermission}
    </output>
  );
}

function shown() {
  return screen.getByTestId("timers").textContent ?? "";
}

async function settle() {
  await act(async () => {
    await Promise.resolve();
  });
}

async function mounted() {
  const view = render(
    <EventTimersProvider>
      <Probe />
    </EventTimersProvider>,
  );
  await settle();
  return view;
}

// Each poll answers with a fresh list, as a server sends fresh JSON every time.
function serve(...items: EventTimer[]) {
  vi.mocked(listEventTimers).mockImplementation(
    async () => ({ items: [...items] }) satisfies EventTimerList,
  );
}

beforeEach(() => {
  vi.useFakeTimers();
  FakeNotification.permission = "default";
  FakeNotification.requestPermission.mockClear();
  FakeNotification.shown = [];
  vi.stubGlobal("Notification", FakeNotification);
  vi.mocked(listEventTimers).mockReset();
  serve();
  for (const fn of [acknowledgePreAlert, createEventTimer, deleteEventTimer, dismissEventTimer]) {
    vi.mocked(fn).mockReset();
  }
  vi.mocked(acknowledgePreAlert).mockImplementation(async (id) =>
    aTimer(3, { id, pre_alert_fired_at: "2026-01-01T00:00:00Z" }),
  );
  vi.mocked(playFiring).mockReset();
  vi.mocked(playPreAlert).mockReset();
  vi.mocked(unlockAudio).mockReset();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("the event timers", () => {
  it("load the live timers and sort them by where each stands", async () => {
    serve(
      aTimer(-1, { id: "due" }),
      aTimer(3, { id: "soon", pre_alert_fired_at: "2026-01-01T00:00:00Z" }),
      aTimer(60, { id: "later" }),
      aTimer(-30, { id: "done", dismissed_at: "2026-01-01T00:00:00Z" }),
    );
    await mounted();
    expect(listEventTimers).toHaveBeenCalledWith(false);
    expect(shown()).toContain("loaded firing=due pre=soon upcoming=later dismissed=done error=-");
  });

  it("ask again every ten seconds, and stop when they are gone", async () => {
    const view = await mounted();
    expect(listEventTimers).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(listEventTimers).toHaveBeenCalledTimes(2);
    view.unmount();
    await vi.advanceTimersByTimeAsync(30_000);
    expect(listEventTimers).toHaveBeenCalledTimes(2);
  });

  it("say why they could not load, in the analyst's words", async () => {
    vi.mocked(listEventTimers).mockRejectedValueOnce({ response: { status: 500 } });
    await mounted();
    expect(shown()).toContain("error=Could not load timers.");
    vi.mocked(listEventTimers).mockRejectedValueOnce(new Error("Network down"));
    await act(async () => {
      await context.refresh();
    });
    expect(shown()).toContain("error=Network down");
    vi.mocked(listEventTimers).mockRejectedValueOnce("odd");
    await act(async () => {
      await context.refresh();
    });
    expect(shown()).toContain("error=Could not load timers.");
    await act(async () => {
      await context.refresh();
    });
    expect(shown()).toContain("error=-");
  });

  it("turn on sound, and ask to notify, at the analyst's first click", async () => {
    await mounted();
    expect(shown()).toContain("audio=off permission=default");
    fireEvent.click(document.body);
    await settle();
    expect(unlockAudio).toHaveBeenCalledTimes(1);
    expect(FakeNotification.requestPermission).toHaveBeenCalledTimes(1);
    expect(shown()).toContain("audio=on permission=granted");
    fireEvent.keyDown(document.body);
    expect(unlockAudio).toHaveBeenCalledTimes(2);
  });

  it("turn on sound at the first click even when the browser will not be asked", async () => {
    FakeNotification.requestPermission.mockRejectedValueOnce(new Error("blocked"));
    await mounted();
    fireEvent.click(document.body);
    await settle();
    expect(FakeNotification.requestPermission).toHaveBeenCalledTimes(1);
    expect(shown()).toContain("audio=on permission=default");
  });

  it("turn on sound without asking again once the browser has an answer", async () => {
    FakeNotification.permission = "denied";
    await mounted();
    fireEvent.keyDown(document.body);
    await settle();
    expect(FakeNotification.requestPermission).not.toHaveBeenCalled();
    expect(shown()).toContain("audio=on permission=denied");
  });

  it("carry on without notifications in a browser that has none", async () => {
    vi.stubGlobal("Notification", undefined);
    serve(aTimer(-1, { id: "due" }), aTimer(3, { id: "soon" }));
    await mounted();
    expect(shown()).toContain("permission=unsupported");
    fireEvent.click(document.body);
    await act(async () => {
      await context.enableAudio();
    });
    expect(playFiring).toHaveBeenCalledTimes(1);
    expect(playPreAlert).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(playFiring).toHaveBeenCalledTimes(2);
  });

  it("turn on sound from the banner's button, whatever the browser says", async () => {
    await mounted();
    FakeNotification.requestPermission.mockRejectedValueOnce(new Error("blocked"));
    await act(async () => {
      await context.enableAudio();
    });
    expect(shown()).toContain("audio=on permission=default");
    await act(async () => {
      await context.enableAudio();
    });
    expect(shown()).toContain("permission=granted");
    FakeNotification.permission = "granted";
    await act(async () => {
      await context.enableAudio();
    });
    expect(FakeNotification.requestPermission).toHaveBeenCalledTimes(2);
  });

  it("chime once for a timer entering its pre-alert, notify, and record it", async () => {
    FakeNotification.permission = "granted";
    serve(aTimer(3, { id: "soon", label: "Synthetic burn", pre_alert_minutes: 5 }));
    await mounted();
    expect(playPreAlert).toHaveBeenCalledTimes(1);
    expect(FakeNotification.shown).toEqual([
      { title: "Event in 5 min", options: { body: "Synthetic burn", tag: "event-timer-pre-soon" } },
    ]);
    expect(acknowledgePreAlert).toHaveBeenCalledWith("soon");
    serve(aTimer(3, { id: "soon", label: "Synthetic burn", pre_alert_minutes: 5 }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(playPreAlert).toHaveBeenCalledTimes(1);
  });

  it("stay quiet for a pre-alert already recorded, or one the browser may not show", async () => {
    vi.mocked(acknowledgePreAlert).mockRejectedValue(new Error("offline"));
    serve(
      aTimer(3, { id: "acked", pre_alert_fired_at: "2026-01-01T00:00:00Z" }),
      aTimer(4, { id: "new" }),
    );
    await mounted();
    expect(playPreAlert).toHaveBeenCalledTimes(1);
    expect(FakeNotification.shown).toEqual([]);
    expect(acknowledgePreAlert).toHaveBeenCalledWith("new");
  });

  it("sound and notify when a timer fires, then every thirty seconds until it is dismissed", async () => {
    FakeNotification.permission = "granted";
    serve(aTimer(-1, { id: "due", label: "Synthetic burn" }));
    await mounted();
    expect(playFiring).toHaveBeenCalledTimes(1);
    const firing = {
      title: "Event firing",
      options: { body: "Synthetic burn", tag: "event-timer-firing-due", requireInteraction: true },
    };
    expect(FakeNotification.shown).toEqual([firing]);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(playFiring).toHaveBeenCalledTimes(2);
    expect(FakeNotification.shown).toEqual([firing, firing]);
    vi.mocked(dismissEventTimer).mockResolvedValue(
      aTimer(-1, { id: "due", dismissed_at: "2026-01-01T00:00:00Z" }),
    );
    await act(async () => {
      await context.dismissTimer("due");
    });
    expect(shown()).toContain("firing=- pre=- upcoming=- dismissed=due");
    // The server lists live timers only, so the dismissed one leaves at the next poll.
    serve();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(playFiring).toHaveBeenCalledTimes(2);
    expect(shown()).toContain("dismissed=-");
  });

  it("sound without notifying while the browser has not allowed notifications", async () => {
    serve(aTimer(-1, { id: "due" }));
    await mounted();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(playFiring).toHaveBeenCalledTimes(2);
    expect(FakeNotification.shown).toEqual([]);
  });

  it("stop the repeat when the last firing timer is deleted", async () => {
    serve(aTimer(-1, { id: "due" }));
    await mounted();
    vi.mocked(deleteEventTimer).mockResolvedValue();
    serve();
    await act(async () => {
      await context.deleteTimer("due");
    });
    expect(shown()).toContain("firing=-");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(playFiring).toHaveBeenCalledTimes(1);
  });

  it("add, acknowledge, dismiss and delete timers, keeping the list in step", async () => {
    serve(aTimer(3, { id: "soon", pre_alert_fired_at: "2026-01-01T00:00:00Z" }));
    await mounted();
    vi.mocked(createEventTimer).mockResolvedValue(aTimer(60, { id: "new" }));
    let created: EventTimer | undefined;
    await act(async () => {
      created = await context.createTimer({ label: "New", target_time: "2026-01-02T00:00:00Z" });
    });
    expect(created?.id).toBe("new");
    expect(shown()).toContain("pre=soon upcoming=new");
    await act(async () => {
      await context.acknowledgePreAlert("soon");
    });
    expect(acknowledgePreAlert).toHaveBeenCalledWith("soon");
    vi.mocked(dismissEventTimer).mockResolvedValue(
      aTimer(60, { id: "new", dismissed_at: "2026-01-01T00:00:00Z" }),
    );
    await act(async () => {
      await context.dismissTimer("new");
    });
    expect(shown()).toContain("upcoming=- dismissed=new");
    vi.mocked(deleteEventTimer).mockResolvedValue();
    await act(async () => {
      await context.deleteTimer("soon");
    });
    expect(deleteEventTimer).toHaveBeenCalledWith("soon");
    expect(shown()).toContain("firing=- pre=- upcoming=- dismissed=new");
  });

  it("chime again for a timer deleted and created anew", async () => {
    serve(aTimer(3, { id: "soon" }));
    await mounted();
    expect(playPreAlert).toHaveBeenCalledTimes(1);
    vi.mocked(deleteEventTimer).mockResolvedValue();
    await act(async () => {
      await context.deleteTimer("soon");
    });
    vi.mocked(createEventTimer).mockResolvedValue(aTimer(3, { id: "soon" }));
    await act(async () => {
      await context.createTimer({ label: "Again", target_time: "2026-01-02T00:00:00Z" });
    });
    expect(playPreAlert).toHaveBeenCalledTimes(2);
  });

  it("are only available inside their provider", () => {
    // React reports the error to the window as well as throwing it; that report is expected here.
    const expected = (event: ErrorEvent) => event.preventDefault();
    window.addEventListener("error", expected);
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    try {
      expect(() => render(<Probe />)).toThrow(
        "useEventTimers must be used inside EventTimersProvider",
      );
    } finally {
      window.removeEventListener("error", expected);
      vi.mocked(console.error).mockRestore();
    }
  });
});
