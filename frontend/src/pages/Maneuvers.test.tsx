// @vitest-environment jsdom
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { listManeuvers } from "../api/maneuvers";
import { renderAt } from "../test/render";
import type { Maneuver, ManeuverPage } from "../types";
import ManeuversPage from "./Maneuvers";

vi.mock("../api/maneuvers");

// A synthetic record built to the API's type: every value is made up for the tests.
function aManeuver(overrides: Partial<Maneuver> = {}): Maneuver {
  return {
    id: "m-1",
    udl_id: "udl-test-m-1",
    data_mode: "TEST",
    source: "test-source",
    classification_marking: "U",
    created_by: "test.creator",
    orig_network: "test-network",
    origin: "test-origin",
    udl_created_at: "2026-01-02T03:20:00Z",
    sat_no: 90001,
    event_start_time: "2026-01-02T03:04:05Z",
    event_stop_time: "2026-01-02T03:14:05Z",
    mnvr_type: "TEST-BURN",
    description: null,
    delta_v: 1.23456,
    thrust_magnitude: null,
    thrust_duration: null,
    propulsion_type: null,
    maneuver_status: null,
    responsible_nation: null,
    created_at: "2026-01-02T03:25:00Z",
    updated_at: "2026-01-02T03:25:00Z",
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

function pageOf(items: Maneuver[], total = items.length): ManeuverPage {
  return { items, total, limit: 50, offset: 0 };
}

function lastQuery() {
  return vi.mocked(listManeuvers).mock.lastCall?.[0];
}

function requests() {
  return vi.mocked(listManeuvers).mock.calls.length;
}

function bodyRows() {
  return screen.getAllByRole("row").slice(1);
}

function cellsOf(row: HTMLElement) {
  return within(row)
    .getAllByRole("cell")
    .map((cell) => cell.textContent);
}

function satNoField() {
  return screen.getByLabelText("Satellite number") as HTMLInputElement;
}

function typeField() {
  return screen.getByLabelText("Maneuver type") as HTMLInputElement;
}

function button(name: string | RegExp) {
  return screen.getByRole("button", { name }) as HTMLButtonElement;
}

async function shown() {
  renderAt(<ManeuversPage />, "/maneuvers");
  await waitFor(() => expect(screen.queryByText("Loading...")).toBeNull());
}

beforeEach(() => {
  vi.mocked(listManeuvers)
    .mockReset()
    .mockResolvedValue(pageOf([aManeuver()]));
});

describe("the maneuvers page", () => {
  it("asks for the latest maneuvers first, a page at a time, and shows each one", async () => {
    await shown();
    expect(requests()).toBe(1);
    expect(lastQuery()).toEqual({
      sat_no: undefined,
      mnvr_type: undefined,
      limit: 50,
      offset: 0,
      sort_by: "event_start_time",
      sort_dir: "desc",
    });
    expect(screen.getByRole("heading", { name: "Maneuvers" })).toBeTruthy();
    expect(screen.getAllByRole("columnheader").map((header) => header.textContent)).toEqual([
      "Sat No",
      "Start▼",
      "Stop",
      "Type",
      "Delta-V (m/s)",
      "Source",
    ]);
    expect(cellsOf(bodyRows()[0])).toEqual([
      "90001",
      "2026-01-02 03:04:05",
      "2026-01-02 03:14:05",
      "TEST-BURN",
      "1.235",
      "test-source",
    ]);
    expect(screen.getByText(/1 total/).textContent).toBe("1 total · page 1 of 1");
  });

  it("shows that it is loading, then says when there is nothing to show", async () => {
    let answer: (page: ManeuverPage) => void = () => undefined;
    vi.mocked(listManeuvers).mockReturnValueOnce(
      new Promise((resolve) => {
        answer = resolve;
      }),
    );
    renderAt(<ManeuversPage />, "/maneuvers");
    expect(screen.getByText("Loading...")).toBeTruthy();
    expect(screen.queryByText("No maneuvers to show.")).toBeNull();
    answer(pageOf([]));
    expect(await screen.findByText("No maneuvers to show.")).toBeTruthy();
    expect(screen.queryByText("Loading...")).toBeNull();
    expect(screen.getByText(/0 total/).textContent).toBe("0 total · page 1 of 1");
    expect(button("Previous").disabled).toBe(true);
    expect(button("Next").disabled).toBe(true);
  });

  it("falls back field by field when a maneuver lacks one, and keeps a zero delta-v", async () => {
    vi.mocked(listManeuvers).mockResolvedValue(
      pageOf([
        aManeuver({
          id: "m-1",
          sat_no: null,
          event_start_time: null,
          event_stop_time: null,
          mnvr_type: null,
          delta_v: null,
          source: null,
        }),
        aManeuver({ id: "m-2", delta_v: 0 }),
        aManeuver({ id: "m-3", delta_v: undefined }),
      ]),
    );
    await shown();
    const [bare, zero, omitted] = bodyRows();
    expect(cellsOf(bare)).toEqual(["n/a", "n/a", "n/a", "n/a", "n/a", "n/a"]);
    expect(cellsOf(zero)[4]).toBe("0.000");
    expect(cellsOf(omitted)[4]).toBe("n/a");
  });

  it("filters by satellite number and maneuver type, trimmed, from the first page", async () => {
    vi.mocked(listManeuvers).mockResolvedValue(pageOf([aManeuver()], 120));
    await shown();
    fireEvent.click(button("Next"));
    await waitFor(() => expect(lastQuery()?.offset).toBe(50));
    const before = requests();
    fireEvent.change(satNoField(), { target: { value: "90002" } });
    fireEvent.change(typeField(), { target: { value: "  TEST-BURN  " } });
    expect(requests()).toBe(before);
    fireEvent.click(button("Apply"));
    await waitFor(() =>
      expect(lastQuery()).toEqual({
        sat_no: 90002,
        mnvr_type: "TEST-BURN",
        limit: 50,
        offset: 0,
        sort_by: "event_start_time",
        sort_dir: "desc",
      }),
    );
    expect(requests()).toBe(before + 1);
    fireEvent.change(satNoField(), { target: { value: "" } });
    fireEvent.change(typeField(), { target: { value: "   " } });
    fireEvent.click(button("Apply"));
    await waitFor(() =>
      expect(lastQuery()).toMatchObject({ sat_no: undefined, mnvr_type: undefined }),
    );
  });

  it("clears every filter back to the first page", async () => {
    vi.mocked(listManeuvers).mockResolvedValue(pageOf([aManeuver()], 120));
    await shown();
    fireEvent.change(satNoField(), { target: { value: "90002" } });
    fireEvent.change(typeField(), { target: { value: "TEST-BURN" } });
    fireEvent.click(button("Apply"));
    await waitFor(() =>
      expect(lastQuery()).toMatchObject({ sat_no: 90002, mnvr_type: "TEST-BURN" }),
    );
    fireEvent.click(button("Next"));
    await waitFor(() => expect(lastQuery()?.offset).toBe(50));
    fireEvent.click(button("Clear"));
    await waitFor(() =>
      expect(lastQuery()).toMatchObject({ sat_no: undefined, mnvr_type: undefined, offset: 0 }),
    );
    expect(satNoField().value).toBe("");
    expect(typeField().value).toBe("");
  });

  it("asks again for the same filter, sort and page on Refresh", async () => {
    vi.mocked(listManeuvers).mockResolvedValue(pageOf([aManeuver()], 120));
    await shown();
    fireEvent.change(satNoField(), { target: { value: "90002" } });
    fireEvent.click(button("Apply"));
    await waitFor(() => expect(lastQuery()?.sat_no).toBe(90002));
    fireEvent.click(button(/^Sat No/));
    await waitFor(() => expect(lastQuery()?.sort_by).toBe("sat_no"));
    fireEvent.click(button("Next"));
    await waitFor(() => expect(lastQuery()?.offset).toBe(50));
    const view = lastQuery();
    expect(view).toEqual({
      sat_no: 90002,
      mnvr_type: undefined,
      limit: 50,
      offset: 50,
      sort_by: "sat_no",
      sort_dir: "desc",
    });
    const before = requests();
    fireEvent.click(button("Refresh"));
    await waitFor(() => expect(requests()).toBe(before + 1));
    expect(lastQuery()).toEqual(view);
  });

  it("sorts by a new column latest first, flips the current one, and goes back to the first page", async () => {
    vi.mocked(listManeuvers).mockResolvedValue(pageOf([aManeuver()], 120));
    await shown();
    fireEvent.click(button(/^Start/));
    await waitFor(() =>
      expect(lastQuery()).toMatchObject({ sort_by: "event_start_time", sort_dir: "asc" }),
    );
    expect(button(/^Start/).textContent).toBe("Start▲");
    fireEvent.click(button(/^Start/));
    await waitFor(() => expect(lastQuery()?.sort_dir).toBe("desc"));
    expect(button(/^Start/).textContent).toBe("Start▼");
    fireEvent.click(button("Next"));
    await waitFor(() => expect(lastQuery()?.offset).toBe(50));
    fireEvent.click(button(/^Sat No/));
    await waitFor(() =>
      expect(lastQuery()).toMatchObject({ sort_by: "sat_no", sort_dir: "desc", offset: 0 }),
    );
    expect(button(/^Sat No/).textContent).toBe("Sat No▼");
    expect(button(/^Start/).textContent).toBe("Start");
    fireEvent.click(button(/^Stop/));
    await waitFor(() =>
      expect(lastQuery()).toMatchObject({ sort_by: "event_stop_time", sort_dir: "desc" }),
    );
    fireEvent.click(button(/^Type/));
    await waitFor(() =>
      expect(lastQuery()).toMatchObject({ sort_by: "mnvr_type", sort_dir: "desc" }),
    );
  });

  it("pages through the results 50 at a time", async () => {
    vi.mocked(listManeuvers).mockResolvedValue(pageOf([aManeuver()], 101));
    await shown();
    expect(screen.getByText(/101 total/).textContent).toBe("101 total · page 1 of 3");
    expect(button("Previous").disabled).toBe(true);
    fireEvent.click(button("Next"));
    await waitFor(() => expect(lastQuery()?.offset).toBe(50));
    await screen.findByText("101 total · page 2 of 3");
    fireEvent.click(button("Next"));
    await waitFor(() => expect(lastQuery()?.offset).toBe(100));
    await screen.findByText("101 total · page 3 of 3");
    expect(button("Next").disabled).toBe(true);
    fireEvent.click(button("Previous"));
    await waitFor(() => expect(lastQuery()?.offset).toBe(50));
    await screen.findByText("101 total · page 2 of 3");
  });

  it("says why the list cannot load, or that it failed, until a later load succeeds", async () => {
    vi.mocked(listManeuvers).mockRejectedValueOnce({
      response: { status: 503, data: { detail: "Test store unavailable" } },
    });
    await shown();
    expect(screen.getByText("Test store unavailable")).toBeTruthy();
    vi.mocked(listManeuvers).mockRejectedValueOnce(new Error("Network Error"));
    fireEvent.click(button("Refresh"));
    expect(await screen.findByText("Network Error")).toBeTruthy();
    expect(screen.queryByText("Test store unavailable")).toBeNull();
    vi.mocked(listManeuvers).mockRejectedValueOnce({ response: { status: 500, data: {} } });
    fireEvent.click(button("Refresh"));
    expect(await screen.findByText("Failed to load maneuvers.")).toBeTruthy();
    fireEvent.click(button("Refresh"));
    expect(await screen.findByText("90001")).toBeTruthy();
    expect(screen.queryByText("Failed to load maneuvers.")).toBeNull();
  });

  it("refuses a satellite number that is not numeric where the field takes free text", async () => {
    await shown();
    const before = requests();
    // A browser without number fields treats this one as text, which leaves the page's own
    // check as the only guard; changing the field's type stands in for such a browser.
    satNoField().type = "text";
    fireEvent.change(satNoField(), { target: { value: "9000x" } });
    fireEvent.change(typeField(), { target: { value: "TEST-BURN" } });
    fireEvent.click(button("Apply"));
    expect(screen.getByText("Satellite number must be numeric.")).toBeTruthy();
    expect(requests()).toBe(before);
    fireEvent.change(satNoField(), { target: { value: "90003" } });
    fireEvent.change(typeField(), { target: { value: "TEST-BURN" } });
    fireEvent.click(button("Apply"));
    await waitFor(() =>
      expect(lastQuery()).toMatchObject({ sat_no: 90003, mnvr_type: "TEST-BURN", offset: 0 }),
    );
    expect(screen.queryByText("Satellite number must be numeric.")).toBeNull();
  });

  it("keeps the newest page when an older one answers late", async () => {
    let answer: (page: ManeuverPage) => void = () => undefined;
    vi.mocked(listManeuvers)
      .mockReturnValueOnce(
        new Promise((resolve) => {
          answer = resolve;
        }),
      )
      .mockResolvedValueOnce(pageOf([aManeuver({ id: "m-2", sat_no: 90002 })]));
    renderAt(<ManeuversPage />, "/maneuvers");
    fireEvent.click(button(/^Sat No/));
    expect(await screen.findByText("90002")).toBeTruthy();
    await act(async () => {
      answer(pageOf([aManeuver({ id: "m-1", sat_no: 90001 })], 7));
    });
    expect(screen.queryByText("90001")).toBeNull();
    expect(screen.getByText("1 total · page 1 of 1")).toBeTruthy();
    expect(screen.queryByText("Loading...")).toBeNull();
  });

  it("keeps loading while the page asked for last is on its way", async () => {
    const older = held<ManeuverPage>();
    const newer = held<ManeuverPage>();
    vi.mocked(listManeuvers).mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise);
    renderAt(<ManeuversPage />, "/maneuvers");
    fireEvent.click(button(/^Sat No/));
    await act(async () => older.resolve(pageOf([])));
    expect(screen.getByText("Loading...")).toBeTruthy();
    await act(async () => newer.resolve(pageOf([aManeuver({ id: "m-2", sat_no: 90002 })])));
    expect(screen.queryByText("Loading...")).toBeNull();
    expect(screen.getByText("90002")).toBeTruthy();
  });

  it("never shows why an earlier request failed", async () => {
    const older = held<ManeuverPage>();
    vi.mocked(listManeuvers)
      .mockReturnValueOnce(older.promise)
      .mockResolvedValueOnce(pageOf([aManeuver({ id: "m-2", sat_no: 90002 })]));
    renderAt(<ManeuversPage />, "/maneuvers");
    fireEvent.click(button(/^Sat No/));
    expect(await screen.findByText("90002")).toBeTruthy();
    await act(async () => older.reject({ response: { data: { detail: "Old failure" } } }));
    expect(screen.queryByText("Old failure")).toBeNull();
  });
});
