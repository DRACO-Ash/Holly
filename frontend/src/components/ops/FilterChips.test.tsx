// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import FilterChips from "./FilterChips";

describe("FilterChips", () => {
  it("shows nothing with no filters", () => {
    const { container } = render(<FilterChips filters={[]} onClear={vi.fn()} />);
    expect(container.innerHTML).toBe("");
  });

  it("removes one filter, and offers clear all only for several", () => {
    const remove = vi.fn();
    const clear = vi.fn();
    const { rerender } = render(
      <FilterChips filters={[{ key: "a", label: "GEO", onRemove: remove }]} onClear={clear} />,
    );
    expect(screen.queryByRole("button", { name: "Clear all" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /GEO.*remove this filter/ }));
    expect(remove).toHaveBeenCalledOnce();
    rerender(
      <FilterChips
        filters={[
          { key: "a", label: "GEO", onRemove: remove },
          { key: "b", label: "KBR", onRemove: vi.fn() },
        ]}
        onClear={clear}
      />,
    );
    expect(screen.getByRole("list", { name: "Filters in force" }).children).toHaveLength(3);
    fireEvent.click(screen.getByRole("button", { name: "Clear all" }));
    expect(clear).toHaveBeenCalledOnce();
  });
});
