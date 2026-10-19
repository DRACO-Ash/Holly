// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import DisplayToggles from "./DisplayToggles";

function box(name: string) {
  return screen.getByRole("checkbox", { name }) as HTMLInputElement;
}

function reducedMotion(reduce: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({ matches: reduce && query === "(prefers-reduced-motion: reduce)" })),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the screen effect toggles", () => {
  it("show each effect as the analyst set it, where the browser cannot say about motion", () => {
    render(<DisplayToggles prefs={{ scanlines: true, flicker: true }} onChange={vi.fn()} />);
    expect(box("Scanlines").checked).toBe(true);
    expect(box("CRT flicker").checked).toBe(true);
    expect(box("CRT flicker").disabled).toBe(false);
  });

  it("report each change with the other effect kept", () => {
    reducedMotion(false);
    const onChange = vi.fn();
    render(<DisplayToggles prefs={{ scanlines: true, flicker: false }} onChange={onChange} />);
    fireEvent.click(box("Scanlines"));
    expect(onChange).toHaveBeenLastCalledWith({ scanlines: false, flicker: false });
    fireEvent.click(box("CRT flicker"));
    expect(onChange).toHaveBeenLastCalledWith({ scanlines: true, flicker: true });
  });

  it("turn flicker off, and say why, when the system asks for reduced motion", () => {
    reducedMotion(true);
    render(<DisplayToggles prefs={{ scanlines: false, flicker: true }} onChange={vi.fn()} />);
    const flicker = box("CRT flicker");
    expect(flicker.checked).toBe(false);
    expect(flicker.disabled).toBe(true);
    expect(flicker.getAttribute("aria-describedby")).toBe("flicker-off-note");
    expect(document.getElementById("flicker-off-note")?.textContent).toBe(
      "Off: your system reduces motion",
    );
    expect(flicker.closest("label")?.title).toBe("Off: your system reduces motion");
  });
});
