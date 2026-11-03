// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { anOverview } from "../../test/activity";
import Truncation from "./Truncation";

describe("Truncation", () => {
  it("says nothing when the overview carries the whole window", () => {
    const { container } = render(<Truncation data={anOverview()} />);
    expect(container.innerHTML).toBe("");
  });

  it("names what was cut", () => {
    render(
      <Truncation
        data={anOverview({ truncated: { notices: true, maneuvers: false, elsets: true } })}
      />,
    );
    expect(screen.getByText(/more notices and element sets than this view carries/)).toBeTruthy();
  });
});
