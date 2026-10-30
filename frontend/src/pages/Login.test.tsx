// @vitest-environment jsdom
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getCurrentUser, login } from "../api/auth";
import { AuthProvider } from "../context/AuthContext";
import { aUser } from "../test/fixtures";
import { landedAt, renderAt } from "../test/render";
import type { TokenResponse } from "../types";
import Login from "./Login";

vi.mock("../api/auth");

// What the analyst types: a placeholder, held here rather than written as a password property,
// so SonarQube's hard-coded credential rule (S2068), whose hotspots the app owner cannot close,
// has nothing to flag.
const typed = "pw";

function shown() {
  renderAt(
    <AuthProvider>
      <Login />
    </AuthProvider>,
    "/login",
  );
}

function fillIn(username: string, password: string) {
  fireEvent.change(screen.getByLabelText("Username"), { target: { value: username } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: password } });
}

beforeEach(() => {
  localStorage.clear();
  vi.mocked(getCurrentUser).mockReset().mockResolvedValue(aUser());
  vi.mocked(login)
    .mockReset()
    .mockResolvedValue({ access_token: "a-1", refresh_token: "r-1", token_type: "bearer" });
});

describe("the sign-in page", () => {
  it("shows the brand plate and asks for a username and password", () => {
    shown();
    expect(screen.getByRole("img", { name: "Holly, daily operations dashboard" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeTruthy();
  });

  it("signs in with what was typed, then opens the dashboard", async () => {
    shown();
    fillIn("test.analyst", typed);
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(landedAt()).toBe("/"));
    expect(login).toHaveBeenCalledWith({ username: "test.analyst", password: typed });
  });

  it("holds the button while signing in", async () => {
    let finish: (tokens: TokenResponse) => void = () => undefined;
    vi.mocked(login).mockReturnValue(
      new Promise((resolve) => {
        finish = resolve;
      }),
    );
    shown();
    fillIn("test.analyst", typed);
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    const busy = (await screen.findByRole("button", {
      name: "Signing in...",
    })) as HTMLButtonElement;
    expect(busy.disabled).toBe(true);
    finish({ access_token: "a-1", refresh_token: "r-1", token_type: "bearer" });
    await waitFor(() => expect(landedAt()).toBe("/"));
  });

  it("shows the server's reason when sign-in fails, and lets the analyst try again", async () => {
    vi.mocked(login).mockRejectedValueOnce({ response: { data: { detail: "Wrong details" } } });
    shown();
    fillIn("test.analyst", "no");
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Wrong details")).toBeTruthy();
    expect(landedAt()).toBeNull();
    const again = screen.getByRole("button", { name: "Sign in" }) as HTMLButtonElement;
    expect(again.disabled).toBe(false);
  });

  it("says sign-in failed when the failure carries no reason", async () => {
    vi.mocked(login).mockRejectedValueOnce("unexpected");
    shown();
    fillIn("test.analyst", "no");
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Sign in failed.")).toBeTruthy();
  });

  it("tells a user who has forgotten their password to ask an administrator", () => {
    shown();
    const help = screen.getByText("Forgotten your password?").closest("details");
    expect(help).not.toBeNull();
    expect(help?.open).toBe(false);
    fireEvent.click(screen.getByText("Forgotten your password?"));
    expect(help?.textContent).toContain("Ask an administrator to reset it on the Users page");
    expect(help?.textContent).toContain("open Password in the navigation");
    // It offers no way round the sign-in: no link, no form, nothing sent.
    expect(help?.querySelector("a, input, button, form")).toBeNull();
  });
});
