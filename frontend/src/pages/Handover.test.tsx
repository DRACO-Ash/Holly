// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  addHandoverNote,
  decideThreadLink,
  deleteHandoverNote,
  getHandoverObjects,
  getHandoverStory,
} from "../api/handover";
import { renderAt } from "../test/render";
import type { HandoverObjectList, HandoverStory } from "../types";
import { aStory } from "../test/handover";
import Handover from "./Handover";

vi.mock("../api/handover");

function aList(overrides: Partial<HandoverObjectList> = {}): HandoverObjectList {
  return {
    window_hours: 120,
    window_start: "2026-01-01T12:00:00Z",
    generated_at: "2026-01-06T12:00:00Z",
    truncated: false,
    objects: [
      {
        sat_no: 90001,
        name: "TEST-SAT 1",
        kinds: ["Maneuver"],
        latest_at: "2026-01-05T09:00:00Z",
        events: 2,
        maneuvers: 1,
      },
      {
        sat_no: 90002,
        name: null,
        kinds: ["Photometric change"],
        latest_at: null,
        events: 1,
        maneuvers: 0,
      },
    ],
    ...overrides,
  };
}

function aFullStory(): HandoverStory {
  return aStory({
    notices: [
      {
        id: "n-1",
        event_key: "EVT-1",
        notice: "ABC-0001",
        event_class: "Maneuver / TEST-SAT 1 (90001)",
        kind: "Maneuver",
        status: "OPEN",
        udl_created_at: "2026-01-05T09:00:00Z",
        source: "JCO",
        udl_id: "UDL-1",
      },
    ],
    suggestions: [
      {
        thread_id: "t-9",
        event_key: "EVT-1",
        channel_name: "Example Channel",
        reason: "Mentions NOTSO ABC-0001",
        first_post: {
          post_id: "p-9",
          posted_at: "2026-01-05T10:00:00Z",
          author: "Example Analyst",
          message: "ABC-0001 burn seen",
        },
        matching_posts: 3,
      },
    ],
    timers: [
      {
        id: "timer-1",
        label: "Closest approach",
        target_time: "2026-01-06T03:40:00Z",
        event_key: "EVT-1",
      },
    ],
    notes: [
      {
        id: "note-1",
        author_id: "u-1",
        author: "example-lead",
        text: "Watch the approach.",
        created_at: "2026-01-05T12:30:00Z",
      },
    ],
  });
}

beforeEach(() => {
  vi.mocked(getHandoverObjects).mockReset().mockResolvedValue(aList());
  vi.mocked(getHandoverStory).mockReset().mockResolvedValue(aFullStory());
  vi.mocked(decideThreadLink).mockReset();
  vi.mocked(addHandoverNote).mockReset();
  vi.mocked(deleteHandoverNote).mockReset().mockResolvedValue();
});

afterEach(() => {
  vi.restoreAllMocks();
});

async function openFirstObject() {
  renderAt(<Handover />, "/handover");
  fireEvent.click(await screen.findByRole("button", { name: /TEST-SAT 1/ }));
  await screen.findByRole("heading", { name: /TEST-SAT 1/ });
}

