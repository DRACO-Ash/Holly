// @vitest-environment jsdom
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getFeed } from "./api/assistant";
import { getCurrentUser } from "./api/auth";
import { ACCESS_TOKEN_KEY } from "./api/client";
import { listEventTimers } from "./api/event_timers";
import { listNotifications } from "./api/notifications";
import App from "./App";
import { aUser } from "./test/fixtures";

vi.mock("./api/assistant");
vi.mock("./api/auth");
vi.mock("./api/event_timers");
vi.mock("./api/notifications");

async function open(path: string) {
  window.history.pushState({}, "", path);
  render(<App />);
  await act(async () => undefined);
}

beforeEach(() => {
  localStorage.clear();
  vi.mocked(getCurrentUser).mockReset().mockResolvedValue(aUser());
  vi.mocked(getFeed).mockReset().mockResolvedValue({ items: [], window_hours: 120 });
  vi.mocked(listEventTimers).mockReset().mockResolvedValue({ items: [] });
  vi.mocked(listNotifications)
    .mockReset()
    .mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
});

afterEach(() => {
  window.history.pushState({}, "", "/");
});

describe("the dashboard app", () => {
  it("sends a visitor who has not signed in to the sign-in page", async () => {
    await open("/");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeTruthy();
    expect(window.location.pathname).toBe("/login");
  });

  it("opens the dashboard, in its frame, for an analyst who has signed in", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "a-1");
    await open("/");
    expect(await screen.findByRole("heading", { name: "What needs your attention" })).toBeTruthy();
    expect(screen.getByRole("navigation")).toBeTruthy();
  });

  it("opens the page the address names", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "a-1");
    await open("/notifications");
    expect(await screen.findByRole("heading", { level: 1, name: "Notifications" })).toBeTruthy();
  });
});
