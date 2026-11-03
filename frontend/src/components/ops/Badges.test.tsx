// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  KindBadge,
  KindGlyph,
  RegimeBadge,
  SourceBadge,
  StatusBadge,
  UrgencyBadge,
} from "./Badges";

describe("KindBadge", () => {
  it("names the kind beside its glyph, as written or by its own label", () => {
    const { container } = render(
      <>
        <KindBadge kind="rpo" />
        <KindBadge kind="maneuver" label="Cancelled Maneuver" />
      </>,
    );
    expect(screen.getByText("RPO")).toHaveProperty("className", "kind-badge kind-rpo");
    expect(screen.getByText("Cancelled Maneuver")).toBeTruthy();
    const glyphs = container.querySelectorAll(".kind-glyph");
    expect(glyphs).toHaveLength(2);
    expect(glyphs[0].getAttribute("aria-hidden")).toBe("true");
  });

  it("draws a bare glyph", () => {
    const { container } = render(<KindGlyph kind="launch" />);
    expect(container.firstElementChild?.className).toBe("kind-glyph kind-launch");
  });
});

describe("RegimeBadge", () => {
  it("shows nothing without a regime", () => {
    const { container } = render(<RegimeBadge regime={null} from="notice" />);
    expect(container.innerHTML).toBe("");
  });

  it("says where the regime came from, and marks one derived from the element set", () => {
    render(
      <>
        <RegimeBadge regime="GEO" from="notice" />
        <RegimeBadge regime="LEO" from="elset" />
        <RegimeBadge regime="MEO" />
      </>,
    );
    expect(screen.getByTitle("GEO, as the notice states").textContent).toBe("GEO");
    const leo = screen.getByTitle("LEO, from the latest element set's period and eccentricity");
    expect(leo.className).toBe("regime-badge regime-leo");
    expect(screen.getByLabelText("derived from the element set").textContent).toBe("*");
    expect(screen.getByTitle("MEO").textContent).toBe("MEO");
  });
});

describe("UrgencyBadge and StatusBadge", () => {
  it("shows urgency but not info only, and status only when there is one", () => {
    const { container } = render(
      <>
        <UrgencyBadge urgency="none" />
        <StatusBadge status={null} />
      </>,
    );
    expect(container.innerHTML).toBe("");
    render(
      <>
        <UrgencyBadge urgency="pending" />
        <StatusBadge status="CLOSED" />
      </>,
    );
    expect(screen.getByText("Awaiting analysis").className).toBe("urgency-pill urgency-pending");
    expect(screen.getByText("CLOSED").className).toBe("status-pill status-closed");
  });
});

describe("SourceBadge", () => {
  it("names the source beside its slot's dot", () => {
    render(<SourceBadge source="TEST-PROVIDER" slot={2} />);
    const badge = screen.getByText("TEST-PROVIDER");
    expect(badge.className).toBe("source-badge source-2");
    expect(badge.querySelector(".source-dot")).toBeTruthy();
  });
});
