// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useEventTimers } from "../context/EventTimersContext";
import { aTimer } from "../test/fixtures";
import type { EventTimer } from "../types";
import TimerBanner from "./TimerBanner";

vi.mock("../context/EventTimersContext", () => ({ useEventTimers: vi.fn() }));

const enableAudio = vi.fn(async () => undefined);
const dismissTimer = vi.fn(async () => undefined);

function timers(
  firing: EventTimer[],
  audioEnabled: boolean,
  notificationPermission: NotificationPermission | "unsupported" = "granted",
) {
  vi.mocked(useEventTimers).mockReturnValue({
    firing,
    audioEnabled,
    notificationPermission,
    enableAudio,
    dismissTimer,
  } as unknown as ReturnType<typeof useEventTimers>);
}

beforeEach(() => {
  enableAudio.mockClear();
  dismissTimer.mockClear();
});

describe("the timer banner", () => {
  it("shows nothing while no timer fires and sound is on", () => {
    timers([], true);
    const { container } = render(<TimerBanner />);
    expect(container.innerHTML).toBe("");
  });

  it("offers to turn on alerts until the analyst does", () => {
    timers([], false);
    render(<TimerBanner />);
    expect(screen.getByText(/Audio alerts disabled/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Enable alerts" }));
    expect(enableAudio).toHaveBeenCalledTimes(1);
  });

  it("names each firing timer, its target in UTC and its event, and dismisses it", () => {
    const due = aTimer(-1, {
      id: "t-9",
      label: "Synthetic burn",
      event_key: "EVT-TEST",
      target_time: "2026-01-02T03:04:05.000Z",
    });
    timers([due, aTimer(-2, { id: "t-8", label: "Second" })], true);
    render(<TimerBanner />);
    expect(screen.getByText("Synthetic burn")).toBeTruthy();
    expect(screen.getByText("target 03:04:05Z")).toBeTruthy();
    expect(screen.getByText("event EVT-TEST")).toBeTruthy();
    expect(screen.getAllByText("FIRING")).toHaveLength(2);
    expect(screen.queryByText(/notifications denied/)).toBeNull();
    fireEvent.click(screen.getAllByRole("button", { name: "Dismiss" })[0]);
    expect(dismissTimer).toHaveBeenCalledWith("t-9");
  });

  it("says alerts are sound only when the browser refused notifications", () => {
    timers([aTimer(-1)], true, "denied");
    render(<TimerBanner />);
    expect(screen.getByText("Browser notifications denied; audio only.")).toBeTruthy();
  });
});
