// The Markdown the manuals are written in, read into blocks the Help page renders as React
// elements. No HTML is ever built from the text, so nothing in a manual can become markup: what
// it holds is shown as text. Only what the manuals use is read: headings, paragraphs, the ● and
// ■ bullets, numbered steps, tables, quotes, fenced code, and bold, italic, code and links inline.

export type Inline =
  | { kind: "text"; text: string }
  | { kind: "strong"; children: Inline[] }
  | { kind: "em"; children: Inline[] }
  | { kind: "code"; text: string }
  | { kind: "link"; href: string; children: Inline[] };

export type Block =
  | { kind: "heading"; level: number; id: string; text: string; children: Inline[] }
  | { kind: "eyebrow"; text: string }
  | { kind: "paragraph"; lines: Inline[][] }
  | { kind: "bullets"; items: Inline[][] }
  | { kind: "steps"; items: Inline[][] }
  | { kind: "table"; head: Inline[][]; rows: Inline[][][] }
  | { kind: "quote"; blocks: Block[] }
  | { kind: "code"; text: string };

// One inline mark: code, bold, italic or a link, in that order of precedence.
const INLINE = /`([^`]+)`|\*\*(.+?)\*\*|\*([^*\s][^*]*?)\*|\[([^\]]+)\]\(([^)\s]+)\)/;

export function parseInline(text: string): Inline[] {
  const out: Inline[] = [];
  let rest = text;
  for (let match = INLINE.exec(rest); match; match = INLINE.exec(rest)) {
    if (match.index > 0) out.push({ kind: "text", text: rest.slice(0, match.index) });
    out.push(inlineMark(match));
    rest = rest.slice(match.index + match[0].length);
  }
  if (rest) out.push({ kind: "text", text: rest });
  return out;
}

function inlineMark(match: RegExpExecArray): Inline {
  const [, code, strong, em, label, href] = match;
  if (code !== undefined) return { kind: "code", text: code };
  if (strong !== undefined) return { kind: "strong", children: parseInline(strong) };
  if (em !== undefined) return { kind: "em", children: parseInline(em) };
  return { kind: "link", href: href ?? "", children: parseInline(label ?? "") };
}

// The words of an inline run, marks dropped: for headings' ids and the contents list.
export function plainText(inlines: readonly Inline[]): string {
  return inlines
    .map((part) => ("children" in part ? plainText(part.children) : part.text))
    .join("");
}

function slug(text: string): string {
  return (
    text
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "") || "section"
  );
}

// A table row's cells. A pipe inside code is part of the code, not a cell edge.
function cells(line: string): string[] {
  const out: string[] = [];
  let cell = "";
  let inCode = false;
  for (const char of line.trim().replace(/^\||\|$/g, "")) {
    if (char === "`") inCode = !inCode;
    if (char === "|" && !inCode) {
      out.push(cell.trim());
      cell = "";
    } else {
      cell += char;
    }
  }
  out.push(cell.trim());
  return out;
}

const HEADING = /^(#{1,4}) (.+)$/;
const BULLET = /^[●■] /;
const STEP = /^\d+\. /;
const EYEBROW = /^\*\*(SECTION \d+)\*\*$/;

function startsBlock(line: string): boolean {
  return (
    line.startsWith("```") ||
    line.startsWith("|") ||
    line.startsWith(">") ||
    HEADING.test(line) ||
    BULLET.test(line) ||
    STEP.test(line)
  );
}

// The lines from `from` on that `keep` accepts, and where they end.
function run(
  lines: readonly string[],
  from: number,
  keep: (line: string, index: number) => boolean,
) {
  let end = from;
  while (end < lines.length && keep(lines[end], end)) end += 1;
  return { taken: lines.slice(from, end), end };
}

class Reader {
  private readonly ids = new Map<string, number>();

  // A heading's id, made unique on the page by a number after its first use.
  id(text: string): string {
    const base = slug(text);
    const seen = this.ids.get(base) ?? 0;
    this.ids.set(base, seen + 1);
    return seen ? `${base}-${seen + 1}` : base;
  }

  blocks(lines: readonly string[]): Block[] {
    const out: Block[] = [];
    let at = 0;
    while (at < lines.length) {
      const line = lines[at];
      if (!line.trim()) {
        at += 1;
        continue;
      }
      const { block, end } = this.block(lines, at);
      out.push(block);
      at = end;
    }
    return out;
  }

  private block(lines: readonly string[], at: number): { block: Block; end: number } {
    const line = lines[at];
    if (line.startsWith("```")) return fence(lines, at);
    const heading = HEADING.exec(line);
    if (heading) return { block: this.heading(heading[1].length, heading[2]), end: at + 1 };
    if (line.startsWith("|")) return table(lines, at);
    if (line.startsWith(">")) return this.quote(lines, at);
    if (BULLET.test(line)) return list(lines, at, BULLET, "bullets");
    if (STEP.test(line)) return list(lines, at, STEP, "steps");
    return paragraph(lines, at);
  }

  private heading(level: number, text: string): Block {
    const children = parseInline(text);
    const words = plainText(children);
    return { kind: "heading", level, id: this.id(words), text: words, children };
  }

  private quote(lines: readonly string[], at: number) {
    const { taken, end } = run(lines, at, (line) => line.startsWith(">"));
    const inner = taken.map((line) => line.replace(/^> ?/, ""));
    return { block: { kind: "quote", blocks: this.blocks(inner) } as Block, end };
  }
}

function fence(lines: readonly string[], at: number) {
  const { taken, end } = run(lines, at + 1, (line) => !line.startsWith("```"));
  // Past the closing fence, or to the end when a fence is never closed.
  return { block: { kind: "code", text: taken.join("\n") } as Block, end: end + 1 };
}

function table(lines: readonly string[], at: number) {
  const { taken, end } = run(lines, at, (line) => line.startsWith("|"));
  const [head = "", ...body] = taken;
  const rows = body.filter((line) => !/^\|?[\s:|-]+\|?$/.test(line));
  return {
    block: {
      kind: "table",
      head: cells(head).map(parseInline),
      rows: rows.map((row) => cells(row).map(parseInline)),
    } as Block,
    end,
  };
}

function list(lines: readonly string[], at: number, marker: RegExp, kind: "bullets" | "steps") {
  const { taken, end } = run(lines, at, (line) => marker.test(line));
  const items = taken.map((line) => parseInline(line.replace(marker, "")));
  return { block: { kind, items } as Block, end };
}

function paragraph(lines: readonly string[], at: number) {
  const { taken, end } = run(
    lines,
    at,
    (line, index) => line.trim() !== "" && (index === at || !startsBlock(line)),
  );
  const eyebrow = taken.length === 1 ? EYEBROW.exec(taken[0].trim()) : null;
  if (eyebrow) return { block: { kind: "eyebrow", text: eyebrow[1] } as Block, end };
  return { block: { kind: "paragraph", lines: taken.map(parseInline) } as Block, end };
}

export function parseMarkdown(text: string): Block[] {
  return new Reader().blocks(text.replace(/\r\n?/g, "\n").split("\n"));
}
