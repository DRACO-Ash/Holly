// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  createShiftNote,
  deleteShiftNote,
  downloadShiftExport,
  generateShiftSummary,
  getShiftSummary,
  listShiftDates,
  listShiftNotes,
  repolishShiftNote,
  updateShiftNote,
} from "../api/shift";
import { renderAt } from "../test/render";
import type { ShiftDateSummary, ShiftNote, ShiftNoteList, ShiftSummary } from "../types";
import ShiftLogPage from "./ShiftLog";

vi.mock("../api/shift");
// The timers panel needs the provider Layout mounts, and is tested on its own: here it is blank.
vi.mock("../components/EventTimersPanel", () => ({ default: () => null }));

// The page opens on today's shift by the UTC calendar, so each test holds the clock at midday.
const TODAY = "2026-01-05";
const ENTRY_HINT = "Type whatever you want, however you want. Claude will tidy it up.";

function aNote(overrides: Partial<ShiftNote> = {}): ShiftNote {
  return {
    id: "note-1",
    author_id: "user-1",
    shift_date: TODAY,
    raw_text: "synthetic raw note",
    polished_text: "Synthetic polished note.",
    polish_error: null,
    model: "test-model",
    created_at: "2026-01-05T08:15:30Z",
    updated_at: "2026-01-05T08:15:30Z",
    ...overrides,
  };
}

// An entry with no tidied text, which shows its raw words.
function aRawNote(overrides: Partial<ShiftNote> = {}): ShiftNote {
  return aNote({
    id: "note-2",
    raw_text: "synthetic second raw note",
    polished_text: null,
    model: null,
    created_at: "2026-01-05T09:30:00Z",
    updated_at: "2026-01-05T09:30:00Z",
    ...overrides,
  });
}

function aSummary(overrides: Partial<ShiftSummary> = {}): ShiftSummary {
  return {
    id: "summary-1",
    shift_date: TODAY,
    generated_by: "user-1",
    narrative: "Synthetic narrative of the shift.",
    source_note_ids: ["note-1"],
    model: "test-model",
    error: null,
    created_at: "2026-01-05T11:00:00Z",
    updated_at: "2026-01-05T11:00:00Z",
    ...overrides,
  };
}

function notesOf(items: ShiftNote[], shiftDate = TODAY): ShiftNoteList {
  return { items, shift_date: shiftDate };
}

function aShiftDate(shiftDate: string, noteCount: number, hasSummary = false): ShiftDateSummary {
  return { shift_date: shiftDate, note_count: noteCount, has_summary: hasSummary };
}

// A request the test answers by hand, to see the page while it is in flight.
function held<T>() {
  let resolve: (value: T) => void = () => undefined;
  const promise = new Promise<T>((settle) => {
    resolve = settle;
  });
  return { promise, resolve };
}

// A failed request, with the server's reason when one is given.
function refusal(detail?: string) {
  return { response: { data: detail === undefined ? {} : { detail } } };
}

async function shown() {
  renderAt(<ShiftLogPage />, "/shift-log");
  await waitFor(() => expect(screen.queryByText("Loading...")).toBeNull());
}

function dateInput() {
  return screen.getByLabelText("Shift date") as HTMLInputElement;
}

function entryBox() {
  return screen.getByPlaceholderText(ENTRY_HINT) as HTMLTextAreaElement;
}

function buttonNamed(name: string, scope: HTMLElement = document.body) {
  return within(scope).getByRole("button", { name }) as HTMLButtonElement;
}

// The timeline row that shows `text`.
function rowOf(text: string) {
  return screen.getByText(text).closest("li")!;
}

