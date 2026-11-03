// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import StatTile from "./StatTile";

describe("StatTile", () => {
  it("is a plain count without a toggle", () => {
    const { container } = render(<StatTile count={7} label="Notices" detail="+2 in 24 h" />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(container.firstElementChild?.className).toBe("stat-tile tone-neutral");
    expect(screen.getByText("7").className).toBe("stat-count");
    expect(screen.getByText("+2 in 24 h").className).toBe("stat-detail");
  });

  it("is a filter button that says whether it is on", () => {
    const onToggle = vi.fn();
    const { rerender } = render(<StatTile count={3} label="GEO" tone="high" onToggle={onToggle} />);
    const button = screen.getByRole("button", { name: /3\s*GEO/ });
    expect(button.getAttribute("aria-pressed")).toBe("false");
    expect(button.className).toBe("stat-tile stat-toggle tone-high");
    expect(button.querySelector(".stat-detail")).toBeNull();
    fireEvent.click(button);
    expect(onToggle).toHaveBeenCalledOnce();
    rerender(<StatTile count={3} label="GEO" pressed onToggle={onToggle} />);
    expect(screen.getByRole("button").getAttribute("aria-pressed")).toBe("true");
  });
});
