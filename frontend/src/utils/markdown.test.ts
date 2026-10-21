import { describe, expect, it } from "vitest";
import { parseInline, parseMarkdown, plainText } from "./markdown";

describe("parseInline", () => {
  it("reads code, bold, italic and links, and leaves the rest as text", () => {
    expect(
      parseInline("Run `verify.sh`, **then** *wait* for [the log](https://example.test)."),
    ).toEqual([
      { kind: "text", text: "Run " },
      { kind: "code", text: "verify.sh" },
      { kind: "text", text: ", " },
      { kind: "strong", children: [{ kind: "text", text: "then" }] },
      { kind: "text", text: " " },
      { kind: "em", children: [{ kind: "text", text: "wait" }] },
      { kind: "text", text: " for " },
      { kind: "link", href: "https://example.test", children: [{ kind: "text", text: "the log" }] },
      { kind: "text", text: "." },
    ]);
  });

  it("keeps marks inside code as code, and reads marks inside bold", () => {
    expect(parseInline("`**not bold**`")).toEqual([{ kind: "code", text: "**not bold**" }]);
    expect(parseInline("**Check `PORT`**")).toEqual([
      {
        kind: "strong",
        children: [
          { kind: "text", text: "Check " },
          { kind: "code", text: "PORT" },
        ],
      },
    ]);
  });

  it("takes markup-like text as text, never as markup", () => {
    expect(parseInline("<script>alert(1)</script> & 2 * 3")).toEqual([
      { kind: "text", text: "<script>alert(1)</script> & 2 * 3" },
    ]);
  });
});

describe("parseMarkdown", () => {
  const manual = [
    "**BLUESTAQ LIMITED** | Test Manual",
    "",
    "# Test Manual",
    "",
    "**Owner:** TBC, re-verify",
    "**Version:** 0.1",
    "",
    "> **BLUF**",
    ">",
    "> Read this first.",
    "",
    "**SECTION 01**",
    "",
    "## At a glance",
    "",
    "● **One container:** the app.",
    "■ A second point.",
    "1. Open Holly.",
    "2. Sign in.",
    "",
    "| Check | How |",
    "|-------|-----|",
    "| Liveness | `curl a|b` |",
    "",
    "```sh",
    "sh scripts/verify.sh   # **not bold**",
    "```",
    "",
    "### At a glance",
  ].join("\n");

  it("reads each kind of block a manual uses", () => {
    const blocks = parseMarkdown(manual);
    expect(blocks.map((b) => b.kind)).toEqual([
      "paragraph",
      "heading",
      "paragraph",
      "quote",
      "eyebrow",
      "heading",
      "bullets",
      "steps",
      "table",
      "code",
      "heading",
    ]);
  });

  it("keeps a paragraph's lines apart, and a quote's blocks within it", () => {
    const [, , meta, quote] = parseMarkdown(manual);
    expect(meta.kind === "paragraph" && meta.lines.map(plainText)).toEqual([
      "Owner: TBC, re-verify",
      "Version: 0.1",
    ]);
    expect(quote.kind === "quote" && quote.blocks.map((b) => b.kind)).toEqual([
      "paragraph",
      "paragraph",
    ]);
  });

  it("names a SECTION line, and gives each heading an id of its own", () => {
    const blocks = parseMarkdown(manual);
    expect(blocks[4]).toEqual({ kind: "eyebrow", text: "SECTION 01" });
    const ids = blocks.flatMap((b) => (b.kind === "heading" ? [b.id] : []));
    expect(ids).toEqual(["test-manual", "at-a-glance", "at-a-glance-2"]);
  });

  it("splits a table at its pipes but not those inside code, and drops the rule", () => {
    const table = parseMarkdown(manual)[8];
    expect(table.kind).toBe("table");
    if (table.kind !== "table") return;
    expect(table.head.map(plainText)).toEqual(["Check", "How"]);
    expect(table.rows.map((row) => row.map(plainText))).toEqual([["Liveness", "curl a|b"]]);
  });

  it("keeps code as written, and reads an unclosed fence to the end", () => {
    expect(parseMarkdown(manual)[9]).toEqual({
      kind: "code",
      text: "sh scripts/verify.sh   # **not bold**",
    });
    expect(parseMarkdown("```\nleft open")).toEqual([{ kind: "code", text: "left open" }]);
  });

  it("reads Windows line endings, and gives a heading of symbols an id still", () => {
    const [heading] = parseMarkdown("## ●●\r\ntext");
    expect(heading).toMatchObject({ kind: "heading", id: "section", text: "●●" });
  });
});
