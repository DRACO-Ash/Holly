// @vitest-environment jsdom
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { listNotifications, refreshNotificationsNow } from "../api/notifications";
import { aNotification } from "../test/fixtures";
import { landedAt, renderAt } from "../test/render";
import type { Notification, NotificationPage } from "../types";
import NotificationsPage from "./Notifications";

vi.mock("../api/notifications");

function pageOf(items: Notification[], total = items.length): NotificationPage {
  return { items, total, limit: 50, offset: 0 };
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

function lastQuery() {
  return vi.mocked(listNotifications).mock.lastCall?.[0];
}

async function shown() {
  renderAt(<NotificationsPage />, "/notifications");
  await waitFor(() => expect(screen.queryByText("Loading...")).toBeNull());
}

beforeEach(() => {
  vi.mocked(listNotifications)
    .mockReset()
    .mockResolvedValue(pageOf([aNotification()]));
  vi.mocked(refreshNotificationsNow).mockReset().mockResolvedValue();
});

describe("the notifications page", () => {
  it("asks for the newest notices first, a page at a time, and shows each one", async () => {
    await shown();
    expect(lastQuery()).toEqual({
      event_type: undefined,
      status: undefined,
      limit: 50,
      offset: 0,
      sort_by: "udl_created_at",
      sort_dir: "desc",
    });
    const row = screen.getByText("NOTSO-TEST-1").closest("tr")!;
    expect(within(row).getByText("OPEN").className).toBe("status-pill status-open");
    expect(within(row).getByText("other")).toBeTruthy();
    expect(within(row).getByText("Test event class")).toBeTruthy();
    expect(within(row).getByText("90001")).toBeTruthy();
    expect(within(row).getByText("2026-01-02 03:04:05")).toBeTruthy();
    expect(screen.getByText(/1 total/).textContent).toBe("1 total · page 1 of 1");
  });

  it("falls back field by field when a notice lacks one", async () => {
    vi.mocked(listNotifications).mockResolvedValue(
      pageOf([
        aNotification({ id: "a", notso_identifier: null, notice_id: "NOTICE-ONLY" }),
        aNotification({
          id: "b",
          notso_identifier: null,
          notice_id: null,
          status: null,
          event_type: null,
          event_class: null,
          sat_no: null,
          udl_created_at: null,
        }),
      ]),
    );
    await shown();
    expect(screen.getByText("NOTICE-ONLY")).toBeTruthy();
    const bare = screen.getAllByRole("row")[2];
    expect(within(bare).getAllByText("n/a")).toHaveLength(6);
  });

  it("lists up to three satellite IDs and counts the rest", async () => {
    vi.mocked(listNotifications).mockResolvedValue(
      pageOf([
        aNotification({ id: "a", sat_ids: ["S1", "S2", "S3"] }),
        aNotification({ id: "b", sat_ids: ["S1", "S2", "S3", "S4", "S5"] }),
        aNotification({ id: "c", sat_ids: [], sat_no: 7 }),
      ]),
    );
    await shown();
    expect(screen.getByText("S1, S2, S3")).toBeTruthy();
    expect(screen.getByText("S1, S2, S3 (+2)")).toBeTruthy();
    expect(screen.getByText("7")).toBeTruthy();
  });

  it("says when there is nothing to show", async () => {
    vi.mocked(listNotifications).mockResolvedValue(pageOf([]));
    await shown();
    expect(screen.getByText("No notifications to show.")).toBeTruthy();
  });

  it("filters by event type, trimmed, and by status, from the first page", async () => {
    await shown();
    fireEvent.change(screen.getByLabelText("Event type (filter)"), {
      target: { value: "  maneuver  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(lastQuery()?.event_type).toBe("maneuver"));
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "CLOSED" } });
    await waitFor(() => expect(lastQuery()?.status).toBe("CLOSED"));
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "" } });
    await waitFor(() => expect(lastQuery()?.status).toBeUndefined());
    fireEvent.change(screen.getByLabelText("Event type (filter)"), { target: { value: "   " } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(lastQuery()?.event_type).toBeUndefined());
  });

  it("clears every filter, and reloads on Refresh", async () => {
    await shown();
    fireEvent.change(screen.getByLabelText("Event type (filter)"), { target: { value: "launch" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "OPEN" } });
    await waitFor(() =>
      expect(lastQuery()).toMatchObject({ event_type: "launch", status: "OPEN" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    await waitFor(() =>
      expect(lastQuery()).toMatchObject({ event_type: undefined, status: undefined }),
    );
    expect((screen.getByLabelText("Event type (filter)") as HTMLInputElement).value).toBe("");
    const calls = vi.mocked(listNotifications).mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(vi.mocked(listNotifications).mock.calls.length).toBe(calls + 1));
  });

  it("sorts by a new column newest first, and flips the order of the current one", async () => {
    await shown();
    fireEvent.click(screen.getByRole("button", { name: /Notice/ }));
    await waitFor(() =>
      expect(lastQuery()).toMatchObject({ sort_by: "notso_identifier", sort_dir: "desc" }),
    );
    fireEvent.click(screen.getByRole("button", { name: /Notice/ }));
    await waitFor(() =>
      expect(lastQuery()).toMatchObject({ sort_by: "notso_identifier", sort_dir: "asc" }),
    );
    fireEvent.click(screen.getByRole("button", { name: /Notice/ }));
    await waitFor(() => expect(lastQuery()?.sort_dir).toBe("desc"));
  });

  it("pages through the results fifty at a time", async () => {
    vi.mocked(listNotifications).mockResolvedValue(pageOf([aNotification()], 120));
    await shown();
    expect(screen.getByText(/120 total/).textContent).toBe("120 total · page 1 of 3");
    const previous = screen.getByRole("button", { name: "Previous" }) as HTMLButtonElement;
    expect(previous.disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(lastQuery()?.offset).toBe(50));
    await screen.findByText("120 total · page 2 of 3");
    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    await waitFor(() => expect(lastQuery()?.offset).toBe(0));
  });

  it("opens a notice when its row is clicked", async () => {
    await shown();
    fireEvent.click(screen.getByText("NOTSO-TEST-1"));
    expect(landedAt()).toBe("/notifications/n-1");
  });

  it("shows the server's reason when the list cannot load", async () => {
    vi.mocked(listNotifications).mockRejectedValue({ response: { data: { detail: "No access" } } });
    await shown();
    expect(screen.getByText("No access")).toBeTruthy();
  });

  it("pulls from UDL, then reloads the list", async () => {
    await shown();
    const calls = vi.mocked(listNotifications).mock.calls.length;
    let finish: () => void = () => undefined;
    vi.mocked(refreshNotificationsNow).mockReturnValue(
      new Promise<void>((resolve) => {
        finish = resolve;
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Pull from UDL" }));
    const pulling = (await screen.findByRole("button", {
      name: "Pulling...",
    })) as HTMLButtonElement;
    expect(pulling.disabled).toBe(true);
    finish();
    await screen.findByRole("button", { name: "Pull from UDL" });
    await waitFor(() => expect(vi.mocked(listNotifications).mock.calls.length).toBe(calls + 1));
  });

  it("says why a pull from UDL failed, or that it failed", async () => {
    await shown();
    vi.mocked(refreshNotificationsNow).mockRejectedValueOnce({
      response: { data: { detail: "UDL is unreachable" } },
    });
    fireEvent.click(screen.getByRole("button", { name: "Pull from UDL" }));
    expect(await screen.findByText("UDL is unreachable")).toBeTruthy();
    vi.mocked(refreshNotificationsNow).mockRejectedValueOnce(new Error("network"));
    fireEvent.click(screen.getByRole("button", { name: "Pull from UDL" }));
    expect(await screen.findByText("UDL pull failed.")).toBeTruthy();
    vi.mocked(refreshNotificationsNow).mockRejectedValueOnce({ response: { data: {} } });
    fireEvent.click(screen.getByRole("button", { name: "Pull from UDL" }));
    await waitFor(() => expect(screen.queryByText("UDL pull failed.")).toBeTruthy());
  });

  it("shows the list asked for last, never a late answer to an earlier request", async () => {
    const late = held<NotificationPage>();
    vi.mocked(listNotifications)
      .mockReturnValueOnce(late.promise)
      .mockResolvedValue(pageOf([aNotification({ id: "b", notso_identifier: "NOTSO-B" })]));
    renderAt(<NotificationsPage />, "/notifications");
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "CLOSED" } });
    expect(await screen.findByText("NOTSO-B")).toBeTruthy();
    await act(async () =>
      late.resolve(pageOf([aNotification({ id: "a", notso_identifier: "NOTSO-A" })], 99)),
    );
    expect(screen.getByText("NOTSO-B")).toBeTruthy();
    expect(screen.queryByText("NOTSO-A")).toBeNull();
    expect(screen.getByText(/total/).textContent).toBe("1 total · page 1 of 1");
  });

  it("keeps loading while the list asked for last is on its way", async () => {
    const late = held<NotificationPage>();
    const current = held<NotificationPage>();
    vi.mocked(listNotifications)
      .mockReturnValueOnce(late.promise)
      .mockReturnValueOnce(current.promise);
    renderAt(<NotificationsPage />, "/notifications");
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "CLOSED" } });
    await act(async () => late.resolve(pageOf([])));
    expect(screen.getByText("Loading...")).toBeTruthy();
    await act(async () =>
      current.resolve(pageOf([aNotification({ id: "b", notso_identifier: "NOTSO-B" })])),
    );
    expect(screen.queryByText("Loading...")).toBeNull();
    expect(screen.getByText("NOTSO-B")).toBeTruthy();
  });

  it("never shows why an earlier request failed", async () => {
    const late = held<NotificationPage>();
    vi.mocked(listNotifications).mockReturnValueOnce(late.promise);
    renderAt(<NotificationsPage />, "/notifications");
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "CLOSED" } });
    expect(await screen.findByText("NOTSO-TEST-1")).toBeTruthy();
    await act(async () => late.reject({ response: { data: { detail: "Old failure" } } }));
    expect(screen.queryByText("Old failure")).toBeNull();
  });
});