describe("the Handover tab", () => {
  it("lists the objects with live events and asks for one to be picked", async () => {
    renderAt(<Handover />, "/handover");
    const rail = await screen.findByRole("navigation", { name: "Objects with live events" });
    expect(
      within(rail).getByText(/2 notices · 1 provider record · latest 05 Jan 09:00Z/),
    ).toBeTruthy();
    expect(within(rail).getByText("Unnamed object")).toBeTruthy();
    expect(within(rail).getByText(/1 notice · 0 provider records$/)).toBeTruthy();
    expect(screen.getByText("Pick an object to read its story.")).toBeTruthy();
  });

  it("finds an object by name, number or kind", async () => {
    renderAt(<Handover />, "/handover");
    const search = await screen.findByRole("searchbox", { name: "Find an object" });
    fireEvent.change(search, { target: { value: "photometric" } });
    expect(screen.queryByRole("button", { name: /TEST-SAT 1/ })).toBeNull();
    fireEvent.change(search, { target: { value: "nothing like it" } });
    expect(screen.getByText("No object matches.")).toBeTruthy();
  });

  it("says when no notice names an object, or the list is cut", async () => {
    vi.mocked(getHandoverObjects).mockResolvedValue(aList({ objects: [], truncated: true }));
    renderAt(<Handover />, "/handover");
    expect(
      await screen.findByText("No notice in the last 120 hours names an object."),
    ).toBeTruthy();
    expect(screen.getByText(/it shows the objects named by the newest/)).toBeTruthy();
  });

  it("says when the objects cannot be loaded", async () => {
    vi.mocked(getHandoverObjects).mockRejectedValue(new Error("down"));
    renderAt(<Handover />, "/handover");
    expect((await screen.findByRole("alert")).textContent).toMatch(/could not load the objects/);
  });

  it("tells a picked object's story with its sources, suggestions, timers and notes", async () => {
    await openFirstObject();
    expect(getHandoverStory).toHaveBeenCalledWith(90001);
    expect(screen.getByText("Maneuver · ABC-0001")).toBeTruthy();
    expect(screen.getByText("Source: NOTSO · UDL UDL-1")).toBeTruthy();
    expect(screen.getByText("Mentions NOTSO ABC-0001 · Example Channel")).toBeTruthy();
    expect(screen.getByText("and 2 more matching in this thread")).toBeTruthy();
    expect(screen.getByText("Closest approach")).toBeTruthy();
    expect(screen.getByText("Watch the approach.")).toBeTruthy();
  });

  it("says when the story is empty, or cut", async () => {
    vi.mocked(getHandoverStory).mockResolvedValue(aStory({ truncated: true, name: null }));
    renderAt(<Handover />, "/handover");
    fireEvent.click(await screen.findByRole("button", { name: /TEST-SAT 1/ }));
    expect(await screen.findByText("Nothing held about this object in the window.")).toBeTruthy();
    expect(screen.getByText(/it shows the newest of each kind/)).toBeTruthy();
    expect(screen.getByRole("heading", { name: /Unnamed object/ })).toBeTruthy();
  });

  it("confirms a suggested thread and reads the story again", async () => {
    vi.mocked(decideThreadLink).mockResolvedValue({
      thread_id: "t-9",
      event_key: "EVT-1",
      decision: "confirmed",
    });
    await openFirstObject();
    fireEvent.click(screen.getByRole("button", { name: "Confirm this thread" }));
    await waitFor(() =>
      expect(decideThreadLink).toHaveBeenCalledWith({
        thread_id: "t-9",
        event_key: "EVT-1",
        decision: "confirmed",
      }),
    );
    await waitFor(() => expect(getHandoverStory).toHaveBeenCalledTimes(2));
  });

  it("rejects a suggestion, and says so when saving fails", async () => {
    vi.mocked(decideThreadLink).mockRejectedValue(new Error("down"));
    await openFirstObject();
    fireEvent.click(screen.getByRole("button", { name: "Not this one" }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/could not save that/);
    expect(vi.mocked(decideThreadLink).mock.calls[0][0].decision).toBe("rejected");
  });

  it("adds a note, trimmed, and clears the box", async () => {
    vi.mocked(addHandoverNote).mockResolvedValue({
      id: "note-2",
      author_id: "u-1",
      author: "example-lead",
      text: "New note.",
      created_at: "2026-01-06T10:00:00Z",
    });
    await openFirstObject();
    const box = screen.getByLabelText<HTMLTextAreaElement>("Add a note to this object's story");
    const add = screen.getByRole<HTMLButtonElement>("button", { name: "Add note" });
    expect(add.disabled).toBe(true);
    fireEvent.change(box, { target: { value: "  New note.  " } });
    fireEvent.click(add);
    await waitFor(() => expect(addHandoverNote).toHaveBeenCalledWith(90001, "New note."));
    await waitFor(() => expect(box.value).toBe(""));
  });

  it("keeps the note's text when it cannot be saved", async () => {
    vi.mocked(addHandoverNote).mockRejectedValue(new Error("down"));
    await openFirstObject();
    const box = screen.getByLabelText<HTMLTextAreaElement>("Add a note to this object's story");
    fireEvent.change(box, { target: { value: "Keep me." } });
    fireEvent.submit(box.closest("form") as HTMLFormElement);
    expect((await screen.findByRole("alert")).textContent).toMatch(/could not save that/);
    expect(box.value).toBe("Keep me.");
  });

  it("deletes a note only once the analyst confirms", async () => {
    const confirm = vi
      .spyOn(globalThis, "confirm")
      .mockReturnValueOnce(false)
      .mockReturnValueOnce(true);
    await openFirstObject();
    fireEvent.click(screen.getByRole("button", { name: "Delete note" }));
    expect(deleteHandoverNote).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Delete note" }));
    await waitFor(() => expect(deleteHandoverNote).toHaveBeenCalledWith("note-1"));
    expect(confirm).toHaveBeenCalledTimes(2);
  });

  it("says when a story cannot be loaded, and drops a slower answer for another object", async () => {
    let answerFirst: (story: HandoverStory) => void = () => undefined;
    vi.mocked(getHandoverStory)
      .mockImplementationOnce(() => new Promise((resolve) => (answerFirst = resolve)))
      .mockRejectedValueOnce(new Error("down"));
    renderAt(<Handover />, "/handover");
    fireEvent.click(await screen.findByRole("button", { name: /TEST-SAT 1/ }));
    expect(screen.getByText("Loading the story...")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Unnamed object/ }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/could not load this object/);
    answerFirst(aFullStory());
    await waitFor(() => expect(screen.queryByText("Maneuver · ABC-0001")).toBeNull());
  });

  it("keeps the object picked during a save, and files a note on the object on screen", async () => {
    let finishDecision: () => void = () => undefined;
    vi.mocked(decideThreadLink).mockImplementation(
      () =>
        new Promise((resolve) => {
          finishDecision = () =>
            resolve({ thread_id: "t-9", event_key: "EVT-1", decision: "confirmed" });
        }),
    );
    vi.mocked(getHandoverStory).mockImplementation(async (satNo) =>
      satNo === 90001 ? aFullStory() : aStory({ sat_no: 90002, name: "OTHER-SAT" }),
    );
    vi.mocked(addHandoverNote).mockResolvedValue({
      id: "note-9",
      author_id: "u-1",
      author: "example-lead",
      text: "On B.",
      created_at: "2026-01-06T10:00:00Z",
    });
    await openFirstObject();
    fireEvent.click(screen.getByRole("button", { name: "Confirm this thread" }));
    fireEvent.click(screen.getByRole("button", { name: /Unnamed object/ }));
    await screen.findByRole("heading", { name: /OTHER-SAT/ });
    finishDecision();
    await waitFor(() => expect(getHandoverStory).toHaveBeenCalledTimes(2));
    expect(screen.getByRole("heading", { name: /OTHER-SAT/ })).toBeTruthy();
    const box = screen.getByLabelText<HTMLTextAreaElement>("Add a note to this object's story");
    fireEvent.change(box, { target: { value: "On B." } });
    fireEvent.click(screen.getByRole("button", { name: "Add note" }));
    await waitFor(() => expect(addHandoverNote).toHaveBeenCalledWith(90002, "On B."));
  });

  it("says nothing about a failed save once another object is on screen", async () => {
    let failDecision: () => void = () => undefined;
    vi.mocked(decideThreadLink).mockImplementation(
      () =>
        new Promise((_resolve, reject) => {
          failDecision = () => reject(new Error("down"));
        }),
    );
    vi.mocked(getHandoverStory).mockImplementation(async (satNo) =>
      satNo === 90001 ? aFullStory() : aStory({ sat_no: 90002, name: "OTHER-SAT" }),
    );
    await openFirstObject();
    fireEvent.click(screen.getByRole("button", { name: "Not this one" }));
    fireEvent.click(screen.getByRole("button", { name: /Unnamed object/ }));
    await screen.findByRole("heading", { name: /OTHER-SAT/ });
    failDecision();
    await waitFor(() =>
      expect((screen.getByRole("button", { name: "Add note" }) as HTMLButtonElement).disabled).toBe(
        true,
      ),
    );
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
