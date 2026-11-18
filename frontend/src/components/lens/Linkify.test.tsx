// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { aLens, renderWithLens } from "../../test/lens";
import { Linkify, SatChip } from "./Linkify";

describe("numbers as links", () => {
  it("shows text exactly as before outside the lens", () => {
    render(<Linkify text="Check 90001 now" />);
    expect(screen.getByText("Check 90001 now")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("links known catalogue numbers and held NOTSO numbers, and leaves the rest", () => {
    renderWithLens(<p>{<Linkify text="90001 vs 190001, see 7afc_19Oct-1726Z at 14:10Z" />}</p>);
    expect(screen.getAllByRole("button").map((b) => b.textContent)).toEqual([
      "90001",
      "7afc_19Oct-1726Z",
    ]);
    expect(screen.getByRole("paragraph").textContent).toBe(
      "90001 vs 190001, see 7afc_19Oct-1726Z at 14:10Z",
    );
  });

  it("opens the lens on the object, or the notice's first known object, and only that", () => {
    const lens = aLens();
    const row = vi.fn();
    renderWithLens(
      <div onClick={row}>
        <Linkify text="90002 and 7afc_19Oct-1726Z" />
      </div>,
      lens,
    );
    fireEvent.click(screen.getByRole("button", { name: "Open the lens on TEST-SAT 2 90002" }));
    expect(lens.open).toHaveBeenLastCalledWith(90002, expect.any(HTMLButtonElement));
    fireEvent.click(screen.getByRole("button", { name: /notice 7afc_19Oct-1726Z/ }));
    expect(lens.open).toHaveBeenLastCalledWith(90001, expect.any(HTMLButtonElement));
    expect(row).not.toHaveBeenCalled();
  });

  it.each([true, false])("shows markup in chat as text, never as elements (lens on: %s)", (on) => {
    const text =
      '<img src=x onerror="go()"> 90001 <a href="javascript:go()">x</a> <script>1</script> 7afc_19Oct-1726Z';
    const { container } = renderWithLens(
      <p>
        <Linkify text={text} />
      </p>,
      aLens({ enabled: on }),
    );
    expect(container.querySelector("img, a, script")).toBeNull();
    expect(screen.getByRole("paragraph").textContent).toBe(text);
    expect(screen.queryAllByRole("button")).toHaveLength(on ? 2 : 0);
  });

  it("leaves text alone when the lens is switched off", () => {
    renderWithLens(<Linkify text="90001" />, aLens({ enabled: false }));
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("links a lone number only for a known object", () => {
    renderWithLens(
      <>
        <SatChip id="90001" />
        <SatChip id="90009" />
      </>,
    );
    expect(screen.getAllByRole("button")).toHaveLength(1);
    expect(screen.getByText("90009")).toBeTruthy();
  });

  it("keeps a NOTSO number as text when Holly holds none of its objects", () => {
    const lens = aLens({ objects: new Map() });
    renderWithLens(<Linkify text="7afc_19Oct-1726Z" />, lens);
    expect(screen.queryByRole("button")).toBeNull();
  });
});
