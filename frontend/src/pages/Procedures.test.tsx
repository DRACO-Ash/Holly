// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  deleteProcedure,
  downloadProcedure,
  getProcedure,
  listProcedures,
  uploadProcedure,
} from "../api/procedures";
import { renderAt } from "../test/render";
import type { Procedure, ProcedureContent, ProcedurePage } from "../types";
import ProceduresPage from "./Procedures";

vi.mock("../api/procedures");

function aProcedure(overrides: Partial<Procedure> = {}): Procedure {
  return {
    id: "proc-1",
    name: "Synthetic procedure",
    description: "Synthetic description",
    filename: "synthetic-procedure.md",
    content_type: "text/markdown",
    size_bytes: 512,
    file_hash: "synthetic-hash-1",
    uploaded_by: "user-1",
    created_at: "2026-01-02T03:04:05Z",
    updated_at: "2026-01-02T03:04:05Z",
    ...overrides,
  };
}

// A second procedure, with no description and a file the server cannot preview.
const second = aProcedure({
  id: "proc-2",
  name: "Second synthetic procedure",
  description: null,
  filename: "second-synthetic-procedure.pdf",
  content_type: "application/pdf",
  size_bytes: 2_621_440,
  file_hash: "synthetic-hash-2",
  created_at: "2026-01-03T05:06:07+01:00",
  updated_at: "2026-01-03T05:06:07+01:00",
});

function itsContent(overrides: Partial<ProcedureContent> = {}): ProcedureContent {
  return {
    ...aProcedure(),
    content: "Synthetic step one.",
    content_truncated: false,
    ...overrides,
  };
}

function pageOf(items: Procedure[]): ProcedurePage {
  return { items, total: items.length };
}

function aFile(): File {
  return new File(["Synthetic step one."], "synthetic-procedure.md", { type: "text/markdown" });
}

// A promise the test settles itself, to hold the page while it waits.
function deferred<T>() {
  let resolve: (value: T) => void = () => undefined;
  const promise = new Promise<T>((settle) => {
    resolve = settle;
  });
  return { promise, resolve };
}

async function shown() {
  const view = renderAt(<ProceduresPage />, "/procedures");
  await waitFor(() => expect(screen.queryByText("Loading...")).toBeNull());
  return view;
}

function rowOf(name: string): HTMLElement {
  return within(screen.getByRole("table")).getByText(name).closest("tr")!;
}

function inRow(name: string, action: string): HTMLElement {
  return within(rowOf(name)).getByRole("button", { name: action });
}

function openCard(): HTMLElement {
  return screen.getByRole("button", { name: "Close" }).closest("section")!;
}

function uploadButton(): HTMLButtonElement {
  return screen.getByRole("button", { name: "Upload" }) as HTMLButtonElement;
}

function fillIn(name: string, description: string, file: File | null) {
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: name } });
  fireEvent.change(screen.getByLabelText("Description (optional)"), {
    target: { value: description },
  });
  fireEvent.change(screen.getByLabelText("File"), { target: { files: file ? [file] : [] } });
}

// jsdom keeps no real file list behind a test's File, so its form validation would refuse a
// click on Upload; submit the form the button belongs to instead.
function submitUpload() {
  fireEvent.submit(screen.getByLabelText("Name").closest("form")!);
}

