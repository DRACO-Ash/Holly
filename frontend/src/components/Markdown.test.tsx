// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { parseMarkdown } from "../utils/markdown";
import MarkdownBlocks from "./Markdown";

const text = [
  "## Heading two",
  "",
  "### Heading three",
  "",
  "#### Heading four",
  "",
  "A line with `code`, **bold** and *italic*.",
  "A second line, same paragraph.",
  "",
  "● A bullet",
  "■ Another bullet",
  "",
  "1. First step",
  "2. Second step",
  "",
  "| Check | How |",
  "|---|---|",
  "| Liveness | `curl` |",
  "",
  "> **Note**",
  ">",
  "> Inside the callout.",
  "",
  "```",
  "sh scripts/verify.sh",
  "```",
  "",
  "**SECTION 02**",
].join("\n");

function shown() {
  return render(
    <MemoryRouter>
      <MarkdownBlocks blocks={parseMarkdown(text)} />
    </MemoryRouter>,
  ).container;
}

describe("MarkdownBlocks", () => {
  it("renders each heading level, focusable for the contents list", () => {
    shown();
    for (const [level, name] of [
      [2, "Heading two"],
      [3, "Heading three"],
      [4, "Heading four"],
    ] as const) {
      const heading = screen.getByRole("heading", { level, name });
      expect(heading.getAttribute("tabindex")).toBe("-1");
      expect(heading.id).toBe(name.toLowerCase().replace(" ", "-"));
    }
  });

  it("renders inline code, bold and italic, and keeps a paragraph's lines apart", () => {
    const container = shown();
    expect(container.querySelector("p code")?.textContent).toBe("code");
    expect(container.querySelector("p strong")?.textContent).toBe("bold");
    expect(container.querySelector("p em")?.textContent).toBe("italic");
    expect(container.querySelector("p br")).not.toBeNull();
  });

  it("renders bullets, steps, a table with column headers, a callout and code", () => {
    const container = shown();
    expect(
      [...container.querySelectorAll("ul.manual-bullets li")].map((li) => li.textContent),
    ).toEqual(["A bullet", "Another bullet"]);
    expect([...container.querySelectorAll("ol li")].map((li) => li.textContent)).toEqual([
      "First step",
      "Second step",
    ]);
    const table = screen.getByRole("table");
    const headers = within(table).getAllByRole("columnheader");
    expect(headers.map((h) => [h.textContent, h.getAttribute("scope")])).toEqual([
      ["Check", "col"],
      ["How", "col"],
    ]);
    expect(within(table).getByRole("cell", { name: "curl" }).querySelector("code")).not.toBeNull();
    const callout = container.querySelector("aside.manual-callout");
    expect(callout?.querySelector("strong")?.textContent).toBe("Note");
    expect(callout?.textContent).toContain("Inside the callout.");
    expect(container.querySelector("pre.manual-code code")?.textContent).toBe(
      "sh scripts/verify.sh",
    );
    expect(container.querySelector("p.manual-eyebrow")?.textContent).toBe("SECTION 02");
  });
});
