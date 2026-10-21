// @vitest-environment jsdom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getManual, listManuals } from "../api/manuals";
import { renderAt } from "../test/render";
import type { Manual } from "../types";
import HelpPage from "./Help";

vi.mock("../api/manuals");

const training: Manual = {
  slug: "training",
  title: "Analyst training manual",
  markdown: [
    "**BLUESTAQ LIMITED** | Analyst Training Manual",
    "",
    "# Analyst Training Manual",
    "",
    "**SECTION 01**",
    "",
    "## Signing in",
    "",
    "1. Open Holly.",
    "",
    "### Your password",
    "",
    "See the [operator manual](../runbook/operator-manual.md), [the web](https://example.test)",
    "and [a file](../../src/app/main.py).",
    "",
    "**SECTION 02**",
    "",
    "## The Dashboard",
    "",
    "<b>not bold</b>",
  ].join("\n"),
};
const operator: Manual = {
  slug: "operator",
  title: "Operator manual",
  markdown: "# Operator Manual\n\n## Daily checks\n\nCurl the probes.",
};

function shown(route = "/help") {
  renderAt(<HelpPage />, route, "/help");
}

beforeEach(() => {
  vi.mocked(listManuals)
    .mockReset()
    .mockResolvedValue([
      { slug: "training", title: training.title },
      { slug: "operator", title: operator.title },
    ]);
  vi.mocked(getManual)
    .mockReset()
    .mockImplementation((slug) => Promise.resolve(slug === "operator" ? operator : training));
});

describe("the Help page", () => {
  it("opens the first manual offered, its title the page's, with numbered contents", async () => {
    shown();
    expect(screen.getByText("Loading the manual...")).toBeTruthy();
    expect(await screen.findByRole("heading", { level: 1, name: training.title })).toBeTruthy();
    expect(getManual).toHaveBeenCalledWith("training");
    const contents = screen.getByRole("navigation", { name: "Contents" });
    expect(
      within(contents)
        .getAllByRole("link")
        .map((l) => l.textContent),
    ).toEqual(["01Signing in", "Your password", "02The Dashboard"]);
    // The brand line and the manual's own title are the page's header, not its body.
    const article = screen.getByRole("article", { name: training.title });
    expect(within(article).queryByText(/BLUESTAQ LIMITED/)).toBeNull();
    expect(within(article).getByText("<b>not bold</b>")).toBeTruthy();
  });

  it("links the other manual in the app, the web in a new tab, and a repository file not at all", async () => {
    shown();
    const article = await screen.findByRole("article");
    const toManual = within(article).getByRole("link", { name: "operator manual" });
    expect(toManual.getAttribute("href")).toBe("/help?manual=operator");
    const web = within(article).getByRole("link", { name: "the web" });
    expect(web.getAttribute("target")).toBe("_blank");
    expect(web.getAttribute("rel")).toBe("noopener noreferrer");
    expect(within(article).queryByRole("link", { name: "a file" })).toBeNull();
    expect(within(article).getByText(/a file/)).toBeTruthy();
  });

  it("switches manual, and opens the one the address names", async () => {
    shown();
    await screen.findByRole("article");
    const manual = screen.getByRole("group", { name: "Manual" });
    fireEvent.click(within(manual).getByRole("button", { name: operator.title }));
    expect(await screen.findByRole("heading", { level: 1, name: operator.title })).toBeTruthy();
    expect(
      within(manual).getByRole("button", { name: operator.title }).getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("opens the manual the address names", async () => {
    shown("/help?manual=operator");
    expect(await screen.findByRole("heading", { level: 1, name: operator.title })).toBeTruthy();
  });

  it("offers no choice to a user offered one manual, nor a manual they may not read", async () => {
    vi.mocked(listManuals).mockResolvedValue([{ slug: "training", title: training.title }]);
    shown("/help?manual=operator");
    expect(await screen.findByRole("heading", { level: 1, name: training.title })).toBeTruthy();
    expect(getManual).not.toHaveBeenCalledWith("operator");
    expect(screen.queryByRole("group", { name: "Manual" })).toBeNull();
  });

  it("finds a section by its name and jumps to it", async () => {
    shown();
    await screen.findByRole("article");
    fireEvent.change(screen.getByLabelText("Find a section"), { target: { value: "dash" } });
    const contents = screen.getByRole("navigation", { name: "Contents" });
    const [link] = within(contents).getAllByRole("link");
    expect(link.textContent).toBe("02The Dashboard");
    const target = screen.getByRole("heading", { level: 2, name: "The Dashboard" });
    target.scrollIntoView = vi.fn();
    fireEvent.click(link);
    expect(target.scrollIntoView).toHaveBeenCalled();
    expect(document.activeElement).toBe(target);
    fireEvent.change(screen.getByLabelText("Find a section"), { target: { value: "nothing" } });
    expect(screen.getByText("No section is called that.")).toBeTruthy();
  });

  it("prints the manual on request", async () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    shown();
    await screen.findByRole("article");
    fireEvent.click(screen.getByRole("button", { name: "Print or save as PDF" }));
    expect(print).toHaveBeenCalled();
    print.mockRestore();
  });

  it("says why the manuals, or a manual, could not be read", async () => {
    vi.mocked(listManuals).mockRejectedValueOnce({});
    shown();
    expect((await screen.findByRole("alert")).textContent).toBe("Failed to load the manuals.");
  });

  it("says why a manual could not be read", async () => {
    vi.mocked(getManual).mockRejectedValue({
      response: { status: 503, data: { detail: "This release does not carry the manual." } },
    });
    shown();
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toBe("This release does not carry the manual."),
    );
  });
});
