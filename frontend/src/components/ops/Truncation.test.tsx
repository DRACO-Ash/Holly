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
    expect(
      screen.getByText(/more notices than this view carries: it shows the newest/),
    ).toBeTruthy();
    expect(
      screen.getByText(/looked up only for those with the lowest catalogue numbers/),
    ).toBeTruthy();
  });

  it("names both lists when both were cut, and says nothing of element sets when they were not", () => {
    render(
      <Truncation
        data={anOverview({ truncated: { notices: true, maneuvers: true, elsets: false } })}
      />,
    );
    expect(screen.getByText(/more notices and maneuvers than this view carries/)).toBeTruthy();
    expect(screen.queryByText(/catalogue numbers/)).toBeNull();
  });
});
