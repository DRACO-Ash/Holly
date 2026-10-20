// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getCurrentUser } from "../api/auth";
import { ACCESS_TOKEN_KEY } from "../api/client";
import { AuthProvider } from "../context/AuthContext";
import { aUser } from "../test/fixtures";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./ProtectedRoute";

vi.mock("../api/auth");

function at(route: string, guarded: React.ReactNode) {
  render(
    <AuthProvider>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/login" element={<p>The sign-in page</p>} />
          {guarded}
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.mocked(getCurrentUser).mockReset().mockResolvedValue(aUser());
});

describe("the protected route", () => {
  it("sends a visitor who has not signed in to the sign-in page", () => {
    at(
      "/",
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <p>The dashboard</p>
          </ProtectedRoute>
        }
      />,
    );
    expect(screen.getByText("The sign-in page")).toBeTruthy();
    expect(screen.queryByText("The dashboard")).toBeNull();
  });

  it("shows what it guards to an analyst who has signed in", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "a-1");
    at(
      "/",
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <p>The dashboard</p>
          </ProtectedRoute>
        }
      />,
    );
    expect(await screen.findByText("The dashboard")).toBeTruthy();
  });

  it("shows the matched child route when it wraps routes rather than an element", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "a-1");
    at(
      "/audit",
      <Route element={<ProtectedRoute />}>
        <Route path="/audit" element={<p>The audit log</p>} />
      </Route>,
    );
    expect(await screen.findByText("The audit log")).toBeTruthy();
  });

  it("keeps a user whose password an admin set on the password page until they change it", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "a-1");
    vi.mocked(getCurrentUser).mockResolvedValue(aUser({ must_change_password: true }));
    at(
      "/audit",
      <Route element={<ProtectedRoute />}>
        <Route path="/audit" element={<p>The audit log</p>} />
        <Route path="/password" element={<p>The password page</p>} />
      </Route>,
    );
    expect(await screen.findByText("The password page")).toBeTruthy();
    expect(screen.queryByText("The audit log")).toBeNull();
  });
});
