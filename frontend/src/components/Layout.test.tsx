// @vitest-environment jsdom
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getCurrentUser, logout } from "../api/auth";
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from "../api/client";
import { listEventTimers } from "../api/event_timers";
import { AuthProvider } from "../context/AuthContext";
import { aUser } from "../test/fixtures";
import type { User } from "../types";
import { DISPLAY_STORAGE_KEY } from "../utils/displayPrefs";
import Layout from "./Layout";

vi.mock("../api/auth");
vi.mock("../api/event_timers");

// The frame at a route, once its providers' first answers (who signed in, the timers) have
// landed inside act, as they would before an analyst could look.
async function shell(route = "/") {
  render(
    <AuthProvider>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<p>Dashboard content</p>} />
            <Route path="/notifications" element={<p>Notifications content</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
  await act(async () => {
    await Promise.resolve();
  });
}

function links() {
  return within(screen.getByRole("navigation"))
    .getAllByRole("link")
    .map((link) => link.textContent);
}

function signedInAs(user: User | Promise<User>) {
  localStorage.setItem(ACCESS_TOKEN_KEY, "a-1");
  localStorage.setItem(REFRESH_TOKEN_KEY, "r-1");
  if (user instanceof Promise) vi.mocked(getCurrentUser).mockReturnValue(user);
  else vi.mocked(getCurrentUser).mockResolvedValue(user);
}

beforeEach(() => {
  localStorage.clear();
  vi.mocked(getCurrentUser).mockReset();
  vi.mocked(logout).mockReset().mockResolvedValue();
  vi.mocked(listEventTimers).mockReset().mockResolvedValue({ items: [] });
});

describe("the dashboard's frame", () => {
  it("shows the page inside it, the analyst's name, and every page an analyst may open", async () => {
    signedInAs(aUser({ role: "analyst" }));
    await shell();
    expect(screen.getByText("Dashboard content")).toBeTruthy();
    expect(await screen.findByText("test.analyst")).toBeTruthy();
    expect(links()).toEqual([
      "Dashboard",
      "Notifications",
      "Maneuvers",
      "Comms",
      "Procedures",
      "Shift log",
      "Password",
    ]);
  });

  it("adds the audit log for an operator or an admin", async () => {
    signedInAs(aUser({ role: "operator" }));
    await shell();
    await waitFor(() => expect(links()).toContain("Audit log"));
    expect(links()).not.toContain("Users");
  });

  it("adds the users page for an admin alone", async () => {
    signedInAs(aUser({ role: "admin" }));
    await shell();
    await waitFor(() => expect(links()).toContain("Users"));
    expect(links()).toContain("Audit log");
  });

  it("offers the password page alone while a password an admin set is still to change", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      signedInAs(aUser({ role: "admin", must_change_password: true }));
      await shell();
      await waitFor(() => expect(links()).toEqual(["Password"]));
      // Nothing polls the timers meanwhile, past a whole poll interval: Holly would refuse it.
      vi.mocked(listEventTimers).mockClear();
      await act(() => vi.advanceTimersByTimeAsync(11_000));
      expect(listEventTimers).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it("holds the audit log back until it knows who signed in", async () => {
    signedInAs(new Promise<User>(() => undefined));
    await shell();
    expect(links()).not.toContain("Audit log");
  });

  it("marks the link to the page being shown", async () => {
    signedInAs(aUser());
    await shell("/notifications");
    const current = screen.getByRole("link", { name: "Notifications" });
    expect(current.getAttribute("aria-current")).toBe("page");
    expect(current.className).toBe("nav-link active");
    const other = screen.getByRole("link", { name: "Dashboard" });
    expect(other.getAttribute("aria-current")).toBeNull();
    expect(other.className).toBe("nav-link");
  });

  it("signs the analyst out", async () => {
    signedInAs(aUser());
    await shell();
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(logout).toHaveBeenCalledWith("r-1"));
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
  });

  it("applies the screen effects and keeps the analyst's choice", async () => {
    signedInAs(aUser());
    await shell();
    const frame = document.querySelector(".app-shell")!;
    expect(frame.getAttribute("data-scanlines")).toBe("on");
    expect(frame.getAttribute("data-flicker")).toBe("off");
    fireEvent.click(screen.getByRole("checkbox", { name: "Scanlines" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "CRT flicker" }));
    expect(frame.getAttribute("data-scanlines")).toBe("off");
    expect(frame.getAttribute("data-flicker")).toBe("on");
    expect(JSON.parse(localStorage.getItem(DISPLAY_STORAGE_KEY)!)).toEqual({
      scanlines: false,
      flicker: true,
    });
  });
});
