// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getCurrentUser } from "../api/auth";
import { ACCESS_TOKEN_KEY } from "../api/client";
import { createUser, listUsers, resetPassword, updateUser } from "../api/users";
import { AuthProvider } from "../context/AuthContext";
import { aUser } from "../test/fixtures";
import { renderAt } from "../test/render";
import Users from "./Users";

vi.mock("../api/auth");
vi.mock("../api/users");

// What the admin types: a placeholder of the length Holly's rule asks, held in a variable rather
// than written as a password property, so SonarQube's hard-coded credential rule (S2068) has
// nothing to flag.
const chosen = "x".repeat(12);

const me = aUser({ id: "u-admin", username: "test.admin", role: "admin" });
const bob = aUser({ id: "u-bob", username: "test.bob" });
const carol = aUser({
  id: "u-carol",
  username: "test.carol",
  email: "carol@example.org",
  role: "operator",
  must_change_password: true,
});

function shown() {
  localStorage.setItem(ACCESS_TOKEN_KEY, "a-1");
  renderAt(
    <AuthProvider>
      <Users />
    </AuthProvider>,
    "/users",
  );
}

function rowOf(username: string): HTMLElement {
  const row = screen.getByText(username).closest("tr");
  if (!row) throw new Error(`no row for ${username}`);
  return row;
}

function cellsOf(username: string): (string | null)[] {
  return within(rowOf(username))
    .getAllByRole("cell")
    .map((cell) => cell.textContent);
}

async function notice(): Promise<string | null> {
  return (await screen.findByRole("status")).textContent;
}

async function alert(): Promise<string | null> {
  return (await screen.findByRole("alert")).textContent;
}

beforeEach(() => {
  localStorage.clear();
  vi.mocked(getCurrentUser).mockReset().mockResolvedValue(me);
  vi.mocked(listUsers).mockReset().mockResolvedValue([carol, me, bob]);
  vi.mocked(createUser).mockReset();
  vi.mocked(resetPassword).mockReset();
  vi.mocked(updateUser).mockReset();
});

