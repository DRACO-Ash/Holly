// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { SortDirection } from "../types";
import SortableHeader from "./SortableHeader";

function header(active: "name" | "date", direction: SortDirection, onChange = vi.fn()) {
  render(
    <table>
      <thead>
        <tr>
          <SortableHeader
            column="name"
            label="Name"
            activeColumn={active}
            activeDirection={direction}
            onChange={onChange}
          />
        </tr>
      </thead>
    </table>,
  );
  return screen.getByRole("button", { name: /Name/ });
}

describe("a sortable column header", () => {
  it("marks nothing on a column the list is not sorted by, and asks to sort by it", () => {
    const onChange = vi.fn();
    const button = header("date", "asc", onChange);
    expect(button.className).toBe("sort-header");
    expect(button.textContent).toBe("Name");
    expect(button.closest("th")!.hasAttribute("aria-sort")).toBe(false);
    expect(button.hasAttribute("aria-sort")).toBe(false);
    fireEvent.click(button);
    expect(onChange).toHaveBeenCalledWith("name");
  });

  it("shows the order of the column the list is sorted by", () => {
    const ascending = header("name", "asc");
    expect(ascending.className).toBe("sort-header active");
    expect(ascending.textContent).toBe("Name▲");
    expect(screen.getByRole("columnheader").getAttribute("aria-sort")).toBe("ascending");
    expect(ascending.hasAttribute("aria-sort")).toBe(false);
  });

  it("shows a descending order", () => {
    const descending = header("name", "desc");
    expect(descending.textContent).toBe("Name▼");
    expect(screen.getByRole("columnheader").getAttribute("aria-sort")).toBe("descending");
  });
});