beforeEach(() => {
  vi.mocked(listProcedures)
    .mockReset()
    .mockResolvedValue(pageOf([aProcedure()]));
  vi.mocked(getProcedure).mockReset().mockResolvedValue(itsContent());
  vi.mocked(uploadProcedure).mockReset().mockResolvedValue(aProcedure());
  vi.mocked(downloadProcedure).mockReset().mockResolvedValue();
  vi.mocked(deleteProcedure).mockReset().mockResolvedValue();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("the procedures page", () => {
  it("lists each procedure with its description, file, size and upload time in UTC", async () => {
    vi.mocked(listProcedures).mockResolvedValue(pageOf([aProcedure(), second]));
    await shown();
    expect(listProcedures).toHaveBeenCalledTimes(1);
    expect(listProcedures).toHaveBeenCalledWith();
    const first = rowOf("Synthetic procedure");
    expect(within(first).getByText("Synthetic description")).toBeTruthy();
    expect(within(first).getByText("synthetic-procedure.md")).toBeTruthy();
    expect(within(first).getByText("512 B")).toBeTruthy();
    expect(within(first).getByText("2026-01-02 03:04:05")).toBeTruthy();
    for (const action of ["View", "Download", "Delete"]) {
      expect(within(first).getByRole("button", { name: action })).toBeTruthy();
    }
    const other = rowOf("Second synthetic procedure");
    expect(within(other).getAllByRole("cell")[0].textContent).toBe("Second synthetic procedure");
    expect(within(other).getByText("2.50 MB")).toBeTruthy();
    expect(within(other).getByText("2026-01-03 04:06:07")).toBeTruthy();
    expect(screen.queryByText("No procedures uploaded yet.")).toBeNull();
  });

  it("gives sizes in bytes, kilobytes or megabytes", async () => {
    vi.mocked(listProcedures).mockResolvedValue(
      pageOf([
        aProcedure({ id: "proc-1", name: "Synthetic 1023 bytes", size_bytes: 1023 }),
        aProcedure({ id: "proc-2", name: "Synthetic 1024 bytes", size_bytes: 1024 }),
        aProcedure({ id: "proc-3", name: "Synthetic 1536 bytes", size_bytes: 1536 }),
        aProcedure({ id: "proc-4", name: "Synthetic 1048576 bytes", size_bytes: 1_048_576 }),
      ]),
    );
    await shown();
    expect(within(rowOf("Synthetic 1023 bytes")).getByText("1023 B")).toBeTruthy();
    expect(within(rowOf("Synthetic 1024 bytes")).getByText("1.0 kB")).toBeTruthy();
    expect(within(rowOf("Synthetic 1536 bytes")).getByText("1.5 kB")).toBeTruthy();
    expect(within(rowOf("Synthetic 1048576 bytes")).getByText("1.00 MB")).toBeTruthy();
  });

  it("says when nothing has been uploaded, but not while the list is loading", async () => {
    const answer = deferred<ProcedurePage>();
    vi.mocked(listProcedures).mockReturnValueOnce(answer.promise);
    renderAt(<ProceduresPage />, "/procedures");
    expect(screen.getByText("Loading...")).toBeTruthy();
    expect(screen.queryByText("No procedures uploaded yet.")).toBeNull();
    answer.resolve(pageOf([]));
    expect(await screen.findByText("No procedures uploaded yet.")).toBeTruthy();
    expect(screen.queryByText("Loading...")).toBeNull();
  });

  it("shows the server's reason when the list cannot load", async () => {
    vi.mocked(listProcedures).mockRejectedValue({ response: { data: { detail: "No access" } } });
    await shown();
    expect(screen.getByText("No access")).toBeTruthy();
  });

  it("says the list failed to load when the server gives no reason", async () => {
    vi.mocked(listProcedures).mockRejectedValue({});
    await shown();
    expect(screen.getByText("Failed to load procedures.")).toBeTruthy();
  });

  it("uploads a procedure with its name and description trimmed, then clears the form and reloads", async () => {
    vi.mocked(listProcedures).mockResolvedValueOnce(pageOf([]));
    await shown();
    const upload = deferred<Procedure>();
    vi.mocked(uploadProcedure).mockReturnValueOnce(upload.promise);
    const file = aFile();
    fillIn("  Synthetic procedure  ", "  Synthetic description  ", file);
    const cleared = vi.spyOn(screen.getByLabelText("File") as HTMLInputElement, "value", "set");
    expect(uploadButton().disabled).toBe(false);
    submitUpload();
    expect(uploadProcedure).toHaveBeenCalledWith(
      "Synthetic procedure",
      "Synthetic description",
      file,
    );
    const uploading = screen.getByRole("button", { name: "Uploading..." }) as HTMLButtonElement;
    expect(uploading.disabled).toBe(true);
    upload.resolve(aProcedure());
    await screen.findByRole("button", { name: "Upload" });
    expect(rowOf("Synthetic procedure")).toBeTruthy();
    expect(listProcedures).toHaveBeenCalledTimes(2);
    expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("");
    expect((screen.getByLabelText("Description (optional)") as HTMLInputElement).value).toBe("");
    expect(cleared).toHaveBeenCalledWith("");
    expect(uploadButton().disabled).toBe(true);
  });

  it("sends no description when it is left blank", async () => {
    await shown();
    const file = aFile();
    fillIn("Synthetic procedure", "   ", file);
    submitUpload();
    expect(uploadProcedure).toHaveBeenCalledWith("Synthetic procedure", null, file);
    await screen.findByRole("button", { name: "Upload" });
  });

  it("keeps Upload disabled, and sends nothing, until there is both a name and a file", async () => {
    await shown();
    expect(uploadButton().disabled).toBe(true);
    submitUpload();
    fillIn("   ", "", aFile());
    expect(uploadButton().disabled).toBe(true);
    submitUpload();
    fillIn("Synthetic procedure", "", null);
    expect(uploadButton().disabled).toBe(true);
    submitUpload();
    expect(uploadProcedure).not.toHaveBeenCalled();
    fillIn("Synthetic procedure", "", aFile());
    expect(uploadButton().disabled).toBe(false);
  });

  it("shows why an upload failed, or that it failed, and keeps the form for another try", async () => {
    await shown();
    const file = aFile();
    fillIn("Synthetic procedure", "Synthetic description", file);
    vi.mocked(uploadProcedure).mockRejectedValueOnce({
      response: { data: { detail: "Synthetic upload refusal" } },
    });
    submitUpload();
    expect(await screen.findByText("Synthetic upload refusal")).toBeTruthy();
    expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("Synthetic procedure");
    expect(uploadButton().disabled).toBe(false);
    vi.mocked(uploadProcedure).mockRejectedValueOnce({});
    submitUpload();
    expect(await screen.findByText("Upload failed.")).toBeTruthy();
    expect(screen.queryByText("Synthetic upload refusal")).toBeNull();
    expect(uploadProcedure).toHaveBeenCalledTimes(2);
    expect(uploadProcedure).toHaveBeenLastCalledWith(
      "Synthetic procedure",
      "Synthetic description",
      file,
    );
    expect(listProcedures).toHaveBeenCalledTimes(1);
  });

  it("downloads a procedure under its file name", async () => {
    vi.mocked(listProcedures).mockResolvedValue(pageOf([aProcedure(), second]));
    await shown();
    fireEvent.click(inRow("Second synthetic procedure", "Download"));
    expect(downloadProcedure).toHaveBeenCalledTimes(1);
    expect(downloadProcedure).toHaveBeenCalledWith("proc-2", "second-synthetic-procedure.pdf");
  });

  it("shows why a download failed, or that it failed, and clears that when one works", async () => {
    await shown();
    const download = inRow("Synthetic procedure", "Download");
    vi.mocked(downloadProcedure).mockRejectedValueOnce({
      response: { data: { detail: "Synthetic download refusal" } },
    });
    fireEvent.click(download);
    expect(await screen.findByText("Synthetic download refusal")).toBeTruthy();
    vi.mocked(downloadProcedure).mockRejectedValueOnce({});
    fireEvent.click(download);
    expect(await screen.findByText("Download failed.")).toBeTruthy();
    fireEvent.click(download);
    expect(screen.queryByText("Download failed.")).toBeNull();
    expect(downloadProcedure).toHaveBeenCalledTimes(3);
  });

  it("asks before deleting, and deletes nothing when the analyst declines", async () => {
    await shown();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    fireEvent.click(inRow("Synthetic procedure", "Delete"));
    expect(confirm).toHaveBeenCalledWith("Delete this procedure? This cannot be undone.");
    expect(deleteProcedure).not.toHaveBeenCalled();
    expect(listProcedures).toHaveBeenCalledTimes(1);
    expect(rowOf("Synthetic procedure")).toBeTruthy();
  });

  it("deletes a procedure once confirmed, then reloads the list", async () => {
    vi.mocked(listProcedures)
      .mockResolvedValueOnce(pageOf([aProcedure(), second]))
      .mockResolvedValueOnce(pageOf([second]));
    await shown();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    fireEvent.click(inRow("Synthetic procedure", "Delete"));
    expect(deleteProcedure).toHaveBeenCalledWith("proc-1");
    await waitFor(() => expect(screen.queryByText("Synthetic procedure")).toBeNull());
    expect(listProcedures).toHaveBeenCalledTimes(2);
    expect(rowOf("Second synthetic procedure")).toBeTruthy();
  });

  it("closes the open procedure when that one is deleted, and only then", async () => {
    vi.mocked(listProcedures)
      .mockResolvedValueOnce(pageOf([aProcedure(), second]))
      .mockResolvedValueOnce(pageOf([aProcedure()]))
      .mockResolvedValueOnce(pageOf([]));
    await shown();
    fireEvent.click(inRow("Synthetic procedure", "View"));
    await screen.findByRole("heading", { name: "Synthetic procedure" });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    fireEvent.click(inRow("Second synthetic procedure", "Delete"));
    await waitFor(() => expect(screen.queryByText("Second synthetic procedure")).toBeNull());
    expect(screen.getByRole("heading", { name: "Synthetic procedure" })).toBeTruthy();
    fireEvent.click(inRow("Synthetic procedure", "Delete"));
    expect(await screen.findByText("No procedures uploaded yet.")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Synthetic procedure" })).toBeNull();
    expect(vi.mocked(deleteProcedure).mock.calls).toEqual([["proc-2"], ["proc-1"]]);
  });

  it("shows why a delete failed, or that it failed", async () => {
    await shown();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const remove = inRow("Synthetic procedure", "Delete");
    vi.mocked(deleteProcedure).mockRejectedValueOnce({
      response: { data: { detail: "Synthetic delete refusal" } },
    });
    fireEvent.click(remove);
    expect(await screen.findByText("Synthetic delete refusal")).toBeTruthy();
    vi.mocked(deleteProcedure).mockRejectedValueOnce({});
    fireEvent.click(remove);
    expect(await screen.findByText("Delete failed.")).toBeTruthy();
    expect(listProcedures).toHaveBeenCalledTimes(1);
    expect(rowOf("Synthetic procedure")).toBeTruthy();
  });

  it("opens a procedure's text, saying so while it loads, and closes it", async () => {
    await shown();
    const answer = deferred<ProcedureContent>();
    vi.mocked(getProcedure).mockReturnValueOnce(answer.promise);
    fireEvent.click(inRow("Synthetic procedure", "View"));
    expect(getProcedure).toHaveBeenCalledWith("proc-1");
    expect(screen.getByText("Loading procedure...")).toBeTruthy();
    answer.resolve(itsContent({ content: "Synthetic step one.\nSynthetic step two." }));
    await screen.findByRole("heading", { name: "Synthetic procedure" });
    expect(screen.queryByText("Loading procedure...")).toBeNull();
    const card = openCard();
    expect(within(card).getByText("synthetic-procedure.md · 512 B · text/markdown")).toBeTruthy();
    expect(within(card).getByText("Synthetic description")).toBeTruthy();
    expect(within(card).getByText(/Synthetic step one\./).textContent).toBe(
      "Synthetic step one.\nSynthetic step two.",
    );
    fireEvent.click(within(card).getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("heading", { name: "Synthetic procedure" })).toBeNull();
  });

  it("marks a preview that was cut short, and points to Download when there is none", async () => {
    vi.mocked(listProcedures).mockResolvedValue(pageOf([aProcedure(), second]));
    await shown();
    vi.mocked(getProcedure).mockResolvedValueOnce(
      itsContent({ content: "Synthetic opening lines", content_truncated: true }),
    );
    fireEvent.click(inRow("Synthetic procedure", "View"));
    const preview = await screen.findByText(/Synthetic opening lines/);
    expect(preview.textContent).toBe("Synthetic opening lines\n\n... (truncated)");
    vi.mocked(getProcedure).mockResolvedValueOnce({
      ...second,
      content: null,
      content_truncated: false,
    });
    fireEvent.click(inRow("Second synthetic procedure", "View"));
    await screen.findByRole("heading", { name: "Second synthetic procedure" });
    const card = openCard();
    expect(
      within(card).getByText("second-synthetic-procedure.pdf · 2.50 MB · application/pdf"),
    ).toBeTruthy();
    expect(
      within(card)
        .getAllByRole("paragraph")
        .map((p) => p.textContent),
    ).toEqual(["Inline preview not available for this file type. Use Download."]);
    expect(within(card).queryByText(/Synthetic opening lines/)).toBeNull();
  });

  it("shows why a procedure could not open, or that it could not", async () => {
    await shown();
    const open = inRow("Synthetic procedure", "View");
    vi.mocked(getProcedure).mockRejectedValueOnce({
      response: { data: { detail: "Synthetic view refusal" } },
    });
    fireEvent.click(open);
    expect(await screen.findByText("Synthetic view refusal")).toBeTruthy();
    expect(screen.queryByText("Loading procedure...")).toBeNull();
    vi.mocked(getProcedure).mockRejectedValueOnce({});
    fireEvent.click(open);
    expect(await screen.findByText("Failed to load procedure.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Close" })).toBeNull();
  });
});
