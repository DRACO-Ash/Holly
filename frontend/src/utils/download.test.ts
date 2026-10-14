import { afterEach, describe, expect, it, vi } from "vitest";
import { filenameFromDisposition, saveBlob } from "./download";

describe("filenameFromDisposition", () => {
  it("prefers the RFC 6266 UTF-8 name", () => {
    const header = `attachment; filename="r_sum_.pdf"; filename*=UTF-8''r%C3%A9sum%C3%A9.pdf`;
    expect(filenameFromDisposition(header, "fallback.bin")).toBe("résumé.pdf");
  });

  it("reads a quoted or bare plain name", () => {
    expect(filenameFromDisposition('attachment; filename="shift-log.md"', "x")).toBe(
      "shift-log.md",
    );
    expect(filenameFromDisposition("attachment; filename=notes.html", "x")).toBe("notes.html");
  });

  it("falls back to the plain name when the UTF-8 name is malformed", () => {
    const header = `attachment; filename="plain.txt"; filename*=UTF-8''bad%E0%A4%A`;
    expect(filenameFromDisposition(header, "x")).toBe("plain.txt");
  });

  it("uses the fallback when no name is given", () => {
    expect(filenameFromDisposition(null, "fallback.bin")).toBe("fallback.bin");
    expect(filenameFromDisposition("attachment", "fallback.bin")).toBe("fallback.bin");
    expect(filenameFromDisposition('attachment; filename=""', "fallback.bin")).toBe("fallback.bin");
  });
});

describe("saveBlob", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("clicks a temporary download link, then releases the object URL", () => {
    vi.useFakeTimers();
    const link = { href: "", download: "", click: vi.fn(), remove: vi.fn() };
    const appendChild = vi.fn();
    vi.stubGlobal("document", { createElement: vi.fn(() => link), body: { appendChild } });
    const createObjectURL = vi.fn(() => "blob:holly/1");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });

    const blob = new Blob(["# Shift log"]);
    saveBlob(blob, "shift-log-2026-06-05.md");

    expect(createObjectURL).toHaveBeenCalledWith(blob);
    expect(link.href).toBe("blob:holly/1");
    expect(link.download).toBe("shift-log-2026-06-05.md");
    expect(appendChild).toHaveBeenCalledWith(link);
    expect(link.click).toHaveBeenCalledOnce();
    expect(link.remove).toHaveBeenCalledOnce();
    expect(revokeObjectURL).not.toHaveBeenCalled();
    vi.runAllTimers();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:holly/1");
  });
});
