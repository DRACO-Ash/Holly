// @vitest-environment jsdom
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getEvaluation } from "../api/assistant";
import { getNotification } from "../api/notifications";
import { aNotification } from "../test/fixtures";
import { renderAt } from "../test/render";
import type { NotificationDetail } from "../types";
import NotificationDetailPage from "./NotificationDetail";

vi.mock("../api/assistant");
vi.mock("../api/notifications");

// The page once the notice, and the assistant's panel for it, have loaded.
async function shown(route = "/notifications/n-1") {
  renderAt(<NotificationDetailPage />, route, "/notifications/:id");
  await waitFor(() => expect(screen.queryByText("Loading...")).toBeNull());
}

// The value a definition list gives for a term.
function valueOf(term: string) {
  const dt = screen.getAllByText(term, { selector: "dt" })[0];
  return dt.nextElementSibling as HTMLElement;
}

// The page on the first notice, with a control that moves it to the next, as following a link
// from one notice to another does: the same page, given a new id.
function NextNotice() {
  const navigate = useNavigate();
  return (
    <button type="button" onClick={() => navigate("/notifications/n-2")}>
      Next notice
    </button>
  );
}

function movingFromFirstNotice() {
  render(
    <MemoryRouter initialEntries={["/notifications/n-1"]}>
      <Routes>
        <Route
          path="/notifications/:id"
          element={
            <>
              <NotificationDetailPage />
              <NextNotice />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

function pending<T>() {
  let resolve: (value: T) => void = () => undefined;
  let reject: (reason: unknown) => void = () => undefined;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  vi.mocked(getNotification).mockReset().mockResolvedValue(aNotification());
  vi.mocked(getEvaluation).mockReset().mockResolvedValue(null);
});

describe("a notice's page", () => {
  it("loads the notice named in the address, with the assistant's panel for it", async () => {
    await shown();
    expect(getNotification).toHaveBeenCalledWith("n-1");
    expect(getEvaluation).toHaveBeenCalledWith("n-1");
    expect(screen.getByRole("heading", { level: 1, name: "NOTSO-TEST-1" })).toBeTruthy();
    expect(screen.getByText("Test event class")).toBeTruthy();
    expect(screen.getByRole("link", { name: "← Back to notifications" }).getAttribute("href")).toBe(
      "/notifications",
    );
    expect(screen.getByRole("heading", { name: "Assistant" })).toBeTruthy();
  });

  it("says it is loading until the notice arrives", async () => {
    const answer = pending<NotificationDetail>();
    vi.mocked(getNotification).mockReturnValue(answer.promise);
    renderAt(<NotificationDetailPage />, "/notifications/n-1", "/notifications/:id");
    expect(screen.getByText("Loading...")).toBeTruthy();
    await act(async () => answer.resolve(aNotification()));
    expect(screen.queryByText("Loading...")).toBeNull();
  });

  it("shows every field, n/a where one is missing and text for a structured one", async () => {
    vi.mocked(getNotification).mockResolvedValue(
      aNotification({
        event_type: null,
        msg_type: "TACREP_NOTSO",
        data_mode: { mode: "TEST" } as unknown as string,
        udl_created_at: "2026-01-02T03:04:05Z",
        effective_until: null,
        sat_no: 90001,
        sat_ids: null,
        region: null,
      }),
    );
    await shown();
    expect(within(valueOf("Status")).getByText("OPEN").className).toBe("status-pill status-open");
    expect(valueOf("Event type").textContent).toBe("n/a");
    expect(valueOf("Message type").textContent).toBe("TACREP_NOTSO");
    expect(valueOf("Data mode").textContent).toBe('{"mode":"TEST"}');
    expect(valueOf("Notice").textContent).toBe("NOTSO-TEST-1");
    expect(valueOf("UDL created").textContent).toBe("2026-01-02 03:04:05");
    expect(valueOf("Effective until").textContent).toBe("n/a");
    expect(valueOf("Satellite numbers").textContent).toBe("90001");
    expect(valueOf("Region").textContent).toBe("n/a");
    expect(document.querySelector(".raw-json")?.textContent).toBe('{\n  "synthetic": true\n}');
  });

  it("shows a number as written, and the notice id, satellite IDs and status where they stand in", async () => {
    vi.mocked(getNotification).mockResolvedValue(
      aNotification({
        notso_identifier: null,
        notice_id: "NOTICE-ONLY",
        status: null,
        event_class: null,
        region: 7 as unknown as string,
        sat_ids: ["S1", "S2"],
      }),
    );
    await shown();
    expect(screen.getByRole("heading", { level: 1, name: "NOTICE-ONLY" })).toBeTruthy();
    expect(screen.queryByText("Test event class")).toBeNull();
    expect(valueOf("Status").textContent).toBe("n/a");
    expect(valueOf("Notice").textContent).toBe("NOTICE-ONLY");
    expect(valueOf("Region").textContent).toBe("7");
    expect(valueOf("Satellite numbers").textContent).toBe("S1, S2");
  });

  it("names a notice with neither identifier plainly, and says when no satellite is known", async () => {
    vi.mocked(getNotification).mockResolvedValue(
      aNotification({ notso_identifier: null, notice_id: null, sat_no: null, sat_ids: [] }),
    );
    await shown();
    expect(screen.getByRole("heading", { level: 1, name: "Notification" })).toBeTruthy();
    expect(valueOf("Satellite numbers").textContent).toBe("n/a");
  });

  it("links a safe source link into a new tab, and shows an unsafe one as text only", async () => {
    vi.mocked(getNotification).mockResolvedValue(
      aNotification({ notso_link: "https://example.invalid/notso/1" }),
    );
    await shown();
    const link = within(valueOf("Source link")).getByRole("link");
    expect(link.getAttribute("href")).toBe("https://example.invalid/notso/1");
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("never makes a link of a source link that is not plain web", async () => {
    vi.mocked(getNotification).mockResolvedValue(
      aNotification({ notso_link: "javascript:alert(1)" }),
    );
    await shown();
    const value = valueOf("Source link");
    expect(within(value).queryByRole("link")).toBeNull();
    expect(value.textContent).toBe("javascript:alert(1)");
  });

  it("leaves out the source link, the description and the artefacts when a notice has none", async () => {
    await shown();
    expect(screen.queryByText("Source link")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Event description" })).toBeNull();
    expect(screen.queryByRole("heading", { name: /Source artefacts/ })).toBeNull();
  });

  it("shows the description, and lists the artefacts, linking only the safe ones", async () => {
    vi.mocked(getNotification).mockResolvedValue(
      aNotification({
        description: "Synthetic description",
        raw: {
          msgBody: {
            NOTSO_Image_Metadata: JSON.stringify([
              {
                id: "a1",
                filename: "safe.png",
                caption: "Synthetic caption",
                url: "https://example.invalid/a.png",
              },
              { url: "https://example.invalid/b.png" },
              { id: "a3", filename: "unsafe.png", url: "javascript:alert(1)" },
              { id: "a4" },
            ]),
          },
        },
      }),
    );
    await shown();
    expect(screen.getByText("Synthetic description")).toBeTruthy();
    const list = screen.getByRole("heading", { name: "Source artefacts (4)" }).nextElementSibling!;
    const items = within(list as HTMLElement).getAllByRole("listitem");
    const safe = within(items[0]).getByRole("link", { name: "safe.png" });
    expect(safe.getAttribute("href")).toBe("https://example.invalid/a.png");
    expect(safe.getAttribute("rel")).toBe("noopener noreferrer");
    expect(items[0].textContent).toContain("· Synthetic caption");
    expect(
      within(items[1]).getByRole("link", { name: "https://example.invalid/b.png" }),
    ).toBeTruthy();
    expect(within(items[2]).queryByRole("link")).toBeNull();
    expect(items[2].textContent).toBe("unsafe.png");
    expect(items[3].textContent).toBe("(unnamed artefact)");
  });

  it("says when the notice does not exist, and when it could not load", async () => {
    vi.mocked(getNotification).mockRejectedValueOnce({ response: { status: 404 } });
    await shown();
    expect(screen.getByText("Notification not found.")).toBeTruthy();
  });

  it("says the notice failed to load for any other failure", async () => {
    for (const failure of [{ response: { status: 500 } }, new Error("offline"), null]) {
      vi.mocked(getNotification).mockRejectedValueOnce(failure);
      const view = renderAt(<NotificationDetailPage />, "/notifications/n-1", "/notifications/:id");
      expect(await screen.findByText("Failed to load notification.")).toBeTruthy();
      view.unmount();
    }
  });

  it("shows nothing when the server sends no notice", async () => {
    vi.mocked(getNotification).mockResolvedValue(null as unknown as NotificationDetail);
    await shown();
    expect(screen.queryByText("Loading...")).toBeNull();
    expect(screen.queryByRole("heading")).toBeNull();
  });

  it("asks for nothing where the address names no notice", async () => {
    renderAt(<NotificationDetailPage />, "/notifications", "/notifications");
    await act(async () => undefined);
    expect(getNotification).not.toHaveBeenCalled();
    expect(screen.getByText("Loading...")).toBeTruthy();
  });

  it("shows the notice it moved to, never a late answer about the one before", async () => {
    const late = pending<NotificationDetail>();
    vi.mocked(getNotification)
      .mockReturnValueOnce(late.promise)
      .mockResolvedValueOnce(aNotification({ id: "n-2", notso_identifier: "NOTSO-TEST-2" }));
    movingFromFirstNotice();
    fireEvent.click(screen.getByRole("button", { name: "Next notice" }));
    expect(await screen.findByRole("heading", { level: 1, name: "NOTSO-TEST-2" })).toBeTruthy();
    await act(async () => late.resolve(aNotification()));
    expect(screen.getByRole("heading", { level: 1, name: "NOTSO-TEST-2" })).toBeTruthy();
    expect(screen.queryByText("NOTSO-TEST-1")).toBeNull();
  });

  it("keeps loading the notice it moved to when the one before answers first", async () => {
    const late = pending<NotificationDetail>();
    const current = pending<NotificationDetail>();
    vi.mocked(getNotification)
      .mockReturnValueOnce(late.promise)
      .mockReturnValueOnce(current.promise);
    movingFromFirstNotice();
    fireEvent.click(screen.getByRole("button", { name: "Next notice" }));
    await act(async () => late.resolve(aNotification()));
    expect(screen.getByText("Loading...")).toBeTruthy();
    await act(async () =>
      current.resolve(aNotification({ id: "n-2", notso_identifier: "NOTSO-TEST-2" })),
    );
    expect(screen.getByRole("heading", { level: 1, name: "NOTSO-TEST-2" })).toBeTruthy();
  });

  it("never shows why the notice before could not load", async () => {
    const late = pending<NotificationDetail>();
    vi.mocked(getNotification)
      .mockReturnValueOnce(late.promise)
      .mockResolvedValueOnce(aNotification({ id: "n-2", notso_identifier: "NOTSO-TEST-2" }));
    movingFromFirstNotice();
    fireEvent.click(screen.getByRole("button", { name: "Next notice" }));
    await screen.findByRole("heading", { level: 1, name: "NOTSO-TEST-2" });
    await act(async () => late.reject({ response: { status: 404 } }));
    expect(screen.queryByText("Notification not found.")).toBeNull();
    expect(screen.getByRole("heading", { level: 1, name: "NOTSO-TEST-2" })).toBeTruthy();
  });
});
