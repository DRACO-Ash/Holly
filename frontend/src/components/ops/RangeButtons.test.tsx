// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import RangeButtons from "./RangeButtons";

const pressed = (name: string) => screen.getByRole("button", { name }).getAttribute("aria-pressed");

describe("RangeButtons", () => {
  it("presses the whole window by default and chooses a preset", () => {
    const onChoose = vi.fn();
    render(<RangeButtons choice={null} onChoose={onChoose} />);
    expect(pressed("Whole window")).toBe("true");
    expect(pressed("Last 6 h")).toBe("false");
    expect(screen.queryByRole("button", { name: "Dragged range: clear" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Last 24 h" }));
    expect(onChoose).toHaveBeenCalledWith({ hours: 24 });
    fireEvent.click(screen.getByRole("button", { name: "Whole window" }));
    expect(onChoose).toHaveBeenLastCalledWith(null);
  });

  it("presses the preset in force", () => {
    render(<RangeButtons choice={{ hours: 72 }} onChoose={vi.fn()} />);
    expect(pressed("Last 3 days")).toBe("true");
    expect(pressed("Whole window")).toBe("false");
  });

  it("offers to clear a dragged range", () => {
    const onChoose = vi.fn();
    render(<RangeButtons choice={{ from: 1, to: 2 }} onChoose={onChoose} />);
    expect(pressed("Last 6 h")).toBe("false");
    const clear = screen.getByRole("button", { name: "Dragged range: clear" });
    expect(clear.getAttribute("aria-pressed")).toBeNull();
    fireEvent.click(clear);
    expect(onChoose).toHaveBeenCalledWith(null);
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Whole window" }));
  });
});