function editBox(row: HTMLElement) {
  return within(row).getByRole("textbox") as HTMLTextAreaElement;
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date("2026-01-05T12:00:00Z"));
  vi.mocked(listShiftNotes)
    .mockReset()
    .mockResolvedValue(notesOf([aNote()]));
  vi.mocked(getShiftSummary).mockReset().mockResolvedValue(null);
  vi.mocked(listShiftDates).mockReset().mockResolvedValue({ items: [] });
  vi.mocked(createShiftNote)
    .mockReset()
    .mockResolvedValue(aNote({ id: "note-3" }));
  vi.mocked(updateShiftNote).mockReset().mockResolvedValue(aNote());
  vi.mocked(repolishShiftNote).mockReset().mockResolvedValue(aNote());
  vi.mocked(deleteShiftNote).mockReset().mockResolvedValue();
  vi.mocked(generateShiftSummary).mockReset().mockResolvedValue(aSummary());
  vi.mocked(downloadShiftExport).mockReset().mockResolvedValue();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("the shift log page", () => {
  it("opens on today's UTC shift, asking for its entries, its narrative and 30 days of shifts", async () => {
    vi.mocked(listShiftNotes).mockResolvedValue(notesOf([aNote(), aRawNote()]));
    await shown();
    expect(dateInput().value).toBe(TODAY);
    expect(listShiftNotes).toHaveBeenCalledWith(TODAY);
    expect(getShiftSummary).toHaveBeenCalledWith(TODAY);
    expect(listShiftDates).toHaveBeenCalledWith(30);
    expect(screen.getByRole("heading", { name: "Timeline · 2" })).toBeTruthy();
    const [first, second] = screen.getAllByRole("listitem");
    expect(within(first).getByText("08:15:30Z")).toBeTruthy();
    expect(within(first).getByText("Synthetic polished note.")).toBeTruthy();
    expect(within(second).getByText("09:30:00Z")).toBeTruthy();
    expect(within(second).getByText("synthetic second raw note")).toBeTruthy();
    expect(screen.queryByText(/Polish failed/)).toBeNull();
    expect(screen.queryByText("No entries yet for this shift.")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Recent shifts" })).toBeNull();
    expect(screen.queryByText("Add at least one entry to generate a narrative.")).toBeNull();
    expect(buttonNamed("Generate").disabled).toBe(false);
  });

  it("says it is loading until the shift arrives, then that the shift has no entries yet", async () => {
    const notes = held<ShiftNoteList>();
    vi.mocked(listShiftNotes).mockReturnValue(notes.promise);
    renderAt(<ShiftLogPage />, "/shift-log");
    expect(screen.getByText("Loading...")).toBeTruthy();
    expect(screen.queryByText("No entries yet for this shift.")).toBeNull();
    notes.resolve(notesOf([]));
    expect(await screen.findByText("No entries yet for this shift.")).toBeTruthy();
    expect(screen.queryByText("Loading...")).toBeNull();
    expect(screen.getByRole("heading", { name: "Timeline · 0" })).toBeTruthy();
    expect(screen.getByText("Add at least one entry to generate a narrative.")).toBeTruthy();
    expect(buttonNamed("Generate").disabled).toBe(true);
  });

  it("shows the server's reason, or a fallback, when a shift cannot load", async () => {
    vi.mocked(listShiftNotes).mockRejectedValueOnce(refusal("Synthetic outage"));
    await shown();
    expect(screen.getByText("Synthetic outage")).toBeTruthy();
    vi.mocked(getShiftSummary).mockRejectedValueOnce(refusal());
    fireEvent.change(dateInput(), { target: { value: "2026-01-02" } });
    expect(await screen.findByText("Failed to load shift log.")).toBeTruthy();
    expect(screen.queryByText("Synthetic outage")).toBeNull();
    expect(screen.queryByText("Loading...")).toBeNull();
  });

  it("loads the shift for a picked date, and today's again when the date is cleared", async () => {
    await shown();
    vi.mocked(listShiftNotes).mockResolvedValueOnce(
      notesOf(
        [aNote({ id: "note-4", shift_date: "2026-01-02", polished_text: "Synthetic older note." })],
        "2026-01-02",
      ),
    );
    fireEvent.change(dateInput(), { target: { value: "2026-01-02" } });
    expect(await screen.findByText("Synthetic older note.")).toBeTruthy();
    expect(listShiftNotes).toHaveBeenLastCalledWith("2026-01-02");
    expect(getShiftSummary).toHaveBeenLastCalledWith("2026-01-02");
    expect(screen.queryByText("Synthetic polished note.")).toBeNull();
    fireEvent.change(dateInput(), { target: { value: "" } });
    expect(dateInput().value).toBe(TODAY);
    expect(await screen.findByText("Synthetic polished note.")).toBeTruthy();
    expect(listShiftNotes).toHaveBeenLastCalledWith(TODAY);
    expect(listShiftDates).toHaveBeenCalledTimes(1);
  });

  it("lists recent shifts as Today, Yesterday or a short date, with counts, and opens one", async () => {
    vi.mocked(listShiftDates).mockResolvedValue({
      items: [aShiftDate(TODAY, 1, true), aShiftDate("2026-01-04", 2), aShiftDate("2026-01-02", 0)],
    });
    await shown();
    expect(screen.getByRole("heading", { name: "Recent shifts" })).toBeTruthy();
    const today = screen.getByTitle(TODAY);
    expect(today.className).toBe("shift-recent-pill active");
    expect(within(today).getByText("Today")).toBeTruthy();
    expect(within(today).getByText("1 entry")).toBeTruthy();
    expect(within(today).getByText("summary")).toBeTruthy();
    const yesterday = screen.getByTitle("2026-01-04");
    expect(yesterday.className).toBe("shift-recent-pill");
    expect(within(yesterday).getByText("Yesterday")).toBeTruthy();
    expect(within(yesterday).getByText("2 entries")).toBeTruthy();
    expect(within(yesterday).queryByText("summary")).toBeNull();
    // Further back, a short date in the analyst's locale, on the UTC calendar.
    const shortUtcDate = new Intl.DateTimeFormat(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      timeZone: "UTC",
    });
    const older = screen.getByTitle("2026-01-02");
    expect(within(older).getByText(shortUtcDate.format(Date.UTC(2026, 0, 2)))).toBeTruthy();
    expect(within(older).getByText("0 entries")).toBeTruthy();
    fireEvent.click(yesterday);
    expect(dateInput().value).toBe("2026-01-04");
    expect(yesterday.className).toBe("shift-recent-pill active");
    expect(today.className).toBe("shift-recent-pill");
    expect(listShiftNotes).toHaveBeenLastCalledWith("2026-01-04");
    expect(getShiftSummary).toHaveBeenLastCalledWith("2026-01-04");
    await waitFor(() => expect(screen.queryByText("Loading...")).toBeNull());
  });

  it("carries on without the recent shifts when they cannot load", async () => {
    vi.mocked(listShiftDates).mockRejectedValue(new Error("Synthetic outage"));
    await shown();
    expect(screen.queryByRole("heading", { name: "Recent shifts" })).toBeNull();
    expect(screen.queryByText("Synthetic outage")).toBeNull();
    expect(screen.getByText("Synthetic polished note.")).toBeTruthy();
  });

  it("adds a trimmed entry to the shown shift, clears the box and refreshes the recent shifts", async () => {
    await shown();
    expect(screen.getByText("0 chars")).toBeTruthy();
    expect(buttonNamed("Add to log").disabled).toBe(true);
    fireEvent.change(entryBox(), { target: { value: "  Synthetic new entry  " } });
    expect(screen.getByText("23 chars")).toBeTruthy();
    const saving = held<ShiftNote>();
    vi.mocked(createShiftNote).mockReturnValueOnce(saving.promise);
    fireEvent.click(buttonNamed("Add to log"));
    expect(createShiftNote).toHaveBeenCalledWith("Synthetic new entry", TODAY);
    expect(buttonNamed("Saving...").disabled).toBe(true);
    expect(entryBox().disabled).toBe(true);
    saving.resolve(
      aNote({
        id: "note-3",
        raw_text: "Synthetic new entry",
        polished_text: "Synthetic new entry, tidied.",
        created_at: "2026-01-05T10:00:00Z",
      }),
    );
    expect(await screen.findByText("Synthetic new entry, tidied.")).toBeTruthy();
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(within(rows[1]).getByText("Synthetic new entry, tidied.")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Timeline · 2" })).toBeTruthy();
    expect(entryBox().value).toBe("");
    expect(entryBox().disabled).toBe(false);
    expect(screen.getByText("0 chars")).toBeTruthy();
    expect(listShiftDates).toHaveBeenCalledTimes(2);
  });

  it("never sends a blank entry", async () => {
    await shown();
    fireEvent.change(entryBox(), { target: { value: "   " } });
    expect(screen.getByText("3 chars")).toBeTruthy();
    const add = buttonNamed("Add to log");
    expect(add.disabled).toBe(true);
    fireEvent.submit(add.closest("form")!);
    expect(createShiftNote).not.toHaveBeenCalled();
    expect(entryBox().value).toBe("   ");
  });

  it("keeps the draft and says why when an entry cannot be saved", async () => {
    await shown();
    fireEvent.change(entryBox(), { target: { value: "Synthetic entry" } });
    vi.mocked(createShiftNote).mockRejectedValueOnce(refusal("Synthetic refusal"));
    fireEvent.click(buttonNamed("Add to log"));
    expect(await screen.findByText("Synthetic refusal")).toBeTruthy();
    expect(entryBox().value).toBe("Synthetic entry");
    vi.mocked(createShiftNote).mockRejectedValueOnce(refusal());
    fireEvent.click(buttonNamed("Add to log"));
    expect(await screen.findByText("Failed to save note.")).toBeTruthy();
    expect(screen.queryByText("Synthetic refusal")).toBeNull();
    expect(entryBox().value).toBe("Synthetic entry");
    expect(buttonNamed("Add to log").disabled).toBe(false);
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(listShiftDates).toHaveBeenCalledTimes(1);
  });

  it("composes the narrative for the shown shift, then offers to compose it again", async () => {
    await shown();
    const composing = held<ShiftSummary>();
    vi.mocked(generateShiftSummary).mockReturnValueOnce(composing.promise);
    fireEvent.click(buttonNamed("Generate"));
    expect(generateShiftSummary).toHaveBeenCalledWith(TODAY);
    expect(buttonNamed("Composing...").disabled).toBe(true);
    composing.resolve(aSummary());
    expect(await screen.findByText("Synthetic narrative of the shift.")).toBeTruthy();
    expect(screen.getByText("test-model · generated 2026-01-05T11:00:00.000Z")).toBeTruthy();
    expect(screen.queryByText(/Generation error/)).toBeNull();
    expect(buttonNamed("Regenerate").disabled).toBe(false);
    expect(listShiftDates).toHaveBeenCalledTimes(2);
  });

  it("shows a stored narrative with the error that came with it", async () => {
    vi.mocked(getShiftSummary).mockResolvedValue(aSummary({ error: "Synthetic model fault" }));
    await shown();
    expect(screen.getByText("Synthetic narrative of the shift.")).toBeTruthy();
    expect(screen.getByText("Generation error: Synthetic model fault")).toBeTruthy();
    expect(buttonNamed("Regenerate").disabled).toBe(false);
  });

  it("says why a narrative could not be composed", async () => {
    await shown();
    vi.mocked(generateShiftSummary).mockRejectedValueOnce(refusal("Synthetic model unavailable"));
    fireEvent.click(buttonNamed("Generate"));
    expect(await screen.findByText("Synthetic model unavailable")).toBeTruthy();
    vi.mocked(generateShiftSummary).mockRejectedValueOnce(refusal());
    fireEvent.click(buttonNamed("Generate"));
    expect(await screen.findByText("Failed to generate summary.")).toBeTruthy();
    expect(screen.queryByText("Synthetic model unavailable")).toBeNull();
    expect(buttonNamed("Generate").disabled).toBe(false);
    expect(listShiftDates).toHaveBeenCalledTimes(1);
  });

  it("exports the shown shift as Markdown or HTML", async () => {
    await shown();
    fireEvent.click(buttonNamed("Export .md"));
    expect(downloadShiftExport).toHaveBeenLastCalledWith(TODAY, "md");
    fireEvent.change(dateInput(), { target: { value: "2026-01-02" } });
    await waitFor(() => expect(screen.queryByText("Loading...")).toBeNull());
    fireEvent.click(buttonNamed("Export .html"));
    expect(downloadShiftExport).toHaveBeenLastCalledWith("2026-01-02", "html");
    expect(downloadShiftExport).toHaveBeenCalledTimes(2);
  });

  it("says why an export failed, and clears the message when the next export starts", async () => {
    await shown();
    vi.mocked(downloadShiftExport).mockRejectedValueOnce(refusal("Synthetic export refusal"));
    fireEvent.click(buttonNamed("Export .html"));
    expect(await screen.findByText("Synthetic export refusal")).toBeTruthy();
    vi.mocked(downloadShiftExport).mockRejectedValueOnce(refusal());
    fireEvent.click(buttonNamed("Export .md"));
    expect(await screen.findByText("Export failed.")).toBeTruthy();
    fireEvent.click(buttonNamed("Export .md"));
    expect(screen.queryByText("Export failed.")).toBeNull();
    expect(downloadShiftExport).toHaveBeenCalledTimes(3);
  });
});

describe("an entry in the timeline", () => {
  it("shows its raw words on request, setting them aside while it is edited", async () => {
    await shown();
    const row = rowOf("Synthetic polished note.");
    expect(within(row).queryByText("synthetic raw note")).toBeNull();
    fireEvent.click(buttonNamed("Show raw", row));
    expect(within(row).getByText("Raw input:")).toBeTruthy();
    expect(within(row).getByText("synthetic raw note")).toBeTruthy();
    fireEvent.click(buttonNamed("Edit", row));
    expect(within(row).queryByText("Raw input:")).toBeNull();
    fireEvent.click(buttonNamed("Cancel", row));
    expect(within(row).getByText("Raw input:")).toBeTruthy();
    fireEvent.click(buttonNamed("Hide raw", row));
    expect(within(row).queryByText("Raw input:")).toBeNull();
    expect(within(row).queryByText("synthetic raw note")).toBeNull();
  });

  it("shows its raw words, with the reason, when they could not be tidied", async () => {
    vi.mocked(listShiftNotes).mockResolvedValue(
      notesOf([aRawNote({ polish_error: "Synthetic polish fault" })]),
    );
    await shown();
    const row = rowOf("synthetic second raw note");
    expect(
      within(row).getByText("Polish failed: Synthetic polish fault. Showing raw text."),
    ).toBeTruthy();
  });

  it("is edited in place and saved, leaving the other entries as they were", async () => {
    vi.mocked(listShiftNotes).mockResolvedValue(notesOf([aNote(), aRawNote()]));
    await shown();
    const row = rowOf("Synthetic polished note.");
    fireEvent.click(buttonNamed("Edit", row));
    expect(editBox(row).value).toBe("Synthetic polished note.");
    expect(within(row).queryByRole("button", { name: "Edit" })).toBeNull();
    fireEvent.change(editBox(row), { target: { value: "Synthetic edited note." } });
    const saving = held<ShiftNote>();
    vi.mocked(updateShiftNote).mockReturnValueOnce(saving.promise);
    fireEvent.click(buttonNamed("Save", row));
    expect(updateShiftNote).toHaveBeenCalledWith("note-1", "Synthetic edited note.");
    for (const name of ["Saving...", "Cancel", "Show raw", "Re-polish", "Delete"]) {
      expect(buttonNamed(name, row).disabled, name).toBe(true);
    }
    saving.resolve(aNote({ polished_text: "Synthetic edited note." }));
    expect(await within(row).findByText("Synthetic edited note.")).toBeTruthy();
    expect(within(row).queryByRole("textbox")).toBeNull();
    expect(buttonNamed("Edit", row).disabled).toBe(false);
    expect(screen.getByText("synthetic second raw note")).toBeTruthy();
  });

  it("drops an edit on Cancel, putting back the text it showed", async () => {
    vi.mocked(listShiftNotes).mockResolvedValue(notesOf([aNote(), aRawNote()]));
    await shown();
    for (const text of ["Synthetic polished note.", "synthetic second raw note"]) {
      const row = rowOf(text);
      fireEvent.click(buttonNamed("Edit", row));
      expect(editBox(row).value).toBe(text);
      fireEvent.change(editBox(row), { target: { value: "Synthetic discarded edit" } });
      fireEvent.click(buttonNamed("Cancel", row));
      expect(within(row).getByText(text)).toBeTruthy();
      fireEvent.click(buttonNamed("Edit", row));
      expect(editBox(row).value).toBe(text);
    }
    expect(updateShiftNote).not.toHaveBeenCalled();
  });

  it("stays open, and the page says why, when an edit cannot be saved", async () => {
    await shown();
    const row = rowOf("Synthetic polished note.");
    fireEvent.click(buttonNamed("Edit", row));
    fireEvent.change(editBox(row), { target: { value: "Synthetic edited note." } });
    vi.mocked(updateShiftNote).mockRejectedValueOnce(refusal("Synthetic conflict"));
    fireEvent.click(buttonNamed("Save", row));
    expect(await screen.findByText("Synthetic conflict")).toBeTruthy();
    vi.mocked(updateShiftNote).mockRejectedValueOnce(refusal());
    fireEvent.click(buttonNamed("Save", row));
    expect(await screen.findByText("Failed to save.")).toBeTruthy();
    expect(editBox(row).value).toBe("Synthetic edited note.");
    expect(buttonNamed("Save", row).disabled).toBe(false);
  });

  it("is re-polished, showing the new text and editing from it", async () => {
    await shown();
    const row = rowOf("Synthetic polished note.");
    const polishing = held<ShiftNote>();
    vi.mocked(repolishShiftNote).mockReturnValueOnce(polishing.promise);
    fireEvent.click(buttonNamed("Re-polish", row));
    expect(repolishShiftNote).toHaveBeenCalledWith("note-1");
    for (const name of ["Show raw", "Edit", "Re-polish", "Delete"]) {
      expect(buttonNamed(name, row).disabled, name).toBe(true);
    }
    polishing.resolve(aNote({ polished_text: "Synthetic re-polished note." }));
    expect(await within(row).findByText("Synthetic re-polished note.")).toBeTruthy();
    fireEvent.click(buttonNamed("Edit", row));
    expect(editBox(row).value).toBe("Synthetic re-polished note.");
  });

  it("falls back to its raw words when a re-polish cannot tidy them", async () => {
    await shown();
    const row = rowOf("Synthetic polished note.");
    vi.mocked(repolishShiftNote).mockResolvedValueOnce(
      aNote({ polished_text: null, polish_error: "Synthetic polish fault" }),
    );
    fireEvent.click(buttonNamed("Re-polish", row));
    expect(
      await within(row).findByText("Polish failed: Synthetic polish fault. Showing raw text."),
    ).toBeTruthy();
    expect(within(row).getByText("synthetic raw note")).toBeTruthy();
    fireEvent.click(buttonNamed("Edit", row));
    expect(editBox(row).value).toBe("synthetic raw note");
  });

  it("keeps its text, and the page says why, when a re-polish fails", async () => {
    await shown();
    const row = rowOf("Synthetic polished note.");
    vi.mocked(repolishShiftNote).mockRejectedValueOnce(refusal("Synthetic model unavailable"));
    fireEvent.click(buttonNamed("Re-polish", row));
    expect(await screen.findByText("Synthetic model unavailable")).toBeTruthy();
    vi.mocked(repolishShiftNote).mockRejectedValueOnce(refusal());
    fireEvent.click(buttonNamed("Re-polish", row));
    expect(await screen.findByText("Re-polish failed.")).toBeTruthy();
    expect(within(row).getByText("Synthetic polished note.")).toBeTruthy();
    expect(buttonNamed("Re-polish", row).disabled).toBe(false);
  });

  it("is deleted only once the analyst confirms, then the recent shifts refresh", async () => {
    await shown();
    const row = rowOf("Synthetic polished note.");
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    fireEvent.click(buttonNamed("Delete", row));
    expect(confirm).toHaveBeenCalledWith("Delete this entry?");
    expect(deleteShiftNote).not.toHaveBeenCalled();
    expect(buttonNamed("Delete", row).disabled).toBe(false);
    confirm.mockReturnValue(true);
    const deleting = held<void>();
    vi.mocked(deleteShiftNote).mockReturnValueOnce(deleting.promise);
    fireEvent.click(buttonNamed("Delete", row));
    expect(deleteShiftNote).toHaveBeenCalledWith("note-1");
    expect(buttonNamed("Delete", row).disabled).toBe(true);
    deleting.resolve();
    expect(await screen.findByText("No entries yet for this shift.")).toBeTruthy();
    expect(screen.queryByText("Synthetic polished note.")).toBeNull();
    expect(screen.getByRole("heading", { name: "Timeline · 0" })).toBeTruthy();
    expect(listShiftDates).toHaveBeenCalledTimes(2);
  });

  it("stays, and the page says why, when it cannot be deleted", async () => {
    await shown();
    const row = rowOf("Synthetic polished note.");
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(deleteShiftNote).mockRejectedValueOnce(refusal("Synthetic refusal"));
    fireEvent.click(buttonNamed("Delete", row));
    expect(await screen.findByText("Synthetic refusal")).toBeTruthy();
    vi.mocked(deleteShiftNote).mockRejectedValueOnce(refusal());
    fireEvent.click(buttonNamed("Delete", row));
    expect(await screen.findByText("Delete failed.")).toBeTruthy();
    expect(within(row).getByText("Synthetic polished note.")).toBeTruthy();
    expect(buttonNamed("Delete", row).disabled).toBe(false);
    expect(listShiftDates).toHaveBeenCalledTimes(1);
  });
});