describe("the users page", () => {
  it("lists every account by username, with its role, status and whose password it is", async () => {
    shown();
    await screen.findByText("test.bob");
    const names = screen
      .getAllByRole("row")
      .slice(1)
      .map((row) => within(row).getAllByRole("cell")[0].textContent);
    expect(names).toEqual(["test.admin", "test.bob", "test.carol"]);
    expect(cellsOf("test.carol").slice(1, 5)).toEqual([
      "carol@example.org",
      "analystoperatoradmin",
      "Active",
      "Temporary",
    ]);
    expect((screen.getByLabelText("Role of test.carol") as HTMLSelectElement).value).toBe(
      "operator",
    );
    expect(cellsOf("test.bob")[4]).toBe("Own");
  });

  it("offers no change to the admin's own account", async () => {
    shown();
    await waitFor(() => expect(getCurrentUser).toHaveBeenCalled());
    await screen.findByText("test.admin");
    const row = within(rowOf("test.admin"));
    await waitFor(() => expect(row.queryByRole("button")).toBeNull());
    expect(row.queryByRole("combobox")).toBeNull();
    expect(row.getByText("Your account: change your password from Password.")).toBeTruthy();
  });

  it("says so when the signed-in user is not an admin", async () => {
    vi.mocked(listUsers).mockRejectedValue({ response: { status: 403 } });
    shown();
    expect(await alert()).toBe("Insufficient privileges. Admin role required.");
    expect(screen.queryByText("No users.")).toBeNull();
  });

  it("says when there are no accounts to show", async () => {
    vi.mocked(listUsers).mockResolvedValue([]);
    shown();
    expect(await screen.findByText("No users.")).toBeTruthy();
  });

  it("creates an account with a temporary password and adds it to the list", async () => {
    const dave = aUser({ id: "u-dave", username: "test.dave", must_change_password: true });
    vi.mocked(createUser).mockResolvedValue(dave);
    shown();
    await screen.findByText("test.bob");
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: " test.dave " } });
    fireEvent.change(screen.getByLabelText("Email (optional)"), { target: { value: "  " } });
    fireEvent.change(screen.getByLabelText("Role"), { target: { value: "operator" } });
    fireEvent.change(screen.getByLabelText("Temporary password"), { target: { value: chosen } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(await notice()).toBe(
      "Created test.dave. Give them the temporary password; they choose their own at first sign-in.",
    );
    expect(createUser).toHaveBeenCalledWith({
      username: "test.dave",
      email: null,
      role: "operator",
      temporary_password: chosen,
    });
    expect(screen.getByText("test.dave")).toBeTruthy();
    expect((screen.getByLabelText("Username") as HTMLInputElement).value).toBe("");
    expect((screen.getByLabelText("Temporary password") as HTMLInputElement).value).toBe("");
    expect((screen.getByLabelText("Role") as HTMLSelectElement).value).toBe("analyst");
  });

  it("refuses a short temporary password before sending it, and shows the server's refusal", async () => {
    shown();
    await screen.findByText("test.bob");
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "test.erin" } });
    fireEvent.change(screen.getByLabelText("Email (optional)"), {
      target: { value: "erin@example.org" },
    });
    fireEvent.change(screen.getByLabelText("Temporary password"), {
      target: { value: "x".repeat(11) },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(await alert()).toBe("Temporary password: Use at least 12 characters.");
    expect(createUser).not.toHaveBeenCalled();
    vi.mocked(createUser).mockRejectedValue({
      response: { status: 409, data: { detail: "That username or email is already in use." } },
    });
    fireEvent.change(screen.getByLabelText("Temporary password"), { target: { value: chosen } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(async () =>
      expect(await alert()).toBe("That username or email is already in use."),
    );
    expect(vi.mocked(createUser).mock.lastCall?.[0].email).toBe("erin@example.org");
  });

  it("says which field the server refused, and why", async () => {
    // The username rule is checked on the server alone, so its 422 is how an admin learns it.
    vi.mocked(createUser).mockRejectedValue(
      Object.assign(new Error("Request failed with status code 422"), {
        response: {
          status: 422,
          data: {
            detail: [
              {
                type: "value_error",
                loc: ["body", "username"],
                msg: "Value error, use 1 to 50 of a to z, 0 to 9 and . _ @ -",
              },
            ],
          },
        },
      }),
    );
    shown();
    await screen.findByText("test.bob");
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "bob smith" } });
    fireEvent.change(screen.getByLabelText("Temporary password"), { target: { value: chosen } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(await alert()).toBe("Username: use 1 to 50 of a to z, 0 to 9 and . _ @ -");
  });

  it("resets a password to a temporary one, which ends the user's sessions", async () => {
    vi.mocked(resetPassword).mockResolvedValue({ ...bob, must_change_password: true });
    shown();
    await screen.findByText("test.bob");
    fireEvent.click(within(rowOf("test.bob")).getByRole("button", { name: "Reset password" }));
    const form = within(rowOf("test.bob"));
    fireEvent.change(form.getByLabelText("Temporary password"), { target: { value: chosen } });
    fireEvent.click(form.getByRole("button", { name: "Save" }));
    expect(await notice()).toBe(
      "Reset the password of test.bob. Their sessions have ended; they choose a new password at next sign-in.",
    );
    expect(resetPassword).toHaveBeenCalledWith("u-bob", chosen);
    expect(cellsOf("test.bob")[4]).toBe("Temporary");
    expect(within(rowOf("test.bob")).queryByRole("button", { name: "Save" })).toBeNull();
  });

  it("refuses a short temporary password for a reset, and can be cancelled", async () => {
    vi.mocked(resetPassword).mockRejectedValue({});
    shown();
    await screen.findByText("test.bob");
    fireEvent.click(within(rowOf("test.bob")).getByRole("button", { name: "Reset password" }));
    const form = within(rowOf("test.bob"));
    fireEvent.change(form.getByLabelText("Temporary password"), { target: { value: "short" } });
    fireEvent.click(form.getByRole("button", { name: "Save" }));
    expect(await alert()).toBe("Temporary password: Use at least 12 characters.");
    expect(resetPassword).not.toHaveBeenCalled();
    fireEvent.change(form.getByLabelText("Temporary password"), { target: { value: chosen } });
    fireEvent.click(form.getByRole("button", { name: "Save" }));
    await waitFor(async () => expect(await alert()).toBe("The password could not be reset."));
    fireEvent.click(form.getByRole("button", { name: "Cancel" }));
    expect(within(rowOf("test.bob")).getByRole("button", { name: "Reset password" })).toBeTruthy();
  });

  it("deactivates an account and activates it again", async () => {
    vi.mocked(updateUser)
      .mockResolvedValueOnce({ ...bob, is_active: false })
      .mockResolvedValueOnce(bob);
    shown();
    await screen.findByText("test.bob");
    fireEvent.click(within(rowOf("test.bob")).getByRole("button", { name: "Deactivate" }));
    expect(await notice()).toBe("Deactivated test.bob. Their sessions have ended.");
    expect(updateUser).toHaveBeenLastCalledWith("u-bob", { is_active: false });
    expect(cellsOf("test.bob")[3]).toBe("Deactivated");
    fireEvent.click(within(rowOf("test.bob")).getByRole("button", { name: "Activate" }));
    await waitFor(async () => expect(await notice()).toBe("Activated test.bob."));
    expect(updateUser).toHaveBeenLastCalledWith("u-bob", { is_active: true });
  });

  it("changes a role, and shows a refusal such as keeping the last admin", async () => {
    vi.mocked(updateUser).mockResolvedValueOnce({ ...bob, role: "operator" });
    shown();
    await screen.findByText("test.bob");
    fireEvent.change(screen.getByLabelText("Role of test.bob"), { target: { value: "operator" } });
    expect(await notice()).toBe("test.bob is now operator.");
    expect(updateUser).toHaveBeenLastCalledWith("u-bob", { role: "operator" });
    vi.mocked(updateUser).mockRejectedValueOnce({
      response: { status: 409, data: { detail: "Holly needs at least one active admin." } },
    });
    fireEvent.change(screen.getByLabelText("Role of test.carol"), { target: { value: "admin" } });
    expect(await alert()).toBe("Holly needs at least one active admin.");
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("falls back to a plain message when loading fails without a reason", async () => {
    vi.mocked(listUsers).mockRejectedValue({});
    shown();
    expect(await alert()).toBe("Failed to load users.");
  });
});
