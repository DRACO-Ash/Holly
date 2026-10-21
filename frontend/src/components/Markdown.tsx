import { Fragment, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type { Block, Inline } from "../utils/markdown";
import { withContentKeys } from "../utils/keys";

// Keys from each item's content, since a manual's items carry no id and may repeat.
function keyed<T>(items: readonly T[]) {
  return withContentKeys(items, (item) => JSON.stringify(item));
}

function inlines(parts: readonly Inline[]): ReactNode[] {
  return keyed(parts).map(({ key, item }) => inline(item, key));
}

// A link in a manual: to the other manual, on the Help page; to the web, in a new tab; to a file
// in the repository, which the dashboard cannot open, as its words alone.
const MANUAL_LINKS: Record<string, string> = {
  "training-manual.md": "/help?manual=training",
  "operator-manual.md": "/help?manual=operator",
};

function link(href: string, children: ReactNode, key: string): ReactNode {
  const manual = MANUAL_LINKS[href.split("/").pop() ?? ""];
  if (manual) {
    return (
      <Link key={key} to={manual}>
        {children}
      </Link>
    );
  }
  if (href.startsWith("https://")) {
    return (
      <a key={key} href={href} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    );
  }
  return <Fragment key={key}>{children}</Fragment>;
}

export function InlineText({ parts }: Readonly<{ parts: readonly Inline[] }>) {
  return <>{inlines(parts)}</>;
}

function inline(part: Inline, key: string): ReactNode {
  switch (part.kind) {
    case "text":
      return <Fragment key={key}>{part.text}</Fragment>;
    case "code":
      return <code key={key}>{part.text}</code>;
    case "strong":
      return <strong key={key}>{inlines(part.children)}</strong>;
    case "em":
      return <em key={key}>{inlines(part.children)}</em>;
    case "link":
      return link(part.href, inlines(part.children), key);
  }
}

function Heading({ block }: Readonly<{ block: Extract<Block, { kind: "heading" }> }>) {
  const content = <InlineText parts={block.children} />;
  // The manual's own title is the page's; its sections follow one level down.
  // Each takes focus from the contents list, so the keyboard lands where the eye does.
  if (block.level <= 2)
    return (
      <h2 id={block.id} tabIndex={-1}>
        {content}
      </h2>
    );
  if (block.level === 3)
    return (
      <h3 id={block.id} tabIndex={-1}>
        {content}
      </h3>
    );
  return (
    <h4 id={block.id} tabIndex={-1}>
      {content}
    </h4>
  );
}

function Lines({ lines }: Readonly<{ lines: readonly Inline[][] }>) {
  return (
    <p>
      {keyed(lines).map(({ key, item }, at) => (
        <Fragment key={key}>
          {at > 0 && <br />}
          <InlineText parts={item} />
        </Fragment>
      ))}
    </p>
  );
}

function Table({ block }: Readonly<{ block: Extract<Block, { kind: "table" }> }>) {
  return (
    <div className="manual-table">
      <table>
        <thead>
          <tr>
            {keyed(block.head).map(({ key, item }) => (
              <th key={key} scope="col">
                <InlineText parts={item} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {keyed(block.rows).map(({ key, item: row }) => (
            <tr key={key}>
              {keyed(row).map((cell) => (
                <td key={cell.key}>
                  <InlineText parts={cell.item} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Items({ items }: Readonly<{ items: readonly Inline[][] }>) {
  return (
    <>
      {keyed(items).map(({ key, item }) => (
        <li key={key}>
          <InlineText parts={item} />
        </li>
      ))}
    </>
  );
}

// A quote that opens with a bold label, as the manuals' BLUF and their notes do, is a callout.
function Quote({ blocks }: Readonly<{ blocks: readonly Block[] }>) {
  return (
    <aside className="manual-callout">
      <MarkdownBlocks blocks={blocks} />
    </aside>
  );
}

function block(item: Block): ReactNode {
  switch (item.kind) {
    case "heading":
      return <Heading block={item} />;
    case "eyebrow":
      return <p className="manual-eyebrow">{item.text}</p>;
    case "paragraph":
      return <Lines lines={item.lines} />;
    case "bullets":
      return (
        <ul className="manual-bullets">
          <Items items={item.items} />
        </ul>
      );
    case "steps":
      return (
        <ol>
          <Items items={item.items} />
        </ol>
      );
    case "table":
      return <Table block={item} />;
    case "quote":
      return <Quote blocks={item.blocks} />;
    case "code":
      return (
        <pre className="manual-code">
          <code>{item.text}</code>
        </pre>
      );
  }
}

export default function MarkdownBlocks({ blocks }: Readonly<{ blocks: readonly Block[] }>) {
  return (
    <>
      {keyed(blocks).map(({ key, item }) => (
        <Fragment key={key}>{block(item)}</Fragment>
      ))}
    </>
  );
}
