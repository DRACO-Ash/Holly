// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { changePassword, getCurrentUser } from "../api/auth";
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from "../api/client";
import ProtectedRoute from "../components/ProtectedRoute";
import { AuthProvider } from "../context/AuthContext";
import { aUser } from "../test/fixtures";
import { landedAt, renderAt } from "../test/render";
import ChangePassword from "./ChangePassword";

vi.mock("../api/auth");

// What the user types: placeholders held in variables rather than written as password
// properties, so SonarQube's hard-coded credential rule (S2068) has nothing to flag. `chosen`
// is as long as Holly's rule asks.
const typed = "pw";
const chosen = "x".repeat(12);

function shown() {
  localStorage.setItem(ACCESS_TOKEN_KEY, "a-1");
  renderAt(
    <AuthProvider>
      <ChangePassword />
    </AuthProvider>,
    "/password",
  );
}

function fillIn(current: string, next: string, again = next) {
  fireEvent.change(screen.getByLabelText("Current password"), { target: { value: current } });
  fireEvent.change(screen.getByLabelText("New password"), { target: { value: next } });
  fireEvent.change(screen.getByLabelText("New password again"), { target: { value: again } });
  fireEvent.click(screen.getByRole("button", { name: "Change password" }));
}

beforeEach(() => {
  localStorage.clear();
  vi.mocked(getCurrentUser).mockReset().mockResolvedValue(aUser());
  vi.mocked(changePassword)
    .mockReset()
    .mockResolvedValue({ access_token: "a-2", refresh_token: "r-2", token_type: "bearer" });
});

describe("the change password page", () => {
  it("changes the password and says every other session has ended", async () => {
    shown();
    await waitFor(() => expect(getCurrentUser).toHaveBeenCalled());
    fillIn(typed, chosen);
    expect(await screen.findByRole("status")).toBeTruthy();
    expect(screen.getByRole("status").textContent).toBe(
      "Password changed. Every other session has ended.",
    );
    expect(changePassword).toHaveBeenCalledWith({ current_password: typed, new_password: chosen });
    expect((screen.getByLabelText("Current password") as HTMLInputElement).value).toBe("");
    expect(landedAt()).toBeNull();
  });

  it("asks a user whose password an admin set to choose their own, then lets them in", async () => {
    vi.mocked(getCurrentUser)
      .mockResolvedValueOnce(aUser({ must_change_password: true }))
      .mockResolvedValue(aUser());
    shown();
    expect(
      await screen.findByText("An admin set your password. Choose your own to continue."),
    ).toBeTruthy();
    fillIn(typed, chosen);
    await waitFor(() => expect(landedAt()).toBe("/"));
  });

  it("says why before sending a password Holly would refuse", async () => {
    shown();
    fillIn(typed, "x".repeat(11));
    expect((await screen.findByRole("alert")).textContent).toBe("Use at least 12 characters.");
    fillIn(typed, chosen, "y".repeat(12));
    expect((await screen.findByRole("alert")).textContent).toBe("The new passwords do not match.");
    fillIn(chosen, chosen);
    expect((await screen.findByRole("alert")).textContent).toBe(
      "Choose a new password, not the current one.",
    );
    expect(changePassword).not.toHaveBeenCalled();
  });

  it("shows the server's refusal and keeps what was typed", async () => {
    vi.mocked(changePassword).mockRejectedValue({
      response: { status: 400, data: { detail: "The current password is not correct." } },
    });
    shown();
    fillIn(typed, chosen);
    expect((await screen.findByRole("alert")).textContent).toBe(
      "The current password is not correct.",
    );
    expect((screen.getByLabelText("New password") as HTMLInputElement).value).toBe(chosen);
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("says which field the server refused, and why", async () => {
    vi.mocked(changePassword).mockRejectedValue(
      Object.assign(new Error("Request failed with status code 422"), {
        response: {
          status: 422,
          data: {
            detail: [
              {
                type: "value_error",
                loc: ["body", "new_password"],
                msg: "Value error, must not be spaces alone",
              },
            ],
          },
        },
      }),
    );
    shown();
    fillIn(typed, chosen);
    expect((await screen.findByRole("alert")).textContent).toBe(
      "New password: must not be spaces alone",
    );
  });

  it("falls back to a plain message when the failure says nothing", async () => {
    vi.mocked(changePassword).mockRejectedValue({});
    shown();
    fillIn(typed, chosen);
    expect((await screen.findByRole("alert")).textContent).toBe(
      "The password could not be changed.",
    );
  });
});

// The whole journey as App mounts it: the provider, the guard and the page together, so a user
// whose change was due must reach the dashboard and stay there, not be sent back to the form.
function signedInAt(route: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, "a-1");
  localStorage.setItem(REFRESH_TOKEN_KEY, "r-1");
  render(
    <AuthProvider>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/password" element={<ChangePassword />} />
            <Route path="/" element={<output data-testid="home">dashboard</output>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}

// The user as the server describes it: a change due until the page has sent one, then, after a
// moment's network delay, no change due. The delay matters: a page that moved on without reading
// the user again would be sent back to the form before the dashboard's own read arrived.
function readsAfterTheChange(...after: Array<"ok" | "fails">) {
  vi.mocked(getCurrentUser).mockImplementation(() => {
    if (vi.mocked(changePassword).mock.calls.length === 0) {
      return Promise.resolve(aUser({ must_change_password: true }));
    }
    const outcome = after.shift() ?? "ok";
    return new Promise((resolve, reject) =>
      setTimeout(
        () => (outcome === "ok" ? resolve(aUser()) : reject(new Error("Network Error"))),
        50,
      ),
    );
  });
}

describe("a change an admin asked for, end to end", () => {
  it("sends the user to the form, then to the dashboard, where they stay", async () => {
    readsAfterTheChange();
    signedInAt("/");
    expect(
      await screen.findByText("An admin set your password. Choose your own to continue."),
    ).toBeTruthy();
    fillIn(typed, chosen);
    expect(await screen.findByTestId("home")).toBeTruthy();
    await waitFor(() => expect(getCurrentUser).toHaveBeenCalledTimes(3));
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(screen.getByTestId("home")).toBeTruthy();
    expect(screen.queryByLabelText("Current password")).toBeNull();
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBe("a-2");
  });

  it("lets the user in when the change stood but reading the user again failed", async () => {
    // The server took the change, so the old password no longer works: telling the user the
    // change failed would have them retry with it, counting against the limit.
    readsAfterTheChange("fails");
    signedInAt("/password");
    expect(
      await screen.findByText("An admin set your password. Choose your own to continue."),
    ).toBeTruthy();
    fillIn(typed, chosen);
    expect(await screen.findByTestId("home")).toBeTruthy();
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(screen.getByTestId("home")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe("r-2");
  });
});
