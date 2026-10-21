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

// One inline mark at `at`, and where it ends, or null when none starts there. Each is found with
// indexOf, never with a backtracking pattern: code, then bold, italic and a link.
type Mark = { part: Inline; end: number } | null;

function codeAt(text: string, at: number): Mark {
  const close = text.indexOf("`", at + 1);
  if (close <= at + 1) return null;
  return { part: { kind: "code", text: text.slice(at + 1, close) }, end: close + 1 };
}

function strongAt(text: string, at: number): Mark {
  const close = text.indexOf("**", at + 3);
  if (close === -1) return null;
  return {
    part: { kind: "strong", children: parseInline(text.slice(at + 2, close)) },
    end: close + 2,
  };
}

function emAt(text: string, at: number): Mark {
  const first = text[at + 1];
  if (first === undefined || first === "*" || /\s/.test(first)) return null;
  const close = text.indexOf("*", at + 2);
  if (close === -1) return null;
  return { part: { kind: "em", children: parseInline(text.slice(at + 1, close)) }, end: close + 1 };
}

function linkAt(text: string, at: number): Mark {
  const middle = text.indexOf("](", at + 2);
  if (middle === -1 || text.slice(at + 1, middle).includes("]")) return null;
  const close = text.indexOf(")", middle + 2);
  const href = close === -1 ? "" : text.slice(middle + 2, close);
  if (!href || /\s/.test(href)) return null;
  const children = parseInline(text.slice(at + 1, middle));
  return { part: { kind: "link", href, children }, end: close + 1 };
}

function markAt(text: string, at: number): Mark {
  const char = text[at];
  if (char === "`") return codeAt(text, at);
  if (char === "[") return linkAt(text, at);
  if (char !== "*") return null;
  return text[at + 1] === "*" ? strongAt(text, at) : emAt(text, at);
}

export function parseInline(text: string): Inline[] {
  const out: Inline[] = [];
  let plain = "";
  let at = 0;
  while (at < text.length) {
    const mark = markAt(text, at);
    if (mark) {
      if (plain) out.push({ kind: "text", text: plain });
      plain = "";
      out.push(mark.part);
      at = mark.end;
    } else {
      plain += text[at];
      at += 1;
    }
  }
  if (plain) out.push({ kind: "text", text: plain });
  return out;
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
