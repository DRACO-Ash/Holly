// @vitest-environment jsdom
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { listAuditLog } from "../api/audit";
import { renderAt } from "../test/render";
import type { AuditLog, AuditLogPage as EntryPage } from "../types";
import AuditLogPage from "./AuditLog";

vi.mock("../api/audit");

// A synthetic audit entry: every value is made up for the tests, and the address comes from the
// range set aside for documentation.
function anEntry(overrides: Partial<AuditLog> = {}): AuditLog {
  return {
    id: "a-1",
    timestamp: "2026-01-02T03:04:05Z",
    user_id: "u-1234567890",
    action_type: "test.action",
    entity_type: "test-entity",
    entity_id: "e-1234567890",
    ip_address: "192.0.2.1",
    detail: '{ "synthetic": true, "count": 2 }',
    previous_hash: null,
    entry_hash: "test-hash-1",
    ...overrides,
  };
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

function pageOf(items: AuditLog[], total = items.length): EntryPage {
  return { items, total, limit: 50, offset: 0 };
}

function lastQuery() {
  return vi.mocked(listAuditLog).mock.lastCall?.[0];
}

function requests() {
  return vi.mocked(listAuditLog).mock.calls.length;
}

function bodyRows() {
  return screen.getAllByRole("row").slice(1);
}

function cellsOf(row: HTMLElement) {
  return within(row)
    .getAllByRole("cell")
    .map((cell) => cell.textContent);
}

function actionField() {
  return screen.getByLabelText("Filter by action type") as HTMLInputElement;
}

function button(name: string) {
  return screen.getByRole("button", { name }) as HTMLButtonElement;
}

function filterBy(actionType: string) {
  fireEvent.change(actionField(), { target: { value: actionType } });
  fireEvent.click(button("Apply"));
}

async function shown() {
  renderAt(<AuditLogPage />, "/audit");
  await waitFor(() => expect(screen.queryByText("Loading...")).toBeNull());
}

beforeEach(() => {
  vi.mocked(listAuditLog)
    .mockReset()
    .mockResolvedValue(pageOf([anEntry()]));
});

describe("the audit log page", () => {
  it("asks for the entries a page at a time, and shows each one", async () => {
    await shown();
    expect(requests()).toBe(1);
    expect(lastQuery()).toEqual({ action_type: undefined, limit: 50, offset: 0 });
    expect(screen.getByRole("heading", { name: "Audit log" })).toBeTruthy();
    expect(screen.getAllByRole("columnheader").map((header) => header.textContent)).toEqual([
      "Timestamp",
      "Action",
      "Entity",
      "User",
      "IP",
      "Detail",
    ]);
    expect(cellsOf(bodyRows()[0])).toEqual([
      "2026-01-02 03:04:05",
      "test.action",
      "test-entity · e-123456…",
      "u-123456…",
      "192.0.2.1",
      '{"synthetic":true,"count":2}',
    ]);
    expect(screen.getByText(/1 total/).textContent).toBe("1 total · page 1 of 1");
  });

  it("shows IDs of up to 8 characters whole, and falls back field by field", async () => {
    vi.mocked(listAuditLog).mockResolvedValue(
      pageOf([
        anEntry({ id: "a-1", entity_id: "e-123456", user_id: "u-123456" }),
        anEntry({ id: "a-2", entity_id: "e-1234567", user_id: "u-1234567" }),
        anEntry({
          id: "a-3",
          entity_type: null,
          entity_id: null,
          user_id: null,
          ip_address: null,
          detail: null,
        }),
        anEntry({ id: "a-4", entity_type: null, entity_id: "e-4" }),
      ]),
    );
    await shown();
    const [whole, shortened, bare, typeless] = bodyRows();
    expect(cellsOf(whole).slice(2, 4)).toEqual(["test-entity · e-123456", "u-123456"]);
    expect(cellsOf(shortened).slice(2, 4)).toEqual(["test-entity · e-123456…", "u-123456…"]);
    expect(cellsOf(bare)).toEqual(["2026-01-02 03:04:05", "test.action", "n/a", "n/a", "n/a", ""]);
    expect(cellsOf(typeless)[2]).toBe("n/a · e-4");
  });

  it("shows a detail that is not JSON as written, with any markup in it as plain text", async () => {
    vi.mocked(listAuditLog).mockResolvedValue(
      pageOf([
        anEntry({ id: "a-1", detail: "plain test detail" }),
        anEntry({ id: "a-2", detail: '<img alt="test markup" src="x">' }),
      ]),
    );
    await shown();
    const [plain, markup] = bodyRows();
    expect(cellsOf(plain)[5]).toBe("plain test detail");
    expect(cellsOf(markup)[5]).toBe('<img alt="test markup" src="x">');
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("shows that it is loading, then says when there are no entries", async () => {
    let answer: (page: EntryPage) => void = () => undefined;
    vi.mocked(listAuditLog).mockReturnValueOnce(
      new Promise((resolve) => {
        answer = resolve;
      }),
    );
    renderAt(<AuditLogPage />, "/audit");
    expect(screen.getByText("Loading...")).toBeTruthy();
    expect(screen.queryByText("No audit entries.")).toBeNull();
    answer(pageOf([]));
    expect(await screen.findByText("No audit entries.")).toBeTruthy();
    expect(screen.queryByText("Loading...")).toBeNull();
    expect(screen.getByText(/0 total/).textContent).toBe("0 total · page 1 of 1");
    expect(button("Previous").disabled).toBe(true);
    expect(button("Next").disabled).toBe(true);
  });

  it("filters by action type, trimmed, from the first page", async () => {
    vi.mocked(listAuditLog).mockResolvedValue(pageOf([anEntry()], 120));
    await shown();
    fireEvent.click(button("Next"));
    await waitFor(() => expect(lastQuery()?.offset).toBe(50));
    const before = requests();
    fireEvent.change(actionField(), { target: { value: "  test.action  " } });
    expect(requests()).toBe(before);
    fireEvent.click(button("Apply"));
    await waitFor(() =>
      expect(lastQuery()).toEqual({ action_type: "test.action", limit: 50, offset: 0 }),
    );
    expect(requests()).toBe(before + 1);
    filterBy("   ");
    await waitFor(() =>
      expect(lastQuery()).toEqual({ action_type: undefined, limit: 50, offset: 0 }),
    );
  });

  it("clears the filter back to the first page", async () => {
    vi.mocked(listAuditLog).mockResolvedValue(pageOf([anEntry()], 120));
    await shown();
    filterBy("test.other");
    await waitFor(() => expect(lastQuery()?.action_type).toBe("test.other"));
    fireEvent.click(button("Next"));
    await waitFor(() =>
      expect(lastQuery()).toEqual({ action_type: "test.other", limit: 50, offset: 50 }),
    );
    fireEvent.click(button("Clear"));
    await waitFor(() =>
      expect(lastQuery()).toEqual({ action_type: undefined, limit: 50, offset: 0 }),
    );
    expect(actionField().value).toBe("");
  });

  it("pages through the entries 50 at a time", async () => {
    vi.mocked(listAuditLog).mockResolvedValue(pageOf([anEntry()], 100));
    await shown();
    expect(screen.getByText(/100 total/).textContent).toBe("100 total · page 1 of 2");
    expect(button("Previous").disabled).toBe(true);
    fireEvent.click(button("Next"));
    await waitFor(() => expect(lastQuery()?.offset).toBe(50));
    await screen.findByText("100 total · page 2 of 2");
    expect(button("Next").disabled).toBe(true);
    fireEvent.click(button("Previous"));
    await waitFor(() => expect(lastQuery()?.offset).toBe(0));
    await screen.findByText("100 total · page 1 of 2");
    expect(button("Previous").disabled).toBe(true);
  });

  it("tells an analyst without the operator or admin role that the log is not theirs to see", async () => {
    vi.mocked(listAuditLog).mockRejectedValue({
      response: { status: 403, data: { detail: "Test forbidden detail" } },
    });
    await shown();
    expect(
      screen.getByText("Insufficient privileges. Operator or admin role required."),
    ).toBeTruthy();
    expect(screen.queryByText("Test forbidden detail")).toBeNull();
  });

  it("says why the log cannot load, or that it failed, until a later load succeeds", async () => {
    vi.mocked(listAuditLog).mockRejectedValueOnce({
      response: { status: 500, data: { detail: "Test store unavailable" } },
    });
    await shown();
    expect(screen.getByText("Test store unavailable")).toBeTruthy();
    vi.mocked(listAuditLog).mockRejectedValueOnce(new Error("Network Error"));
    filterBy("test.one");
    expect(await screen.findByText("Network Error")).toBeTruthy();
    expect(screen.queryByText("Test store unavailable")).toBeNull();
    vi.mocked(listAuditLog).mockRejectedValueOnce("unreadable");
    filterBy("test.two");
    expect(await screen.findByText("Failed to load audit log.")).toBeTruthy();
    filterBy("test.three");
    expect(await screen.findByText("test.action")).toBeTruthy();
    expect(screen.queryByText("Failed to load audit log.")).toBeNull();
  });

  it("keeps the newest page when an older one answers late", async () => {
    let answer: (page: EntryPage) => void = () => undefined;
    vi.mocked(listAuditLog)
      .mockReturnValueOnce(
        new Promise((resolve) => {
          answer = resolve;
        }),
      )
      .mockResolvedValueOnce(pageOf([anEntry({ id: "a-2", action_type: "test.newer" })]));
    renderAt(<AuditLogPage />, "/audit");
    filterBy("test.newer");
    expect(await screen.findByText("test.newer")).toBeTruthy();
    await act(async () => {
      answer(pageOf([anEntry({ id: "a-1", action_type: "test.older" })], 7));
    });
    expect(screen.queryByText("test.older")).toBeNull();
    expect(screen.getByText("1 total · page 1 of 1")).toBeTruthy();
    expect(screen.queryByText("Loading...")).toBeNull();
  });

  it("keeps loading while the page asked for last is on its way", async () => {
    const older = held<EntryPage>();
    const newer = held<EntryPage>();
    vi.mocked(listAuditLog).mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise);
    renderAt(<AuditLogPage />, "/audit");
    filterBy("test.newer");
    await act(async () => older.resolve(pageOf([])));
    expect(screen.getByText("Loading...")).toBeTruthy();
    await act(async () => newer.resolve(pageOf([anEntry({ action_type: "test.newer" })])));
    expect(screen.queryByText("Loading...")).toBeNull();
    expect(screen.getByText("test.newer")).toBeTruthy();
  });

  it("never shows why an earlier request failed", async () => {
    const older = held<EntryPage>();
    vi.mocked(listAuditLog)
      .mockReturnValueOnce(older.promise)
      .mockResolvedValueOnce(pageOf([anEntry({ action_type: "test.newer" })]));
    renderAt(<AuditLogPage />, "/audit");
    filterBy("test.newer");
    expect(await screen.findByText("test.newer")).toBeTruthy();
    await act(async () => older.reject({ response: { data: { detail: "Old failure" } } }));
    expect(screen.queryByText("Old failure")).toBeNull();
  });
});
