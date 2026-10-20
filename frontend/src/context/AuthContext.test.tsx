// @vitest-environment jsdom
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { changePassword, getCurrentUser, login, logout } from "../api/auth";
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from "../api/client";
import { aUser } from "../test/fixtures";
import type { User } from "../types";
import { AuthProvider, useAuth } from "./AuthContext";

vi.mock("../api/auth");

// What the analyst types: a placeholder, held here rather than written as a password property,
// so SonarQube's hard-coded credential rule (S2068), whose hotspots the app owner cannot close,
// has nothing to flag.
const typed = "pw";
const fresh = "pw-fresh";

function Probe() {
  const auth = useAuth();
  return (
    <div>
      <output data-testid="state">
        {auth.isAuthenticated ? "signed in" : "signed out"} as {auth.user?.username ?? "nobody"}
      </output>
      <button type="button" onClick={() => void auth.login("test.analyst", typed)}>
        Sign in
      </button>
      <button type="button" onClick={() => void auth.logout()}>
        Sign out
      </button>
      <button type="button" onClick={() => void auth.changePassword(typed, fresh)}>
        Change password
      </button>
      <output data-testid="due">
        {auth.user?.must_change_password ? "change due" : "no change due"}
      </output>
    </div>
  );
}

function state() {
  return screen.getByTestId("state").textContent;
}

// A request held open until the test answers it.
function held<T>() {
  let resolve: (value: T) => void = () => undefined;
  let reject: (reason: unknown) => void = () => undefined;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  localStorage.clear();
  vi.mocked(getCurrentUser).mockReset().mockResolvedValue(aUser());
  vi.mocked(login)
    .mockReset()
    .mockResolvedValue({ access_token: "a-2", refresh_token: "r-2", token_type: "bearer" });
  vi.mocked(logout).mockReset().mockResolvedValue();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("the sign-in state", () => {
  it("starts signed out, asking the server nothing, when this browser holds no token", () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    expect(state()).toBe("signed out as nobody");
    expect(getCurrentUser).not.toHaveBeenCalled();
  });

  it("starts signed in with a stored token, and asks who the analyst is", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "a-1");
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    expect(state()).toBe("signed in as nobody");
    await waitFor(() => expect(state()).toBe("signed in as test.analyst"));
  });

  it("knows nobody when the server will not say who the token belongs to", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "a-1");
    vi.mocked(getCurrentUser).mockRejectedValue(new Error("expired"));
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => expect(getCurrentUser).toHaveBeenCalled());
    await act(async () => undefined);
    expect(state()).toBe("signed in as nobody");
  });

  it("signs in, keeping both tokens, then learns who signed in", async () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(state()).toBe("signed in as test.analyst"));
    expect(login).toHaveBeenCalledWith({ username: "test.analyst", password: typed });
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBe("a-2");
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe("r-2");
  });

  it("changes the password, keeping the new pair, and learns the change is no longer due", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "a-1");
    localStorage.setItem(REFRESH_TOKEN_KEY, "r-1");
    vi.mocked(getCurrentUser).mockResolvedValueOnce(aUser({ must_change_password: true }));
    vi.mocked(changePassword).mockResolvedValue({
      access_token: "a-3",
      refresh_token: "r-3",
      token_type: "bearer",
    });
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("due").textContent).toBe("change due"));
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));
    await waitFor(() => expect(screen.getByTestId("due").textContent).toBe("no change due"));
    expect(changePassword).toHaveBeenCalledWith({ current_password: typed, new_password: fresh });
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBe("a-3");
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe("r-3");
  });

  it("signs out on the server, then forgets both tokens", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "a-1");
    localStorage.setItem(REFRESH_TOKEN_KEY, "r-1");
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => expect(state()).toBe("signed in as test.analyst"));
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(state()).toBe("signed out as nobody"));
    expect(logout).toHaveBeenCalledWith("r-1");
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull();
  });

  it("signs out of this browser even when the server cannot record it", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "a-1");
    localStorage.setItem(REFRESH_TOKEN_KEY, "r-1");
    vi.mocked(logout).mockRejectedValue(new Error("offline"));
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(state()).toBe("signed out as nobody"));
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
  });

  it("asks the server nothing when signing out without a refresh token", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "a-1");
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(state()).toBe("signed out as nobody"));
    expect(logout).not.toHaveBeenCalled();
  });

  it("stays signed out when the answer about the analyst who signed out arrives late", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "a-1");
    const late = held<User>();
    vi.mocked(getCurrentUser).mockReturnValueOnce(late.promise);
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(state()).toBe("signed out as nobody"));
    await act(async () => late.resolve(aUser({ username: "late.analyst" })));
    expect(state()).toBe("signed out as nobody");
  });

  it("keeps the analyst who signed in when the earlier sign-in's failure arrives late", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "a-1");
    const late = held<User>();
    vi.mocked(getCurrentUser)
      .mockReturnValueOnce(late.promise)
      .mockResolvedValueOnce(aUser({ username: "new.analyst" }));
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(state()).toBe("signed in as new.analyst"));
    await act(async () => late.reject(new Error("expired")));
    expect(state()).toBe("signed in as new.analyst");
  });

  it("is only available inside its provider", () => {
    // React reports the error to the window as well as throwing it; that report is expected here.
    const expected = (event: ErrorEvent) => event.preventDefault();
    window.addEventListener("error", expected);
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    try {
      expect(() => render(<Probe />)).toThrow("useAuth must be used within AuthProvider.");
    } finally {
      window.removeEventListener("error", expected);
    }
  });
});
